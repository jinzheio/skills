from __future__ import annotations

import csv
from datetime import UTC, date, datetime
import json
import os
from pathlib import Path
import sqlite3
from time import sleep
from typing import Any

import requests

from .filters import guess_registrable_domain, normalize_domain

API_BASE = "https://trustmrr.com"
STARTUPS_PATH = "/api/v1/startups"
DEFAULT_LIMIT = 50
DEFAULT_SLEEP_SECONDS = 3.2


def load_env_file(path: str | Path = ".env") -> None:
    env_path = Path(path)
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text or text.startswith("#") or "=" not in text:
            continue
        key, value = text.split("=", 1)
        key = key.strip()
        value = value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value


def trustmrr_api_key() -> str:
    load_env_file()
    key = os.getenv("TRUSTMRR_API_KEY") or os.getenv("TRUST_MRR_API_KEY") or os.getenv("TMRR_API_KEY")
    if not key:
        raise RuntimeError("missing TRUSTMRR_API_KEY")
    return key


def fetch_startups_page(
    session: requests.Session,
    *,
    api_key: str,
    page: int,
    limit: int,
    params: dict[str, Any] | None = None,
) -> dict[str, Any]:
    query = {"page": page, "limit": limit, **(params or {})}
    response = session.get(
        f"{API_BASE}{STARTUPS_PATH}",
        params=query,
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def fetch_all_startups(
    *,
    api_key: str,
    raw_dir: str | Path,
    limit: int = DEFAULT_LIMIT,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    force: bool = False,
    params: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    raw_path = Path(raw_dir)
    raw_path.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    startups_by_slug: dict[str, dict[str, Any]] = {}
    page = 1
    total = None
    pages = 0
    while True:
        page_path = raw_path / f"page-{page:04d}.json"
        if page_path.exists() and not force:
            payload = json.loads(page_path.read_text(encoding="utf-8"))
            source = "cache"
        else:
            payload = fetch_startups_page(
                session,
                api_key=api_key,
                page=page,
                limit=limit,
                params=params,
            )
            page_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            source = "fetch"
        meta = payload.get("meta") or {}
        data = payload.get("data") or []
        total = meta.get("total", total)
        pages += 1
        print(
            f"trustmrr: page={page} source={source} count={len(data)} total={total} "
            f"has_more={bool(meta.get('hasMore'))}",
            flush=True,
        )
        for item in data:
            slug = str(item.get("slug") or "").strip()
            if slug:
                startups_by_slug[slug] = item
        if not meta.get("hasMore"):
            break
        page += 1
        if source == "fetch" and sleep_seconds > 0:
            sleep(sleep_seconds)
    manifest = {
        "fetched_at": datetime.now(UTC).isoformat(),
        "api_path": STARTUPS_PATH,
        "total": total,
        "pages": pages,
        "limit": limit,
        "filters": params or {},
        "status": "complete",
    }
    (raw_path / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return list(startups_by_slug.values()), manifest


def store_trustmrr_snapshot(
    conn: sqlite3.Connection,
    *,
    snapshot_date: str,
    raw_dir: str | Path,
    startups: list[dict[str, Any]],
    manifest: dict[str, Any],
) -> int:
    fetched_at = str(manifest.get("fetched_at") or datetime.now(UTC).isoformat())
    conn.execute(
        """
        insert into trustmrr_snapshots(
          snapshot_date, fetched_at, api_path, total, pages, page_limit, raw_dir, status
        ) values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(snapshot_date) do update set
          fetched_at=excluded.fetched_at,
          api_path=excluded.api_path,
          total=excluded.total,
          pages=excluded.pages,
          page_limit=excluded.page_limit,
          raw_dir=excluded.raw_dir,
          status=excluded.status
        """,
        (
            snapshot_date,
            fetched_at,
            str(manifest.get("api_path") or STARTUPS_PATH),
            manifest.get("total"),
            manifest.get("pages"),
            manifest.get("limit"),
            str(raw_dir),
            str(manifest.get("status") or "complete"),
        ),
    )
    snapshot_id = conn.execute(
        "select id from trustmrr_snapshots where snapshot_date=?",
        (snapshot_date,),
    ).fetchone()["id"]
    conn.execute("delete from trustmrr_metrics where snapshot_id=?", (snapshot_id,))
    for item in startups:
        slug = str(item.get("slug") or "").strip()
        if not slug:
            continue
        website = normalize_domain(item.get("website") or "")
        root_domain = guess_registrable_domain(website)
        existing = conn.execute(
            "select first_seen_snapshot_id from trustmrr_startups where slug=?",
            (slug,),
        ).fetchone()
        first_seen_snapshot_id = existing["first_seen_snapshot_id"] if existing else snapshot_id
        conn.execute(
            """
            insert into trustmrr_startups(
              slug, name, website, root_domain, category, description, payment_provider,
              founded_date, country, target_audience, first_listed_for_sale_at, url,
              first_seen_snapshot_id, last_seen_snapshot_id
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(slug) do update set
              name=excluded.name,
              website=excluded.website,
              root_domain=excluded.root_domain,
              category=excluded.category,
              description=excluded.description,
              payment_provider=excluded.payment_provider,
              founded_date=excluded.founded_date,
              country=excluded.country,
              target_audience=excluded.target_audience,
              first_listed_for_sale_at=excluded.first_listed_for_sale_at,
              url=excluded.url,
              first_seen_snapshot_id=coalesce(trustmrr_startups.first_seen_snapshot_id, excluded.first_seen_snapshot_id),
              last_seen_snapshot_id=excluded.last_seen_snapshot_id,
              updated_at=current_timestamp
            """,
            (
                slug,
                item.get("name"),
                website,
                root_domain,
                item.get("category"),
                item.get("description"),
                item.get("paymentProvider"),
                item.get("foundedDate"),
                item.get("country"),
                item.get("targetAudience"),
                item.get("firstListedForSaleAt"),
                item.get("url") or f"https://trustmrr.com/startup/{slug}",
                first_seen_snapshot_id,
                snapshot_id,
            ),
        )
        revenue = item.get("revenue") or {}
        conn.execute(
            """
            insert into trustmrr_metrics(
              snapshot_id, slug, revenue_30d, mrr, total_revenue, growth_30d,
              growth_mrr_30d, customers, active_subscriptions, visitors_30d,
              google_search_impressions_30d, revenue_per_visitor, asking_price,
              profit_margin_30d, multiple, rank, on_sale, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot_id,
                slug,
                revenue.get("last30Days"),
                revenue.get("mrr"),
                revenue.get("total"),
                item.get("growth30d"),
                item.get("growthMRR30d"),
                item.get("customers"),
                item.get("activeSubscriptions"),
                item.get("visitorsLast30Days"),
                item.get("googleSearchImpressionsLast30Days"),
                item.get("revenuePerVisitor"),
                item.get("askingPrice"),
                item.get("profitMarginLast30Days"),
                item.get("multiple"),
                item.get("rank"),
                1 if item.get("onSale") else 0,
                json.dumps(item, ensure_ascii=False),
            ),
        )
    conn.commit()
    return int(snapshot_id)


def latest_snapshot_id(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("select id from trustmrr_snapshots order by snapshot_date desc limit 1").fetchone()
    return int(row["id"]) if row else None


def export_trustmrr_csv(conn: sqlite3.Connection, output: str | Path, *, snapshot_id: int | None = None) -> int:
    snapshot_id = snapshot_id or latest_snapshot_id(conn)
    if snapshot_id is None:
        raise RuntimeError("no TrustMRR snapshot found")
    rows = conn.execute(
        """
        select
          s.website as domain,
          s.website,
          s.name as title,
          s.description,
          s.category,
          m.revenue_30d as trustmrr_revenue_30d,
          m.growth_30d as paid_growth,
          s.slug as trustmrr_slug,
          s.url as trustmrr_url,
          s.payment_provider,
          m.mrr,
          m.total_revenue,
          m.visitors_30d
        from trustmrr_metrics m
        join trustmrr_startups s on s.slug = m.slug
        where m.snapshot_id = ?
        order by m.revenue_30d desc nulls last
        """,
        (snapshot_id,),
    ).fetchall()
    out = Path(output)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = rows[0].keys() if rows else [
        "domain",
        "website",
        "title",
        "description",
        "category",
        "trustmrr_revenue_30d",
        "paid_growth",
        "trustmrr_slug",
        "trustmrr_url",
        "payment_provider",
        "mrr",
        "total_revenue",
        "visitors_30d",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))
    return len(rows)


def default_snapshot_date() -> str:
    return date.today().isoformat()
