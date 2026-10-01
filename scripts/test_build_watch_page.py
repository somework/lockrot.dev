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


def history_row(name, date="2026-09-15", tag="v1.2.3", lockrot="0.10.0", **counts):
    row = {f: "" for f in bw.HISTORY_FIELDS}
    row.update(
        date=date, lockrot=lockrot, kind="release", repo=f"acme/{name}", tag=tag,
        commit="c0ffee1234567890", packages="10", name=name,
        **{c: "0" for c in bw.COUNTED}, unknown="0", marked_on_packagist="0",
    )
    row.update({k.replace("_", "-"): str(v) for k, v in counts.items()})
    return row


class TableTest(unittest.TestCase):
    def test_totals_every_column(self):
        rows = bw.rows(
            manifest("one", "two"),
            {"one": report({"abandoned": 2}, checked=10), "two": report({"abandoned": 5}, checked=7)},
        )

        table = bw.table(rows)

        self.assertIn("<tfoot><tr><td>2 projects</td><td></td><td>17</td><td>7</td>", table)

    def test_the_project_name_opens_its_report(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report()}))

        self.assertIn(f'href="{bw.VIEWER}/one"', table)
        self.assertIn('<span class="lockrot-owner">acme/</span>one</a>', table)

    def test_names_the_release_and_the_commit_it_read(self):
        table = bw.table(bw.rows(manifest("one", tag="2.6.15"), {"one": report()}))

        self.assertIn('<a href="https://github.com/acme/one/releases/tag/2.6.15">2.6.15</a>', table)
        self.assertIn('href="https://github.com/acme/one/tree/c0ffee1234567890"><code>c0ffee1</code>', table)

    def test_a_count_carries_its_sort_value_and_its_shade(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report({"abandoned": 7, "stale": 0})}))

        self.assertIn('<td data-sort="7" class="lockrot-heat-3">7</td>', table)
        # stale is not shaded; a zero in it only recedes.
        self.assertIn('<td data-sort="0" class="lockrot-zero">0</td>', table)

    def test_shades_by_fixed_steps(self):
        self.assertEqual(
            ["lockrot-zero", "lockrot-heat-1", "lockrot-heat-2", "lockrot-heat-2", "lockrot-heat-3", "lockrot-heat-4"],
            [bw.heat(v) for v in (0, 1, 2, 4, 5, 10)],
        )

    def test_prints_the_heaviest_projects_first(self):
        rows = bw.rows(
            manifest("calm", "loud", "quiet"),
            {
                "calm": report({"silent": 1}),
                "loud": report({"abandoned": 4}),
                "quiet": report({"silent": 3}),
            },
        )

        self.assertEqual(["loud", "quiet", "calm"], [r["name"] for r in bw.order(rows)])

    def test_escapes_what_a_project_named_itself(self):
        rows = bw.rows(manifest("one", tag="<b>1.0</b>"), {"one": report()})

        self.assertNotIn("<b>1.0</b>", bw.table(rows))
        self.assertIn("&lt;b&gt;1.0&lt;/b&gt;", bw.table(rows))

    def test_headings_sort_counts_as_numbers_and_break_only_at_a_hyphen(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report()}))

        self.assertIn('data-sort-method="number" data-sort-reverse><code>left-<wbr>behind</code>', table)
        self.assertIn('<th data-sort-method="none">Release</th>', table)


class CompareTest(unittest.TestCase):
    def test_the_previous_run_is_the_newest_one_before_this(self):
        history = [history_row("one", date=d) for d in ("2026-09-01", "2026-09-08", "2026-09-15")]

        since, previous = bw.previous_run(history, "2026-09-15")

        self.assertEqual("2026-09-08", since)
        self.assertEqual({"one"}, set(previous))

    def test_the_first_run_has_nothing_to_compare_with(self):
        self.assertEqual((None, {}), bw.previous_run([], "2026-09-15"))

    def test_marks_how_far_a_count_moved(self):
        rows = bw.rows(manifest("one"), {"one": report({"abandoned": 5, "silent": 1})})
        previous = {"one": history_row("one", abandoned=3, silent=2)}

        table = bw.table(rows, previous, "2026-09-15")

        self.assertIn('lockrot-delta-up" title="+2 since 2026-09-15">+2</span>', table)
        self.assertIn(f'lockrot-delta-down" title="{bw.MINUS}1 since 2026-09-15">{bw.MINUS}1</span>', table)

    def test_a_count_that_held_carries_no_mark(self):
        rows = bw.rows(manifest("one"), {"one": report({"abandoned": 3})})

        table = bw.table(rows, {"one": history_row("one", abandoned=3)}, "2026-09-15")

        self.assertNotIn("lockrot-delta", table)

    def test_a_new_release_is_marked_with_the_one_before_it(self):
        rows = bw.rows(manifest("one", tag="v1.3.0"), {"one": report()})

        table = bw.table(rows, {"one": history_row("one", tag="v1.2.3")}, "2026-09-15")

        self.assertIn('<span class="lockrot-new" title="v1.2.3 on 2026-09-15">new</span>', table)

    def test_a_project_new_to_the_list_is_not_compared(self):
        rows = bw.rows(manifest("one", "two"), {"one": report({"silent": 2}), "two": report({"silent": 9})})

        table = bw.table(rows, {"one": history_row("one", silent=1)}, "2026-09-15")

        self.assertEqual(1, table.count("lockrot-delta-up"))
        # The total is not compared either: it moved because the list grew.
        self.assertNotIn("lockrot-delta", table[table.index("<tfoot>"):])

    def test_the_summary_names_the_tool_when_it_changed(self):
        rows = bw.rows(manifest("one"), {"one": report({"stale": 4}, version="0.11.0")})
        previous = {"one": history_row("one", stale=6, lockrot="0.10.0")}

        line = bw.since_line(rows, previous, "2026-09-15")

        self.assertIn("Compared with the run of 2026-09-15: `stale` 6 → 4.", line)
        self.assertIn("lockrot itself moved from 0.10.0 to 0.11.0", line)

    def test_the_summary_names_the_projects_that_released(self):
        rows = bw.rows(manifest("one", tag="v2.0.0"), {"one": report()})

        line = bw.since_line(rows, {"one": history_row("one", tag="v1.0.0")}, "2026-09-15")

        self.assertIn("no total moved.", line)
        self.assertIn("Since then 1 project moved to a new release or starter version: one.", line)


class ArchiveTest(unittest.TestCase):
    def test_lists_every_run_newest_first_with_a_link_per_report(self):
        history = [
            history_row("one", date="2026-09-08", abandoned=2),
            history_row("two", date="2026-09-08", abandoned=1, silent=4),
            history_row("one", date="2026-09-15", lockrot="0.11.0"),
        ]

        archive = bw.archive(history)

        self.assertLess(archive.index("2026-09-15"), archive.index("2026-09-08"))
        self.assertIn("lockrot 0.11.0 · 1 reports", archive)
        self.assertIn("2 reports · 3 abandoned, 4 silent", archive)
        self.assertIn(f'href="{bw.VIEWER}/2026-09-08/two"', archive)


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
        self.assertIn('<td data-sort="3" class="lockrot-heat-2">3</td>', bw.starter_table(rows))

    def test_the_starter_table_links_the_package_and_the_report(self):
        table = bw.starter_table(bw.rows(starter_manifest(), {"new-laravel": report()}))

        self.assertIn(
            '<a href="https://packagist.org/packages/laravel/laravel">laravel/laravel</a> <code>v13.10.1</code>',
            table,
        )
        self.assertIn(f'href="{bw.VIEWER}/new-laravel" title="Open the report lockrot wrote">Laravel</a>', table)


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
        # The run's own name, which tells apart three starters built from one package.
        self.assertEqual("one", written[-1]["name"])


if __name__ == "__main__":
    unittest.main()
