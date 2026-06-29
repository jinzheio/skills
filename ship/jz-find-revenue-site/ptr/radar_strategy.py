from __future__ import annotations

import csv
import re
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .filters import classify_domain_filter, guess_registrable_domain, normalize_domain


DEFAULT_MIN_TRUSTMRR_REVENUE = 3000.0
DEFAULT_MIN_PAID_GROWTH = 0.20
DEFAULT_MIN_REFERRAL_VISITS = 10000.0


@dataclass
class RadarCandidate:
    domain: str
    root_domain: str
    title: str = ""
    description: str = ""
    category: str = ""
    source: str = ""
    trustmrr_revenue_30d: float | None = None
    paid_growth: float | None = None
    paid_referral_visits: float | None = None
    target_domains: set[str] = field(default_factory=set)
    sample_match: bool = False


@dataclass
class RadarResult:
    domain: str
    title: str
    description: str
    category: str
    sources: list[str]
    trustmrr_revenue_30d: float | None
    paid_growth: float | None
    paid_referral_visits: float | None
    target_domains: list[str]
    reasons: list[str]
    score: float


def parse_money(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    multiplier = 1.0
    if text[-1:].lower() == "k":
        multiplier = 1_000.0
        text = text[:-1]
    elif text[-1:].lower() == "m":
        multiplier = 1_000_000.0
        text = text[:-1]
    text = text.replace("$", "").replace(",", "").strip()
    if not text:
        return None
    try:
        return float(text) * multiplier
    except ValueError:
        return None


def parse_ratio(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("%"):
            return float(text[:-1].replace(",", "")) / 100.0
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _first(row: dict[str, str], names: Iterable[str]) -> str:
    lowered = {key.strip().lower(): value for key, value in row.items()}
    for name in names:
        value = lowered.get(name.lower())
        if value:
            return value
    return ""


def _words(value: str) -> set[str]:
    short_terms = {"ai", "ui", "ux", "3d"}
    return {
        word
        for word in re.findall(r"[a-z0-9]+", value.lower())
        if len(word) >= 3 or word in short_terms
    }


def _topic_terms(keyword: str, sample_domains: list[str]) -> set[str]:
    terms = _words(keyword)
    for domain in sample_domains:
        root = guess_registrable_domain(domain)
        labels = root.split(".")
        if labels:
            terms.update(_words(labels[0].replace("-", " ")))
    return terms


def matches_topic(candidate: RadarCandidate, *, keyword: str, sample_domains: list[str]) -> bool:
    sample_roots = {guess_registrable_domain(domain) for domain in sample_domains if domain.strip()}
    if candidate.root_domain in sample_roots:
        return True
    keyword_terms = _words(keyword)
    haystack = " ".join(
        [
            candidate.domain,
            candidate.root_domain,
            candidate.title,
            candidate.description,
            candidate.category,
        ]
    ).lower()
    haystack_terms = _words(haystack)
    if keyword_terms:
        return keyword_terms.issubset(haystack_terms)
    terms = _topic_terms(keyword, sample_domains)
    return not terms or bool(terms.intersection(haystack_terms))


def candidate_from_csv_row(row: dict[str, str], *, source: str) -> RadarCandidate | None:
    domain = normalize_domain(
        _first(row, ["domain", "website", "url", "site", "startup", "source_domain", "root_domain"])
    )
    if not domain:
        return None
    root_domain = guess_registrable_domain(domain)
    candidate = RadarCandidate(
        domain=domain,
        root_domain=root_domain,
        title=_first(row, ["title", "name", "startup_name", "product"]),
        description=_first(row, ["description", "value_proposition", "problem_solved", "summary"]),
        category=_first(row, ["category", "tags", "categories"]),
        source=source,
        trustmrr_revenue_30d=parse_money(
            _first(row, ["revenue_30d", "revenue (30d)", "last_30_days_revenue", "trustmrr_revenue_30d"])
        ),
        paid_growth=parse_ratio(_first(row, ["paid_growth", "growth", "change", "monthly_change"])),
        paid_referral_visits=parse_money(
            _first(row, ["paid_referral_visits", "referral_visits", "estimated_visits", "visits"])
        ),
    )
    target = _first(row, ["target_domain", "target", "payment_target"])
    if target:
        candidate.target_domains.add(target)
    return candidate


def load_candidates_csv(path: str | Path, *, source: str | None = None) -> list[RadarCandidate]:
    csv_path = Path(path)
    label = source or csv_path.stem
    with csv_path.open(encoding="utf-8", newline="") as f:
        return [
            candidate
            for row in csv.DictReader(f)
            if (candidate := candidate_from_csv_row(row, source=label)) is not None
        ]


def referral_candidates_from_db(conn: sqlite3.Connection) -> list[RadarCandidate]:
    rows = conn.execute(
        """
        select
          rr.source_domain,
          coalesce(d.root_domain, rr.source_domain) as root_domain,
          coalesce(d.title, '') as title,
          coalesce(d.description, '') as description,
          coalesce(d.h1, '') as h1,
          coalesce(max(rr.category), '') as category,
          max(rr.estimated_visits) as paid_referral_visits,
          max(rr.change) as paid_growth,
          group_concat(distinct rr.target_domain) as target_domains
        from referral_records rr
        left join domains d on d.domain = rr.source_domain
        where rr.is_filtered = 0
        group by rr.source_domain
        """
    ).fetchall()
    candidates: list[RadarCandidate] = []
    for row in rows:
        domain = normalize_domain(row["source_domain"])
        if not domain:
            continue
        root_domain = guess_registrable_domain(row["root_domain"] or domain)
        target_domains = {
            target.strip()
            for target in str(row["target_domains"] or "").split(",")
            if target.strip()
        }
        candidates.append(
            RadarCandidate(
                domain=domain,
                root_domain=root_domain,
                title=row["title"] or "",
                description=" ".join(part for part in [row["description"], row["h1"]] if part),
                category=row["category"] or "",
                source="referral_db",
                paid_growth=row["paid_growth"],
                paid_referral_visits=row["paid_referral_visits"],
                target_domains=target_domains,
            )
        )
    return candidates


def merge_candidates(candidates: Iterable[RadarCandidate]) -> list[RadarCandidate]:
    merged: dict[str, RadarCandidate] = {}
    for candidate in candidates:
        root = guess_registrable_domain(candidate.root_domain or candidate.domain)
        existing = merged.get(root)
        if existing is None:
            candidate.root_domain = root
            merged[root] = candidate
            continue
        existing.title = existing.title or candidate.title
        existing.description = existing.description or candidate.description
        existing.category = existing.category or candidate.category
        existing.source = ", ".join(dict.fromkeys([*existing.source.split(", "), candidate.source]))
        existing.sample_match = existing.sample_match or candidate.sample_match
        existing.target_domains.update(candidate.target_domains)
        existing.trustmrr_revenue_30d = _max_optional(existing.trustmrr_revenue_30d, candidate.trustmrr_revenue_30d)
        existing.paid_growth = _max_optional(existing.paid_growth, candidate.paid_growth)
        existing.paid_referral_visits = _max_optional(existing.paid_referral_visits, candidate.paid_referral_visits)
    return list(merged.values())


def _max_optional(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)


def select_radar_candidates(
    candidates: Iterable[RadarCandidate],
    *,
    keyword: str,
    sample_domains: list[str] | None = None,
    min_trustmrr_revenue: float = DEFAULT_MIN_TRUSTMRR_REVENUE,
    min_paid_growth: float = DEFAULT_MIN_PAID_GROWTH,
    min_referral_visits: float = DEFAULT_MIN_REFERRAL_VISITS,
    limit: int = 100,
) -> list[RadarResult]:
    sample_domains = sample_domains or []
    results: list[RadarResult] = []
    for candidate in merge_candidates(candidates):
        filter_reason = classify_domain_filter(candidate.root_domain)
        if filter_reason:
            continue
        if not matches_topic(candidate, keyword=keyword, sample_domains=sample_domains):
            continue
        reasons: list[str] = []
        if candidate.trustmrr_revenue_30d is not None and candidate.trustmrr_revenue_30d >= min_trustmrr_revenue:
            reasons.append(f"trustmrr_revenue_30d>={min_trustmrr_revenue:g}")
        if candidate.paid_growth is not None and candidate.paid_growth >= min_paid_growth:
            reasons.append(f"paid_growth>={min_paid_growth:g}")
        if candidate.paid_referral_visits is not None and candidate.paid_referral_visits >= min_referral_visits:
            reasons.append(f"paid_referral_visits>={min_referral_visits:g}")
        if not reasons:
            continue
        score = _score_candidate(candidate, min_trustmrr_revenue, min_paid_growth, min_referral_visits)
        results.append(
            RadarResult(
                domain=candidate.root_domain,
                title=candidate.title,
                description=candidate.description,
                category=candidate.category,
                sources=[source for source in candidate.source.split(", ") if source],
                trustmrr_revenue_30d=candidate.trustmrr_revenue_30d,
                paid_growth=candidate.paid_growth,
                paid_referral_visits=candidate.paid_referral_visits,
                target_domains=sorted(candidate.target_domains),
                reasons=reasons,
                score=score,
            )
        )
    return sorted(results, key=lambda row: row.score, reverse=True)[:limit]


def _score_candidate(
    candidate: RadarCandidate,
    min_trustmrr_revenue: float,
    min_paid_growth: float,
    min_referral_visits: float,
) -> float:
    revenue = (candidate.trustmrr_revenue_30d or 0.0) / max(min_trustmrr_revenue, 1.0)
    growth = (candidate.paid_growth or 0.0) / max(min_paid_growth, 0.01)
    visits = (candidate.paid_referral_visits or 0.0) / max(min_referral_visits, 1.0)
    return round(revenue * 4 + growth * 3 + visits * 2, 3)


def write_radar_csv(path: str | Path, rows: list[RadarResult]) -> None:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "domain",
        "score",
        "title",
        "description",
        "category",
        "sources",
        "trustmrr_revenue_30d",
        "paid_growth",
        "paid_referral_visits",
        "target_domains",
        "reasons",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    "domain": row.domain,
                    "score": row.score,
                    "title": row.title,
                    "description": row.description,
                    "category": row.category,
                    "sources": ";".join(row.sources),
                    "trustmrr_revenue_30d": row.trustmrr_revenue_30d,
                    "paid_growth": row.paid_growth,
                    "paid_referral_visits": row.paid_referral_visits,
                    "target_domains": ";".join(row.target_domains),
                    "reasons": ";".join(row.reasons),
                }
            )
