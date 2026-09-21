#!/usr/bin/env python3
"""Unit tests for scripts/build_watch_page.py."""

from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

import build_watch_page as bw


def report(counts=None, checked=10, marked=0, version="0.10.0"):
    counts = {**{c: 0 for c in bw.COLUMNS}, "unknown": 0, "finished": 0, "ok": 0, **(counts or {})}
    findings = [
        {"package": f"vendor/p{i}", "signals": [{"id": "S1"}]} for i in range(marked)
    ]
    return {
        "lockrot": {"version": version, "schema": 1},
        "packages_checked": checked,
        "counts": counts,
        "findings": findings,
    }


def manifest(*names, date="2026-09-22", tag="v1.2.3"):
    return {
        "run": {"date": date},
        "projects": [
            {
                "name": n,
                "repo": f"acme/{n}",
                "tag": tag,
                "tag_url": f"https://github.com/acme/{n}/releases/tag/{tag}",
                "commit": "c0ffee1234567890",
                "commit_url": f"https://github.com/acme/{n}/tree/c0ffee1234567890",
            }
            for n in names
        ],
    }


class RowsTest(unittest.TestCase):
    def test_carries_the_counts_the_run_wrote(self):
        rows = bw.rows(manifest("one"), {"one": report({"abandoned": 3, "silent": 2}, checked=40)})

        self.assertEqual(1, len(rows))
        self.assertEqual(40, rows[0]["packages"])
        self.assertEqual(3, rows[0]["abandoned"])
        self.assertEqual("0.10.0", rows[0]["lockrot"])
        self.assertEqual("2026-09-22", rows[0]["date"])

    def test_counts_the_packagist_marker_out_of_the_findings(self):
        rows = bw.rows(manifest("one"), {"one": report({"abandoned": 4}, marked=3)})

        self.assertEqual(3, rows[0]["marked_on_packagist"])

    def test_refuses_a_run_that_left_a_project_out(self):
        with self.assertRaises(SystemExit):
            bw.rows(manifest("one", "two"), {"one": report()})


class TableTest(unittest.TestCase):
    def test_totals_every_column(self):
        rows = bw.rows(
            manifest("one", "two"),
            {"one": report({"abandoned": 2}, checked=10), "two": report({"abandoned": 5}, checked=7)},
        )

        table = bw.table(rows)

        self.assertIn("| **2 projects** | | **17** |", table)
        self.assertIn("**7**", table)
        self.assertIn(f"{bw.VIEWER}/one.html", table)

    def test_names_the_release_and_the_commit_it_read(self):
        rows = bw.rows(manifest("one", tag="2.6.15"), {"one": report()})

        table = bw.table(rows)

        self.assertIn("[2.6.15](https://github.com/acme/one/releases/tag/2.6.15)", table)
        self.assertIn("[`c0ffee1`](https://github.com/acme/one/tree/c0ffee1234567890)", table)


def starter_manifest(name="new-laravel", date="2026-09-22"):
    return {
        "run": {"date": date},
        "projects": [
            {
                "kind": "starter",
                "name": name,
                "title": "Laravel",
                "package": "laravel/laravel",
                "version": "v13.10.1",
                "packagist_url": "https://packagist.org/packages/laravel/laravel",
                "command": "composer create-project laravel/laravel:v13.10.1 .",
            }
        ],
    }


def with_advisories(count):
    rep = report()
    rep["findings"] = [
        {"package": f"vendor/p{i}", "signals": [{"id": "S9"}]} for i in range(count)
    ]
    return rep


class StarterTest(unittest.TestCase):
    def test_a_starter_row_carries_the_command_rather_than_a_commit(self):
        rows = bw.rows(starter_manifest(), {"new-laravel": report(checked=76)})

        self.assertEqual("starter", rows[0]["kind"])
        self.assertEqual("laravel/laravel", rows[0]["package"])
        self.assertEqual("", rows[0]["commit"])
        self.assertIn("create-project", rows[0]["command"])

    def test_counts_the_packages_an_advisory_affects(self):
        rows = bw.rows(starter_manifest(), {"new-laravel": with_advisories(3)})

        self.assertEqual(3, rows[0]["advisories"])
        self.assertIn("**3**", bw.starter_table(rows))

    def test_the_starter_table_links_the_package_and_the_report(self):
        table = bw.starter_table(bw.rows(starter_manifest(), {"new-laravel": report()}))

        self.assertIn("[laravel/laravel v13.10.1](https://packagist.org/packages/laravel/laravel)", table)
        self.assertIn(f"{bw.VIEWER}/new-laravel.html", table)
        self.assertIn("| Laravel |", table)


class HistoryTest(unittest.TestCase):
    def test_a_rerun_of_the_same_day_replaces_that_day_rather_than_doubling_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            bw.write_history(path, bw.rows(manifest("one", date="2026-09-15"), {"one": report()}))
            bw.write_history(
                path, bw.rows(manifest("one", date="2026-09-22"), {"one": report({"silent": 1})})
            )
            bw.write_history(
                path, bw.rows(manifest("one", date="2026-09-22"), {"one": report({"silent": 4})})
            )

            with path.open(newline="", encoding="utf-8") as fh:
                written = list(csv.DictReader(fh))

        self.assertEqual(["2026-09-15", "2026-09-22"], [r["date"] for r in written])
        self.assertEqual("4", written[-1]["silent"])


if __name__ == "__main__":
    unittest.main()
