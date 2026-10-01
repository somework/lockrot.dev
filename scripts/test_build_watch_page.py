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


def flagged_report(**by_verdict):
    """A report whose findings name each flagged package, as lockrot writes them."""
    rep = report({v.replace("_", "-"): len(p) for v, p in by_verdict.items()})
    rep["findings"] = [
        {"package": name, "verdict": v.replace("_", "-"), "signals": []}
        for v, packages in by_verdict.items() for name in packages
    ]
    return rep


def view(abandoned=(), advisories=(), version="2.10.3"):
    return {"version": version, "abandoned": list(abandoned), "advisories": list(advisories)}


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

        self.assertIn("<tfoot><tr><td>2 projects</td><td></td><td>17</td>", table)
        self.assertIn(
            '<td class="lockrot-flagged">7 <span class="lockrot-share">41%</span></td>'
            '<td class="lockrot-missed">—</td><td>7</td>',
            table,
        )

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

    def test_prints_the_most_flagged_first_and_abandoned_breaks_a_tie(self):
        rows = bw.rows(
            manifest("calm", "loud", "quiet", "wide"),
            {
                "calm": report({"silent": 1}),
                "loud": report({"abandoned": 4}),
                "quiet": report({"silent": 4}),
                "wide": report({"left-behind": 9}),
            },
        )

        self.assertEqual(["wide", "loud", "quiet", "calm"], [r["name"] for r in bw.order(rows)])

    def test_the_flagged_heading_is_the_sort_the_rows_arrive_in(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report()}))

        self.assertIn("data-sort-default>Flagged</th>", table)
        self.assertEqual(1, table.count("data-sort-default"))

    def test_escapes_what_a_project_named_itself(self):
        rows = bw.rows(manifest("one", tag="<b>1.0</b>"), {"one": report()})

        self.assertNotIn("<b>1.0</b>", bw.table(rows))
        self.assertIn("&lt;b&gt;1.0&lt;/b&gt;", bw.table(rows))

    def test_headings_sort_counts_as_numbers_and_break_only_at_a_hyphen(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report()}))

        self.assertIn('data-sort-method="number" data-sort-reverse><code>left-<wbr>behind</code>', table)
        self.assertIn('<th data-sort-method="none">Release</th>', table)


class FlaggedTest(unittest.TestCase):
    def test_is_the_six_verdicts_and_nothing_else(self):
        counts = {"abandoned": 1, "silent": 2, "pinned": 3, "left-behind": 4, "old-promise": 5, "stale": 6}
        rows = bw.rows(manifest("one"), {"one": report({**counts, "unknown": 7, "finished": 8, "ok": 9})})

        self.assertEqual(21, bw.flagged(rows[0]))
        self.assertEqual(21, bw.flagged(history_row("one", **{k.replace("-", "_"): v for k, v in counts.items()})))

    def test_shows_the_count_its_share_of_the_lock_and_how_far_it_moved(self):
        rows = bw.rows(manifest("one"), {"one": report({"abandoned": 2, "stale": 3}, checked=20)})

        table = bw.table(rows, {"one": history_row("one", stale=1)}, "2026-09-15")

        self.assertIn(
            '<td data-sort="5" class="lockrot-flagged">5 <span class="lockrot-share">25%</span>'
            ' <span class="lockrot-delta lockrot-delta-up" title="+4 since 2026-09-15">+4</span></td>',
            table,
        )

    def test_an_empty_lock_has_no_share_to_divide_by(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report(checked=0)}))

        self.assertIn('class="lockrot-flagged lockrot-zero">0 <span class="lockrot-share">0%</span>', table)

    def test_the_summary_leads_with_the_flagged_total(self):
        rows = bw.rows(manifest("one"), {"one": report({"silent": 3})})

        line = bw.since_line(rows, {"one": history_row("one", silent=1)}, "2026-09-15")

        self.assertIn("Compared with the run of 2026-09-15: flagged 1 → 3; `silent` 1 → 3.", line)


class ComposerTest(unittest.TestCase):
    def test_counts_the_flagged_packages_composer_audit_names_for_nothing(self):
        rep = flagged_report(abandoned=["a/marked", "a/archived"], silent=["s/quiet"], stale=["s/cve"])

        # a/marked is in the lock's abandoned marker; s/cve has an advisory; the rest are not named.
        missed = bw.composer_missed(rep, view(abandoned=["a/marked", "x/not-flagged"], advisories=["s/cve"]))

        self.assertEqual(2, missed)

    def test_a_run_that_did_not_ask_composer_has_no_number(self):
        self.assertEqual("", bw.composer_missed(flagged_report(silent=["s/quiet"]), None))

    def test_refuses_a_report_whose_findings_do_not_add_up(self):
        rep = flagged_report(silent=["s/quiet"])
        rep["counts"]["silent"] = 2

        with self.assertRaises(SystemExit):
            bw.composer_missed(rep, view())

    def test_the_cell_shows_the_count_and_its_share_of_the_flagged(self):
        rows = bw.rows(
            manifest("one"),
            {"one": flagged_report(abandoned=["a/a"], silent=["s/a", "s/b", "s/c"])},
            {"one": view(abandoned=["a/a"])},
        )

        self.assertIn('class="lockrot-missed">3 <span class="lockrot-share">75%</span></td>', bw.table(rows))

    def test_an_unmeasured_row_shows_a_dash_that_sorts_last(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report()}))

        self.assertIn('<td data-sort="-1" class="lockrot-missed lockrot-zero" title="Not measured in this run">—</td>', table)

    def test_the_headline_needs_every_application_measured(self):
        measured = bw.rows(
            manifest("one", "two"),
            {"one": flagged_report(silent=["s/a", "s/b"]), "two": flagged_report(abandoned=["a/a"])},
            {"one": view(), "two": view(abandoned=["a/a"])},
        )

        self.assertIn("Of the **3** packages lockrot flags in these 2 applications, `composer audit` names 1.", bw.headline(measured))
        self.assertIn("the other **2**.", bw.headline(measured))
        self.assertEqual("", bw.headline(bw.rows(manifest("one"), {"one": report()})))

    def test_the_note_names_the_composer_version_that_ran(self):
        rows = bw.rows(manifest("one"), {"one": flagged_report(silent=["s/a"])}, {"one": view(version="2.10.3")})

        self.assertIn("(Composer 2.10.3)", bw.composer_note(rows))
        self.assertEqual("", bw.composer_note(bw.rows(manifest("one"), {"one": report()})))

    def test_the_history_keeps_the_number(self):
        rows = bw.rows(manifest("one"), {"one": flagged_report(silent=["s/a"])}, {"one": view()})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            bw.write_history(path, rows)
            self.assertEqual("1", bw.read_history(path)[0]["composer_missed"])


def with_run(target="8.4", release=5, push=5, flagged=None):
    rep = report()
    rep["run"] = {
        "target_php": target,
        "thresholds": {"release-high-years": release, "push-high-years": push},
        "flagged_verdicts": list(bw.COLUMNS) if flagged is None else flagged,
    }
    return rep


class SettingsTest(unittest.TestCase):
    def test_reads_the_target_and_the_silent_years_from_the_run(self):
        settings = bw.run_settings({"one": with_run(target="8.5", release=4, push=4)})

        self.assertEqual("8.5", settings["target_php"])
        self.assertEqual("no stable release and no push to any branch for 4 years", settings["silent_span"])

    def test_names_both_spans_when_they_differ(self):
        settings = bw.run_settings({"one": with_run(release=5, push=3)})

        self.assertEqual(
            "no stable release for 5 years and no push to any branch for 3", settings["silent_span"]
        )

    def test_refuses_reports_measured_against_different_php(self):
        with self.assertRaises(SystemExit):
            bw.run_settings({"one": with_run(target="8.4"), "two": with_run(target="8.3")})

    def test_refuses_a_lockrot_that_flags_a_verdict_the_page_has_no_column_for(self):
        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"one": with_run(flagged=[*bw.COLUMNS, "unmaintained"])})

        self.assertIn("unmaintained", str(raised.exception))

    def test_names_the_starters_without_a_lock_from_the_project_list(self):
        rows = bw.rows(starter_manifest(), {"new-laravel": report()})
        projects = {"starters": [
            {"name": "new-laravel", "title": "Laravel", "no_lock_in_repository": True},
            {"name": "new-gone", "title": "Gone", "no_lock_in_repository": True},
        ]}

        # Only the starters this run actually has.
        self.assertEqual("Laravel", bw.lockless(projects, rows))

    def test_joins_several_names_as_prose(self):
        rows = [{"name": n} for n in ("a", "b", "c")]
        projects = {"starters": [{"name": n, "title": n.upper(), "no_lock_in_repository": True} for n in "abc"]}

        self.assertEqual("A, B and C", bw.lockless(projects, rows))


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

        rows_html = table[table.index("<tbody>"):table.index("</tbody>")].split("<tr>")
        two = next(r for r in rows_html if "/two" in r)
        one = next(r for r in rows_html if "/one" in r)
        self.assertNotIn("lockrot-delta", two)
        self.assertIn("lockrot-delta-up", one)
        # The total is not compared either: it moved because the list grew.
        self.assertNotIn("lockrot-delta", table[table.index("<tfoot>"):])

    def test_the_summary_names_the_tool_when_it_changed(self):
        rows = bw.rows(manifest("one"), {"one": report({"stale": 4}, version="0.11.0")})
        previous = {"one": history_row("one", stale=6, lockrot="0.10.0")}

        line = bw.since_line(rows, previous, "2026-09-15")

        self.assertIn("Compared with the run of 2026-09-15: flagged 6 → 4; `stale` 6 → 4.", line)
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
