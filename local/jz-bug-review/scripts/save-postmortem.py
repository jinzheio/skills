#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import os
import re
import subprocess
from pathlib import Path
from zoneinfo import ZoneInfo


SKILL_NAME = "jz-bug-review"
LEGACY_SKILL_NAME = "jz-record-postmortem"


def parse_simple_yaml(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        value = value.strip().strip('"').strip("'")
        values[key.strip()] = value
    return values


def config_path() -> Path:
    explicit = os.environ.get("JZ_BUG_REVIEW_CONFIG") or os.environ.get("JZ_RECORD_POSTMORTEM_CONFIG")
    if explicit:
        return Path(explicit).expanduser()
    preferred = Path.home() / ".config" / "skills" / SKILL_NAME / "config.yml"
    if preferred.exists():
        return preferred
    return Path.home() / ".config" / "skills" / LEGACY_SKILL_NAME / "config.yml"


def load_config() -> dict[str, str]:
    path = config_path()
    config = parse_simple_yaml(path)
    if not config.get("hkb_root"):
        raise SystemExit(
            f"Missing hkb_root in {path}. Copy config.example.yml to the local config path and set hkb_root."
        )
    config.setdefault("wiki_notes_dir", "Wiki/Notes")
    config.setdefault("gbrain_slug_prefix", "learnings")
    config.setdefault("gbrain_type", "learning")
    return config


def today_text() -> str:
    return dt.datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y-%m-%d")


def validate_slug(slug: str) -> str:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        raise SystemExit("slug must use lowercase letters, digits, and hyphens only.")
    return slug


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_list(name: str, values: list[str]) -> list[str]:
    if not values:
        return [f"{name}: []"]
    lines = [f"{name}:"]
    lines.extend(f"  - {yaml_quote(value)}" for value in values)
    return lines


def hkb_frontmatter(args: argparse.Namespace) -> str:
    lines = [
        "---",
        f"title: {yaml_quote(args.title)}",
        f"date: {args.date}",
        "type: discussion-note",
        *yaml_list("sources", args.source),
        *yaml_list("related", args.related),
        f"status: {args.status}",
        "---",
        "",
    ]
    return "\n".join(lines)


def gbrain_frontmatter(args: argparse.Namespace, page_type: str) -> str:
    lines = [
        "---",
        f"title: {yaml_quote(args.title)}",
        f"date: {args.date}",
        f"type: {page_type}",
        *yaml_list("tags", args.tag),
        "---",
        "",
    ]
    return "\n".join(lines)


def read_body(path_text: str) -> str:
    path = Path(path_text).expanduser()
    if not path.exists():
        raise SystemExit(f"Body file not found: {path}")
    return path.read_text(encoding="utf-8").strip() + "\n"


def write_hkb_note(config: dict[str, str], args: argparse.Namespace, content: str) -> Path:
    hkb_root = Path(config["hkb_root"]).expanduser()
    notes_dir = hkb_root / config["wiki_notes_dir"]
    note_path = notes_dir / f"{args.date}-{args.slug}.md"
    notes_dir.mkdir(parents=True, exist_ok=True)
    if note_path.exists() and not args.force:
        raise SystemExit(f"HKB note already exists: {note_path}. Use --force to overwrite.")
    note_path.write_text(content, encoding="utf-8")
    return note_path


def capture_gbrain(config: dict[str, str], args: argparse.Namespace, content: str) -> str:
    gbrain_slug = f"{config['gbrain_slug_prefix'].rstrip('/')}/{args.slug}"
    command = ["gbrain", "capture", "--slug", gbrain_slug, "--type", config["gbrain_type"], "--stdin", "--quiet"]
    result = subprocess.run(command, input=content, text=True, capture_output=True, check=False)
    if result.returncode != 0:
        raise SystemExit(result.stderr.strip() or result.stdout.strip() or "gbrain capture failed")
    return result.stdout.strip() or gbrain_slug


def main() -> int:
    parser = argparse.ArgumentParser(description="Save a postmortem to HKB Wiki and gbrain.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--slug", required=True, type=validate_slug)
    parser.add_argument("--date", default=today_text())
    parser.add_argument("--hkb-body-file", required=True)
    parser.add_argument("--gbrain-body-file", required=True)
    parser.add_argument("--source", action="append", default=[])
    parser.add_argument("--related", action="append", default=[])
    parser.add_argument("--tag", action="append", default=[])
    parser.add_argument("--status", default="verified", choices=["verified", "tentative"])
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-gbrain", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = load_config()
    hkb_content = hkb_frontmatter(args) + read_body(args.hkb_body_file)
    gbrain_content = gbrain_frontmatter(args, config["gbrain_type"]) + read_body(args.gbrain_body_file)

    hkb_root = Path(config["hkb_root"]).expanduser()
    note_path = hkb_root / config["wiki_notes_dir"] / f"{args.date}-{args.slug}.md"
    gbrain_slug = f"{config['gbrain_slug_prefix'].rstrip('/')}/{args.slug}"

    if args.dry_run:
        print(f"HKB_NOTE={note_path}")
        print(f"GBRAIN_SLUG={gbrain_slug}")
        return 0

    written_note = write_hkb_note(config, args, hkb_content)
    print(f"HKB_NOTE={written_note}")

    if not args.no_gbrain:
        captured_slug = capture_gbrain(config, args, gbrain_content)
        print(f"GBRAIN_SLUG={captured_slug}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
