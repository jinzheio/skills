from __future__ import annotations

import os
from pathlib import Path
import tomllib
from urllib.parse import urlparse

DEFAULT_FILTER_CONFIG = Path(__file__).resolve().parent.parent / "config" / "filters.toml"
COMMON_TWO_PART_PUBLIC_SUFFIXES = {
    "co.jp",
    "co.nz",
    "co.uk",
    "com.au",
    "com.br",
    "com.cn",
    "com.mx",
    "com.sg",
    "com.tr",
    "net.au",
    "org.uk",
}


def normalize_domain(value: str | None) -> str:
    if not value:
        return ""
    text = value.strip().lower()
    if "://" not in text:
        text = "https://" + text
    parsed = urlparse(text)
    host = parsed.netloc or parsed.path.split("/")[0]
    host = host.split("@")[-1].split(":")[0].strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def guess_registrable_domain(value: str | None) -> str:
    host = normalize_domain(value)
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    suffix = ".".join(labels[-2:])
    if suffix in COMMON_TWO_PART_PUBLIC_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def filter_config_path() -> Path:
    configured = os.getenv("PTR_FILTERS_CONFIG")
    if configured:
        return Path(configured)
    cwd_config = Path.cwd() / "config" / "filters.toml"
    if cwd_config.exists():
        return cwd_config
    return DEFAULT_FILTER_CONFIG


def load_filter_config(path: str | Path | None = None) -> tuple[set[str], set[str]]:
    config_path = Path(path) if path else filter_config_path()
    with config_path.open("rb") as f:
        data = tomllib.load(f)
    mature_domains = {
        normalized
        for value in data.get("mature_company_domains", {}).get("values", [])
        if (normalized := normalize_domain(str(value)))
    }
    generic_channels = {
        str(value).strip()
        for value in data.get("generic_channels", {}).get("values", [])
        if str(value).strip()
    }
    return mature_domains, generic_channels


MATURE_COMPANY_DOMAINS, GENERIC_CHANNELS = load_filter_config()


def classify_domain_filter(domain: str | None) -> str | None:
    host = normalize_domain(domain)
    if not host:
        return "empty_domain"
    if host in MATURE_COMPANY_DOMAINS:
        return "mature_company"
    # Also filter subdomains of mature companies, except keep unknown custom domains untouched.
    if any(host.endswith("." + mature) for mature in MATURE_COMPANY_DOMAINS):
        return "mature_company"
    return None
