from __future__ import annotations

import sqlite3
import tomllib
from pathlib import Path
from typing import Iterable

DEFAULT_TARGETS_CONFIG = Path(__file__).resolve().parent.parent / "config" / "payment_targets.toml"

SCHEMA = """
pragma foreign_keys = on;

create table if not exists payment_targets (
  id integer primary key,
  domain text not null unique,
  platform text not null,
  target_type text not null,
  priority integer not null default 50,
  enabled integer not null default 1,
  notes text,
  created_at text not null default current_timestamp
);

create table if not exists referral_snapshots (
  id integer primary key,
  target_domain text not null,
  source text not null,
  date_from text not null,
  date_to text not null,
  country integer not null default 999,
  web_source text not null default 'Desktop',
  total_visits real,
  total_count integer,
  raw_json_path text,
  created_at text not null default current_timestamp,
  unique(target_domain, source, date_from, date_to, country, web_source)
);

create table if not exists referral_records (
  id integer primary key,
  snapshot_id integer not null references referral_snapshots(id) on delete cascade,
  target_domain text not null,
  source_domain text not null,
  category text,
  estimated_visits real,
  share real,
  change real,
  rank integer,
  is_filtered integer not null default 0,
  filter_reason text,
  raw_json text,
  created_at text not null default current_timestamp,
  unique(snapshot_id, source_domain)
);

create table if not exists domains (
  domain text primary key,
  root_domain text,
  first_seen_at text,
  last_seen_at text,
  first_seen_target text,
  title text,
  description text,
  h1 text,
  pricing_url text,
  signup_url text,
  docs_url text,
  github_url text,
  category_guess text,
  registration_date text,
  first_archive_date text,
  domain_age_source text,
  age_score real,
  is_big_company integer not null default 0,
  is_noise integer not null default 0,
  notes text,
  updated_at text not null default current_timestamp
);

create table if not exists referring_domain_snapshots (
  id integer primary key,
  target_domain text not null,
  source text not null,
  exported_at text,
  import_path text,
  created_at text not null default current_timestamp
);

create table if not exists referring_domain_records (
  id integer primary key,
  snapshot_id integer not null references referring_domain_snapshots(id) on delete cascade,
  target_domain text not null,
  referring_domain text not null,
  domain_authority real,
  domain_trust_score real,
  traffic real,
  backlinks integer,
  first_seen text,
  last_seen text,
  raw_json text,
  created_at text not null default current_timestamp,
  unique(snapshot_id, referring_domain)
);

create table if not exists domain_scores (
  id integer primary key,
  domain text not null,
  snapshot_month text not null,
  payment_signal_score real not null default 0,
  novelty_score real not null default 0,
  growth_score real not null default 0,
  commercial_score real not null default 0,
  opportunity_score real not null default 0,
  reasons_json text,
  created_at text not null default current_timestamp,
  unique(domain, snapshot_month)
);

create table if not exists trustmrr_snapshots (
  id integer primary key,
  snapshot_date text not null unique,
  fetched_at text not null,
  api_path text not null,
  total integer,
  pages integer,
  page_limit integer,
  raw_dir text,
  status text not null default 'complete',
  created_at text not null default current_timestamp
);

create table if not exists trustmrr_startups (
  slug text primary key,
  name text,
  website text,
  root_domain text,
  category text,
  description text,
  payment_provider text,
  founded_date text,
  country text,
  target_audience text,
  first_listed_for_sale_at text,
  url text,
  first_seen_snapshot_id integer references trustmrr_snapshots(id),
  last_seen_snapshot_id integer references trustmrr_snapshots(id),
  updated_at text not null default current_timestamp
);

create table if not exists trustmrr_metrics (
  id integer primary key,
  snapshot_id integer not null references trustmrr_snapshots(id) on delete cascade,
  slug text not null references trustmrr_startups(slug) on delete cascade,
  revenue_30d real,
  mrr real,
  total_revenue real,
  growth_30d real,
  growth_mrr_30d real,
  customers integer,
  active_subscriptions integer,
  visitors_30d integer,
  google_search_impressions_30d integer,
  revenue_per_visitor real,
  asking_price real,
  profit_margin_30d real,
  multiple real,
  rank integer,
  on_sale integer,
  raw_json text,
  created_at text not null default current_timestamp,
  unique(snapshot_id, slug)
);

create index if not exists idx_referral_records_source_domain on referral_records(source_domain);
create index if not exists idx_referral_records_target on referral_records(target_domain);
create index if not exists idx_referring_records_last_seen on referring_domain_records(last_seen);
create index if not exists idx_referring_records_authority on referring_domain_records(domain_authority, domain_trust_score);
create index if not exists idx_trustmrr_startups_root_domain on trustmrr_startups(root_domain);
create index if not exists idx_trustmrr_metrics_snapshot on trustmrr_metrics(snapshot_id);
create index if not exists idx_trustmrr_metrics_revenue on trustmrr_metrics(revenue_30d);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"pragma table_info({table})").fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            conn.execute(f"alter table {table} add column {name} {definition}")


def init_db(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _ensure_columns(
        conn,
        "domains",
        {
            "registration_date": "text",
            "first_archive_date": "text",
            "domain_age_source": "text",
            "age_score": "real",
        },
    )
    conn.commit()


def load_payment_targets(path: str | Path = DEFAULT_TARGETS_CONFIG) -> list[tuple[str, str, str, int, int, str]]:
    config_path = Path(path)
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
    targets = []
    configured_targets = payload.get("targets", {})
    next_priority = 1000
    if isinstance(configured_targets, list):
        for item in configured_targets:
            targets.append(_payment_target_row(item, target_type=str(item["target_type"]), priority=next_priority))
            next_priority -= 1
        return targets
    for target_type, group in configured_targets.items():
        group_enabled = bool(group.get("enabled", True))
        for item in group.get("items", []):
            targets.append(
                _payment_target_row(
                    item,
                    target_type=target_type,
                    priority=next_priority,
                    enabled=group_enabled,
                )
            )
            next_priority -= 1
    return targets


def _payment_target_row(
    item: str | dict,
    *,
    target_type: str,
    priority: int,
    enabled: bool = True,
) -> tuple[str, str, str, int, int, str]:
    item = {"domain": item} if isinstance(item, str) else item
    domain = str(item["domain"])
    return (
        domain,
        str(item.get("platform") or _infer_platform(domain)),
        target_type,
        int(item.get("priority", priority)),
        1 if bool(item.get("enabled", enabled)) else 0,
        str(item.get("notes", "")),
    )


def _infer_platform(domain: str) -> str:
    labels = domain.split(".")
    if len(labels) > 2 and labels[0] in {"billing", "buy", "checkout"}:
        return labels[1]
    return labels[0]


def seed_payment_targets(conn: sqlite3.Connection, targets: Iterable[tuple] | None = None) -> None:
    targets = list(targets) if targets is not None else load_payment_targets()
    conn.executemany(
        """
        insert into payment_targets(domain, platform, target_type, priority, enabled, notes)
        values (?, ?, ?, ?, ?, ?)
        on conflict(domain) do update set
          platform=excluded.platform,
          target_type=excluded.target_type,
          priority=excluded.priority,
          enabled=excluded.enabled,
          notes=excluded.notes
        """,
        targets,
    )
    conn.commit()
