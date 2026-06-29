from __future__ import annotations

from dataclasses import dataclass
import json
import sqlite3
from typing import Any

import requests

from .filters import GENERIC_CHANNELS, classify_domain_filter


@dataclass
class ReferralRecord:
    source_domain: str
    category: str | None
    estimated_visits: float | None
    share: float | None
    change: float | None
    rank: int
    is_filtered: bool
    filter_reason: str | None
    raw: dict[str, Any]


@dataclass
class ReferralSnapshot:
    target_domain: str
    total_visits: float | None
    total_count: int | None
    records: list[ReferralRecord]
    raw: dict[str, Any]


def classify_filter_reason(domain: str) -> str | None:
    if domain in GENERIC_CHANNELS:
        return "generic_channel"
    return classify_domain_filter(domain)


def parse_referral_response(target_domain: str, payload: dict[str, Any]) -> ReferralSnapshot:
    records: list[ReferralRecord] = []
    for idx, row in enumerate(payload.get("Records") or [], start=1):
        domain = row.get("Domain") or ""
        reason = classify_filter_reason(domain)
        records.append(
            ReferralRecord(
                source_domain=domain,
                category=row.get("Category"),
                estimated_visits=row.get("TotalVisits"),
                share=row.get("Share"),
                change=row.get("Change"),
                rank=idx,
                is_filtered=reason is not None,
                filter_reason=reason,
                raw=row,
            )
        )
    return ReferralSnapshot(
        target_domain=target_domain,
        total_visits=payload.get("TotalVisits"),
        total_count=payload.get("TotalCount"),
        records=records,
        raw=payload,
    )


def merge_referral_pages(target_domain: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    seen_domains: set[str] = set()
    for page in pages:
        for row in page.get("Records") or []:
            domain = row.get("Domain") or ""
            if domain in seen_domains:
                continue
            seen_domains.add(domain)
            records.append(row)

    first = pages[0] if pages else {}
    total_count = first.get("TotalCount")
    if not total_count or total_count < len(records):
        total_count = len(records)
    return {
        **first,
        "TargetDomain": target_domain,
        "TotalCount": total_count,
        "Records": records,
        "FetchedPages": len(pages),
        "PageRecordCounts": [len(page.get("Records") or []) for page in pages],
    }


def store_referral_snapshot(
    conn: sqlite3.Connection,
    snapshot: ReferralSnapshot,
    *,
    source: str,
    date_from: str,
    date_to: str,
    country: int,
    web_source: str,
    raw_json_path: str | None = None,
) -> int:
    conn.execute(
        """
        insert into referral_snapshots(
          target_domain, source, date_from, date_to, country, web_source,
          total_visits, total_count, raw_json_path
        ) values (?, ?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(target_domain, source, date_from, date_to, country, web_source)
        do update set
          total_visits=excluded.total_visits,
          total_count=excluded.total_count,
          raw_json_path=excluded.raw_json_path
        """,
        (
            snapshot.target_domain,
            source,
            date_from,
            date_to,
            country,
            web_source,
            snapshot.total_visits,
            snapshot.total_count,
            raw_json_path,
        ),
    )
    snapshot_id = conn.execute(
        """
        select id from referral_snapshots
        where target_domain=? and source=? and date_from=? and date_to=? and country=? and web_source=?
        """,
        (snapshot.target_domain, source, date_from, date_to, country, web_source),
    ).fetchone()["id"]

    for rec in snapshot.records:
        conn.execute(
            """
            insert into referral_records(
              snapshot_id, target_domain, source_domain, category, estimated_visits,
              share, change, rank, is_filtered, filter_reason, raw_json
            ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            on conflict(snapshot_id, source_domain) do update set
              category=excluded.category,
              estimated_visits=excluded.estimated_visits,
              share=excluded.share,
              change=excluded.change,
              rank=excluded.rank,
              is_filtered=excluded.is_filtered,
              filter_reason=excluded.filter_reason,
              raw_json=excluded.raw_json
            """,
            (
                snapshot_id,
                snapshot.target_domain,
                rec.source_domain,
                rec.category,
                rec.estimated_visits,
                rec.share,
                rec.change,
                rec.rank,
                int(rec.is_filtered),
                rec.filter_reason,
                json.dumps(rec.raw, ensure_ascii=False),
            ),
        )
        conn.execute(
            """
            insert into domains(domain, first_seen_at, last_seen_at, first_seen_target, category_guess)
            values (?, current_timestamp, current_timestamp, ?, ?)
            on conflict(domain) do update set
              last_seen_at=current_timestamp,
              category_guess=coalesce(domains.category_guess, excluded.category_guess),
              first_seen_target=coalesce(domains.first_seen_target, excluded.first_seen_target),
              updated_at=current_timestamp
            """,
            (rec.source_domain, snapshot.target_domain, rec.category),
        )
    conn.commit()
    return int(snapshot_id)


def fetch_referrals(
    session: requests.Session,
    *,
    target_domain: str,
    date_from_pipe: str,
    date_to_pipe: str,
    country: int = 999,
    web_source: str = "Desktop",
    page: int | None = None,
    page_size: int | None = None,
    order_by: str | None = None,
    include_trending_referrals: bool | None = None,
    base_url: str = "https://sim.3ue.co",
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "country": country,
        "from": date_from_pipe,
        "to": date_to_pipe,
        "includeSubDomains": True,
        "isWindow": False,
        "key": target_domain,
        "timeGranularity": "Monthly",
        "webSource": web_source,
    }
    if page is not None:
        params["page"] = page
    if page_size is not None:
        params["pageSize"] = page_size
    if order_by:
        params["orderBy"] = order_by
    if include_trending_referrals is not None:
        params["IncludeTrendingReferrals"] = str(include_trending_referrals).lower()
    response = session.get(
        f"{base_url}/api/websiteanalysis/GetTrafficSourcesReferralsTable",
        params=params,
        headers={
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{base_url}/website/{target_domain}/traffic-sources/referrals/",
        },
        timeout=90,
    )
    response.raise_for_status()
    if "json" not in response.headers.get("content-type", ""):
        raise RuntimeError(f"Expected JSON from Similarweb, got {response.headers.get('content-type')}: {response.text[:120]}")
    return response.json()
