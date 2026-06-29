from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from datetime import UTC, date, datetime, timedelta
from math import ceil
from typing import Any

import requests

from .db import DEFAULT_TARGETS_CONFIG, connect, init_db, load_payment_targets, seed_payment_targets
from .domain_age import candidate_age_score, fetch_domain_age
from .filters import guess_registrable_domain
from .refdomains import import_referring_domains, recent_low_authority_candidates
from .radar_strategy import (
    DEFAULT_MIN_PAID_GROWTH,
    DEFAULT_MIN_REFERRAL_VISITS,
    DEFAULT_MIN_TRUSTMRR_REVENUE,
    load_candidates_csv,
    referral_candidates_from_db,
    select_radar_candidates,
    write_radar_csv,
)
from .similarweb import fetch_referrals, merge_referral_pages, parse_referral_response, store_referral_snapshot
from .trustmrr import (
    DEFAULT_LIMIT as TRUSTMRR_DEFAULT_LIMIT,
    DEFAULT_SLEEP_SECONDS as TRUSTMRR_DEFAULT_SLEEP_SECONDS,
    default_snapshot_date,
    export_trustmrr_csv,
    fetch_all_startups,
    store_trustmrr_snapshot,
    trustmrr_api_key,
)

DEFAULT_DB = "data/paid_traction_radar.sqlite3"


def month_bounds(month: str) -> tuple[str, str, str, str]:
    year, mon = map(int, month.split("-"))
    start = datetime(year, mon, 1)
    if mon == 12:
        end = datetime(year + 1, 1, 1)
    else:
        end = datetime(year, mon + 1, 1)
    # inclusive last day for APIs/reports
    last_day = (end - __import__("datetime").timedelta(days=1)).day
    return (
        f"{year:04d}-{mon:02d}-01",
        f"{year:04d}-{mon:02d}-{last_day:02d}",
        f"{year:04d}|{mon:02d}|01",
        f"{year:04d}|{mon:02d}|{last_day:02d}",
    )


def last_complete_month(reference_date: date | None = None) -> str:
    reference_date = reference_date or date.today()
    first_day = reference_date.replace(day=1)
    last_day_previous_month = first_day - timedelta(days=1)
    return f"{last_day_previous_month.year:04d}-{last_day_previous_month.month:02d}"


def _safe_name(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ".-_" else "_" for ch in value)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _page_signature(payload: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get("Domain") or "") for row in (payload.get("Records") or [])[:10])


def dash_login(username: str | None, password: str | None) -> requests.Session:
    session = requests.Session()
    if username and password:
        session.get(
            "https://dash.3ue.co/api/account/login",
            params={"username": username, "password": password, "ts": str(int(datetime.now().timestamp() * 1000))},
            timeout=30,
        )
    return session


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        text = value.strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def _domains_missing_registration_date(conn, limit: int) -> list[str]:
    return [
        row[0]
        for row in conn.execute(
            "select domain from domains where registration_date is null order by updated_at desc limit ?",
            (limit,),
        ).fetchall()
    ]


def _copy_existing_domain_age(conn, *, domain: str, root_domain: str) -> bool:
    existing = conn.execute(
        """
        select registration_date, first_archive_date, domain_age_source, age_score
        from domains
        where registration_date is not null
          and (domain=? or root_domain=?)
        order by case when domain=? then 0 else 1 end, updated_at desc
        limit 1
        """,
        (root_domain, root_domain, root_domain),
    ).fetchone()
    if not existing:
        return False
    conn.execute(
        """
        insert into domains(domain, root_domain, registration_date, first_archive_date, domain_age_source, age_score)
        values (?, ?, ?, ?, ?, ?)
        on conflict(domain) do update set
          root_domain=coalesce(domains.root_domain, excluded.root_domain),
          registration_date=coalesce(domains.registration_date, excluded.registration_date),
          first_archive_date=coalesce(domains.first_archive_date, excluded.first_archive_date),
          domain_age_source=coalesce(domains.domain_age_source, excluded.domain_age_source),
          age_score=coalesce(domains.age_score, excluded.age_score),
          updated_at=current_timestamp
        """,
        (
            domain,
            root_domain,
            existing["registration_date"],
            existing["first_archive_date"],
            existing["domain_age_source"],
            existing["age_score"],
        ),
    )
    return True


def enrich_domain_ages(
    conn,
    domains: list[str],
    *,
    limit: int,
    timeout: int,
    reference_date: date,
    skip_existing: bool = True,
) -> tuple[int, int, int]:
    checked = 0
    skipped = 0
    failed = 0
    domains_to_check = _unique(domains)[:limit]
    total = len(domains_to_check)
    for index, domain in enumerate(domains_to_check, start=1):
        lookup_domain = guess_registrable_domain(domain)
        if skip_existing:
            existing = conn.execute(
                "select registration_date from domains where domain=?",
                (domain,),
            ).fetchone()
            if existing and existing["registration_date"]:
                print(
                    f"domain-age: {index}/{total} domain={domain} lookup_domain={lookup_domain} "
                    "status=skipped_existing_domain",
                    flush=True,
                )
                skipped += 1
                continue
            if _copy_existing_domain_age(conn, domain=domain, root_domain=lookup_domain):
                print(
                    f"domain-age: {index}/{total} domain={domain} lookup_domain={lookup_domain} "
                    "status=skipped_existing_root_domain",
                    flush=True,
                )
                skipped += 1
                continue
        try:
            print(
                f"domain-age: {index}/{total} domain={domain} lookup_domain={lookup_domain} status=lookup_start",
                flush=True,
            )
            info = fetch_domain_age(lookup_domain, timeout=timeout)
            score = candidate_age_score(info, reference_date=reference_date)
            conn.execute(
                """
                insert into domains(domain, root_domain, registration_date, first_archive_date, domain_age_source, age_score)
                values (?, ?, ?, ?, ?, ?)
                on conflict(domain) do update set
                  root_domain=coalesce(domains.root_domain, excluded.root_domain),
                  registration_date=coalesce(excluded.registration_date, domains.registration_date),
                  first_archive_date=coalesce(excluded.first_archive_date, domains.first_archive_date),
                  domain_age_source=excluded.domain_age_source,
                  age_score=excluded.age_score,
                  updated_at=current_timestamp
                """,
                (
                    domain,
                    lookup_domain,
                    info.registration_date.isoformat() if info.registration_date else None,
                    info.first_archive_date.isoformat() if info.first_archive_date else None,
                    info.source,
                    score,
                ),
            )
            print(
                f"domain-age: {index}/{total} domain={domain} lookup_domain={lookup_domain} "
                f"registration_date={info.registration_date} age_score={score}",
                flush=True,
            )
            checked += 1
        except Exception as exc:
            print(
                f"domain-age: {index}/{total} domain={domain} lookup_domain={lookup_domain} "
                f"age_lookup_failed={exc}",
                flush=True,
            )
            failed += 1
    conn.commit()
    return checked, skipped, failed


def cmd_init_db(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    print(f"initialized {args.db}")


def cmd_seed_targets(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    seed_payment_targets(conn, load_payment_targets(args.config))
    print("seeded payment targets")


def cmd_fetch_similarweb(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    month = args.month or last_complete_month()
    date_from, date_to, pipe_from, pipe_to = month_bounds(month)
    targets = [t.strip() for t in args.targets.split(",") if t.strip()] if args.targets else [
        row[0] for row in conn.execute("select domain from payment_targets where enabled=1 order by priority desc, domain")
    ]
    raw_dir = Path(args.raw_dir) / "similarweb" / month
    raw_dir.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        mode = "all-pages" if args.all_pages else "single-page"
        for target in targets:
            target_dir = raw_dir / _safe_name(target)
            cached_pages = sorted(target_dir.glob("page-*.json")) if target_dir.exists() else []
            cached = f" cached_pages={len(cached_pages)}" if cached_pages else ""
            enrich = (
                f" enrich_domain_age=on domain_age_limit={args.domain_age_limit} "
                f"domain_age_timeout={args.domain_age_timeout}"
                if args.enrich_domain_age
                else " enrich_domain_age=off"
            )
            print(
                f"dry-run target={target} month={month} date_from={date_from} date_to={date_to} "
                f"country={args.country} web_source={args.web_source} mode={mode} "
                f"page_size={args.page_size} max_pages={args.max_pages}{cached}{enrich}"
            )
        return
    session = dash_login(os.getenv("PTR_DASH_USERNAME"), os.getenv("PTR_DASH_PASSWORD"))
    domains_to_enrich: list[str] = []
    for target in targets:
        if args.all_pages:
            target_dir = raw_dir / _safe_name(target)
            pages: list[dict[str, Any]] = []
            signatures: set[tuple[str, ...]] = set()
            total_count = 0
            for page in range(1, args.max_pages + 1):
                page_path = target_dir / f"page-{page:04d}.json"
                if page_path.exists() and not args.force:
                    payload = _read_json(page_path)
                    source = "cache"
                else:
                    payload = fetch_referrals(
                        session,
                        target_domain=target,
                        date_from_pipe=pipe_from,
                        date_to_pipe=pipe_to,
                        country=args.country,
                        web_source=args.web_source,
                        page=page,
                        page_size=args.page_size,
                        order_by=args.order_by,
                        include_trending_referrals=args.include_trending_referrals,
                    )
                    _write_json(page_path, payload)
                    source = "fetch"
                records = payload.get("Records") or []
                if not records:
                    print(f"{target}: page={page} source={source} records=0 stop=empty_page")
                    break
                signature = _page_signature(payload)
                if page > 1 and signature in signatures:
                    print(f"{target}: page={page} source={source} records={len(records)} stop=repeated_page")
                    break
                signatures.add(signature)
                pages.append(payload)
                total_count = int(payload.get("TotalCount") or total_count or 0)
                fetched_records = sum(len(page_payload.get("Records") or []) for page_payload in pages)
                print(
                    f"{target}: page={page} source={source} records={len(records)} "
                    f"fetched_records={fetched_records} total_count={total_count or 'unknown'}"
                )
                if total_count and fetched_records >= total_count:
                    break
                if len(records) < args.page_size:
                    break
            payload = merge_referral_pages(target, pages)
            raw_path = target_dir / "combined.json"
            _write_json(raw_path, payload)
        else:
            raw_path = raw_dir / f"{_safe_name(target)}.json"
            if raw_path.exists() and not args.force:
                payload = _read_json(raw_path)
            else:
                payload = fetch_referrals(
                    session,
                    target_domain=target,
                    date_from_pipe=pipe_from,
                    date_to_pipe=pipe_to,
                    country=args.country,
                    web_source=args.web_source,
                )
                _write_json(raw_path, payload)
        parsed = parse_referral_response(target, payload)
        store_referral_snapshot(
            conn,
            parsed,
            source="similarweb",
            date_from=date_from,
            date_to=date_to,
            country=args.country,
            web_source=args.web_source,
            raw_json_path=str(raw_path),
        )
        pages_text = f" pages={payload.get('FetchedPages')}" if args.all_pages else ""
        expected_pages = ceil((parsed.total_count or 0) / args.page_size) if args.all_pages and parsed.total_count else 0
        expected_text = f" expected_pages={expected_pages}" if expected_pages else ""
        print(f"{target}: total_visits={parsed.total_visits} total_count={parsed.total_count} records={len(parsed.records)}{pages_text}{expected_text}")
        if args.enrich_domain_age:
            domains_to_enrich.extend(rec.source_domain for rec in parsed.records if not rec.is_filtered)
    if args.enrich_domain_age:
        reference = (
            datetime.fromisoformat(args.domain_age_reference_date).date()
            if args.domain_age_reference_date
            else datetime.now(UTC).date()
        )
        checked, skipped, failed = enrich_domain_ages(
            conn,
            domains_to_enrich,
            limit=args.domain_age_limit,
            timeout=args.domain_age_timeout,
            reference_date=reference,
            skip_existing=not args.force_domain_age,
        )
        print(
            f"domain-age: candidates={len(_unique(domains_to_enrich))} "
            f"checked={checked} skipped={skipped} failed={failed}"
        )


def cmd_import_refdomains(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    snapshot_id = import_referring_domains(conn, target_domain=args.target, path=args.path, source=args.source)
    print(f"imported referring domains snapshot_id={snapshot_id}")


def cmd_candidates(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    rows = recent_low_authority_candidates(
        conn,
        reference_date=args.reference_date,
        last_seen_days=args.last_seen_days,
        max_authority=args.max_authority,
        limit=args.limit,
    )
    out = Path(args.output) if args.output else None
    fields = ["target_domain", "referring_domain", "authority", "traffic", "backlinks", "first_seen", "last_seen"]
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for row in rows:
                writer.writerow({k: row[k] for k in fields})
        print(f"wrote {len(rows)} candidates to {out}")
    else:
        for row in rows:
            print(", ".join(f"{k}={row[k]}" for k in fields))


def cmd_enrich_domain_age(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    domains = [d.strip() for d in args.domains.split(",") if d.strip()]
    if not domains:
        domains = _domains_missing_registration_date(conn, args.limit)
    reference = datetime.fromisoformat(args.reference_date).date() if args.reference_date else datetime.now(UTC).date()
    enrich_domain_ages(conn, domains, limit=args.limit, timeout=args.timeout, reference_date=reference)


def cmd_keyword_radar(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    candidates = referral_candidates_from_db(conn) if not args.no_referral_db else []
    for path in args.trustmrr_csv:
        candidates.extend(load_candidates_csv(path, source="trustmrr"))
    for path in args.discovery_csv:
        candidates.extend(load_candidates_csv(path))
    sample_domains = [domain.strip() for domain in args.samples.split(",") if domain.strip()]
    rows = select_radar_candidates(
        candidates,
        keyword=args.keyword,
        sample_domains=sample_domains,
        min_trustmrr_revenue=args.min_trustmrr_revenue,
        min_paid_growth=args.min_paid_growth,
        min_referral_visits=args.min_referral_visits,
        limit=args.limit,
    )
    if args.output:
        write_radar_csv(args.output, rows)
        print(f"wrote {len(rows)} radar candidates to {args.output}")
        return
    for row in rows:
        metrics = [
            f"domain={row.domain}",
            f"score={row.score}",
            f"trustmrr_revenue_30d={row.trustmrr_revenue_30d}",
            f"paid_growth={row.paid_growth}",
            f"paid_referral_visits={row.paid_referral_visits}",
            f"sources={';'.join(row.sources)}",
            f"reasons={';'.join(row.reasons)}",
        ]
        if row.title:
            metrics.append(f"title={row.title}")
        print(", ".join(metrics))


def cmd_fetch_trustmrr(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    snapshot_date = args.snapshot_date or default_snapshot_date()
    raw_dir = Path(args.raw_dir) / "trustmrr" / "api" / snapshot_date
    startups, manifest = fetch_all_startups(
        api_key=trustmrr_api_key(),
        raw_dir=raw_dir,
        limit=args.limit,
        sleep_seconds=args.sleep_seconds,
        force=args.force,
    )
    snapshot_id = store_trustmrr_snapshot(
        conn,
        snapshot_date=snapshot_date,
        raw_dir=raw_dir,
        startups=startups,
        manifest=manifest,
    )
    print(
        f"trustmrr: snapshot_id={snapshot_id} snapshot_date={snapshot_date} "
        f"startups={len(startups)} raw_dir={raw_dir}"
    )
    if args.export:
        count = export_trustmrr_csv(conn, args.export, snapshot_id=snapshot_id)
        print(f"trustmrr: exported {count} rows to {args.export}")


def cmd_export_trustmrr(args: argparse.Namespace) -> None:
    conn = connect(args.db)
    init_db(conn)
    count = export_trustmrr_csv(conn, args.output)
    print(f"trustmrr: exported {count} rows to {args.output}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ptr")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init-db")
    p.add_argument("--db", default=DEFAULT_DB)
    p.set_defaults(func=cmd_init_db)

    p = sub.add_parser("seed-targets")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--config", default=DEFAULT_TARGETS_CONFIG)
    p.set_defaults(func=cmd_seed_targets)

    p = sub.add_parser("fetch-similarweb")
    p.add_argument("--db", default=DEFAULT_DB)
    period = p.add_mutually_exclusive_group(required=False)
    period.add_argument("--month")
    period.add_argument("--period", choices=["1m"], help="Use the latest complete month, matching Similarweb's Last 1 Month view.")
    p.add_argument("--targets", default="")
    p.add_argument("--country", type=int, default=999)
    p.add_argument("--web-source", default="Desktop")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--all-pages", action="store_true")
    p.add_argument("--page-size", type=int, default=100)
    p.add_argument("--max-pages", type=int, default=50)
    p.add_argument("--order-by", default="Change desc")
    p.add_argument("--include-trending-referrals", action="store_true")
    p.add_argument("--enrich-domain-age", action="store_true", help="After fetching, enrich unfiltered referral domains with RDAP/whois age data.")
    p.add_argument("--domain-age-limit", type=int, default=300)
    p.add_argument("--domain-age-timeout", type=int, default=20)
    p.add_argument("--domain-age-reference-date", default="")
    p.add_argument("--force-domain-age", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_fetch_similarweb)

    p = sub.add_parser("import-refdomains")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--target", required=True)
    p.add_argument("--path", required=True)
    p.add_argument("--source", default="similarweb_backlinks")
    p.set_defaults(func=cmd_import_refdomains)

    p = sub.add_parser("candidates")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--reference-date", required=True)
    p.add_argument("--last-seen-days", type=int, default=180)
    p.add_argument("--max-authority", type=float, default=40)
    p.add_argument("--limit", type=int, default=200)
    p.add_argument("--output")
    p.set_defaults(func=cmd_candidates)
    p = sub.add_parser("enrich-domain-age")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--domains", default="", help="Comma-separated domains; defaults to domains missing registration_date")
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--timeout", type=int, default=20)
    p.add_argument("--reference-date", default="")
    p.set_defaults(func=cmd_enrich_domain_age)

    p = sub.add_parser("keyword-radar")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--keyword", required=True)
    p.add_argument("--samples", default="", help="Comma-separated sample domains used as seed context")
    p.add_argument("--trustmrr-csv", action="append", default=[], help="CSV export or manually collected TrustMRR rows")
    p.add_argument("--discovery-csv", action="append", default=[], help="CSV rows from search, directories, or other discovery sources")
    p.add_argument("--min-trustmrr-revenue", type=float, default=DEFAULT_MIN_TRUSTMRR_REVENUE)
    p.add_argument("--min-paid-growth", type=float, default=DEFAULT_MIN_PAID_GROWTH)
    p.add_argument("--min-referral-visits", type=float, default=DEFAULT_MIN_REFERRAL_VISITS)
    p.add_argument("--limit", type=int, default=100)
    p.add_argument("--output")
    p.add_argument("--no-referral-db", action="store_true", help="Only use CSV inputs")
    p.set_defaults(func=cmd_keyword_radar)

    p = sub.add_parser("fetch-trustmrr")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--snapshot-date", default="")
    p.add_argument("--raw-dir", default="data/raw")
    p.add_argument("--limit", type=int, default=TRUSTMRR_DEFAULT_LIMIT)
    p.add_argument("--sleep-seconds", type=float, default=TRUSTMRR_DEFAULT_SLEEP_SECONDS)
    p.add_argument("--force", action="store_true")
    p.add_argument("--export", default="data/input/trustmrr-latest.csv")
    p.set_defaults(func=cmd_fetch_trustmrr)

    p = sub.add_parser("export-trustmrr")
    p.add_argument("--db", default=DEFAULT_DB)
    p.add_argument("--output", default="data/input/trustmrr-latest.csv")
    p.set_defaults(func=cmd_export_trustmrr)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
