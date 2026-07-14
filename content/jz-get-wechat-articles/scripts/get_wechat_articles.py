#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request
from html import unescape


POST_HISTORY_URL = "https://www.dajiala.com/fbmain/monitor/v3/post_history"
ARTICLE_HTML_URL = "https://www.dajiala.com/fbmain/monitor/v3/article_html"
READ_ZAN_PRO_URL = "https://www.dajiala.com/fbmain/monitor/v3/read_zan_pro"
ARTICLE_INFO_URL = "https://www.dajiala.com/fbmain/monitor/v3/article_info"
DEFAULT_TIMEOUT = 30
DEFAULT_QPS_DELAY = 1.5
WECHAT_MOBILE_UA = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_3 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148 "
    "MicroMessenger/8.0.54 NetType/WIFI Language/zh_CN"
)
DEFAULT_CONFIG_ENV = Path.home() / ".config" / "skills" / "jz-get-wechat-articles" / ".env"


class ApiError(RuntimeError):
    pass


@dataclass
class ClientConfig:
    api_key: str
    verifycode: str
    timeout: int
    retry: int
    delay: float


class JizhileClient:
    def __init__(self, config: ClientConfig) -> None:
        self.config = config

    def _post_json(self, url: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        last_error: Exception | None = None
        for attempt in range(1, self.config.retry + 1):
            try:
                with request.urlopen(req, timeout=self.config.timeout) as resp:
                    raw = resp.read().decode("utf-8")
                data = json.loads(raw)
                if not isinstance(data, dict):
                    raise ApiError(f"unexpected response: {raw[:200]}")
                return data
            except (error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                last_error = exc
                if attempt == self.config.retry:
                    break
                time.sleep(min(2 * attempt, 5))

        raise ApiError(f"request failed after {self.config.retry} attempts: {last_error}")

    def fetch_history_page(
        self,
        *,
        name: str = "",
        biz: str = "",
        url: str = "",
        page: int = 1,
        extra_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "biz": biz,
            "url": url,
            "name": name,
            "page": page,
            "key": self.config.api_key,
            "verifycode": self.config.verifycode,
        }
        if extra_body:
            payload.update(extra_body)
        data = self._post_json(POST_HISTORY_URL, payload)
        self._raise_if_error(data, f"history page {page}")
        return data

    def fetch_article_html(self, url: str) -> dict[str, Any]:
        payload = {
            "url": url,
            "key": self.config.api_key,
            "verifycode": self.config.verifycode,
        }
        data = self._post_json(ARTICLE_HTML_URL, payload)
        self._raise_if_error(data, f"article html: {url}")
        return data

    def fetch_read_zan_pro(self, url: str) -> dict[str, Any]:
        payload = {
            "url": url,
            "key": self.config.api_key,
            "verifycode": self.config.verifycode,
        }
        data = self._post_json(READ_ZAN_PRO_URL, payload)
        self._raise_if_error(data, f"read_zan_pro: {url}")
        return data

    def fetch_article_info(self, url: str) -> dict[str, Any]:
        payload = {
            "url": url,
            "key": self.config.api_key,
            "verifycode": self.config.verifycode,
        }
        data = self._post_json(ARTICLE_INFO_URL, payload)
        self._raise_if_error(data, f"article info: {url}")
        return data

    @staticmethod
    def _raise_if_error(data: dict[str, Any], context: str) -> None:
        code = data.get("code")
        if code in (0, "0", None):
            return
        msg = data.get("msg") or data.get("msk") or "unknown api error"
        raise ApiError(f"{context} failed: code={code}, msg={msg}")


def fetch_wechat_article_html(url: str, timeout: int, retry: int) -> dict[str, Any]:
    headers = {
        "User-Agent": WECHAT_MOBILE_UA,
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Referer": "https://mp.weixin.qq.com/",
    }
    req = request.Request(url, headers=headers, method="GET")

    last_error: Exception | None = None
    for attempt in range(1, retry + 1):
        try:
            with request.urlopen(req, timeout=timeout) as resp:
                final_url = resp.geturl()
                html = resp.read().decode("utf-8", errors="replace")
            return {
                "url": url,
                "final_url": final_url,
                "html": html,
                "title": extract_article_title(html),
                "blocked": looks_like_block_page(html),
            }
        except (error.URLError, TimeoutError) as exc:
            last_error = exc
            if attempt == retry:
                break
            time.sleep(min(2 * attempt, 5))

    raise ApiError(f"wechat article fetch failed after {retry} attempts: {last_error}")


def extract_article_title(html: str) -> str:
    patterns = [
        r"<meta property=\"og:title\" content=\"([^\"]+)\"",
        r"var msg_title = '([^']+)'\.html\(false\);",
        r"<title>(.*?)</title>",
    ]
    for pattern in patterns:
        match = re.search(pattern, html, flags=re.DOTALL)
        if match:
            return html_unescape(match.group(1)).strip()
    return ""


def html_unescape(value: str) -> str:
    return unescape(value)


def looks_like_block_page(html: str) -> bool:
    signals = [
        "环境异常",
        "完成验证后即可继续访问",
        "wappoc_appmsgcaptcha",
        "secitptpage/verify",
    ]
    return any(signal in html for signal in signals)


def load_env_file(path: Path = DEFAULT_CONFIG_ENV) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        values[key.strip()] = value
    return values


def default_secret(name: str, fallback_name: str | None = None) -> str:
    env_value = os.environ.get(name)
    if env_value:
        return env_value
    if fallback_name:
        fallback_value = os.environ.get(fallback_name)
        if fallback_value:
            return fallback_value

    file_values = load_env_file()
    value = file_values.get(name, "")
    if value:
        return value
    if fallback_name:
        return file_values.get(fallback_name, "")
    return ""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="获取微信公众号文章、正文和可选的互动指标，并保存到本地。",
        allow_abbrev=False,
    )
    parser.add_argument(
        "--api-key",
        default=default_secret("JZL_API_KEY", "JZL_KEY"),
        help=(
            "极致了 API key。默认先读环境变量 JZL_API_KEY/JZL_KEY，"
            "再读 ~/.config/skills/jz-get-wechat-articles/.env。"
        ),
    )
    parser.add_argument(
        "--verification-code",
        dest="verification_code",
        default=default_secret("JZL_VERIFYCODE"),
        help="可选的极致了 verifycode / 加购码。",
    )
    parser.add_argument(
        "--account",
        default="",
        help="公众号名称或微信 ID。",
    )
    parser.add_argument("--biz-id", default="", help="公众号 biz 标识。")
    parser.add_argument("--source-url", default="", help="公众号文章链接或主页链接。")
    parser.add_argument(
        "--output-dir",
        default="output",
        help="输出目录。默认：./output。",
    )
    parser.add_argument(
        "--no-run-dir",
        action="store_true",
        help="直接写入 --output-dir，不创建 <account>_<timestamp> 单次运行目录。",
    )
    parser.add_argument(
        "--compact-output",
        dest="compact_output",
        action="store_true",
        default=True,
        help="精简输出，只在单次运行目录保留 articles/。默认开启。",
    )
    parser.add_argument(
        "--no-compact-output",
        dest="compact_output",
        action="store_false",
        help="保留完整输出，包括 manifest、jsonl、raw_pages、html 和原始正文响应。",
    )
    parser.add_argument(
        "--mode",
        choices=("backfill", "latest"),
        default="latest",
        help="补齐历史文章，或只获取上次运行后的新文章。默认：latest。",
    )
    parser.add_argument(
        "--start-page",
        type=int,
        default=1,
        help="post_history 起始页。默认：1。",
    )
    parser.add_argument(
        "--end-page",
        type=int,
        default=0,
        help="获取到第几页。0 表示使用 API 返回的 total_page。",
    )
    parser.add_argument(
        "--metadata-only",
        action="store_true",
        help="只保存文章列表元数据，跳过正文请求。",
    )
    parser.add_argument(
        "--fetch-metrics",
        action="store_true",
        help="获取发布时间超过 24 小时的文章互动指标。默认关闭。",
    )
    parser.add_argument(
        "--metrics-from-list-cache-only",
        action="store_true",
        help=(
            "从本地历史列表页缓存读取文章 URL，跳过列表 API 和正文获取；"
            "仍会请求未缓存的互动指标。需同时使用 --fetch-metrics。"
        ),
    )
    parser.add_argument(
        "--published-within-days",
        type=int,
        default=0,
        help="只保留最近 N 天发布的文章。0 表示不限。",
    )
    parser.add_argument(
        "--body-source",
        choices=("wechat", "api"),
        default="wechat",
        help="正文来源。wechat 直接读取微信文章页，api 使用正文 API。默认：wechat。",
    )
    parser.add_argument(
        "--retry",
        type=int,
        default=3,
        help="短暂错误的重试次数。默认：3。",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"HTTP 超时时间，单位秒。默认：{DEFAULT_TIMEOUT}。",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=DEFAULT_QPS_DELAY,
        help=f"请求间隔，单位秒。默认：{DEFAULT_QPS_DELAY}。",
    )
    parser.add_argument(
        "--extra-body",
        default="",
        help="要合并进 post_history 请求体的 JSON 文件路径。",
    )
    parser.add_argument(
        "--state-file",
        default="",
        help="增量获取状态 JSON 路径。默认：<output-dir>/<account>.state.json。",
    )
    return parser.parse_args(argv)


def load_extra_body(path_value: str) -> dict[str, Any]:
    if not path_value:
        return {}
    path = Path(path_value)
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("--extra-body must point to a JSON object file")
    return data


def ensure_query_source(args: argparse.Namespace) -> None:
    if args.biz_id or args.source_url or args.account:
        return
    raise ValueError("you must pass at least one of --biz-id, --source-url, or --account")


def slugify(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^\w\-.]+", "_", value.strip(), flags=re.UNICODE).strip("._")
    return cleaned[:80] or fallback


def make_run_dir(base_dir: Path, account_hint: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / f"{slugify(account_hint, 'wechat')}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "articles").mkdir(exist_ok=True)
    return run_dir


def prepare_flat_run_dir(base_dir: Path, compact_output: bool) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    (base_dir / "articles").mkdir(exist_ok=True)
    for run_file in ("articles.jsonl", "stats.jsonl", "manifest.json"):
        path = base_dir / run_file
        if path.exists():
            path.unlink()
    raw_pages_dir = base_dir / "raw_pages"
    if compact_output:
        if raw_pages_dir.exists():
            shutil.rmtree(raw_pages_dir)
    else:
        raw_pages_dir.mkdir(exist_ok=True)
    return base_dir


def resolve_state_file(output_dir: Path, account_hint: str, state_file_arg: str) -> Path:
    if state_file_arg:
        return Path(state_file_arg)
    return output_dir / f"{slugify(account_hint, 'wechat')}.state.json"


def resolve_history_cache_dir(output_dir: Path, account_hint: str) -> Path:
    return output_dir / f"{slugify(account_hint, 'wechat')}.history_pages"


def resolve_stats_db_path(output_dir: Path, account_hint: str) -> Path:
    return output_dir / f"{slugify(account_hint, 'wechat')}.article_stats.sqlite"


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def iter_cached_history_items(history_cache_dir: Path) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for cache_file in sorted(history_cache_dir.glob("page_*.json")):
        payload = load_json(cache_file)
        page_items = payload.get("data") or []
        if not isinstance(page_items, list):
            continue
        for item in page_items:
            if not isinstance(item, dict):
                continue
            url = str(item.get("url") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            items.append(item)
    return items


def append_jsonl(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False))
        fh.write("\n")


def save_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write(content)


def connect_stats_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            url TEXT PRIMARY KEY,
            account_hint TEXT,
            title TEXT,
            digest TEXT,
            post_time INTEGER,
            post_time_str TEXT,
            pre_post_time INTEGER,
            update_time INTEGER,
            position INTEGER,
            appmsgid INTEGER,
            original INTEGER,
            types INTEGER,
            item_show_type INTEGER,
            msg_status INTEGER,
            msg_fail_reason TEXT,
            send_to_fans_num INTEGER,
            is_deleted TEXT,
            cover_url TEXT,
            pic_cdn_url_235_1 TEXT,
            pic_cdn_url_16_9 TEXT,
            pic_cdn_url_1_1 TEXT,
            raw_json TEXT,
            first_seen_at TEXT,
            last_seen_at TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS article_stats (
            url TEXT PRIMARY KEY,
            title TEXT,
            public_time TEXT,
            wx_name TEXT,
            wxid TEXT,
            ghid TEXT,
            read INTEGER,
            praise INTEGER,
            look INTEGER,
            comment INTEGER,
            repost INTEGER,
            collect INTEGER,
            raw_cost REAL,
            source_api TEXT,
            fetched_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def upsert_article_item(conn: sqlite3.Connection, account_hint: str, item: dict[str, Any]) -> None:
    now = datetime.now().isoformat()
    raw_json = json.dumps(item, ensure_ascii=False)
    conn.execute(
        """
        INSERT INTO articles (
            url, account_hint, title, digest, post_time, post_time_str, pre_post_time,
            update_time, position, appmsgid, original, types, item_show_type,
            msg_status, msg_fail_reason, send_to_fans_num, is_deleted, cover_url,
            pic_cdn_url_235_1, pic_cdn_url_16_9, pic_cdn_url_1_1, raw_json,
            first_seen_at, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            account_hint=excluded.account_hint,
            title=excluded.title,
            digest=excluded.digest,
            post_time=excluded.post_time,
            post_time_str=excluded.post_time_str,
            pre_post_time=excluded.pre_post_time,
            update_time=excluded.update_time,
            position=excluded.position,
            appmsgid=excluded.appmsgid,
            original=excluded.original,
            types=excluded.types,
            item_show_type=excluded.item_show_type,
            msg_status=excluded.msg_status,
            msg_fail_reason=excluded.msg_fail_reason,
            send_to_fans_num=excluded.send_to_fans_num,
            is_deleted=excluded.is_deleted,
            cover_url=excluded.cover_url,
            pic_cdn_url_235_1=excluded.pic_cdn_url_235_1,
            pic_cdn_url_16_9=excluded.pic_cdn_url_16_9,
            pic_cdn_url_1_1=excluded.pic_cdn_url_1_1,
            raw_json=excluded.raw_json,
            last_seen_at=excluded.last_seen_at
        """,
        (
            item.get("url"),
            account_hint,
            item.get("title"),
            item.get("digest"),
            item.get("post_time"),
            item.get("post_time_str"),
            item.get("pre_post_time"),
            item.get("update_time"),
            item.get("position"),
            item.get("appmsgid"),
            item.get("original"),
            item.get("types"),
            item.get("item_show_type"),
            item.get("msg_status"),
            item.get("msg_fail_reason"),
            item.get("send_to_fans_num"),
            item.get("is_deleted"),
            item.get("cover_url"),
            item.get("pic_cdn_url_235_1"),
            item.get("pic_cdn_url_16_9"),
            item.get("pic_cdn_url_1_1"),
            raw_json,
            now,
            now,
        ),
    )
    conn.commit()


def get_cached_stats(conn: sqlite3.Connection, url: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM article_stats WHERE url = ?", (url,)).fetchone()
    return dict(row) if row else None


def upsert_cached_stats(conn: sqlite3.Connection, stats: dict[str, Any]) -> None:
    conn.execute(
        """
        INSERT INTO article_stats (
            url, title, public_time, wx_name, wxid, ghid,
            read, praise, look, comment, repost, collect,
            raw_cost, source_api, fetched_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(url) DO UPDATE SET
            title=excluded.title,
            public_time=excluded.public_time,
            wx_name=excluded.wx_name,
            wxid=excluded.wxid,
            ghid=excluded.ghid,
            read=excluded.read,
            praise=excluded.praise,
            look=excluded.look,
            comment=excluded.comment,
            repost=excluded.repost,
            collect=excluded.collect,
            raw_cost=excluded.raw_cost,
            source_api=excluded.source_api,
            fetched_at=excluded.fetched_at
        """,
        (
            stats.get("url"),
            stats.get("title"),
            stats.get("public_time"),
            stats.get("wx_name"),
            stats.get("wxid"),
            stats.get("ghid"),
            stats.get("read"),
            stats.get("praise"),
            stats.get("look"),
            stats.get("comment"),
            stats.get("repost"),
            stats.get("collect"),
            stats.get("raw_cost"),
            stats.get("source_api"),
            stats.get("fetched_at"),
        ),
    )
    conn.commit()


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {
            "version": 1,
            "seen_urls": [],
            "newest_post_time": 0,
            "last_run_at": None,
            "last_run_dir": None,
        }
    with path.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError(f"state file is not a JSON object: {path}")
    data.setdefault("version", 1)
    data.setdefault("seen_urls", [])
    data.setdefault("newest_post_time", 0)
    data.setdefault("last_run_at", None)
    data.setdefault("last_run_dir", None)
    return data


def update_state(
    state: dict[str, Any],
    new_urls: list[str],
    newest_post_time: int,
    run_dir: Path,
    keep_last_urls: int = 5000,
) -> dict[str, Any]:
    seen_urls = [url for url in state.get("seen_urls", []) if isinstance(url, str) and url]
    merged: list[str] = []
    seen_set: set[str] = set()
    for url in new_urls + seen_urls:
        if url and url not in seen_set:
            seen_set.add(url)
            merged.append(url)
        if len(merged) >= keep_last_urls:
            break

    return {
        "version": 1,
        "seen_urls": merged,
        "newest_post_time": max(int(state.get("newest_post_time") or 0), int(newest_post_time or 0)),
        "last_run_at": datetime.now().isoformat(),
        "last_run_dir": str(run_dir),
    }


def persist_run_state(
    *,
    state_file: Path,
    state: dict[str, Any],
    new_urls_for_state: list[str],
    newest_post_time_seen_this_run: int,
    run_dir: Path,
) -> None:
    updated_state = update_state(
        state=state,
        new_urls=new_urls_for_state,
        newest_post_time=newest_post_time_seen_this_run,
        run_dir=run_dir,
    )
    save_json(state_file, updated_state)


def article_is_older_than_24h(post_time: int) -> bool:
    if post_time <= 0:
        return False
    return post_time <= int(time.time()) - 24 * 60 * 60


def article_is_outside_recent_window(post_time: int, recent_days: int) -> bool:
    if recent_days <= 0 or post_time <= 0:
        return False
    return post_time < int(time.time()) - recent_days * 24 * 60 * 60


def build_stats_cache_key(url: str) -> str:
    import hashlib

    return hashlib.sha1(url.encode("utf-8")).hexdigest()


def normalize_article_stats(raw: dict[str, Any], source_url: str) -> dict[str, Any]:
    # Preferred shape: read_zan_pro
    data = raw.get("data") or {}
    if isinstance(data, dict) and any(key in data for key in ("zan", "looking", "share_num", "comment_count")):
        return {
            "url": source_url,
            "title": None,
            "public_time": None,
            "wx_name": None,
            "wxid": None,
            "ghid": None,
            "read": data.get("read"),
            "praise": data.get("zan"),
            "look": data.get("looking"),
            "comment": data.get("comment_count"),
            "repost": data.get("share_num"),
            "collect": data.get("collect_num"),
            "raw_cost": raw.get("cost") if raw.get("cost") is not None else raw.get("cost_money"),
            "source_api": "read_zan_pro",
            "fetched_at": datetime.now().isoformat(),
        }

    # Fallback shape: article_info
    items = raw.get("data") or []
    item = items[0] if isinstance(items, list) and items else {}
    if not isinstance(item, dict):
        item = {}
    return {
        "url": source_url,
        "title": item.get("title"),
        "public_time": item.get("public_time"),
        "wx_name": item.get("wx_name"),
        "wxid": item.get("wxid"),
        "ghid": item.get("ghid"),
        "read": item.get("read"),
        "praise": item.get("praise"),
        "look": item.get("look"),
        "comment": None,
        "repost": None,
        "collect": None,
        "raw_cost": raw.get("cost") if raw.get("cost") is not None else raw.get("cost_money"),
        "source_api": "article_info",
        "fetched_at": datetime.now().isoformat(),
    }


def update_manifest_balance(manifest: dict[str, Any], response: dict[str, Any]) -> None:
    remain_money = response.get("remain_money")
    if remain_money is None:
        return

    remain_value = float(remain_money)
    cost_raw = response.get("cost")
    if cost_raw is None:
        cost_raw = response.get("cost_money")
    cost_value = float(cost_raw or 0)

    if manifest.get("initial_balance") is None:
        manifest["initial_balance"] = remain_value + cost_value
    manifest["remaining_balance"] = remain_value


def strip_tags(value: str) -> str:
    value = re.sub(r"(?is)<(script|style).*?>.*?</\1>", "", value)
    value = re.sub(r"(?is)<br\s*/?>", "\n", value)
    value = re.sub(r"(?is)</p\s*>", "\n\n", value)
    value = re.sub(r"(?is)</div\s*>", "\n\n", value)
    value = re.sub(r"(?is)</h[1-6]\s*>", "\n\n", value)
    value = re.sub(r"(?is)<[^>]+>", "", value)
    value = html_unescape(value)
    value = value.replace("\xa0", " ")
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def html_fragment_to_markdown(fragment: str) -> str:
    text = fragment
    text = re.sub(r"(?is)<\s*(strong|b)[^>]*>(.*?)<\s*/\s*\1\s*>", r"**\2**", text)
    text = re.sub(r"(?is)<\s*(em|i)[^>]*>(.*?)<\s*/\s*\1\s*>", r"*\2*", text)
    text = re.sub(
        r'(?is)<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
        lambda m: f"[{strip_tags(m.group(2))}]({html_unescape(m.group(1))})",
        text,
    )
    text = re.sub(
        r'(?is)<img[^>]*src="([^"]+)"[^>]*>',
        lambda m: f"\n\n![]({html_unescape(m.group(1))})\n\n",
        text,
    )
    text = re.sub(r"(?is)<li[^>]*>", "- ", text)
    text = re.sub(r"(?is)</li\s*>", "\n", text)
    text = re.sub(r"(?is)<blockquote[^>]*>", "\n\n> ", text)
    text = re.sub(r"(?is)</blockquote\s*>", "\n\n", text)
    text = re.sub(r"(?is)<h1[^>]*>", "\n\n# ", text)
    text = re.sub(r"(?is)<h2[^>]*>", "\n\n## ", text)
    text = re.sub(r"(?is)<h3[^>]*>", "\n\n### ", text)
    text = re.sub(r"(?is)<h[4-6][^>]*>", "\n\n#### ", text)
    text = strip_tags(text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_article_body_html(html: str) -> str:
    patterns = [
        r'(?is)<div[^>]+id="js_content"[^>]*>(.*?)</div>',
        r'(?is)<div[^>]+id="js_content_container"[^>]*>(.*?)</div>',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return match.group(1)
    return ""


def build_markdown_document(title: str, url: str, html: str) -> str:
    body_html = extract_article_body_html(html)
    body_md = html_fragment_to_markdown(body_html) if body_html else ""
    parts = [f"# {title or 'Untitled'}", "", f"原文链接: {url}"]
    if body_md:
        parts.extend(["", body_md])
    return "\n".join(parts).strip() + "\n"


def build_article_filename(article: dict[str, Any], index: int) -> str:
    post_time = article.get("post_time")
    if isinstance(post_time, (int, float)) and post_time > 0:
        stamp = datetime.fromtimestamp(post_time, tz=timezone.utc).strftime("%Y%m%d_%H%M%S")
    else:
        stamp = f"item_{index:05d}"
    position = article.get("position", 0)
    title = slugify(str(article.get("title", "")), f"article_{index:05d}")
    return f"{stamp}_p{position}_{title}"


def save_article_payload(article_dir: Path, payload: dict[str, Any], compact_output: bool) -> None:
    data = payload.get("data") or {}
    file_base = slugify(str(data.get("title", "")), "article")
    if not compact_output:
        save_json(article_dir / f"{file_base}.article.json", payload)
    html = data.get("html", "")
    if html:
        if not compact_output:
            save_text(article_dir / f"{file_base}.html", html)
        markdown = build_markdown_document(
            title=str(data.get("title", "")),
            url=str(data.get("url", "")),
            html=html,
        )
        save_text(article_dir / f"{file_base}.md", markdown)


def save_direct_article_payload(
    article_dir: Path,
    payload: dict[str, Any],
    fallback_title: str,
    compact_output: bool,
) -> None:
    file_base = slugify(payload.get("title") or fallback_title, "article")
    if not compact_output:
        save_json(article_dir / f"{file_base}.direct.json", payload)
    html = payload.get("html", "")
    if html:
        if not compact_output:
            save_text(article_dir / f"{file_base}.html", html)
        markdown = build_markdown_document(
            title=str(payload.get("title") or fallback_title),
            url=str(payload.get("final_url") or payload.get("url") or ""),
            html=html,
        )
        save_text(article_dir / f"{file_base}.md", markdown)


def main() -> int:
    args = parse_args()
    try:
        ensure_query_source(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    if not args.api_key:
        print(
            "error: 缺少 API key。请传 --api-key，设置 JZL_API_KEY，或配置 "
            "~/.config/skills/jz-get-wechat-articles/.env。",
            file=sys.stderr,
        )
        return 2

    try:
        extra_body = load_extra_body(args.extra_body)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: 加载 --extra-body 失败：{exc}", file=sys.stderr)
        return 2

    client = JizhileClient(
        ClientConfig(
            api_key=args.api_key,
            verifycode=args.verification_code,
            timeout=args.timeout,
            retry=args.retry,
            delay=args.delay,
        )
    )

    account_hint = args.biz_id or args.account or args.source_url
    output_dir = Path(args.output_dir)
    run_dir = prepare_flat_run_dir(output_dir, args.compact_output) if args.no_run_dir else make_run_dir(output_dir, account_hint)
    state_file = resolve_state_file(output_dir, account_hint, args.state_file)
    history_cache_dir = resolve_history_cache_dir(output_dir, account_hint)
    stats_db_path = resolve_stats_db_path(output_dir, account_hint)
    use_history_cache = args.mode == "backfill"
    try:
        state = load_state(state_file)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"error: failed to load state file: {exc}", file=sys.stderr)
        return 2
    raw_pages_dir = run_dir / "raw_pages"
    if not args.compact_output:
        raw_pages_dir.mkdir(exist_ok=True)
    manifest_path = run_dir / "articles.jsonl"
    stats_run_path = run_dir / "stats.jsonl"
    stats_conn = connect_stats_db(stats_db_path)
    known_urls = {url for url in state.get("seen_urls", []) if isinstance(url, str) and url}
    known_newest_post_time = int(state.get("newest_post_time") or 0)

    seen_urls: set[str] = set()
    new_urls_for_state: list[str] = []
    newest_post_time_seen_this_run = known_newest_post_time
    manifest: dict[str, Any] = {
        "query": {
            "name": args.account,
            "biz": args.biz_id,
            "url": args.source_url,
            "mode": args.mode,
            "start_page": args.start_page,
            "end_page": args.end_page,
            "metadata_only": args.metadata_only,
            "fetch_stats": args.fetch_metrics,
            "published_within_days": args.published_within_days,
            "body_source": args.body_source,
            "flat_output": args.no_run_dir,
            "compact_output": args.compact_output,
        },
        "state_file": str(state_file),
        "history_cache_dir": str(history_cache_dir),
        "stats_db_path": str(stats_db_path),
        "article_db_path": str(stats_db_path),
        "known_url_count_before_run": len(known_urls),
        "known_newest_post_time_before_run": known_newest_post_time,
        "started_at": datetime.now().isoformat(),
        "pages_fetched": [],
        "history_api_pages_requested": 0,
        "history_cached_pages_used": 0,
        "articles_saved": 0,
        "article_bodies_saved": 0,
        "article_body_fetch_failures": 0,
        "article_body_fetch_errors": [],
        "articles_skipped_existing": 0,
        "stats_fetched": 0,
        "stats_cache_hits": 0,
        "stats_fetch_failures": 0,
        "stats_pending_under_24h": 0,
        "stats_targets_from_cache": 0,
        "article_rows_upserted": 0,
        "articles_skipped_outside_window": 0,
        "cost_money_history": 0,
        "cost_money_article_html": 0,
        "cost_money_article_info": 0,
        "initial_balance": None,
        "remaining_balance": None,
        "total_page": None,
        "total_num": None,
    }

    try:
        if args.metrics_from_list_cache_only:
            if not args.fetch_metrics:
                raise ApiError("--metrics-from-list-cache-only requires --fetch-metrics")
            if not history_cache_dir.exists():
                raise ApiError(f"history cache dir not found: {history_cache_dir}")

            cached_items = iter_cached_history_items(history_cache_dir)
            for item in cached_items:
                url = str(item.get("url", "")).strip()
                post_time = int(item.get("post_time") or 0)
                if not url:
                    continue
                upsert_article_item(stats_conn, account_hint, item)
                manifest["article_rows_upserted"] += 1
                newest_post_time_seen_this_run = max(newest_post_time_seen_this_run, post_time)
                if article_is_outside_recent_window(post_time, args.published_within_days):
                    manifest["articles_skipped_outside_window"] += 1
                    continue
                manifest["stats_targets_from_cache"] += 1
                if not args.compact_output:
                    append_jsonl(manifest_path, item)
                if not article_is_older_than_24h(post_time):
                    manifest["stats_pending_under_24h"] += 1
                    continue

                cached_stats = get_cached_stats(stats_conn, url)
                if cached_stats:
                    manifest["stats_cache_hits"] += 1
                    if not args.compact_output:
                        append_jsonl(stats_run_path, cached_stats)
                    continue

                try:
                    try:
                        raw_stats = client.fetch_read_zan_pro(url)
                    except ApiError:
                        raw_stats = client.fetch_article_info(url)
                    update_manifest_balance(manifest, raw_stats)
                    stats_data = normalize_article_stats(raw_stats, url)
                    stats_data["title"] = stats_data.get("title") or item.get("title")
                    stats_data["public_time"] = stats_data.get("public_time") or item.get("public_time")
                    upsert_cached_stats(stats_conn, stats_data)
                    if not args.compact_output:
                        append_jsonl(stats_run_path, stats_data)
                    manifest["stats_fetched"] += 1
                    manifest["cost_money_article_info"] += float(
                        raw_stats.get("cost") if raw_stats.get("cost") is not None else raw_stats.get("cost_money") or 0
                    )
                    time.sleep(args.delay)
                except ApiError as exc:
                    manifest["stats_fetch_failures"] += 1
                    if len(manifest["article_body_fetch_errors"]) < 50:
                        manifest["article_body_fetch_errors"].append(
                            {
                                "url": url,
                                "title": item.get("title"),
                                "error": f"metrics: {exc}",
                            }
                        )

            manifest["finished_at"] = datetime.now().isoformat()
            persist_run_state(
                state_file=state_file,
                state=state,
                new_urls_for_state=new_urls_for_state,
                newest_post_time_seen_this_run=newest_post_time_seen_this_run,
                run_dir=run_dir,
            )
            if not args.compact_output:
                save_json(run_dir / "manifest.json", manifest)
            print(f"metrics-only scanned {manifest['stats_targets_from_cache']} cached articles")
            print(f"metrics fetched: {manifest['stats_fetched']}, cache hits: {manifest['stats_cache_hits']}")
            if manifest["stats_pending_under_24h"]:
                print(f"metrics pending (<24h): {manifest['stats_pending_under_24h']}")
            if manifest["initial_balance"] is not None:
                print(
                    "balance initial:"
                    f" {manifest['initial_balance']:.2f}, remaining: {manifest['remaining_balance']:.2f}"
                )
            else:
                print("balance initial: unchanged, remaining: unchanged")
            stats_conn.close()
            return 0

        page = max(1, args.start_page)
        last_page = args.end_page
        article_index = 0

        while True:
            stop_after_page = False
            cache_file = history_cache_dir / f"page_{page:05d}.json"
            if use_history_cache and cache_file.exists():
                response = load_json(cache_file)
                page_source = "cache"
                manifest["history_cached_pages_used"] += 1
            else:
                response = client.fetch_history_page(
                    name=args.account,
                    biz=args.biz_id,
                    url=args.source_url,
                    page=page,
                    extra_body=extra_body,
                )
                page_source = "api"
                manifest["history_api_pages_requested"] += 1
                update_manifest_balance(manifest, response)
                if use_history_cache:
                    save_json(cache_file, response)
            if not args.compact_output:
                save_json(raw_pages_dir / f"page_{page:05d}.json", response)

            total_page = int(response.get("total_page") or 0)
            if total_page and manifest["total_page"] is None:
                manifest["total_page"] = total_page
            if response.get("total_num") is not None and manifest["total_num"] is None:
                manifest["total_num"] = response.get("total_num")
            if not last_page and total_page:
                last_page = total_page

            page_items = response.get("data") or []
            if not isinstance(page_items, list):
                raise ApiError(f"history page {page} returned non-list data")

            manifest["pages_fetched"].append(
                {
                    "page": page,
                    "items": len(page_items),
                    "source": page_source,
                    "cost_money": response.get("cost_money", 0),
                    "remain_money": response.get("remain_money"),
                }
            )
            if page_source != "cache":
                manifest["cost_money_history"] += float(response.get("cost_money") or 0)

            if not page_items:
                break

            for item in page_items:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url", "")).strip()
                post_time = int(item.get("post_time") or 0)
                if url:
                    upsert_article_item(stats_conn, account_hint, item)
                    manifest["article_rows_upserted"] += 1
                newest_post_time_seen_this_run = max(newest_post_time_seen_this_run, post_time)
                if not url or url in seen_urls:
                    continue
                seen_urls.add(url)

                if article_is_outside_recent_window(post_time, args.published_within_days):
                    manifest["articles_skipped_outside_window"] += 1
                    stop_after_page = True
                    continue

                is_known = url in known_urls
                is_older_than_checkpoint = args.mode == "latest" and known_newest_post_time and post_time <= known_newest_post_time
                current_article_dir: Path | None = None
                if is_known or (args.mode == "latest" and is_older_than_checkpoint):
                    manifest["articles_skipped_existing"] += 1
                    if args.mode == "latest":
                        stop_after_page = True
                else:
                    article_index += 1
                    file_stem = build_article_filename(item, article_index)
                    article_dir = run_dir / "articles" / file_stem
                    article_dir.mkdir(exist_ok=True)
                    current_article_dir = article_dir

                    save_json(article_dir / "metadata.json", item)
                    if not args.compact_output:
                        append_jsonl(manifest_path, item)
                    manifest["articles_saved"] += 1
                    new_urls_for_state.append(url)

                if current_article_dir and not args.metadata_only:
                    try:
                        if args.body_source == "api":
                            article_response = client.fetch_article_html(url)
                            update_manifest_balance(manifest, article_response)
                            save_article_payload(current_article_dir, article_response, args.compact_output)
                            manifest["article_bodies_saved"] += 1
                            manifest["cost_money_article_html"] += float(article_response.get("cost_money") or 0)
                        else:
                            article_response = fetch_wechat_article_html(
                                url=url,
                                timeout=args.timeout,
                                retry=args.retry,
                            )
                            save_direct_article_payload(
                                current_article_dir,
                                article_response,
                                str(item.get("title", "")),
                                args.compact_output,
                            )
                            if article_response.get("blocked"):
                                manifest["article_body_fetch_failures"] += 1
                            else:
                                manifest["article_bodies_saved"] += 1
                    except ApiError as exc:
                        manifest["article_body_fetch_failures"] += 1
                        if len(manifest["article_body_fetch_errors"]) < 50:
                            manifest["article_body_fetch_errors"].append(
                                {
                                    "url": url,
                                    "title": item.get("title"),
                                    "error": str(exc),
                                }
                            )
                    finally:
                        time.sleep(args.delay)

                if args.fetch_metrics:
                    if not article_is_older_than_24h(post_time):
                        manifest["stats_pending_under_24h"] += 1
                    else:
                        stats_data: dict[str, Any] | None = None
                        cached_stats = get_cached_stats(stats_conn, url)
                        if cached_stats:
                            stats_data = cached_stats
                            manifest["stats_cache_hits"] += 1
                        else:
                            try:
                                try:
                                    raw_stats = client.fetch_read_zan_pro(url)
                                except ApiError:
                                    raw_stats = client.fetch_article_info(url)
                                update_manifest_balance(manifest, raw_stats)
                                stats_data = normalize_article_stats(raw_stats, url)
                                upsert_cached_stats(stats_conn, stats_data)
                                manifest["stats_fetched"] += 1
                                manifest["cost_money_article_info"] += float(
                                    raw_stats.get("cost") if raw_stats.get("cost") is not None else raw_stats.get("cost_money") or 0
                                )
                                time.sleep(args.delay)
                            except ApiError as exc:
                                manifest["stats_fetch_failures"] += 1
                                if len(manifest["article_body_fetch_errors"]) < 50:
                                    manifest["article_body_fetch_errors"].append(
                                        {
                                            "url": url,
                                            "title": item.get("title"),
                                            "error": f"metrics: {exc}",
                                        }
                                    )
                        if stats_data and current_article_dir:
                            save_json(current_article_dir / "stats.json", stats_data)

            if stop_after_page and (args.mode == "latest" or args.published_within_days > 0):
                break

            if last_page and page >= last_page:
                break

            page += 1
            time.sleep(args.delay)

    except ApiError as exc:
        manifest["error"] = str(exc)
        persist_run_state(
            state_file=state_file,
            state=state,
            new_urls_for_state=new_urls_for_state,
            newest_post_time_seen_this_run=newest_post_time_seen_this_run,
            run_dir=run_dir,
        )
        if not args.compact_output:
            save_json(run_dir / "manifest.json", manifest)
        print(f"error: {exc}", file=sys.stderr)
        print(f"partial results saved in: {run_dir}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        manifest["error"] = "interrupted by user"
        persist_run_state(
            state_file=state_file,
            state=state,
            new_urls_for_state=new_urls_for_state,
            newest_post_time_seen_this_run=newest_post_time_seen_this_run,
            run_dir=run_dir,
        )
        if not args.compact_output:
            save_json(run_dir / "manifest.json", manifest)
        print(f"interrupted. partial results saved in: {run_dir}", file=sys.stderr)
        return 130

    manifest["finished_at"] = datetime.now().isoformat()
    persist_run_state(
        state_file=state_file,
        state=state,
        new_urls_for_state=new_urls_for_state,
        newest_post_time_seen_this_run=newest_post_time_seen_this_run,
        run_dir=run_dir,
    )
    if not args.compact_output:
        save_json(run_dir / "manifest.json", manifest)
    print(f"saved {manifest['articles_saved']} articles to {run_dir}")
    if not args.metadata_only:
        print(f"saved {manifest['article_bodies_saved']} article bodies via {args.body_source}")
        if manifest["article_body_fetch_failures"]:
            print(f"blocked or failed article pages: {manifest['article_body_fetch_failures']}")
    if args.fetch_metrics:
        print(f"metrics fetched: {manifest['stats_fetched']}, cache hits: {manifest['stats_cache_hits']}")
        if manifest["stats_pending_under_24h"]:
            print(f"metrics pending (<24h): {manifest['stats_pending_under_24h']}")
    if manifest["initial_balance"] is not None:
        print(
            "balance initial:"
            f" {manifest['initial_balance']:.2f}, remaining: {manifest['remaining_balance']:.2f}"
        )
    else:
        print("balance initial: unchanged, remaining: unchanged")
    if args.mode == "latest":
        print(f"skipped existing or older articles: {manifest['articles_skipped_existing']}")
    stats_conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
