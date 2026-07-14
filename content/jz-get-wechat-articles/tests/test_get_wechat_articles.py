from __future__ import annotations

import importlib.util
import io
import sys
import unittest
from contextlib import redirect_stderr
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "get_wechat_articles.py"
SPEC = importlib.util.spec_from_file_location("get_wechat_articles", SCRIPT_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ParseArgsTest(unittest.TestCase):
    def test_defaults_match_daily_article_fetch(self) -> None:
        args = MODULE.parse_args(["--account", "示例公众号"])

        self.assertEqual(args.account, "示例公众号")
        self.assertEqual(args.mode, "latest")
        self.assertEqual(args.body_source, "wechat")
        self.assertEqual(args.delay, 1.5)
        self.assertTrue(args.compact_output)
        self.assertFalse(args.fetch_metrics)

    def test_backfill_and_metrics_options_use_new_names(self) -> None:
        args = MODULE.parse_args(
            [
                "--biz-id",
                "example-biz",
                "--source-url",
                "https://example.com/article",
                "--verification-code",
                "example-code",
                "--mode",
                "backfill",
                "--fetch-metrics",
                "--metrics-from-list-cache-only",
                "--no-run-dir",
                "--body-source",
                "api",
            ]
        )

        self.assertEqual(args.biz_id, "example-biz")
        self.assertEqual(args.source_url, "https://example.com/article")
        self.assertEqual(args.verification_code, "example-code")
        self.assertEqual(args.mode, "backfill")
        self.assertTrue(args.fetch_metrics)
        self.assertTrue(args.metrics_from_list_cache_only)
        self.assertTrue(args.no_run_dir)
        self.assertEqual(args.body_source, "api")

    def test_old_account_flag_is_rejected(self) -> None:
        with redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                MODULE.parse_args(["--name", "示例公众号"])

    def test_at_least_one_account_locator_is_required(self) -> None:
        args = MODULE.parse_args([])

        with self.assertRaisesRegex(ValueError, "--account"):
            MODULE.ensure_query_source(args)


class PersistentPathCompatibilityTest(unittest.TestCase):
    def test_existing_cache_and_database_names_are_preserved(self) -> None:
        output_dir = Path("output")

        self.assertEqual(
            MODULE.resolve_history_cache_dir(output_dir, "示例公众号"),
            output_dir / "示例公众号.history_pages",
        )
        self.assertEqual(
            MODULE.resolve_stats_db_path(output_dir, "示例公众号"),
            output_dir / "示例公众号.article_stats.sqlite",
        )


if __name__ == "__main__":
    unittest.main()
