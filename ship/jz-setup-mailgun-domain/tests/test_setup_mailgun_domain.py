from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "setup_mailgun_domain.py"
SPEC = importlib.util.spec_from_file_location("setup_mailgun_domain", SCRIPT)
assert SPEC and SPEC.loader
mailgun = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mailgun)


class GitSafetyTests(unittest.TestCase):
    def test_refuses_tracked_env_targets_even_when_ignored(self) -> None:
        for target_name in (".env", ".dev.vars"):
            with self.subTest(target=target_name), tempfile.TemporaryDirectory() as tmp:
                project = Path(tmp)
                subprocess.run(["git", "init", "-q", str(project)], check=True)
                (project / ".gitignore").write_text(".env\n.dev.vars\n")
                target = project / target_name
                target.write_text("SECRET=tracked\n")
                subprocess.run(
                    ["git", "-C", str(project), "add", "-f", target_name], check=True
                )

                with self.assertRaisesRegex(mailgun.SetupError, "tracked config file"):
                    mailgun.check_git_safety(project, [target])

    def test_non_git_project_remains_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            self.assertFalse(mailgun.check_git_safety(project, [project / ".env"]))


class DomainConfirmationTests(unittest.TestCase):
    def test_mg_and_mail_prefixes_do_not_need_extra_confirmation(self) -> None:
        for domain in ("mg.example.com", "mail.example.co.za"):
            with self.subTest(domain=domain):
                mailgun.validate_domain_confirmation(domain, confirm_mx_risk=False)

    def test_other_prefixes_and_bare_domains_require_confirmation(self) -> None:
        for domain in (
            "mgx.example.com",
            "mailing.example.com",
            "example.com",
            "example.co.za",
        ):
            with self.subTest(domain=domain):
                with self.assertRaisesRegex(mailgun.SetupError, "--confirm-mx-risk"):
                    mailgun.validate_domain_confirmation(domain, confirm_mx_risk=False)
                mailgun.validate_domain_confirmation(domain, confirm_mx_risk=True)


class SendingConfigTests(unittest.TestCase):
    def test_existing_email_from_conflict_stops_before_remote_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            env = project / ".env"
            dev_vars = project / ".dev.vars"
            env.write_text(
                "MAILGUN_PRIMARY_API_KEY=primary-key\n"
                "CLOUDFLARE_DNS_API_TOKEN=cf-token\n"
                "EMAIL_FROM=old@mg.example.com\n"
            )
            dev_vars.write_text("EMAIL_FROM=new@mg.example.com\n")
            args = mock.Mock(
                domain="mg.example.com",
                project_dir=str(project),
                region="us",
                confirmed_region="us",
                confirm_mx_risk=False,
                email_from="confirmed@mg.example.com",
                allow_custom_from_domain=False,
                replace_email_from=False,
                poll_attempts=1,
                poll_interval=0,
            )

            with (
                mock.patch.object(mailgun, "parse_args", return_value=args),
                mock.patch.object(mailgun, "find_cloudflare_zone") as remote_call,
                mock.patch.dict(mailgun.os.environ, {"HOME": str(project)}),
                mock.patch.object(mailgun.os.sys, "stderr"),
            ):
                self.assertEqual(mailgun.main(), 1)

            remote_call.assert_not_called()

    def test_new_key_is_revoked_and_files_restored_when_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            env = project / ".env"
            dev_vars = project / ".dev.vars"
            env.write_text("EXISTING=env\n")
            dev_vars.write_text("EXISTING=dev\n")
            original_env = env.read_bytes()
            original_dev_vars = dev_vars.read_bytes()
            real_write = mailgun.write_env_atomic
            calls = 0

            def fail_second_write(path: Path, updates: dict[str, str]) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated write failure")
                real_write(path, updates)

            with (
                mock.patch.object(
                    mailgun,
                    "create_sending_key",
                    return_value=("domain-key", "key-id"),
                ),
                mock.patch.object(mailgun, "validate_sending_key", return_value=True),
                mock.patch.object(
                    mailgun, "write_env_atomic", side_effect=fail_second_write
                ),
                mock.patch.object(mailgun, "revoke_key") as revoke,
            ):
                with self.assertRaisesRegex(OSError, "simulated write failure"):
                    mailgun.ensure_sending_config(
                        mailgun.US_BASE_URL,
                        "primary-key",
                        "mg.example.com",
                        "noreply@mg.example.com",
                        project,
                        [dev_vars, env],
                        replace_email_from=False,
                    )

            revoke.assert_called_once_with(mailgun.US_BASE_URL, "primary-key", "key-id")
            self.assertEqual(dev_vars.read_bytes(), original_dev_vars)
            self.assertEqual(env.read_bytes(), original_env)


if __name__ == "__main__":
    unittest.main()
