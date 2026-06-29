#!/usr/bin/env python3
"""jz-get-analytics — 实时查看站点 metrics（GSC / Cloudflare / Umami / Clarity）."""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone, date
from pathlib import Path
from urllib.parse import quote

try:
    import requests
except ImportError:
    print("Missing 'requests'. Install with: uv pip install requests", file=sys.stderr)
    raise SystemExit(1)

SKILL_ROOT = Path(__file__).resolve().parents[1]
USER_CONFIG_ENV = Path.home() / ".config" / "skills" / "jz-get-analytics" / ".env"
SKILL_ENV = SKILL_ROOT / ".env"
SITE_INTEGRATIONS_PATH = Path(
    os.environ.get(
        "SITE_INTEGRATIONS_CONFIG",
        str(Path.home() / ".config" / "skills" / "jz-get-analytics" / "site-integrations.json"),
    )
).expanduser()


# --- Env loading ---

def read_env_file(path: Path) -> dict:
    values = {}
    if not path.exists():
        return values
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip().strip("'").strip('"')
    return values


def load_env() -> dict:
    """Load credentials: skill .env → config .env → project .env (later overrides earlier)."""
    merged = read_env_file(SKILL_ENV)
    merged.update(read_env_file(USER_CONFIG_ENV))
    # Also try the current working directory's .env (for project-scoped tokens like Clarity)
    cwd_env = Path(os.getcwd()) / ".env"
    merged.update(read_env_file(cwd_env))
    return merged


def env_or(name: str, env: dict, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    return env.get(name, default)


# --- Helpers ---

def normalize_hostname(value: str) -> str:
    return (value or "").strip().lower()


def clean_hostname(value: str) -> str:
    """Normalize a URL/domain string into a bare hostname."""
    if not value:
        return ""
    value = value.strip().lower()
    value = re.sub(r"^https?://", "", value)
    value = value.split("/")[0].split("?")[0].split("#")[0]
    value = value.split(":")[0]
    if value.startswith("www."):
        value = value[4:]
    return value


def strip_jsonc_comments(text: str) -> str:
    """Remove // and /* */ comments so JSON parsing works."""
    text = re.sub(r"//.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return text


def detect_hostname_from_project() -> str:
    """Auto-detect site hostname from common project config files."""
    cwd = Path.cwd()

    # 1. wrangler.jsonc / wrangler.toml
    wrangler_jsonc = cwd / "wrangler.jsonc"
    if wrangler_jsonc.exists():
        try:
            data = json.loads(strip_jsonc_comments(wrangler_jsonc.read_text()))
            candidates = []
            for route in data.get("routes", []):
                pattern = route.get("pattern", "")
                if route.get("custom_domain") and pattern:
                    host = clean_hostname(pattern)
                    if host and host not in candidates:
                        candidates.append(host)
            # Prefer apex domain over www
            for c in candidates:
                if not c.startswith("www."):
                    return c
            if candidates:
                return candidates[0]
        except Exception:
            pass

    wrangler_toml = cwd / "wrangler.toml"
    if wrangler_toml.exists():
        try:
            import tomllib

            data = tomllib.loads(wrangler_toml.read_text())
            candidates = []
            for route in data.get("routes", []):
                pattern = route.get("pattern", "")
                if route.get("custom_domain") and pattern:
                    host = clean_hostname(pattern)
                    if host and host not in candidates:
                        candidates.append(host)
            for c in candidates:
                if not c.startswith("www."):
                    return c
            if candidates:
                return candidates[0]
        except Exception:
            pass

    # 2. .env files
    for env_name in (".env.local", ".env"):
        env_path = cwd / env_name
        if env_path.exists():
            try:
                env = read_env_file(env_path)
                for key in (
                    "NEXT_PUBLIC_BASE_URL",
                    "NEXT_PUBLIC_SITE_URL",
                    "SITE_URL",
                    "BASE_URL",
                ):
                    host = clean_hostname(env.get(key, ""))
                    if host and host not in ("localhost", "127.0.0.1"):
                        return host
            except Exception:
                pass

    # 3. next.config.* — attempt simple regex extraction
    for config_name in ("next.config.ts", "next.config.js", "next.config.mjs"):
        config_path = cwd / config_name
        if config_path.exists():
            try:
                text = config_path.read_text()
                for match in re.finditer(
                    r'(?:domain|hostname|baseUrl|siteUrl)\s*:\s*["\']([^"\']+)["\']', text
                ):
                    host = clean_hostname(match.group(1))
                    if host and host not in ("localhost", "127.0.0.1"):
                        return host
            except Exception:
                pass

    # 4. package.json homepage
    package_path = cwd / "package.json"
    if package_path.exists():
        try:
            data = json.loads(package_path.read_text())
            host = clean_hostname(data.get("homepage", ""))
            if host and host not in ("localhost", "127.0.0.1"):
                return host
        except Exception:
            pass

    # 5. layout / page files
    for glob in (
        "src/app/layout.tsx",
        "src/app/layout.ts",
        "src/app/layout.jsx",
        "src/app/layout.js",
        "app/layout.tsx",
        "app/layout.ts",
        "src/app/page.tsx",
        "src/app/page.ts",
        "app/page.tsx",
        "app/page.ts",
    ):
        layout_path = cwd / glob
        if layout_path.exists():
            try:
                text = layout_path.read_text()
                for match in re.finditer(
                    r'(?:baseUrl|siteUrl|BASE_URL|SITE_URL)\s*(?:=|:)\s*["\'](https?://[^"\']+)["\']',
                    text,
                ):
                    host = clean_hostname(match.group(1))
                    if host and host not in ("localhost", "127.0.0.1"):
                        return host
            except Exception:
                pass

    return ""


def iso_date_range(days: int):
    end = date.today() - timedelta(days=1)
    start = end - timedelta(days=max(1, days) - 1)
    return start.isoformat(), end.isoformat()


def _try_int(v):
    try:
        return int(v)
    except Exception:
        return 0


def _safe_get(obj, key, default="?"):
    if isinstance(obj, dict):
        return obj.get(key, default)
    return obj if obj is not None else default


# --- Google Search Console ---

def gsc_access_token(quota_project: str) -> tuple:
    result = subprocess.run(
        [
            "gcloud", "auth", "application-default", "print-access-token",
            "--scopes=https://www.googleapis.com/auth/webmasters",
            f"--billing-project={quota_project}",
        ],
        capture_output=True, text=True, check=True, timeout=30,
    )
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("Empty GSC access token")
    qp = quota_project
    try:
        adc_text = (Path.home() / ".config" / "gcloud" / "application_default_credentials.json").read_text()
        qp = qp or json.loads(adc_text).get("quota_project_id", "")
    except Exception:
        pass
    return token, qp


def gsc_list_sites(token: str, quota_project: str) -> list:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    if quota_project:
        headers["x-goog-user-project"] = quota_project
    resp = requests.get("https://www.googleapis.com/webmasters/v3/sites", headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json().get("siteEntry", [])


def gsc_resolve_property(hostname: str, sites: list) -> str:
    hostname = normalize_hostname(hostname)
    candidates = [
        f"sc-domain:{hostname}",
        f"https://{hostname}/",
        f"http://{hostname}/",
        f"https://www.{hostname}/",
        f"http://www.{hostname}/",
    ]
    existing = {str(e.get("siteUrl", "")).strip(): e for e in sites if e.get("siteUrl")}
    for c in candidates:
        if c in existing:
            return c
    for site_url, entry in existing.items():
        perm = str(entry.get("permissionLevel", "")).strip()
        if hostname in site_url and perm and perm != "siteUnverifiedUser":
            return site_url
    available = ", ".join(sorted(existing.keys())[:10])
    raise RuntimeError(f"No GSC property for {hostname}. Available: {available}")


def gsc_query(token: str, quota_project: str, property_uri: str, body: dict) -> dict:
    encoded = quote(property_uri, safe="")
    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{encoded}/searchAnalytics/query"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    if quota_project:
        headers["x-goog-user-project"] = quota_project
    resp = requests.post(url, headers=headers, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_gsc(hostname: str, days: int, env: dict) -> dict:
    quota_project = env_or("GCP_QUOTA_PROJECT", env)
    if not quota_project:
        raise RuntimeError("GCP_QUOTA_PROJECT not set in env")

    token, qp = gsc_access_token(quota_project)
    sites = gsc_list_sites(token, qp)
    prop = gsc_resolve_property(hostname, sites)
    start_date, end_date = iso_date_range(days)

    by_date = gsc_query(token, qp, prop, {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["date"], "rowLimit": max(100, days + 7),
    })
    by_query = gsc_query(token, qp, prop, {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["query"], "rowLimit": 25,
    })
    by_page = gsc_query(token, qp, prop, {
        "startDate": start_date, "endDate": end_date,
        "dimensions": ["page"], "rowLimit": 25,
    })

    rows_date = by_date.get("rows", [])
    rows_query = by_query.get("rows", [])
    rows_page = by_page.get("rows", [])

    total_clicks = sum(_try_int(r.get("clicks")) for r in rows_date)
    total_impressions = sum(_try_int(r.get("impressions")) for r in rows_date)
    avg_position = (
        sum(float(r.get("position", 0)) * _try_int(r.get("impressions")) for r in rows_date)
        / max(total_impressions, 1)
    )

    return {
        "provider": "gsc",
        "property": prop,
        "date_range": {"start": start_date, "end": end_date},
        "totals": {
            "clicks": total_clicks,
            "impressions": total_impressions,
            "ctr": round(total_clicks / max(total_impressions, 1), 4),
            "avg_position": round(avg_position, 1),
        },
        "daily": [
            {
                "date": str(r["keys"][0]),
                "clicks": _try_int(r.get("clicks")),
                "impressions": _try_int(r.get("impressions")),
                "ctr": round(r.get("ctr", 0), 4),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows_date
        ],
        "top_queries": [
            {
                "query": str(r["keys"][0]),
                "clicks": _try_int(r.get("clicks")),
                "impressions": _try_int(r.get("impressions")),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows_query[:15]
        ],
        "top_pages": [
            {
                "page": str(r["keys"][0]),
                "clicks": _try_int(r.get("clicks")),
                "impressions": _try_int(r.get("impressions")),
                "position": round(r.get("position", 0), 1),
            }
            for r in rows_page[:15]
        ],
    }


# --- Cloudflare ---

def cloudflare_list_zones(token: str) -> list:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    zones = []
    page = 1
    while True:
        resp = requests.get(
            "https://api.cloudflare.com/client/v4/zones",
            headers=headers, params={"page": page, "per_page": 50}, timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        zones.extend(data.get("result", []))
        info = data.get("result_info", {})
        if page >= info.get("total_pages", 1):
            break
        page += 1
    return zones


def cloudflare_graphql(token: str, zone_id: str, hostname: str, days: int) -> dict:
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)

    series_query = """
query GetSeries($zoneTag: string, $filter: filter) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      series: httpRequestsAdaptiveGroups(limit: 48, filter: $filter) {
        dimensions { datetimeHour }
        count
        sum { visits edgeResponseBytes }
      }
    }
  }
}"""
    top_paths_query = """
query GetTopPaths($zoneTag: string, $filter: filter) {
  viewer {
    zones(filter: { zoneTag: $zoneTag }) {
      topPaths: httpRequestsAdaptiveGroups(limit: 10, orderBy: [sum_edgeResponseBytes_DESC], filter: $filter) {
        count
        sum { visits edgeResponseBytes }
        dimensions { clientRequestPath }
      }
    }
  }
}"""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    series_data = []
    top_paths = {}
    current = start
    while current < end:
        window_end = min(current + timedelta(days=1), end)
        filt = {
            "datetime_geq": current.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "datetime_lt": window_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "requestSource": "eyeball",
        }
        if hostname:
            filt["clientRequestHTTPHost"] = hostname

        for query_str, collector in ((series_query, "series"), (top_paths_query, "topPaths")):
            resp = requests.post(
                "https://api.cloudflare.com/client/v4/graphql",
                headers=headers,
                json={"query": query_str, "variables": {"zoneTag": zone_id, "filter": filt}},
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("errors"):
                raise RuntimeError(json.dumps(data["errors"]))
            zone_data = ((data.get("data", {}).get("viewer") or {}).get("zones") or [])
            zone_payload = zone_data[0] if zone_data else {}
            if collector == "series":
                series_data.extend(zone_payload.get("series") or [])
            else:
                for item in zone_payload.get("topPaths") or []:
                    path = ((item.get("dimensions") or {}).get("clientRequestPath")) or "/"
                    entry = top_paths.setdefault(path, {"count": 0, "visits": 0, "edgeResponseBytes": 0})
                    entry["count"] += item.get("count") or 0
                    entry["visits"] += ((item.get("sum") or {}).get("visits") or 0)
                    entry["edgeResponseBytes"] += ((item.get("sum") or {}).get("edgeResponseBytes") or 0)
        current = window_end

    totals = {
        "requests": sum(item.get("count") or 0 for item in series_data),
        "visits": sum(((item.get("sum") or {}).get("visits") or 0) for item in series_data),
        "edgeResponseBytes": sum(((item.get("sum") or {}).get("edgeResponseBytes") or 0) for item in series_data),
    }

    return {
        "totals": totals,
        "timeseries": series_data,
        "top_paths": sorted(
            [
                {"path": p, "count": v["count"], "visits": v["visits"], "edgeResponseBytes": v["edgeResponseBytes"]}
                for p, v in top_paths.items()
            ],
            key=lambda x: x["edgeResponseBytes"], reverse=True,
        )[:10],
    }


def fetch_cloudflare(hostname: str, days: int, env: dict) -> dict:
    token = env_or("CLOUDFLARE_ANALYTICS_API_TOKEN", env) or env_or("CLOUDFLARE_API_TOKEN", env)
    if not token:
        raise RuntimeError("CLOUDFLARE_ANALYTICS_API_TOKEN or CLOUDFLARE_API_TOKEN not set")

    zones = cloudflare_list_zones(token)
    if hostname:
        hostname_norm = normalize_hostname(hostname)
        zones = [z for z in zones if (z.get("name") or "").lower() == hostname_norm]
    if not zones:
        raise RuntimeError(f"No Cloudflare zone matched hostname {hostname!r}")

    result = {"provider": "cloudflare", "zones": {}}
    for zone in zones:
        zone_name = zone.get("name", "")
        zone_id = zone.get("id", "")
        if not zone_id or not zone_name:
            continue
        result["zones"][zone_name] = cloudflare_graphql(token, zone_id, zone_name, days)
    return result


# --- Umami ---

def umami_login(base_url: str, username: str, password: str) -> str:
    resp = requests.post(
        f"{base_url.rstrip('/')}/auth/login",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        json={"username": username, "password": password}, timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def umami_list_websites(base_url: str, *, api_key: str = "", bearer_token: str = "") -> list:
    headers = {"Accept": "application/json"}
    if api_key:
        headers["x-umami-api-key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    resp = requests.get(
        f"{base_url.rstrip('/')}/websites",
        headers=headers, params={"pageSize": 100, "includeTeams": "true"}, timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    return payload.get("data", payload)


def umami_fetch(base_url: str, website_id: str, days: int, *, api_key: str = "", bearer_token: str = "") -> dict:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    start_ms = int(start.timestamp() * 1000)
    end_ms = int(end.timestamp() * 1000)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["x-umami-api-key"] = api_key
    if bearer_token:
        headers["Authorization"] = f"Bearer {bearer_token}"
    base = base_url.rstrip("/")

    def get(path, **params):
        resp = requests.get(f"{base}{path}", headers=headers, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    return {
        "stats": get(f"/websites/{website_id}/stats", startAt=start_ms, endAt=end_ms),
        "pageviews": get(f"/websites/{website_id}/pageviews", startAt=start_ms, endAt=end_ms, unit="day"),
        "metrics": {
            "referrer": get(f"/websites/{website_id}/metrics", startAt=start_ms, endAt=end_ms, type="referrer"),
            "path": get(f"/websites/{website_id}/metrics", startAt=start_ms, endAt=end_ms, type="path"),
            "browser": get(f"/websites/{website_id}/metrics", startAt=start_ms, endAt=end_ms, type="browser"),
            "device": get(f"/websites/{website_id}/metrics", startAt=start_ms, endAt=end_ms, type="device"),
            "country": get(f"/websites/{website_id}/metrics", startAt=start_ms, endAt=end_ms, type="country"),
        },
    }


def fetch_umami(hostname: str, days: int, env: dict) -> dict:
    base_url = env_or("UMAMI_BASE_URL", env)
    if not base_url:
        raise RuntimeError("UMAMI_BASE_URL not set in env")
    api_key = env_or("UMAMI_API_KEY", env)
    username = env_or("UMAMI_ADMIN_USERNAME", env)
    password = env_or("UMAMI_ADMIN_PASSWORD", env)

    bearer_token = ""
    if api_key:
        bearer_token = ""
    elif username and password:
        try:
            bearer_token = umami_login(base_url, username, password)
        except Exception:
            bearer_token = ""
    else:
        raise RuntimeError("UMAMI_API_KEY or UMAMI_ADMIN_USERNAME+UMAMI_ADMIN_PASSWORD required")

    websites = umami_list_websites(base_url, api_key=api_key, bearer_token=bearer_token)
    if hostname:
        hostname_norm = normalize_hostname(hostname)
        websites = [w for w in websites if (w.get("domain") or "").lower() == hostname_norm]
    if not websites:
        raise RuntimeError(f"No Umami website matched hostname {hostname!r}")

    result = {"provider": "umami", "base_url": base_url, "websites": {}}
    for site in websites:
        site_id = site.get("id")
        domain = site.get("domain") or site.get("name", "")
        if not site_id:
            continue
        result["websites"][domain] = umami_fetch(base_url, site_id, days, api_key=api_key, bearer_token=bearer_token)
    return result


# --- Microsoft Clarity ---

def fetch_clarity(hostname: str, days: int, env: dict) -> dict:
    token = env_or("CLARITY_EXPORT_TOKEN", env)
    if not token and SITE_INTEGRATIONS_PATH.exists():
        try:
            config = json.loads(SITE_INTEGRATIONS_PATH.read_text())
            entry = config.get("domains", {}).get(normalize_hostname(hostname))
            if isinstance(entry, dict):
                clarity = entry.get("clarity")
                if isinstance(clarity, dict):
                    token = clarity.get("token", "")
        except Exception:
            pass
    if not token:
        raise RuntimeError("CLARITY_EXPORT_TOKEN not set and no match in site-integrations.json")

    days = max(1, min(int(days), 3))
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    result = {"provider": "clarity", "summary": None, "dimensions": {}, "errors": []}

    try:
        resp = requests.get(
            "https://www.clarity.ms/export-data/api/v1/project-live-insights",
            params={"numOfDays": str(days)}, headers=headers, timeout=30,
        )
        resp.raise_for_status()
        result["summary"] = resp.json()
    except Exception as exc:
        result["errors"].append(f"summary: {exc}")

    for dims in [("Browser",), ("Device",), ("Country/Region",), ("Source",), ("URL",)]:
        key = "|".join(dims)
        try:
            params = {"numOfDays": str(days)}
            for i, d in enumerate(dims, 1):
                params[f"dimension{i}"] = d
            resp = requests.get(
                "https://www.clarity.ms/export-data/api/v1/project-live-insights",
                params=params, headers=headers, timeout=30,
            )
            resp.raise_for_status()
            result["dimensions"][key] = resp.json()
        except Exception as exc:
            result["errors"].append(f"{key}: {exc}")
        time.sleep(0.3)

    return result


# --- Main ---

PROVIDERS = {
    "gsc": fetch_gsc,
    "cloudflare": fetch_cloudflare,
    "umami": fetch_umami,
    "clarity": fetch_clarity,
}


def build_summary(report: dict) -> str:
    parts = []
    hostname = report.get("hostname", "")
    days = report.get("days", 28)
    results = report.get("providers", {})
    errors = report.get("errors", {})

    parts.append(f"## {hostname} · 最近 {days} 天\n")

    # GSC
    if "gsc" in results:
        gsc = results["gsc"]
        t = gsc.get("totals", {})
        parts.append(
            f"**Search Console** — {t.get('clicks', 0)} 点击 · {t.get('impressions', 0)} 展示 · "
            f"CTR {t.get('ctr', 0):.2%} · 平均排名 {t.get('avg_position', 0)}\n"
        )
        top_q = gsc.get("top_queries", [])[:5]
        if top_q:
            parts.append("热门查询:")
            for q in top_q:
                parts.append(f"  • \"{q['query']}\" — {q['clicks']} 点击, {q['impressions']} 展示, 排名 {q['position']}")
            parts.append("")
        top_p = gsc.get("top_pages", [])[:5]
        if top_p:
            parts.append("热门页面:")
            for p in top_p:
                parts.append(f"  • {p['page']} — {p['clicks']} 点击, {p['impressions']} 展示, 排名 {p['position']}")
            parts.append("")
    elif errors.get("gsc"):
        parts.append(f"**Search Console** — 错误: {errors['gsc']}\n")

    # Cloudflare
    if "cloudflare" in results:
        cf = results["cloudflare"]
        for zone_name, zone_data in cf.get("zones", {}).items():
            t = zone_data.get("totals", {})
            visits = t.get("visits", 0)
            reqs = t.get("requests", 0)
            gb = round(t.get("edgeResponseBytes", 0) / 1e9, 2)
            parts.append(f"**Cloudflare** ({zone_name}) — {reqs:,} 请求 · {visits:,} 访问 · {gb} GB\n")
    elif errors.get("cloudflare"):
        parts.append(f"**Cloudflare** — 错误: {errors['cloudflare']}\n")

    # Umami
    if "umami" in results:
        um = results["umami"]
        for domain, data in um.get("websites", {}).items():
            s = data.get("stats", {})
            pv = _safe_get(s, "pageviews")
            visitors = _safe_get(s, "visitors")
            visits = _safe_get(s, "visits")
            bounces = _safe_get(s, "bounces")
            parts.append(f"**Umami** ({domain}) — {pv} PV · {visitors} 访客 · {visits} 访问 · {bounces} 跳出\n")
    elif errors.get("umami"):
        parts.append(f"**Umami** — 错误: {errors['umami']}\n")

    # Clarity
    if "clarity" in results:
        cl = results["clarity"]
        if cl.get("summary"):
            parts.append("**Clarity** — 导出数据已获取\n")
        if cl.get("errors"):
            parts.append(f"  Clarity 错误: {cl['errors']}\n")
    elif errors.get("clarity"):
        parts.append(f"**Clarity** — 错误: {errors['clarity']}\n")

    # Status
    status_parts = []
    for name in report.get("inputs", {}).get("providers", []):
        if name in results:
            status_parts.append(f"✅ {name}")
        else:
            status_parts.append(f"❌ {name}")
    parts.append(" · ".join(status_parts))

    return "\n".join(parts)


def main():
    parser = argparse.ArgumentParser(description="jz-get-analytics — 实时查看站点 metrics")
    parser.add_argument("--hostname", required=False, help="站点域名（未提供时自动检测）")
    parser.add_argument("--days", type=int, default=28, help="查询天数（默认 28）")
    parser.add_argument(
        "--providers", default="gsc,cloudflare,umami,clarity",
        help="逗号分隔的 provider 列表（默认 gsc,cloudflare,umami,clarity）",
    )
    args = parser.parse_args()

    hostname = normalize_hostname(args.hostname) if args.hostname else detect_hostname_from_project()
    if not hostname:
        print(
            json.dumps(
                {"error": "未检测到站点域名，请提供 --hostname，例如 auditmycareer.com"},
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1
    days = max(1, args.days)
    requested = {p.strip() for p in args.providers.split(",") if p.strip()}
    if not requested:
        requested = {"gsc", "cloudflare", "umami", "clarity"}

    env = load_env()

    report = {
        "hostname": hostname,
        "days": days,
        "inputs": {"providers": sorted(requested)},
        "providers": {},
        "errors": {},
    }

    for provider_name in sorted(requested):
        fetcher = PROVIDERS.get(provider_name)
        if not fetcher:
            report["errors"][provider_name] = f"Unknown provider: {provider_name}"
            continue
        try:
            report["providers"][provider_name] = fetcher(hostname, days, env)
        except Exception as exc:
            report["errors"][provider_name] = str(exc)

    report["summary"] = build_summary(report)
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
