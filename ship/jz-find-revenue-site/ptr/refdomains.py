from __future__ import annotations

import csv
import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import Any


def _norm(name: str) -> str:
    return "".join(ch.lower() if ch.isalnum() else "_" for ch in name).strip("_")


def _first(row: dict[str, str], names: list[str]) -> str | None:
    normalized = {_norm(k): v for k, v in row.items()}
    for name in names:
        v = normalized.get(_norm(name))
        if v not in (None, ""):
            return v
    return None


def _float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value.replace(",", "").replace("%", ""))
    except ValueError:
        return None


def _int(value: str | None) -> int | None:
    f = _float(value)
    return int(f) if f is not None else None


def normalize_refdomain_row(row: dict[str, str]) -> dict[str, Any]:
    authority = _float(_first(row, ["Domain Authority", "Authority", "DA"]))
    dts = _float(_first(row, ["DTS", "Domain Trust Score", "Trust Score"]))
    if authority is None and dts is not None:
        authority = dts
    return {
        "referring_domain": _first(row, ["Referring Domain", "Domain", "Source Domain", "Source"]),
        "domain_authority": authority,
        "domain_trust_score": dts,
        "traffic": _float(_first(row, ["Traffic", "Visits", "Monthly Traffic"])),
        "backlinks": _int(_first(row, ["Backlinks", "Links", "URLs", "Pages"])),
        "first_seen": _first(row, ["First Seen", "First seen", "FirstSeen"]),
        "last_seen": _first(row, ["Last Seen", "Last seen", "LastSeen"]),
        "raw": row,
    }


def import_referring_domains(conn: sqlite3.Connection, *, target_domain: str, path: str | Path, source: str = "similarweb_backlinks") -> int:
    path = Path(path)
    conn.execute(
        "insert into referring_domain_snapshots(target_domain, source, import_path) values (?, ?, ?)",
        (target_domain, source, str(path)),
    )
    snapshot_id = int(conn.execute("select last_insert_rowid()").fetchone()[0])
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw_row in reader:
            row = normalize_refdomain_row(raw_row)
            domain = row["referring_domain"]
            if not domain:
                continue
            conn.execute(
                """
                insert into referring_domain_records(
                  snapshot_id, target_domain, referring_domain, domain_authority,
                  domain_trust_score, traffic, backlinks, first_seen, last_seen, raw_json
                ) values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(snapshot_id, referring_domain) do update set
                  domain_authority=excluded.domain_authority,
                  domain_trust_score=excluded.domain_trust_score,
                  traffic=excluded.traffic,
                  backlinks=excluded.backlinks,
                  first_seen=excluded.first_seen,
                  last_seen=excluded.last_seen,
                  raw_json=excluded.raw_json
                """,
                (
                    snapshot_id,
                    target_domain,
                    domain,
                    row["domain_authority"],
                    row["domain_trust_score"],
                    row["traffic"],
                    row["backlinks"],
                    row["first_seen"],
                    row["last_seen"],
                    json.dumps(row["raw"], ensure_ascii=False),
                ),
            )
            conn.execute(
                """
                insert into domains(domain, first_seen_at, last_seen_at, first_seen_target)
                values (?, ?, ?, ?)
                on conflict(domain) do update set
                  first_seen_at=coalesce(domains.first_seen_at, excluded.first_seen_at),
                  last_seen_at=excluded.last_seen_at,
                  first_seen_target=coalesce(domains.first_seen_target, excluded.first_seen_target),
                  updated_at=current_timestamp
                """,
                (domain, row["first_seen"], row["last_seen"], target_domain),
            )
    conn.commit()
    return snapshot_id


def recent_low_authority_candidates(
    conn: sqlite3.Connection,
    *,
    reference_date: str,
    last_seen_days: int = 180,
    max_authority: float = 40,
    limit: int = 200,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        select
          r.target_domain,
          r.referring_domain,
          coalesce(r.domain_authority, r.domain_trust_score) as authority,
          r.traffic,
          r.backlinks,
          r.first_seen,
          r.last_seen
        from referring_domain_records r
        where r.last_seen is not null
          and date(r.last_seen) >= date(?, '-' || ? || ' days')
          and coalesce(r.domain_authority, r.domain_trust_score, 9999) <= ?
        order by
          coalesce(r.traffic, 0) desc,
          date(r.last_seen) desc,
          coalesce(r.domain_authority, r.domain_trust_score, 9999) asc
        limit ?
        """,
        (reference_date, last_seen_days, max_authority, limit),
    ).fetchall()
