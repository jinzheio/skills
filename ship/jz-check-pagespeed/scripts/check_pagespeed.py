#!/usr/bin/env python3
"""jz-check-pagespeed — PageSpeed Insights + CrUX + Cloudflare Web Vitals."""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlparse
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

SKILL_ROOT = Path(__file__).resolve().parents[1]
USER_CONFIG_ENV = Path.home() / ".config" / "skills" / "jz-check-metrics" / ".env"
SKILL_ENV = SKILL_ROOT / ".env"

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
    merged = read_env_file(SKILL_ENV)
    merged.update(read_env_file(USER_CONFIG_ENV))
    cwd_env = Path(os.getcwd()) / ".env"
    merged.update(read_env_file(cwd_env))
    return merged


def env_or(name: str, env: dict, default: str = "") -> str:
    if os.environ.get(name):
        return os.environ[name]
    return env.get(name, default)


# --- PSI API ---

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

LAB_METRICS = [
    ("first-contentful-paint", "FCP", "ms"),
    ("largest-contentful-paint", "LCP", "ms"),
    ("total-blocking-time", "TBT", "ms"),
    ("cumulative-layout-shift", "CLS", "score"),
    ("speed-index", "SI", "ms"),
    ("interactive", "TTI", "ms"),
]

THRESHOLDS = {
    "FCP":     (1800, 3000),   # ms: green / orange / red
    "LCP":     (2500, 4000),
    "TBT":     (200, 600),
    "CLS":     (0.10, 0.25),
    "SI":      (3400, 5800),
    "TTI":     (3800, 7300),
}

COLOR = {
    "good": "\033[92m",       # green
    "needs_improvement": "\033[93m",  # yellow
    "poor": "\033[91m",       # red
    "reset": "\033[0m",
}


def color_for_metric(name: str, value: float) -> str:
    """Return color level string for a metric value."""
    thresholds = THRESHOLDS.get(name)
    if not thresholds:
        return "unknown"
    green, orange = thresholds
    if name == "CLS":
        if value <= green:
            return "good"
        elif value <= orange:
            return "needs_improvement"
    else:
        if value <= green:
            return "good"
        elif value <= orange:
            return "needs_improvement"
    return "poor"


def color_mark(value: float, name: str) -> str:
    """Return colored indicator for terminal output."""
    level = color_for_metric(name, value)
    icon = {"good": "●", "needs_improvement": "●", "poor": "●"}
    return f"{COLOR.get(level, '')}{icon.get(level, '?')}{COLOR['reset']}"


def fetch_psi(url: str, strategy: str, api_key: str) -> dict:
    """Fetch PageSpeed Insights for a single strategy."""
    params = f"url={quote(url, safe='')}&strategy={strategy}"
    if api_key:
        params += f"&key={api_key}"
    req_url = f"{PSI_ENDPOINT}?{params}"
    req = Request(req_url, headers={"Accept": "application/json"})
    try:
        resp = urlopen(req, timeout=60)
        return json.loads(resp.read())
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"PSI API error ({e.code}): {body[:300]}")
    except URLError as e:
        raise RuntimeError(f"Cannot reach PSI API: {e.reason}")


def extract_psi_metrics(data: dict) -> dict:
    """Extract key metrics and audits from a PSI response."""
    lighthouse = data.get("lighthouseResult", {})
    cats = lighthouse.get("categories", {})
    audits = lighthouse.get("audits", {})

    perf_score = 0
    if "performance" in cats:
        perf_score = (cats["performance"].get("score") or 0) * 100

    metrics = {"performance_score": round(perf_score)}
    for audit_id, name, unit in LAB_METRICS:
        audit = audits.get(audit_id)
        if audit and "numericValue" in audit:
            value = audit["numericValue"]
            if unit == "ms":
                value = round(value)
            else:
                value = round(value, 3)
            metrics[name] = {
                "value": value,
                "unit": unit,
                "display": audit.get("displayValue", ""),
                "level": color_for_metric(name, value),
            }

    # Collect diagnostic failures
    diagnostics = []
    from collections import OrderedDict
    # Get all scored audits sorted by score ascending (worst first)
    scored = []
    for audit_id, audit in audits.items():
        score = audit.get("score")
        if score is not None and isinstance(score, (int, float)):
            scored.append((audit_id, audit, score))
    scored.sort(key=lambda x: x[2])

    for audit_id, audit, score in scored:
        if score >= 0.9:
            continue  # skip passing audits
        description = (audit.get("description") or audit.get("title") or "").replace("\n", " ")[:200]
        diagnostics.append({
            "id": audit_id,
            "title": audit.get("title", ""),
            "score": round(score, 2),
            "displayValue": audit.get("displayValue", ""),
            "description": description,
        })

    # CrUX field data
    crux = {}
    loading = data.get("loadingExperience", {})
    if loading and loading.get("metrics"):
        crux["overall_category"] = loading.get("overall_category", "")
        crux["metrics"] = {}
        for name in ["FIRST_CONTENTFUL_PAINT_MS", "LARGEST_CONTENTFUL_PAINT_MS",
                     "CUMULATIVE_LAYOUT_SHIFT_SCORE", "FIRST_INPUT_DELAY_MS"]:
            m = loading["metrics"].get(name)
            if m:
                crux["metrics"][name] = {
                    "percentile": m.get("percentile", 0),
                    "category": m.get("category", ""),
                }

    return {
        "fetched_at": lighthouse.get("fetchTime", ""),
        "final_url": lighthouse.get("finalUrl", ""),
        "metrics": metrics,
        "diagnostics": diagnostics[:20],
        "crux": crux if crux.get("metrics") else None,
    }


# --- Cloudflare RUM Web Vitals ---

# RUM datasets are on Account (not Zone) level in Cloudflare GraphQL.
# Requires: 1) Cloudflare Web Analytics enabled on the zone, 2) API token with Account:Analytics:Read.
CF_RUM_WEB_VITALS_QUERY = """
query WebVitals($accountTag: string, $filter: AccountRumWebVitalsEventsAdaptiveGroupsFilter_InputObject) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      rumWebVitalsEventsAdaptiveGroups(limit: 10, filter: $filter) {
        count
        avg {
          largestContentfulPaint
          firstContentfulPaint
          cumulativeLayoutShift
          timeToFirstByte
          firstInputDelay
          interactionToNextPaint
        }
        sum {
          lcpGood lcpNeedsImprovement lcpPoor lcpTotal
          fcpGood fcpNeedsImprovement fcpPoor fcpTotal
          clsGood clsNeedsImprovement clsPoor clsTotal
          ttfbGood ttfbNeedsImprovement ttfbPoor ttfbTotal
        }
        dimensions {
          date
          deviceType
        }
      }
    }
  }
}
"""

CF_RUM_PERFORMANCE_QUERY = """
query Perf($accountTag: string, $filter: AccountRumPerformanceEventsAdaptiveGroupsFilter_InputObject) {
  viewer {
    accounts(filter: { accountTag: $accountTag }) {
      rumPerformanceEventsAdaptiveGroups(limit: 10, filter: $filter) {
        count
        avg {
          firstContentfulPaint
          firstPaint
          pageLoadTime
          dnsTime
          connectionTime
        }
        quantiles {
          firstContentfulPaintP50
          firstContentfulPaintP75
          firstContentfulPaintP95
        }
        dimensions {
          date
          deviceType
        }
      }
    }
  }
}
"""


def cloudflare_list_zones(token: str) -> list:
    req = Request(
        "https://api.cloudflare.com/client/v4/zones?page=1&per_page=50",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    resp = json.loads(urlopen(req, timeout=30).read())
    return resp.get("result", [])


def cloudflare_list_rum_sites(token: str, account_id: str) -> list:
    """List Web Analytics / RUM sites for an account."""
    req = Request(
        f"https://api.cloudflare.com/client/v4/accounts/{account_id}/rum/site_info/list",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    resp = json.loads(urlopen(req, timeout=30).read())
    return resp.get("result", [])


def fetch_cloudflare_rum(token: str, hostname: str, days: int = 7) -> dict:
    """Query Cloudflare RUM Web Vitals + Performance. Uses Account-level GraphQL."""
    hostname_norm = hostname.strip().lower()

    # 1. Get zone to find account_id
    zones = cloudflare_list_zones(token)
    zone = next((z for z in zones if (z.get("name") or "").lower() == hostname_norm), None)
    if not zone:
        return {"available": False, "reason": f"No Cloudflare zone for {hostname}"}

    account_id = (zone.get("account", {}) or {}).get("id", "")
    if not account_id:
        return {"available": False, "reason": "Cannot determine account ID from zone"}

    # 2. Find RUM site_tag for this zone
    rum_sites = cloudflare_list_rum_sites(token, account_id)
    site_tag = ""
    for s in rum_sites:
        ruleset = s.get("ruleset", {}) if isinstance(s, dict) else {}
        if ruleset.get("enabled") and (ruleset.get("zone_name", "")).lower() == hostname_norm:
            site_tag = s.get("site_tag", "")
            break

    if not site_tag:
        return {"available": False, "reason": "Web Analytics / RUM not enabled for this zone"}

    # 3. Build time filter
    from datetime import timedelta
    end = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(days=days)
    time_filter = {
        "datetime_geq": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "datetime_lt": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "siteTag": site_tag,
    }

    # 4. Query Web Vitals
    wv_result = None
    try:
        wv_req = Request(
            "https://api.cloudflare.com/client/v4/graphql",
            data=json.dumps({
                "query": CF_RUM_WEB_VITALS_QUERY,
                "variables": {"accountTag": account_id, "filter": time_filter},
            }).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        wv_result = json.loads(urlopen(wv_req, timeout=30).read())
    except Exception as exc:
        return {"available": False, "reason": f"GraphQL error: {exc}"}

    if wv_result and wv_result.get("errors"):
        msg = str(wv_result["errors"][0].get("message", ""))
        return {"available": False, "reason": f"GraphQL: {msg[:120]}"}

    # 5. Parse Web Vitals groups
    vitals_groups = []
    try:
        accounts = ((wv_result or {}).get("data", {}).get("viewer", {}) or {}).get("accounts", [])
        for acct in accounts:
            vitals_groups = acct.get("rumWebVitalsEventsAdaptiveGroups", [])
    except Exception:
        vitals_groups = []

    if not vitals_groups:
        return {"available": False, "reason": "No Web Vitals data in RUM (insufficient traffic or recently enabled)"}

    # Aggregate
    total_count = 0
    sums = {
        "lcp": {"good": 0, "needs_improvement": 0, "poor": 0, "total": 0},
        "fcp": {"good": 0, "needs_improvement": 0, "poor": 0, "total": 0},
        "cls": {"good": 0, "needs_improvement": 0, "poor": 0, "total": 0},
        "ttfb": {"good": 0, "needs_improvement": 0, "poor": 0, "total": 0},
    }
    weighted = {"lcp": 0, "fcp": 0, "cls": 0, "ttfb": 0}

    for g in vitals_groups:
        count = g.get("count", 0) or 0
        total_count += count
        s = g.get("sum", {}) or {}
        sums["lcp"]["good"] += s.get("lcpGood", 0) or 0
        sums["lcp"]["needs_improvement"] += s.get("lcpNeedsImprovement", 0) or 0
        sums["lcp"]["poor"] += s.get("lcpPoor", 0) or 0
        sums["lcp"]["total"] += s.get("lcpTotal", 0) or 0
        sums["fcp"]["good"] += s.get("fcpGood", 0) or 0
        sums["fcp"]["needs_improvement"] += s.get("fcpNeedsImprovement", 0) or 0
        sums["fcp"]["poor"] += s.get("fcpPoor", 0) or 0
        sums["fcp"]["total"] += s.get("fcpTotal", 0) or 0
        sums["cls"]["good"] += s.get("clsGood", 0) or 0
        sums["cls"]["needs_improvement"] += s.get("clsNeedsImprovement", 0) or 0
        sums["cls"]["poor"] += s.get("clsPoor", 0) or 0
        sums["cls"]["total"] += s.get("clsTotal", 0) or 0
        sums["ttfb"]["good"] += s.get("ttfbGood", 0) or 0
        sums["ttfb"]["needs_improvement"] += s.get("ttfbNeedsImprovement", 0) or 0
        sums["ttfb"]["poor"] += s.get("ttfbPoor", 0) or 0
        sums["ttfb"]["total"] += s.get("ttfbTotal", 0) or 0
        avg = g.get("avg", {}) or {}
        for key in ["lcp", "fcp", "cls", "ttfb"]:
            if key == "lcp" and avg.get("largestContentfulPaint"):
                weighted[key] += (avg["largestContentfulPaint"] or 0) * max(count, 1)
            elif key == "fcp" and avg.get("firstContentfulPaint"):
                weighted[key] += (avg["firstContentfulPaint"] or 0) * max(count, 1)
            elif key == "cls" and avg.get("cumulativeLayoutShift"):
                weighted[key] += (avg["cumulativeLayoutShift"] or 0) * max(count, 1)
            elif key == "ttfb" and avg.get("timeToFirstByte"):
                weighted[key] += (avg["timeToFirstByte"] or 0) * max(count, 1)

    averages = {}
    for key in sums:
        if total_count > 0 and weighted[key] > 0:
            avg_weight = sum(g.get("count", 0) or 0 for g in vitals_groups if (g.get("avg", {}).get(
                {"lcp": "largestContentfulPaint", "fcp": "firstContentfulPaint",
                 "cls": "cumulativeLayoutShift", "ttfb": "timeToFirstByte"}[key], 0) or 0) > 0)
            if avg_weight > 0:
                averages[key] = round(weighted[key] / avg_weight / 1000, 1) if key != "cls" else round(weighted[key] / avg_weight, 3)
            else:
                averages[key] = 0
        else:
            averages[key] = 0

    # Format as percentages
    web_vitals = {}
    for metric_key in sums:
        m = sums[metric_key]
        total = m["total"]
        if total > 0:
            web_vitals[metric_key] = {
                "good_pct": round(m["good"] / total * 100, 1),
                "ni_pct": round(m["needs_improvement"] / total * 100, 1),
                "poor_pct": round(m["poor"] / total * 100, 1),
                "total": total,
            }
        else:
            web_vitals[metric_key] = {"good_pct": 0, "ni_pct": 0, "poor_pct": 0, "total": 0}

    return {
        "available": True,
        "hostname": hostname,
        "sample_size": total_count,
        "site_tag": site_tag,
        "web_vitals": web_vitals,
        "averages": {k: averages.get(k, 0) for k in sums},
    }


# --- Framework detection ---

FRAMEWORK_MARKERS = {
    "astro": [
        ("astro.config", "Astro config"),
        ("package.json", '"astro"'),
        ("src/layouts/", "Astro layouts dir"),
        ("src/pages/", "Astro pages (but check for .astro extension)"),
    ],
    "tanstack-start": [
        ("app.config.ts", "TanStack Start config"),
        ("package.json", '"@tanstack/react-start"'),
        ("app/", "TanStack Start app dir"),
    ],
}


def detect_framework(project_root: Path) -> str:
    """Auto-detect web framework from project root."""
    if not project_root.exists():
        return "unknown"

    # Check package.json for dependencies
    pkg_json = project_root / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            if "astro" in deps:
                return "astro"
            if "@tanstack/react-start" in deps:
                return "tanstack-start"
        except Exception:
            pass

    # Check for framework-specific dirs
    if (project_root / "astro.config.mjs").exists() or \
       (project_root / "astro.config.ts").exists():
        return "astro"
    if (project_root / "app.config.ts").exists() or \
       (project_root / "app.config.js").exists():
        return "tanstack-start"

    return "unknown"


# --- Formatters ---

def format_metric_row(name: str, info: dict) -> str:
    """Format a single metric for terminal display."""
    if not info:
        return f"  {name}: N/A"
    mark = color_mark(info["value"], name)
    level = info.get("level", "unknown")
    level_cn = {"good": "好", "needs_improvement": "可改进", "poor": "差"}.get(level, "?")
    return f"  {mark} {name}: {info['value']} {info['unit']} ({level_cn})  {info.get('display', '')}"


def build_summary(reports: dict) -> str:
    """Build human-readable summary of all reports."""
    lines = []
    url = reports.get("url", "")
    lines.append(f"## {url}\n")

    psi_data = reports.get("psi", {})
    for strategy in ["mobile", "desktop"]:
        result = psi_data.get(strategy)
        if not result:
            continue
        metrics = result.get("metrics", {})
        perf = metrics.get("performance_score", "?")
        lines.append(f"### {strategy.upper()} · Lighthouse {perf}/100\n")

        for name, _, _ in LAB_METRICS:
            info = metrics.get(name)
            if info:
                lines.append(format_metric_row(name, info))
        lines.append("")

        # Diagnostics (top 5)
        diags = result.get("diagnostics", [])[:5]
        if diags:
            lines.append(f"**Top issues ({strategy}):**")
            for d in diags:
                lines.append(f"  • {d['title']} — score {d['score']}")
            lines.append("")

        # CrUX
        crux = result.get("crux")
        if crux:
            lines.append(f"**CrUX 现场数据** — 总体: {crux.get('overall_category', '?')}")
            for mname, mdata in crux.get("metrics", {}).items():
                short = mname.replace("FIRST_CONTENTFUL_PAINT_MS", "FCP") \
                             .replace("LARGEST_CONTENTFUL_PAINT_MS", "LCP") \
                             .replace("CUMULATIVE_LAYOUT_SHIFT_SCORE", "CLS") \
                             .replace("FIRST_INPUT_DELAY_MS", "FID")
                lines.append(f"  {short}: p75={mdata['percentile']} ({mdata['category']})")
            lines.append("")

    # Cloudflare RUM
    rum = reports.get("cloudflare_rum")
    if rum and rum.get("available"):
        wv = rum.get("web_vitals", {})
        lines.append(f"**Cloudflare RUM** — {rum['sample_size']} 次真实访问\n")
        for k in ["fcp", "lcp", "cls", "ttfb"]:
            m = wv.get(k, {})
            if m:
                lines.append(f"  {k.upper()}: ● {m.get('good_pct', 0)}% 好 / {m.get('ni_pct', 0)}% 需改进 / {m.get('poor_pct', 0)}% 差 (n={m.get('total', 0)})")
        lines.append("")
    elif rum:
        lines.append(f"**Cloudflare RUM** — 不可用: {rum.get('reason', '?')}\n")

    # Framework
    framework = reports.get("framework", "unknown")
    if framework != "unknown":
        lines.append(f"**框架**: {framework}")
    lines.append("")

    return "\n".join(lines)


# --- Main ---

def main():
    parser = argparse.ArgumentParser(description="jz-check-pagespeed — 页面速度诊断")
    parser.add_argument("--url", required=True, help="目标页面 URL")
    parser.add_argument("--strategy", choices=["mobile", "desktop", "both"], default="mobile",
                        help="测试策略（默认 mobile）")
    parser.add_argument("--fix", action="store_true", help="自动应用改进建议")
    parser.add_argument("--framework", default="auto",
                        help="目标框架，auto 自动检测。可选: astro, tanstack-start, unknown")
    parser.add_argument("--project-root", default=".",
                        help="框架检测时的项目根目录（默认 cwd）")
    args = parser.parse_args()

    url = args.url
    strategies = ["mobile", "desktop"] if args.strategy == "both" else [args.strategy]
    env = load_env()
    api_key = env_or("PAGESPEED_API_KEY", env)

    report = {
        "url": url,
        "strategy": args.strategy,
        "psi": {},
        "cloudflare_rum": None,
        "errors": {},
    }

    # 1. PageSpeed Insights (per strategy)
    for strategy in strategies:
        try:
            data = fetch_psi(url, strategy, api_key)
            report["psi"][strategy] = extract_psi_metrics(data)
        except Exception as exc:
            report["errors"][f"psi_{strategy}"] = str(exc)

    # 2. Cloudflare RUM Web Vitals
    cf_token = env_or("CLOUDFLARE_API_TOKEN", env)
    if not cf_token:
        cf_token = env_or("CLOUDFLARE_ANALYTICS_API_TOKEN", env)
    hostname = urlparse(url).hostname or ""
    if cf_token and hostname:
        try:
            report["cloudflare_rum"] = fetch_cloudflare_rum(cf_token, hostname)
        except Exception as exc:
            report["errors"]["cloudflare_rum"] = str(exc)

    # 3. Framework detection
    framework = args.framework
    if framework == "auto":
        project_root = Path(args.project_root).resolve()
        framework = detect_framework(project_root)
    report["framework"] = framework

    # 4. Framework-specific recommendations
    if framework != "unknown":
        ref_path = SKILL_ROOT / "references" / f"{framework}.md"
        if ref_path.exists():
            report["framework_reference"] = str(ref_path)

    report["summary"] = build_summary(report)

    # 5. Fix mode
    if args.fix:
        if framework == "unknown":
            report["fix_note"] = "Cannot auto-fix without known framework. Provide --framework or run from project root."
        else:
            report["fix"] = {"status": "not_implemented", "note": "Auto-fix logic coming soon."}

    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
