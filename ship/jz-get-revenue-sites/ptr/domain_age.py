from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
import urllib.request
import json
import re
import subprocess


@dataclass(frozen=True)
class DomainAgeInfo:
    domain: str
    registration_date: date | None
    first_archive_date: date | None
    source: str


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        try:
            return date.fromisoformat(value[:10])
        except ValueError:
            return None


def parse_rdap_events(domain: str, payload: dict[str, Any]) -> DomainAgeInfo:
    registration_date = None
    for event in payload.get("events") or []:
        action = str(event.get("eventAction") or "").lower()
        if action in {"registration", "registered", "domain registration"}:
            registration_date = _parse_date(event.get("eventDate"))
            break
    return DomainAgeInfo(domain=domain, registration_date=registration_date, first_archive_date=None, source="rdap")


def fetch_rdap_domain_age(domain: str, *, timeout: int = 20) -> DomainAgeInfo:
    url = f"https://rdap.org/domain/{domain}"
    req = urllib.request.Request(url, headers={"Accept": "application/rdap+json, application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    return parse_rdap_events(domain, payload)


def parse_whois_text(domain: str, text: str) -> DomainAgeInfo:
    patterns = [
        r"^\s*Creation Date:\s*(.+)$",
        r"^\s*Created On:\s*(.+)$",
        r"^\s*Created:\s*(.+)$",
        r"^\s*Domain Registration Date:\s*(.+)$",
        r"^\s*Registered on:\s*(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE | re.MULTILINE)
        if match:
            return DomainAgeInfo(domain=domain, registration_date=_parse_date(match.group(1).strip()), first_archive_date=None, source="whois")
    return DomainAgeInfo(domain=domain, registration_date=None, first_archive_date=None, source="whois")


def fetch_whois_domain_age(domain: str, *, timeout: int = 20) -> DomainAgeInfo:
    proc = subprocess.run(["whois", domain], capture_output=True, text=True, timeout=timeout, check=False)
    return parse_whois_text(domain, proc.stdout)


def fetch_domain_age(domain: str, *, timeout: int = 20) -> DomainAgeInfo:
    try:
        info = fetch_rdap_domain_age(domain, timeout=timeout)
        if info.registration_date:
            return info
    except Exception:
        pass
    return fetch_whois_domain_age(domain, timeout=timeout)


def candidate_age_score(info: DomainAgeInfo, *, reference_date: date) -> float:
    observed = info.registration_date or info.first_archive_date
    if observed is None:
        return 0.0
    age_days = max((reference_date - observed).days, 0)
    if age_days <= 180:
        return 10.0
    if age_days <= 365:
        return 8.0
    if age_days <= 730:
        return 5.0
    if age_days <= 1460:
        return 2.0
    return 0.0
