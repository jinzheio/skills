#!/usr/bin/env python3
"""Infer a Codex usage reset time from limit text or recent local files."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo


LIMIT_AT_RE = re.compile(
    r"(?:you[’']ve hit your usage limit|usage limit|session limit).*?"
    r"(?:try again|resets?|reset|available again)\s+(?:at|on)\s+([^\r\n.。]+)",
    re.IGNORECASE | re.DOTALL,
)
LIMIT_IN_RE = re.compile(
    r"(?:you[’']ve hit your usage limit|usage limit|session limit).*?"
    r"(?:try again|resets?|reset|available again)\s+in\s+([^\r\n.。]+)",
    re.IGNORECASE | re.DOTALL,
)
CN_AT_RE = re.compile(
    r"(?:重置时间|恢复时间|reset\s*time)\s*[:：]?\s*([^\r\n.。]+)|"
    r"(\d{1,2}(?::\d{2})?\s*(?:[ap]\.?m\.?)?)\s*(?:分)?\s*(?:重置|恢复|reset)",
    re.IGNORECASE,
)
TIME_ONLY_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*([ap]\.?m\.?)?\b", re.IGNORECASE)
DURATION_RE = re.compile(
    r"(\d+)\s*"
    r"(weeks?|w|days?|d|hours?|hrs?|hr|h|minutes?|mins?|min|m|seconds?|secs?|sec|s)",
    re.IGNORECASE,
)


def local_tz() -> dt.tzinfo:
    tz_name = os.environ.get("TZ")
    if tz_name:
        try:
            return ZoneInfo(tz_name)
        except Exception:
            pass
    return dt.datetime.now().astimezone().tzinfo or dt.timezone.utc


def parse_duration(text: str) -> dt.timedelta:
    total = dt.timedelta()
    found = False
    for number, unit in DURATION_RE.findall(text):
        found = True
        value = int(number)
        unit = unit.lower()
        if unit in {"w", "week", "weeks"}:
            total += dt.timedelta(weeks=value)
        elif unit in {"d", "day", "days"}:
            total += dt.timedelta(days=value)
        elif unit in {"h", "hr", "hrs", "hour", "hours"}:
            total += dt.timedelta(hours=value)
        elif unit in {"m", "min", "mins", "minute", "minutes"}:
            total += dt.timedelta(minutes=value)
        elif unit in {"s", "sec", "secs", "second", "seconds"}:
            total += dt.timedelta(seconds=value)
    if not found:
        raise ValueError(f"could not parse duration: {text!r}")
    return total


def parse_absolute(raw: str, now: dt.datetime) -> dt.datetime:
    cleaned = re.sub(r"\s+", " ", raw.strip().rstrip(" .)"))
    formats = [
        "%I:%M %p",
        "%I %p",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %I:%M %p",
        "%b %d, %Y %I:%M %p",
        "%B %d, %Y %I:%M %p",
    ]
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(cleaned, fmt)
        except ValueError:
            continue
        if "%Y" not in fmt:
            parsed = parsed.replace(year=now.year)
        if "%m" not in fmt and "%b" not in fmt and "%B" not in fmt:
            parsed = parsed.replace(month=now.month, day=now.day)
        parsed = parsed.replace(tzinfo=now.tzinfo)
        if fmt in {"%I:%M %p", "%I %p"} and parsed <= now:
            parsed += dt.timedelta(days=1)
        return parsed

    match = TIME_ONLY_RE.search(cleaned)
    if not match:
        raise ValueError(f"could not parse absolute time: {raw!r}")

    hour = int(match.group(1))
    minute = int(match.group(2) or "0")
    ampm = (match.group(3) or "").lower().replace(".", "")
    if ampm == "pm" and hour != 12:
        hour += 12
    elif ampm == "am" and hour == 12:
        hour = 0
    if not 0 <= hour <= 23 or not 0 <= minute <= 59:
        raise ValueError(f"invalid time: {raw!r}")

    parsed = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if parsed <= now:
        parsed += dt.timedelta(days=1)
    return parsed


def infer_from_text(text: str, now: dt.datetime) -> dict | None:
    candidates = []
    for match in LIMIT_AT_RE.finditer(text):
        try:
            reset_at = parse_absolute(match.group(1), now)
        except ValueError:
            continue
        candidates.append(("absolute", match.group(1).strip(), reset_at, match.start()))
    for match in LIMIT_IN_RE.finditer(text):
        try:
            reset_at = now + parse_duration(match.group(1))
        except ValueError:
            continue
        candidates.append(("relative", match.group(1).strip(), reset_at, match.start()))
    for match in CN_AT_RE.finditer(text):
        raw = (match.group(1) or match.group(2) or "").strip()
        try:
            reset_at = parse_absolute(raw, now)
        except ValueError:
            continue
        candidates.append(("absolute", raw, reset_at, match.start()))
    if not candidates:
        return None
    kind, raw, reset_at, _ = sorted(candidates, key=lambda item: item[3])[-1]
    return {"kind": kind, "raw": raw, "reset_at": reset_at}


def candidate_paths(since: dt.datetime) -> list[Path]:
    home = Path.home()
    roots = [
        home / ".codex",
        home / "Library/Application Support/com.openai.chat",
        home / "Library/Application Support/OpenAI/Codex",
        home / "Library/Application Support/Codex",
    ]
    files: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_mtime < since.timestamp() or stat.st_size > 5_000_000:
                continue
            if path.suffix.lower() not in {"", ".json", ".jsonl", ".log", ".txt", ".toml", ".md"}:
                continue
            files.append(path)
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def scan_files(now: dt.datetime, since_hours: int) -> dict | None:
    since = now - dt.timedelta(hours=since_hours)
    for path in candidate_paths(since):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        inferred = infer_from_text(text, now)
        if inferred:
            inferred["source"] = str(path)
            return inferred
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", help="Limit message text to parse")
    parser.add_argument("--file", action="append", default=[], help="File to parse; may be repeated")
    parser.add_argument("--scan-codex", action="store_true", help="Scan recent local Codex files")
    parser.add_argument("--since-hours", type=int, default=12)
    parser.add_argument("--grace-minutes", type=int, default=2)
    parser.add_argument("--timezone", default=None, help="IANA timezone, defaults to local timezone")
    args = parser.parse_args()

    tz = ZoneInfo(args.timezone) if args.timezone else local_tz()
    now = dt.datetime.now(tz)

    checks: list[tuple[str, str]] = []
    if args.text:
        checks.append(("argument", args.text))
    for file_name in args.file:
        path = Path(file_name)
        checks.append((str(path), path.read_text(encoding="utf-8", errors="ignore")))
    if not checks and not args.scan_codex and not sys.stdin.isatty():
        checks.append(("stdin", sys.stdin.read()))

    result = None
    for source, text in checks:
        result = infer_from_text(text, now)
        if result:
            result["source"] = source
            break
    if result is None and args.scan_codex:
        result = scan_files(now, args.since_hours)

    if result is None:
        print(json.dumps({"found": False}, ensure_ascii=False))
        return 1

    reset_at = result["reset_at"]
    wake_at = reset_at + dt.timedelta(minutes=args.grace_minutes)
    payload = {
        "found": True,
        "raw": result["raw"],
        "kind": result["kind"],
        "source": result.get("source"),
        "reset_at": reset_at.isoformat(),
        "wake_at": wake_at.isoformat(),
        "timezone": str(tz),
        "confidence": "medium" if result.get("source") in {"argument", "stdin"} else "low",
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
