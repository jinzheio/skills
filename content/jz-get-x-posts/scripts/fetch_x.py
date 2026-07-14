#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


RAPIDAPI_HOST = "twittr-x-api-free-tweets-user-twitter-lookup.p.rapidapi.com"
RAPIDAPI_BASE_URL = f"https://{RAPIDAPI_HOST}"
GLOBAL_ENV_PATH = Path.home() / ".config" / "skills" / "jz-get-x-posts" / ".env"
LOCAL_ENV_PATH = Path(__file__).resolve().parents[1] / ".env"
USER_CACHE_PATH = Path.home() / ".config" / "skills" / "jz-get-x-posts" / "users.json"
DEFAULT_COUNT = 100
MAX_COUNT_PER_REQUEST = 100
DEFAULT_SEARCH_COUNT = 20


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load_credentials() -> list[tuple[str, str]]:
    env_values = load_env_file(GLOBAL_ENV_PATH)
    if not env_values:
        env_values = load_env_file(LOCAL_ENV_PATH)
    env = {**env_values, **os.environ}

    candidates = [
        ("TWITTR_RAPIDAPI_KEY", env.get("TWITTR_RAPIDAPI_KEY", "")),
        ("RAPIDAPI_KEY", env.get("RAPIDAPI_KEY", "")),
        ("X_API_KEY", env.get("X_API_KEY", "")),
        ("TWITTER241_API_KEYS", env.get("TWITTER241_API_KEYS", "")),
    ]

    keys: list[tuple[str, str]] = []
    seen_values: set[str] = set()
    for name, raw_value in candidates:
        if not raw_value.strip():
            continue
        for index, item in enumerate(raw_value.split(","), 1):
            value = item.strip()
            if value and value not in seen_values:
                seen_values.add(value)
                keys.append((f"{name}[{index}]", value))

    if keys:
        return keys
    raise RuntimeError(
        "Missing RapidAPI key. Put it in the global skill .env or the skill-local .env."
    )


class TwittrClient:
    def __init__(self, api_keys: list[tuple[str, str]]) -> None:
        self.api_keys = api_keys
        self.key_index = 0
        self.failed_keys: dict[str, str] = {}
        self.request_count = 0
        self.failed_request_count = 0

    def get(self, path: str, params: dict[str, str | int] | None = None) -> dict:
        url = f"{RAPIDAPI_BASE_URL}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        errors = []
        start_index = self.key_index
        ordered_keys = self.api_keys[start_index:] + self.api_keys[:start_index]

        for key_offset, (key_label, api_key) in enumerate(ordered_keys):
            request = urllib.request.Request(
                url,
                headers={
                    "x-rapidapi-host": RAPIDAPI_HOST,
                    "x-rapidapi-key": api_key,
                    "accept": "application/json",
                    "user-agent": "jz-get-x-posts/1.0",
                },
            )
            self.request_count += 1
            try:
                with urllib.request.urlopen(request, timeout=60) as response:
                    payload = response.read().decode("utf-8", errors="replace")
                self.key_index = (start_index + key_offset) % len(self.api_keys)
                return json.loads(payload)
            except urllib.error.HTTPError as exc:
                payload = exc.read().decode("utf-8", errors="replace")
                message = f"HTTP {exc.code} {payload[:200]}"
            except urllib.error.URLError as exc:
                message = f"request failed: {exc}"
            except json.JSONDecodeError as exc:
                message = f"invalid JSON: {exc}"

            self.failed_request_count += 1
            self.failed_keys[key_label] = message
            errors.append(f"{key_label}: {message}")

        raise RuntimeError("All RapidAPI keys failed:\n" + "\n".join(errors))


def load_user_cache() -> dict:
    if not USER_CACHE_PATH.exists():
        return {"users": {}}
    try:
        payload = json.loads(USER_CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"users": {}}
    if not isinstance(payload, dict):
        return {"users": {}}
    users = payload.get("users")
    if not isinstance(users, dict):
        payload["users"] = {}
    return payload


def save_user_cache(payload: dict) -> None:
    USER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload["updated_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
    USER_CACHE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def cache_lookup_by_username(cache: dict, username: str) -> str | None:
    item = cache.get("users", {}).get(username.lower())
    if isinstance(item, dict) and item.get("user_id"):
        return str(item["user_id"])
    return None


def cache_lookup_by_user_id(cache: dict, user_id: str) -> str | None:
    for username, item in cache.get("users", {}).items():
        if isinstance(item, dict) and str(item.get("user_id", "")) == str(user_id):
            return username
    return None


def update_user_cache(cache: dict, username: str, user_id: str, source: str) -> None:
    users = cache.setdefault("users", {})
    normalized_username = username.lower().lstrip("@")
    existing = users.get(normalized_username, {}) if isinstance(users.get(normalized_username), dict) else {}
    users[normalized_username] = {
        **existing,
        "username": normalized_username,
        "user_id": str(user_id),
        "source": source,
        "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
    }
    save_user_cache(cache)


def parse_created_at(value: str) -> dt.datetime | None:
    if not value:
        return None
    try:
        return dt.datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y")
    except ValueError:
        return None


def extract_user_core(result: dict) -> dict:
    user_result = result.get("core", {}).get("user_results", {}).get("result", {})
    return user_result.get("core") or user_result.get("legacy") or {}


def normalize_tweet(result: dict, source_endpoint: str) -> dict | None:
    if result.get("__typename") == "TweetWithVisibilityResults":
        result = result.get("tweet", {})
    if result.get("__typename") != "Tweet":
        return None

    legacy = result.get("legacy", {})
    user_core = extract_user_core(result)
    post_id = legacy.get("id_str") or result.get("rest_id")
    screen_name = user_core.get("screen_name", "")
    created_at = parse_created_at(legacy.get("created_at", ""))
    text = legacy.get("full_text", "").strip()

    media = []
    for item in legacy.get("extended_entities", {}).get("media", []):
        media.append(
            {
                "type": item.get("type"),
                "media_url_https": item.get("media_url_https"),
                "expanded_url": item.get("expanded_url"),
            }
        )

    expanded_urls = []
    for item in legacy.get("entities", {}).get("urls", []):
        expanded_url = item.get("expanded_url") or item.get("url")
        if expanded_url:
            expanded_urls.append(expanded_url)

    quoted_summary = None
    quoted_result = result.get("quoted_status_result", {}).get("result", {})
    if quoted_result.get("__typename") == "Tweet":
        quoted_legacy = quoted_result.get("legacy", {})
        quoted_user = extract_user_core(quoted_result)
        quoted_id = quoted_legacy.get("id_str") or quoted_result.get("rest_id")
        quoted_screen_name = quoted_user.get("screen_name", "")
        quoted_summary = {
            "id": quoted_id,
            "author_screen_name": quoted_screen_name,
            "url": (
                f"https://x.com/{quoted_screen_name}/status/{quoted_id}"
                if quoted_id and quoted_screen_name
                else ""
            ),
            "text": quoted_legacy.get("full_text", "").strip(),
        }

    return {
        "id": post_id,
        "created_at_raw": legacy.get("created_at", ""),
        "created_at_utc": created_at.astimezone(dt.timezone.utc).isoformat()
        if created_at
        else "",
        "author_screen_name": screen_name,
        "author_name": user_core.get("name", ""),
        "url": f"https://x.com/{screen_name}/status/{post_id}" if post_id and screen_name else "",
        "text": text,
        "favorite_count": legacy.get("favorite_count", 0),
        "reply_count": legacy.get("reply_count", 0),
        "retweet_count": legacy.get("retweet_count", 0),
        "quote_count": legacy.get("quote_count", 0),
        "bookmark_count": legacy.get("bookmark_count", 0),
        "view_count": result.get("views", {}).get("count"),
        "in_reply_to_screen_name": legacy.get("in_reply_to_screen_name"),
        "in_reply_to_status_id": legacy.get("in_reply_to_status_id_str"),
        "conversation_id": legacy.get("conversation_id_str") or post_id,
        "is_retweet_text": text.startswith("RT @"),
        "expanded_urls": expanded_urls,
        "media": media,
        "quoted_tweet": quoted_summary,
        "source_endpoints": [source_endpoint],
    }


def visit_timeline_content(content: dict, source_endpoint: str, posts: list[dict], cursors: list[dict]) -> None:
    if not isinstance(content, dict):
        return

    if content.get("__typename") == "TimelineTimelineCursor" or content.get("entryType") == "TimelineTimelineCursor":
        cursor_value = content.get("value")
        if cursor_value:
            cursors.append({"cursorType": content.get("cursorType"), "value": cursor_value})

    item_content = content.get("itemContent", {})
    tweet_result = item_content.get("tweet_results", {}).get("result", {})
    normalized = normalize_tweet(tweet_result, source_endpoint)
    if normalized:
        posts.append(normalized)

    for nested in content.get("items", []):
        nested_content = (nested.get("item") or {}).get("itemContent") or nested.get("content") or {}
        visit_timeline_content(nested_content, source_endpoint, posts, cursors)

    value = content.get("value")
    if isinstance(value, dict):
        for nested in value.get("items", []):
            nested_content = (nested.get("item") or {}).get("itemContent") or {}
            visit_timeline_content(nested_content, source_endpoint, posts, cursors)


def extract_timeline_posts(payload: dict, source_endpoint: str) -> tuple[list[dict], list[dict]]:
    posts: list[dict] = []
    cursors: list[dict] = []
    instructions = (
        payload.get("data", {})
        .get("user", {})
        .get("result", {})
        .get("timeline", {})
        .get("timeline", {})
        .get("instructions", [])
    )

    for instruction in instructions:
        entry = instruction.get("entry")
        if entry:
            visit_timeline_content(entry.get("content", {}), source_endpoint, posts, cursors)
        for nested_entry in instruction.get("entries", []):
            visit_timeline_content(nested_entry.get("content", {}), source_endpoint, posts, cursors)

    deduped: list[dict] = []
    seen_ids: set[str] = set()
    for post in posts:
        post_id = str(post.get("id") or "")
        if not post_id or post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        deduped.append(post)
    return deduped, cursors


def extract_search_posts(payload: dict, source_endpoint: str) -> tuple[list[dict], list[dict]]:
    posts: list[dict] = []
    cursors: list[dict] = []

    for top_entry in payload.get("entries", []):
        content = top_entry.get("content")
        if content:
            visit_timeline_content(content, source_endpoint, posts, cursors)
        for nested_entry in top_entry.get("entries", []):
            visit_timeline_content(nested_entry.get("content", {}), source_endpoint, posts, cursors)

    deduped: list[dict] = []
    seen_ids: set[str] = set()
    for post in posts:
        post_id = str(post.get("id") or "")
        if not post_id or post_id in seen_ids:
            continue
        seen_ids.add(post_id)
        deduped.append(post)
    return deduped, cursors


def merge_posts(target: dict[str, dict], posts: list[dict]) -> int:
    added = 0
    for post in posts:
        post_id = str(post.get("id") or "")
        if not post_id:
            continue
        existing = target.get(post_id)
        if existing is None:
            target[post_id] = post
            added += 1
            continue
        existing["source_endpoints"] = sorted(
            set(existing.get("source_endpoints", [])) | set(post.get("source_endpoints", []))
        )
    return added


def resolve_user_id(client: TwittrClient, username: str) -> str:
    payload = client.get(f"/username/to/id/{username}")
    user_id = payload.get("userId") or payload.get("id") or payload.get("rest_id")
    if not user_id:
        raise RuntimeError(f"Could not resolve userId for @{username}")
    return str(user_id)


def resolve_username(client: TwittrClient, user_id: str) -> str:
    payload = client.get(f"/user/{user_id}")
    candidates = [
        payload.get("data", {}).get("user", {}).get("result", {}).get("legacy", {}).get("screen_name"),
        payload.get("data", {}).get("user", {}).get("result", {}).get("core", {}).get("screen_name"),
        payload.get("user", {}).get("result", {}).get("legacy", {}).get("screen_name"),
        payload.get("user", {}).get("result", {}).get("core", {}).get("screen_name"),
        payload.get("screen_name"),
        payload.get("username"),
    ]
    for candidate in candidates:
        if candidate:
            return str(candidate)
    raise RuntimeError(f"Could not resolve username for userId {user_id}")


def resolve_identity(
    client: TwittrClient,
    cache: dict,
    username: str | None,
    user_id: str | None,
) -> tuple[str, str, bool]:
    cache_changed = False
    if username:
        username = username.lstrip("@").lower()
    if user_id:
        user_id = str(user_id)

    if username and not user_id:
        cached_user_id = cache_lookup_by_username(cache, username)
        if cached_user_id:
            return username, cached_user_id, cache_changed
        user_id = resolve_user_id(client, username)
        update_user_cache(cache, username, user_id, "username/to/id")
        cache_changed = True
        return username, user_id, cache_changed

    if user_id and not username:
        cached_username = cache_lookup_by_user_id(cache, user_id)
        if cached_username:
            return cached_username, user_id, cache_changed
        username = resolve_username(client, user_id)
        update_user_cache(cache, username, user_id, "/user/{userId}")
        cache_changed = True
        return username, user_id, cache_changed

    if username and user_id:
        cached_user_id = cache_lookup_by_username(cache, username)
        if cached_user_id != user_id:
            update_user_cache(cache, username, user_id, "provided")
            cache_changed = True
        return username, user_id, cache_changed

    raise RuntimeError("Could not resolve both username and userId.")


def collect_user_timeline(
    client: TwittrClient,
    user_id: str,
    username: str,
    target_count: int,
    exclude_retweets: bool,
) -> tuple[dict[str, dict], list[dict]]:
    posts_by_id: dict[str, dict] = {}
    page_logs: list[dict] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()

    for page in range(1, 51):
        params: dict[str, str | int] = {"count": min(target_count, MAX_COUNT_PER_REQUEST)}
        if cursor:
            params["cursor"] = cursor
        payload = client.get(f"/user/{user_id}/tweets", params)
        posts, cursors = extract_timeline_posts(payload, "/user/{userId}/tweets")
        filtered_posts = []
        for post in posts:
            if post.get("author_screen_name", "").lower() != username.lower():
                continue
            if exclude_retweets and post.get("is_retweet_text"):
                continue
            filtered_posts.append(post)

        added = merge_posts(posts_by_id, filtered_posts)
        page_logs.append(
            {
                "page": page,
                "endpoint": "/user/{userId}/tweets",
                "parsed": len(posts),
                "kept_new": added,
                "total_unique": len(posts_by_id),
            }
        )

        if len(posts_by_id) >= target_count:
            break

        bottom_cursor = next(
            (item.get("value") for item in cursors if item.get("cursorType") == "Bottom" and item.get("value")),
            None,
        )
        if not bottom_cursor or bottom_cursor in seen_cursors:
            break
        seen_cursors.add(bottom_cursor)
        cursor = str(bottom_cursor)
        time.sleep(0.8)

    return posts_by_id, page_logs


def collect_search_fallback(
    client: TwittrClient,
    username: str,
    target_count: int,
    exclude_retweets: bool,
    posts_by_id: dict[str, dict],
) -> list[dict]:
    page_logs: list[dict] = []
    cursor: str | None = None
    seen_cursors: set[str] = set()

    for page in range(1, 51):
        params: dict[str, str | int] = {
            "query": f"from:{username}",
            "type": "Latest",
            "count": DEFAULT_SEARCH_COUNT,
        }
        if cursor:
            params["cursor"] = cursor
        payload = client.get("/search", params)
        posts, cursors = extract_search_posts(payload, "/search")
        filtered_posts = []
        for post in posts:
            if post.get("author_screen_name", "").lower() != username.lower():
                continue
            if exclude_retweets and post.get("is_retweet_text"):
                continue
            filtered_posts.append(post)

        added = merge_posts(posts_by_id, filtered_posts)
        page_logs.append(
            {
                "page": page,
                "endpoint": "/search",
                "parsed": len(posts),
                "kept_new": added,
                "total_unique": len(posts_by_id),
            }
        )

        if len(posts_by_id) >= target_count:
            break

        bottom_cursor = next(
            (item.get("value") for item in cursors if item.get("cursorType") == "Bottom" and item.get("value")),
            None,
        )
        if not bottom_cursor or bottom_cursor in seen_cursors:
            break
        seen_cursors.add(bottom_cursor)
        cursor = str(bottom_cursor)
        time.sleep(0.8)

    return page_logs


def render_markdown(posts: list[dict], payload: dict) -> str:
    lines = [
        f"# @{payload['username']} 最近 {len(posts)} 条 X 帖子原文",
        "",
        f"- 账号：[@{payload['username']}](https://x.com/{payload['username']})",
        "- 数据源：RapidAPI Twittr/X API Free Tweets User Twitter Lookup",
        f"- 获取方式：{payload['collection_method']}",
        f"- userId：`{payload['user_id']}`",
        f"- 获取时间：{payload['fetched_at_utc']}",
        f"- 时间跨度：{payload['range']['oldest']} 至 {payload['range']['newest']} UTC",
        f"- 条数：{len(posts)}",
        f"- API 请求次数：{payload['request_count']}",
        "",
        "## 帖子列表",
        "",
    ]

    for index, post in enumerate(posts, 1):
        created_at = post.get("created_at_utc") or post.get("created_at_raw") or ""
        lines.extend(
            [
                f"### {index}. {created_at}",
                "",
                f"- 链接：[{post['id']}]({post['url']})",
                (
                    f"- 互动：赞 {post['favorite_count']} / 回复 {post['reply_count']} / "
                    f"转发 {post['retweet_count']} / 引用 {post['quote_count']} / "
                    f"收藏 {post['bookmark_count']} / 浏览 {post.get('view_count') or ''}"
                ),
                f"- 来源接口：{', '.join(post.get('source_endpoints', []))}",
            ]
        )
        if post.get("is_retweet_text"):
            lines.append("- 类型：转推文本")
        if post.get("in_reply_to_screen_name"):
            lines.append(
                f"- 回复：@{post['in_reply_to_screen_name']} / {post.get('in_reply_to_status_id') or ''}"
            )
        if post.get("media"):
            media_types = ", ".join(sorted({item.get("type") or "media" for item in post["media"]}))
            lines.append(f"- 媒体：{len(post['media'])} 项（{media_types}）")
        for expanded_url in post.get("expanded_urls", []):
            lines.append(f"- 展开链接：{expanded_url}")
        if post.get("quoted_tweet") and post["quoted_tweet"].get("url"):
            quoted = post["quoted_tweet"]
            lines.append(f"- 引用：[@{quoted.get('author_screen_name')}]({quoted.get('url')})")
        lines.extend(["", "原文：", ""])

        if post.get("text"):
            for paragraph in post["text"].splitlines():
                lines.append(f"> {paragraph}" if paragraph else ">")
        else:
            lines.append(">")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_output_paths(output_dir: Path, username: str, count: int, today: dt.date) -> tuple[Path, Path]:
    slug = username.replace("@", "").strip() or "unknown-user"
    json_path = output_dir / f"{slug}-x-recent-{count}-{today.isoformat()}.json"
    md_path = output_dir / f"{slug}-x-recent-{count}-{today.isoformat()}.md"
    return json_path, md_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recent X posts by username or userId.")
    parser.add_argument("--username", help="X username without @")
    parser.add_argument("--user-id", help="X userId / rest_id")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT, help="Target number of latest posts")
    parser.add_argument("--exclude-retweets", action="store_true", help="Drop retweet-text items from results")
    parser.add_argument("--output-dir", help="Write Markdown and JSON files into this directory")
    args = parser.parse_args()

    if not args.username and not args.user_id:
        raise SystemExit("Provide --username or --user-id.")
    if args.count <= 0:
        raise SystemExit("--count must be greater than 0.")

    api_keys = load_credentials()
    client = TwittrClient(api_keys)
    user_cache = load_user_cache()

    username = args.username.lstrip("@") if args.username else None
    user_id = args.user_id
    username, user_id, user_cache_updated = resolve_identity(client, user_cache, username, user_id)

    posts_by_id, timeline_logs = collect_user_timeline(
        client=client,
        user_id=user_id,
        username=username,
        target_count=args.count,
        exclude_retweets=args.exclude_retweets,
    )

    search_logs: list[dict] = []
    if len(posts_by_id) < args.count:
        search_logs = collect_search_fallback(
            client=client,
            username=username,
            target_count=args.count,
            exclude_retweets=args.exclude_retweets,
            posts_by_id=posts_by_id,
        )

    posts = list(posts_by_id.values())
    posts.sort(key=lambda item: item.get("created_at_utc") or "", reverse=True)
    posts = posts[: args.count]

    payload = {
        "username": username,
        "user_id": user_id,
        "count": len(posts),
        "target_count": args.count,
        "exclude_retweets": args.exclude_retweets,
        "collection_method": (
            "`/user/{userId}/tweets` 分页"
            + (" + `/search?query=from:<username>&type=Latest` 补齐" if search_logs else "")
        ),
        "used_search_fallback": bool(search_logs),
        "request_count": client.request_count,
        "failed_request_count": client.failed_request_count,
        "available_key_count": len(api_keys),
        "failed_keys": client.failed_keys,
        "user_cache_path": str(USER_CACHE_PATH),
        "user_cache_updated": user_cache_updated,
        "fetched_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "range": {
            "newest": posts[0]["created_at_utc"] if posts else "",
            "oldest": posts[-1]["created_at_utc"] if posts else "",
        },
        "page_logs": timeline_logs + search_logs,
        "posts": posts,
    }

    if args.output_dir:
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path, md_path = build_output_paths(output_dir, username, len(posts), dt.date.today())
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_markdown(posts, payload), encoding="utf-8")
        payload["output"] = {"json": str(json_path), "markdown": str(md_path)}

    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
