#!/usr/bin/env python3
"""Initialize one Mailgun sending domain backed by Cloudflare DNS."""

from __future__ import annotations

import argparse
import base64
from email.utils import parseaddr
import json
import os
import re
import stat
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any


US_BASE_URL = "https://api.mailgun.net"
EU_BASE_URL = "https://api.eu.mailgun.net"
CONFIG_KEYS = (
    "MAILGUN_API_KEY",
    "MAILGUN_DOMAIN",
    "MAILGUN_API_BASE_URL",
    "EMAIL_FROM",
)


class SetupError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Set up a Mailgun domain, Cloudflare DNS, and a domain sending key."
    )
    parser.add_argument(
        "domain", help="Confirmed Mailgun domain, for example mg.example.com"
    )
    parser.add_argument(
        "--project-dir", default=".", help="Project receiving .dev.vars and .env"
    )
    parser.add_argument("--region", choices=("us", "eu"), default="us")
    parser.add_argument(
        "--confirmed-region",
        choices=("us", "eu"),
        required=True,
        help="Proof that the user confirmed the selected region",
    )
    parser.add_argument(
        "--confirm-mx-risk",
        action="store_true",
        help=(
            "Proceed after the user explicitly accepts MX conflict risk for a "
            "domain not beginning with mg. or mail."
        ),
    )
    parser.add_argument(
        "--email-from",
        required=True,
        help="Confirmed From address, optionally with a display name",
    )
    parser.add_argument(
        "--allow-custom-from-domain",
        action="store_true",
        help="Proceed after the user accepts From-domain alignment risk",
    )
    parser.add_argument(
        "--replace-email-from",
        action="store_true",
        help="Replace an existing EMAIL_FROM after explicit confirmation",
    )
    parser.add_argument("--poll-attempts", type=int, default=10)
    parser.add_argument("--poll-interval", type=float, default=4.0)
    return parser.parse_args()


def normalize_domain(value: str) -> str:
    domain = value.strip().lower().rstrip(".")
    if "://" in domain or "/" in domain or ":" in domain:
        raise SetupError("domain must be a hostname without scheme, path, or port")
    if len(domain) > 253 or not re.fullmatch(
        r"(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?",
        domain,
    ):
        raise SetupError("invalid domain")
    return domain


def requires_mx_risk_confirmation(domain: str) -> bool:
    return domain.split(".", 1)[0] not in {"mg", "mail"}


def validate_domain_confirmation(domain: str, confirm_mx_risk: bool) -> None:
    if requires_mx_risk_confirmation(domain) and not confirm_mx_risk:
        raise SetupError(
            "MX-risk guard: use a domain beginning with mg. or mail., or confirm "
            "the selected domain with --confirm-mx-risk"
        )


def normalize_email_from(
    value: str, mailgun_domain: str, allow_custom_domain: bool
) -> str:
    email_from = value.strip()
    if not email_from or "\r" in email_from or "\n" in email_from:
        raise SetupError("invalid EMAIL_FROM")
    _, address = parseaddr(email_from)
    if not re.fullmatch(r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[^@]+", address):
        raise SetupError("EMAIL_FROM must contain one valid email address")
    from_domain = normalize_domain(address.rsplit("@", 1)[1])
    if from_domain != mailgun_domain and not allow_custom_domain:
        raise SetupError(
            "EMAIL_FROM uses another domain; confirm DMARC alignment risk with "
            "--allow-custom-from-domain"
        )
    return email_from


def read_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] == '"':
            try:
                value = json.loads(value)
            except json.JSONDecodeError:
                value = value[1:-1]
        elif len(value) >= 2 and value[0] == value[-1] == "'":
            value = value[1:-1]
        values[key] = value
    return values


def first_value(sources: list[dict[str, str]], names: tuple[str, ...]) -> str:
    for source in sources:
        for name in names:
            value = source.get(name, "")
            if value:
                return value
    return ""


def project_env_sources(project_dir: Path) -> tuple[list[Path], list[dict[str, str]]]:
    paths = [
        project_dir / ".dev.vars",
        project_dir / ".env",
        project_dir / ".env.local",
        project_dir / ".env.production",
        project_dir / ".env.development",
    ]
    return paths, [read_env_file(path) for path in paths]


def check_git_safety(project_dir: Path, targets: list[Path]) -> bool:
    probe = subprocess.run(
        ["git", "-C", str(project_dir), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0:
        return False
    repo = Path(probe.stdout.strip()).resolve()
    for target in targets:
        if target.is_symlink():
            raise SetupError(
                f"refusing to write a symbolic-link config file: {target.name}"
            )
        try:
            relative = (target.parent.resolve() / target.name).relative_to(repo)
        except ValueError as exc:
            raise SetupError(
                f"config file is outside the Git repository: {target}"
            ) from exc
        tracked = subprocess.run(
            [
                "git",
                "-C",
                str(repo),
                "ls-files",
                "--error-unmatch",
                "--",
                str(relative),
            ],
            capture_output=True,
            text=True,
        )
        if tracked.returncode == 0:
            raise SetupError(f"refusing to write a tracked config file: {relative}")
        ignored = subprocess.run(
            ["git", "-C", str(repo), "check-ignore", "-q", "--no-index", str(relative)]
        )
        if ignored.returncode != 0:
            raise SetupError(f"refusing to write a Git-visible config file: {relative}")
    return True


def request_json(request: urllib.request.Request, attempts: int = 4) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            if exc.code < 500 or attempt == attempts - 1:
                raise
            last_error = exc
        except urllib.error.URLError as exc:
            if attempt == attempts - 1:
                raise
            last_error = exc
        time.sleep(attempt + 1)
    raise SetupError(f"request failed: {type(last_error).__name__}")


def safe_http_error(exc: urllib.error.HTTPError) -> str:
    try:
        body = json.loads(exc.read().decode(errors="replace"))
    except Exception:
        return f"HTTP {exc.code}"
    messages = []
    if body.get("message"):
        messages.append(str(body["message"]))
    for item in body.get("errors") or []:
        messages.append(str(item.get("message") or item.get("code") or "error"))
    return f"HTTP {exc.code}: {'; '.join(messages) or 'request failed'}"


def basic_auth(key: str) -> str:
    return "Basic " + base64.b64encode(f"api:{key}".encode()).decode()


def multipart(fields: dict[str, str]) -> tuple[bytes, str]:
    boundary = "----jz-mailgun-" + uuid.uuid4().hex
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                value.encode(),
                b"\r\n",
            ]
        )
    chunks.append(f"--{boundary}--\r\n".encode())
    return b"".join(chunks), boundary


def cf_get(base: str, token: str, path: str) -> dict[str, Any]:
    return request_json(
        urllib.request.Request(
            base + path, headers={"Authorization": f"Bearer {token}"}
        )
    )


def find_cloudflare_zone(token: str, domain: str) -> dict[str, Any]:
    base = "https://api.cloudflare.com/client/v4"
    labels = domain.split(".")
    try:
        for offset in range(0, len(labels) - 1):
            candidate = ".".join(labels[offset:])
            data = cf_get(
                base, token, "/zones?" + urllib.parse.urlencode({"name": candidate})
            )
            zones = data.get("result") or []
            if len(zones) == 1:
                zone = zones[0]
                cf_get(base, token, f"/zones/{zone['id']}/dns_records?per_page=1")
                return zone
    except urllib.error.HTTPError as exc:
        raise SetupError(
            "Cloudflare token cannot read the target Zone and DNS records; "
            "create a Zone Read + DNS Write project token"
        ) from exc
    raise SetupError("Cloudflare Zone not found for the confirmed domain")


def mailgun_domain(
    base_url: str, primary_key: str, domain: str
) -> dict[str, Any] | None:
    request = urllib.request.Request(
        f"{base_url}/v4/domains/{domain}",
        headers={"Authorization": basic_auth(primary_key)},
    )
    try:
        return request_json(request)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise SetupError(f"cannot read Mailgun domain: {safe_http_error(exc)}") from exc


def ensure_mailgun_domain(
    base_url: str, primary_key: str, domain: str
) -> tuple[dict[str, Any], bool]:
    current = mailgun_domain(base_url, primary_key, domain)
    if current is not None:
        return current, False
    body = urllib.parse.urlencode(
        {
            "name": domain,
            "use_automatic_sender_security": "true",
            "dkim_key_size": "2048",
        }
    ).encode()
    request = urllib.request.Request(
        f"{base_url}/v4/domains",
        data=body,
        method="POST",
        headers={
            "Authorization": basic_auth(primary_key),
            "Content-Type": "application/x-www-form-urlencoded",
        },
    )
    try:
        request_json(request)
    except urllib.error.HTTPError as exc:
        raise SetupError(
            f"cannot create Mailgun domain: {safe_http_error(exc)}"
        ) from exc
    result = mailgun_domain(base_url, primary_key, domain)
    if result is None:
        raise SetupError("Mailgun domain creation returned no readable domain")
    return result, True


def mailgun_dns_targets(
    domain_data: dict[str, Any], domain: str
) -> list[dict[str, Any]]:
    raw = (domain_data.get("sending_dns_records") or []) + (
        domain_data.get("receiving_dns_records") or []
    )
    targets: list[dict[str, Any]] = []
    seen: set[tuple[Any, ...]] = set()
    for record in raw:
        record_type = str(record["record_type"]).upper()
        name = str(record.get("name") or domain).rstrip(".")
        content = str(record["value"])
        priority = (
            int(record["priority"])
            if record.get("priority") not in (None, "")
            else None
        )
        key = (record_type, name.lower(), content.rstrip(".").lower(), priority)
        if key not in seen:
            seen.add(key)
            targets.append(
                {
                    "type": record_type,
                    "name": name,
                    "content": content,
                    "priority": priority,
                }
            )
    if not targets:
        raise SetupError("Mailgun returned no DNS records")
    return targets


def normalized_content(value: Any) -> str:
    return str(value).strip().strip('"').rstrip(".").lower()


def ensure_cloudflare_dns(
    token: str, zone_id: str, domain: str, targets: list[dict[str, Any]]
) -> tuple[int, int]:
    base = "https://api.cloudflare.com/client/v4"
    allowed: dict[tuple[str, str], set[tuple[str, int | None]]] = {}
    for target in targets:
        key = (target["type"], target["name"].lower())
        allowed.setdefault(key, set()).add(
            (normalized_content(target["content"]), target["priority"])
        )
    created = 0
    unchanged = 0
    for target in targets:
        query = urllib.parse.urlencode(
            {"type": target["type"], "name": target["name"], "per_page": 100}
        )
        try:
            existing = (
                cf_get(base, token, f"/zones/{zone_id}/dns_records?{query}").get(
                    "result"
                )
                or []
            )
        except urllib.error.HTTPError as exc:
            raise SetupError(
                f"cannot list Cloudflare DNS: {safe_http_error(exc)}"
            ) from exc
        target_pair = (normalized_content(target["content"]), target["priority"])
        exact = False
        for record in existing:
            priority = (
                int(record.get("priority", 0)) if target["type"] == "MX" else None
            )
            pair = (normalized_content(record.get("content", "")), priority)
            if pair == target_pair:
                exact = True
                break
        if exact:
            unchanged += 1
            continue
        key = (target["type"], target["name"].lower())
        for record in existing:
            content = normalized_content(record.get("content", ""))
            priority = (
                int(record.get("priority", 0)) if target["type"] == "MX" else None
            )
            if (
                target["type"] in {"CNAME", "MX"}
                and (content, priority) not in allowed[key]
            ):
                raise SetupError(
                    f"conflicting {target['type']} record exists at {target['name']}; refusing to overwrite"
                )
            if (
                target["type"] == "TXT"
                and normalized_content(target["content"]).startswith("v=spf1")
                and content.startswith("v=spf1")
            ):
                raise SetupError(
                    f"conflicting SPF record exists at {target['name']}; refusing to overwrite"
                )
        body: dict[str, Any] = {
            "type": target["type"],
            "name": target["name"],
            "content": target["content"],
            "ttl": 1,
            "comment": f"Mailgun setup for {domain}",
        }
        if target["priority"] is not None:
            body["priority"] = target["priority"]
        if target["type"] == "CNAME":
            body["proxied"] = False
        request = urllib.request.Request(
            f"{base}/zones/{zone_id}/dns_records",
            data=json.dumps(body).encode(),
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
        )
        try:
            response = request_json(request)
        except urllib.error.HTTPError as exc:
            raise SetupError(
                f"cannot create Cloudflare DNS: {safe_http_error(exc)}"
            ) from exc
        if not response.get("success"):
            raise SetupError(f"Cloudflare rejected {target['type']} {target['name']}")
        created += 1
    return created, unchanged


def verify_mailgun_domain(
    base_url: str,
    primary_key: str,
    domain: str,
    attempts: int,
    interval: float,
) -> dict[str, Any]:
    auth = {"Authorization": basic_auth(primary_key)}
    consecutive_active = 0
    latest: dict[str, Any] | None = None
    for attempt in range(1, attempts + 1):
        if attempt in (1, 5):
            request = urllib.request.Request(
                f"{base_url}/v4/domains/{domain}/verify",
                data=b"",
                method="PUT",
                headers=auth,
            )
            try:
                request_json(request)
            except urllib.error.HTTPError as exc:
                raise SetupError(
                    f"Mailgun verify failed: {safe_http_error(exc)}"
                ) from exc
        time.sleep(interval)
        latest = mailgun_domain(base_url, primary_key, domain)
        if latest is None:
            raise SetupError("Mailgun domain disappeared during verification")
        state = (latest.get("domain") or {}).get("state")
        consecutive_active = consecutive_active + 1 if state == "active" else 0
        if consecutive_active >= 2:
            records = (latest.get("sending_dns_records") or []) + (
                latest.get("receiving_dns_records") or []
            )
            invalid = [record for record in records if record.get("valid") != "valid"]
            if invalid:
                raise SetupError(
                    "Mailgun is active but some required DNS records are not valid"
                )
            return latest
    state = ((latest or {}).get("domain") or {}).get("state", "unknown")
    raise SetupError(
        f"Mailgun domain did not stabilize as active (last state: {state}); rerun after DNS propagation"
    )


def validate_sending_key(base_url: str, domain: str, key: str) -> bool:
    body, boundary = multipart({})
    request = urllib.request.Request(
        f"{base_url}/v3/{domain}/messages",
        data=body,
        method="POST",
        headers={
            "Authorization": basic_auth(key),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        request_json(request)
        return False
    except urllib.error.HTTPError as exc:
        return exc.code == 400


def create_sending_key(
    base_url: str, primary_key: str, domain: str, description: str
) -> tuple[str, str]:
    body, boundary = multipart(
        {
            "domain_name": domain,
            "kind": "domain",
            "description": description,
            "role": "sending",
        }
    )
    request = urllib.request.Request(
        f"{base_url}/v1/keys",
        data=body,
        method="POST",
        headers={
            "Authorization": basic_auth(primary_key),
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )
    try:
        response = request_json(request)
    except urllib.error.HTTPError as exc:
        raise SetupError(
            f"cannot create Domain Sending Key: {safe_http_error(exc)}"
        ) from exc
    key = response.get("key") or {}
    key_id = str(key.get("id") or "")
    if key.get("kind") != "domain" or key.get("role") != "sending":
        if key_id:
            revoke_key(base_url, primary_key, key_id)
        raise SetupError("Mailgun returned a key with the wrong scope")
    if key.get("domain_name") != domain or not key.get("secret") or not key.get("id"):
        if key_id:
            revoke_key(base_url, primary_key, key_id)
        raise SetupError("Mailgun returned an incomplete Domain Sending Key")
    return str(key["secret"]), key_id


def revoke_key(base_url: str, primary_key: str, key_id: str) -> None:
    request = urllib.request.Request(
        f"{base_url}/v1/keys/{key_id}",
        method="DELETE",
        headers={"Authorization": basic_auth(primary_key)},
    )
    try:
        request_json(request)
    except Exception:
        pass


def write_env_atomic(path: Path, updates: dict[str, str]) -> None:
    existing = path.read_text() if path.is_file() else ""
    output: list[str] = []
    seen: set[str] = set()
    for line in existing.splitlines():
        name = line.split("=", 1)[0].strip() if "=" in line else ""
        if name in updates:
            output.append(f"{name}={encode_env_value(updates[name])}")
            seen.add(name)
        else:
            output.append(line)
    for name, value in updates.items():
        if name not in seen:
            output.append(f"{name}={encode_env_value(value)}")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as handle:
            handle.write("\n".join(output).rstrip() + "\n")
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def encode_env_value(value: str) -> str:
    if re.fullmatch(r"[^\s#\"']+", value):
        return value
    return json.dumps(value, ensure_ascii=False)


def restore_file(path: Path, existed: bool, content: bytes, mode: int) -> None:
    if not existed:
        path.unlink(missing_ok=True)
        return
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.restore.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def ensure_sending_config(
    base_url: str,
    primary_key: str,
    domain: str,
    email_from: str,
    project_dir: Path,
    targets: list[Path],
    replace_email_from: bool,
) -> tuple[bool, str | None]:
    snapshots = {
        path: (
            path.exists(),
            path.read_bytes() if path.exists() else b"",
            stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o600,
        )
        for path in targets
    }
    current = [read_env_file(path) for path in targets]
    keys = validate_existing_sending_config(
        current, domain, base_url, email_from, replace_email_from
    )
    key = next(iter(keys), "")
    key_id: str | None = None
    created = False
    if key:
        if key == primary_key:
            raise SetupError(
                "refusing to store the Mailgun Primary Key as an application key"
            )
        if not validate_sending_key(base_url, domain, key):
            raise SetupError(
                "existing MAILGUN_API_KEY cannot authenticate the sending endpoint"
            )
    else:
        description_base = re.sub(r"[^a-z0-9-]+", "-", project_dir.name.lower()).strip(
            "-"
        )
        key, key_id = create_sending_key(
            base_url, primary_key, domain, f"{description_base or 'project'}-production"
        )
        created = True
        if not validate_sending_key(base_url, domain, key):
            revoke_key(base_url, primary_key, key_id)
            raise SetupError("new Domain Sending Key failed authentication")
    try:
        updates = {
            "MAILGUN_API_KEY": key,
            "MAILGUN_DOMAIN": domain,
            "MAILGUN_API_BASE_URL": base_url,
            "EMAIL_FROM": email_from,
        }
        for path in targets:
            write_env_atomic(path, updates)
    except Exception:
        for path, snapshot in snapshots.items():
            try:
                restore_file(path, *snapshot)
            except Exception:
                pass
        if created and key_id:
            revoke_key(base_url, primary_key, key_id)
        raise
    return created, key_id


def validate_existing_sending_config(
    current: list[dict[str, str]],
    domain: str,
    base_url: str,
    email_from: str,
    replace_email_from: bool,
) -> set[str]:
    keys = {
        source.get("MAILGUN_API_KEY", "")
        for source in current
        if source.get("MAILGUN_API_KEY")
    }
    if len(keys) > 1:
        raise SetupError("MAILGUN_API_KEY differs between target config files")
    existing_from_values = {
        source.get("EMAIL_FROM", "") for source in current if source.get("EMAIL_FROM")
    }
    if len(existing_from_values) > 1 and not replace_email_from:
        raise SetupError(
            "EMAIL_FROM differs between target config files; confirm replacement with "
            "--replace-email-from"
        )
    if (
        any(existing != email_from for existing in existing_from_values)
        and not replace_email_from
    ):
        raise SetupError(
            "existing EMAIL_FROM differs from the confirmed value; use --replace-email-from "
            "after confirmation"
        )
    for source in current:
        existing_domain = source.get("MAILGUN_DOMAIN")
        existing_base = source.get("MAILGUN_API_BASE_URL")
        if existing_domain and existing_domain != domain:
            raise SetupError("existing MAILGUN_DOMAIN targets another domain")
        if existing_base and existing_base.rstrip("/") != base_url:
            raise SetupError("existing MAILGUN_API_BASE_URL targets another region")
    return keys


def main() -> int:
    args = parse_args()
    try:
        domain = normalize_domain(args.domain)
        email_from = normalize_email_from(
            args.email_from, domain, args.allow_custom_from_domain
        )
        if args.confirmed_region != args.region:
            raise SetupError("confirmed region does not match selected region")
        validate_domain_confirmation(domain, args.confirm_mx_risk)
        project_dir = Path(args.project_dir).expanduser().resolve()
        if not project_dir.is_dir():
            raise SetupError("project directory does not exist")
        targets = [project_dir / ".dev.vars", project_dir / ".env"]
        git_ignored = check_git_safety(project_dir, targets)
        _, project_sources = project_env_sources(project_dir)
        local_config = read_env_file(
            Path("~/.config/skills/jz-setup-mailgun-domain/.env").expanduser()
        )
        primary_key = first_value(
            project_sources + [local_config], ("MAILGUN_PRIMARY_API_KEY",)
        )
        cf_token = first_value(
            project_sources, ("CLOUDFLARE_DNS_API_TOKEN", "CLOUDFLARE_API_TOKEN")
        )
        if not primary_key:
            raise SetupError(
                "MAILGUN_PRIMARY_API_KEY not found in project or skill local config"
            )
        if not cf_token:
            raise SetupError("Cloudflare project DNS token not found")
        base_url = US_BASE_URL if args.region == "us" else EU_BASE_URL
        validate_existing_sending_config(
            [read_env_file(path) for path in targets],
            domain,
            base_url,
            email_from,
            args.replace_email_from,
        )
        zone = find_cloudflare_zone(cf_token, domain)
        domain_data, domain_created = ensure_mailgun_domain(
            base_url, primary_key, domain
        )
        targets_dns = mailgun_dns_targets(domain_data, domain)
        dns_created, dns_unchanged = ensure_cloudflare_dns(
            cf_token, str(zone["id"]), domain, targets_dns
        )
        verified = verify_mailgun_domain(
            base_url,
            primary_key,
            domain,
            attempts=args.poll_attempts,
            interval=args.poll_interval,
        )
        key_created, key_id = ensure_sending_config(
            base_url,
            primary_key,
            domain,
            email_from,
            project_dir,
            targets,
            args.replace_email_from,
        )
        final_sources = [read_env_file(path) for path in targets]
        if any(source.get("MAILGUN_DOMAIN") != domain for source in final_sources):
            raise SetupError("final config verification failed")
        if len({source.get("MAILGUN_API_KEY") for source in final_sources}) != 1:
            raise SetupError("final Mailgun key values do not match")
        if any(source.get("EMAIL_FROM") != email_from for source in final_sources):
            raise SetupError("final EMAIL_FROM values do not match")
        summary = {
            "domain": domain,
            "region": args.region,
            "base_url": base_url,
            "email_from": email_from,
            "mailgun_state": (verified.get("domain") or {}).get("state"),
            "domain_created": domain_created,
            "dns_records": len(targets_dns),
            "dns_created": dns_created,
            "dns_unchanged": dns_unchanged,
            "sending_key_created": key_created,
            "sending_key_id": key_id,
            "config_files": [path.name for path in targets],
            "config_variables": list(CONFIG_KEYS),
            "git_ignore_checked": git_ignored,
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except SetupError as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
