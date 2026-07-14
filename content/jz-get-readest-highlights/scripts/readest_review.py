#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SKILL_NAME = "jz-get-readest-highlights"
CONFIG_ENV = "JZ_READEST_REVIEW_ENV"


@dataclass
class Session:
    base_url: str
    headers: dict[str, str]


def script_dir() -> Path:
    return Path(__file__).resolve().parent


def skill_dir() -> Path:
    return script_dir().parent


def config_paths() -> list[Path]:
    paths: list[Path] = []
    if os.environ.get(CONFIG_ENV):
        paths.append(Path(os.environ[CONFIG_ENV]).expanduser())
    paths.append(Path.home() / ".config" / "skills" / SKILL_NAME / ".env")
    paths.append(skill_dir() / ".env")
    return paths


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")
    return values


def load_config() -> dict[str, str]:
    config: dict[str, str] = {}
    for path in config_paths():
        config.update(load_env_file(path))
        if config:
            break
    config.update({key: value for key, value in os.environ.items() if value})
    return config


def normalize_base_url(config: dict[str, str]) -> str:
    base_url = config.get("READEST_BASE_URL", "").strip()
    if not base_url:
        domain = config.get("READEST_PRIMARY_DOMAIN", "").strip()
        if domain:
            base_url = domain if domain.startswith(("http://", "https://")) else f"https://{domain}"
    if not base_url:
        raise SystemExit("Missing READEST_BASE_URL or READEST_PRIMARY_DOMAIN in ~/.config/skills/jz-get-readest-highlights/.env")
    return base_url.rstrip("/")


def request_json(url: str, headers: dict[str, str], method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    req_headers = {
        "Accept": "application/json",
        "User-Agent": f"{SKILL_NAME}/1.0",
        **headers,
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req_headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Readest request failed: HTTP {exc.code} {url}\n{detail}") from exc
    except urllib.error.URLError as exc:
        raise SystemExit(f"Readest request failed: {exc.reason}") from exc


def create_session() -> Session:
    config = load_config()
    base_url = normalize_base_url(config)
    anon_key = (
        config.get("READEST_ANON_KEY")
        or config.get("READEST_SUPABASE_ANON_KEY")
        or config.get("SUPABASE_ANON_KEY")
        or config.get("ANON_KEY")
    )
    email = config.get("READEST_OWNER_EMAIL")
    password = config.get("READEST_OWNER_PASSWORD")
    missing = [name for name, value in {
        "READEST_ANON_KEY": anon_key,
        "READEST_OWNER_EMAIL": email,
        "READEST_OWNER_PASSWORD": password,
    }.items() if not value]
    if missing:
        raise SystemExit(f"Missing {', '.join(missing)} in ~/.config/skills/jz-get-readest-highlights/.env")

    auth_url = f"{base_url}/auth/v1/token?grant_type=password"
    auth_payload = request_json(
        auth_url,
        {"apikey": anon_key},
        method="POST",
        payload={"email": email, "password": password},
    )
    token = auth_payload.get("access_token") if isinstance(auth_payload, dict) else None
    if not token:
        raise SystemExit("Readest login succeeded but no access_token was returned.")
    return Session(base_url=base_url, headers={"apikey": anon_key, "Authorization": f"Bearer {token}"})


def rest_url(session: Session, resource: str, params: dict[str, str]) -> str:
    return f"{session.base_url}/rest/v1/{resource}?{urllib.parse.urlencode(params)}"


def parse_jsonish(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


def progress_label(value: Any) -> str:
    value = parse_jsonish(value)
    if isinstance(value, list) and len(value) >= 2:
        current, total = value[0], value[1]
        if isinstance(current, (int, float)) and isinstance(total, (int, float)) and total:
            return f"{int(current)} / {int(total)} ({round(current / total * 100)}%)"
    return ""


def get_books(session: Session) -> list[dict[str, Any]]:
    books = request_json(
        rest_url(session, "books", {
            "select": "book_hash,title,author,format,reading_status,progress,metadata,created_at,updated_at",
            "deleted_at": "is.null",
            "order": "updated_at.desc",
            "limit": "1000",
        }),
        session.headers,
    )
    if not isinstance(books, list):
        raise SystemExit("Unexpected Readest books response.")

    counts = get_note_counts(session)
    for book in books:
        book["note_count"] = counts.get(book.get("book_hash"), 0)
    return books


def get_note_counts(session: Session) -> dict[str, int]:
    rows = request_json(
        rest_url(session, "book_notes", {
            "select": "book_hash",
            "deleted_at": "is.null",
            "limit": "10000",
        }),
        session.headers,
    )
    counts: dict[str, int] = {}
    if isinstance(rows, list):
        for row in rows:
            book_hash = row.get("book_hash")
            if book_hash:
                counts[book_hash] = counts.get(book_hash, 0) + 1
    return counts


def print_books(books: list[dict[str, Any]]) -> None:
    headers = ["#", "Title", "Author", "Format", "Status", "Progress", "Notes", "Updated"]
    rows = []
    for idx, book in enumerate(books, 1):
        rows.append([
            str(idx),
            clean_inline(book.get("title") or "Untitled"),
            clean_inline(book.get("author") or ""),
            clean_inline(book.get("format") or ""),
            clean_inline(book.get("reading_status") or ""),
            progress_label(book.get("progress")),
            str(book.get("note_count") or 0),
            format_date(book.get("updated_at")),
        ])
    widths = [len(item) for item in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row)]
    print("  ".join(cell.ljust(width) for cell, width in zip(headers, widths)))
    print("  ".join("-" * width for width in widths))
    for row in rows:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths)))


def clean_inline(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()


def format_date(value: Any) -> str:
    if not value:
        return ""
    text = str(value)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        return text[:10]


def find_book(books: list[dict[str, Any]], index: int | None, title: str | None) -> dict[str, Any]:
    if index is not None:
        if index < 1 or index > len(books):
            raise SystemExit(f"Book index out of range: {index}. Run list first.")
        return books[index - 1]
    if not title:
        raise SystemExit("Provide --index or --book.")
    needle = title.casefold().strip()
    exact = [book for book in books if clean_inline(book.get("title") or "").casefold() == needle]
    if len(exact) == 1:
        return exact[0]
    partial = [book for book in books if needle in clean_inline(book.get("title") or "").casefold()]
    if len(partial) == 1:
        return partial[0]
    if not partial:
        raise SystemExit(f"No book matched: {title}")
    options = "\n".join(f"- {book.get('title')}" for book in partial[:20])
    raise SystemExit(f"Multiple books matched {title!r}. Use --index after running list:\n{options}")


def get_notes(session: Session, book_hash: str) -> list[dict[str, Any]]:
    rows = request_json(
        rest_url(session, "book_notes", {
            "select": "id,type,text,note,color,page,created_at,updated_at",
            "book_hash": f"eq.{book_hash}",
            "deleted_at": "is.null",
            "order": "page.asc,created_at.asc",
            "limit": "10000",
        }),
        session.headers,
    )
    if not isinstance(rows, list):
        raise SystemExit("Unexpected Readest notes response.")
    return rows


def safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", " ", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:120] or "Untitled"


def markdown_escape(text: Any) -> str:
    return str(text or "").replace("\r\n", "\n").replace("\r", "\n").strip()


def quote_block(text: str) -> str:
    if not text:
        return ""
    return "\n".join(f"> {line}" if line else ">" for line in text.splitlines())


def note_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        markdown_escape(row.get("text")),
        str(row.get("page") or ""),
        format_date(row.get("created_at")),
    )


def prefer_annotated_notes(notes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated_keys = {
        note_identity(row)
        for row in notes
        if markdown_escape(row.get("note"))
    }
    selected = []
    for row in notes:
        text = markdown_escape(row.get("text"))
        note = markdown_escape(row.get("note"))
        if not text and not note:
            continue
        if not note and note_identity(row) in annotated_keys:
            continue
        selected.append(row)
    return selected


def quote_with_meta(text: str, page: Any, created: str) -> str:
    parts = []
    if page is not None:
        parts.append(f"P{page}")
    if created:
        parts.append(created)
    suffix = f"（{'/'.join(parts)}）" if parts else ""
    quote = f"{text}{suffix}"
    return "\n".join(f"> {line}" if line else ">" for line in quote.splitlines())


def build_notes_markdown(book: dict[str, Any], notes: list[dict[str, Any]]) -> str:
    title = clean_inline(book.get("title") or "Untitled")
    author = clean_inline(book.get("author") or "")
    note_count = sum(1 for row in notes if markdown_escape(row.get("note")))
    highlight_count = sum(1 for row in notes if markdown_escape(row.get("text")))
    display_notes = prefer_annotated_notes(notes)
    lines: list[str] = [
        f"# {title} 阅读笔记",
        "",
        "## 基本信息",
        "",
        f"- 书名：{title}",
        f"- 作者：{author or '未标注'}",
        f"- 格式：{clean_inline(book.get('format') or '未标注')}",
        f"- 阅读状态：{clean_inline(book.get('reading_status') or '未标注')}",
        f"- 进度：{progress_label(book.get('progress')) or '未标注'}",
        f"- 高亮数：{highlight_count}",
        f"- note 数：{note_count}",
        f"- 更新时间：{format_date(book.get('updated_at')) or '未标注'}",
        "",
        "## 阅读笔记",
        "",
    ]

    if not display_notes:
        lines.append("暂无高亮或批注。")
    for idx, row in enumerate(display_notes, 1):
        page = row.get("page")
        created = format_date(row.get("created_at"))
        text = markdown_escape(row.get("text"))
        note = markdown_escape(row.get("note"))
        if note:
            lines.append(f"{idx}. {note}")
        else:
            lines.append(f"{idx}.")
        if text:
            lines.append(quote_with_meta(text, page, created))
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def command_list(_: argparse.Namespace) -> int:
    session = create_session()
    print_books(get_books(session))
    return 0


def command_notes(args: argparse.Namespace) -> int:
    session = create_session()
    books = get_books(session)
    book = find_book(books, args.index, args.book)
    notes = get_notes(session, book["book_hash"])
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    title = clean_inline(book.get("title") or "Untitled")
    output_path = output_dir / f"{safe_filename(title)} 阅读笔记.md"
    output_path.write_text(build_notes_markdown(book, notes), encoding="utf-8")
    note_count = sum(1 for row in notes if markdown_escape(row.get("note")))
    highlight_count = sum(1 for row in notes if markdown_escape(row.get("text")))
    print(f"Book: {title}")
    print(f"Highlights: {highlight_count}")
    print(f"Notes: {note_count}")
    print(f"Output: {output_path}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List Readest books or export book text/note into a reading notes Markdown file.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            """
            Examples:
              readest_review.py list
              readest_review.py notes --index 3 --output-dir .
              readest_review.py notes --book "The Almanack of Naval Ravikant"
            """
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    list_parser = subparsers.add_parser("list", help="List Readest books.")
    list_parser.set_defaults(func=command_list)

    notes_parser = subparsers.add_parser("notes", help="Export book highlights and user notes Markdown.")
    target = notes_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--index", type=int, help="Book index from the list command, starting at 1.")
    target.add_argument("--book", help="Book title or unique title fragment.")
    notes_parser.add_argument("--output-dir", default=".", help="Output directory. Defaults to current directory.")
    notes_parser.set_defaults(func=command_notes)

    review_parser = subparsers.add_parser("review", help="Deprecated alias for notes.")
    review_target = review_parser.add_mutually_exclusive_group(required=True)
    review_target.add_argument("--index", type=int, help="Book index from the list command, starting at 1.")
    review_target.add_argument("--book", help="Book title or unique title fragment.")
    review_parser.add_argument("--output-dir", default=".", help="Output directory. Defaults to current directory.")
    review_parser.set_defaults(func=command_notes)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
