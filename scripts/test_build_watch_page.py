#!/usr/bin/env python3
"""Unit tests for scripts/build_watch_page.py."""

from __future__ import annotations

import csv
import gzip
import json
import tempfile
import unittest
from pathlib import Path

import build_watch_page as bw

FIXTURES = Path(__file__).parent / "fixtures" / "report-2"


def fixture(name):
    """A document lockrot wrote (see fixtures/report-2/README.md), as a fresh copy per test."""
    path = FIXTURES / name
    raw = gzip.decompress(path.read_bytes()) if path.suffix == ".gz" else path.read_bytes()
    return json.loads(raw)


def report(counts=None, checked=10, marked=0, version="0.10.0"):
    counts = {**{c: 0 for c in bw.VERDICTS}, "unknown": 0, "finished": 0, "ok": 0, **(counts or {})}
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
        **{c: "0" for c in ("advisories", *bw.VERDICTS)}, unknown="0", marked_on_packagist="0",
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
        table = bw.table(bw.rows(manifest("one"), {"one": report({"abandoned": 7, "stale": 12})}))
        row = table[table.index("<tbody><tr>"):table.index("</tr></tbody>")]

        self.assertIn('<td data-sort="7" class="lockrot-heat-3">7</td>', row)
        # stale, the last column, is not shaded however large: the count and no class.
        self.assertTrue(row.endswith('<td data-sort="12">12</td>'), row[-60:])

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

    def test_the_flagged_heading_says_the_rows_arrive_in_its_order_without_resorting_them(self):
        table = bw.table(bw.rows(manifest("one"), {"one": report()}))

        self.assertIn('aria-sort="descending">Flagged</th>', table)
        self.assertEqual(1, table.count("aria-sort"))
        # data-sort-default would make tablesort re-sort on load and reverse every tie.
        self.assertNotIn("data-sort-default", table)

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

        self.assertIn("Compared with the run of 2026-09-15, across the 1 application: flagged 1 → 3; `silent` 1 → 3.", line)


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
        "thresholds": {"release-high-years": release, "push-high-years": push, "release-warn-years": 3},
        "flagged_verdicts": list(bw.VERDICTS) if flagged is None else flagged,
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

    def test_names_a_project_measured_against_another_php(self):
        settings = bw.run_settings(
            {"one": with_run(target="8.4"), "two": with_run(target="8.4"), "odd": with_run(target="8.3")}
        )

        self.assertEqual(("8.4", "every project here but odd"), (settings["target_php"], settings["target_scope"]))

    def test_names_a_project_that_set_its_own_silent_years(self):
        settings = bw.run_settings({"one": with_run(), "two": with_run(), "own": with_run(release=4, push=4)})

        self.assertEqual(
            "no stable release and no push to any branch for 5 years (own set their own in `extra.lockrot`)",
            settings["silent_span"],
        )

    def test_a_report_without_thresholds_stops_with_a_message_not_a_traceback(self):
        rep = with_run()
        del rep["run"]["thresholds"]

        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"one": with_run(), "bare": rep})

        self.assertIn("bare", str(raised.exception))

    def test_refuses_a_lockrot_that_flags_a_verdict_the_page_has_no_column_for(self):
        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"one": with_run(flagged=[*bw.VERDICTS, "unmaintained"])})

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


def line_manifest(parent="drupal", tag="10.6.18", date="2026-09-22"):
    return {
        "kind": "line", "name": f"{parent}-v{tag.split('.')[0]}", "parent": parent, "repo": f"acme/{parent}",
        "tag": tag, "commit": "c0ffee1234567890", "line": tag.split(".")[0],
    }


class LinesTest(unittest.TestCase):
    def test_a_row_whose_newest_line_changed_is_marked_and_not_compared(self):
        rows = bw.rows(manifest("one", tag="12.0.0"), {"one": report({"silent": 5})})
        previous = {"one": history_row("one", tag="11.4.8", silent=1)}

        table = bw.table(rows, previous, "2026-09-15")

        self.assertIn('<span class="lockrot-new" title="11.4.8 (11.x) on 2026-09-15">moved</span>', table)
        self.assertNotIn("lockrot-delta", table)
        self.assertIn("one moved from 11.x to 12.x, so its row is not compared.", bw.since_line(rows, previous, "2026-09-15"))
        self.assertIn("no total moved.", bw.since_line(rows, previous, "2026-09-15"))

    def test_a_new_release_on_the_same_line_is_still_compared(self):
        rows = bw.rows(manifest("one", tag="11.4.9"), {"one": report({"silent": 5})})

        table = bw.table(rows, {"one": history_row("one", tag="11.4.8", silent=1)}, "2026-09-15")

        self.assertIn(">new</span>", table)
        self.assertIn("lockrot-delta-up", table)

    def test_older_lines_get_their_own_table_and_stay_out_of_the_totals(self):
        m = manifest("drupal", tag="11.4.8")
        m["projects"].append(line_manifest())
        rows = bw.rows(m, {"drupal": report({"silent": 1}), "drupal-v10": report({"silent": 4})})
        releases = [r for r in rows if r["kind"] == "release"]
        lines_ = [r for r in rows if r["kind"] == "line"]

        main = bw.table(releases, older={"drupal": 1})
        section = bw.lines_section(lines_, releases, {}, None, {"skipped_lines": []}, 3)

        self.assertIn('<a class="lockrot-lines" href="#older-lines-still-releasing">+1 line</a>', main)
        self.assertIn("<td>1 project</td>", main)
        self.assertIn("## Older lines still releasing", section)
        self.assertIn("1 of the 1 application maintain more than one release line", section)
        self.assertIn("released in the last 3 years", section)
        self.assertIn('<span class="lockrot-line">10.x</span>', section)
        self.assertIn("<td>1 older line</td>", section)

    def test_a_run_with_no_lines_prints_no_section(self):
        self.assertEqual("", bw.lines_section([], [], {}, None, {}, 3))

    def test_a_skipped_line_is_named_not_dropped(self):
        releases = bw.rows(manifest("drupal"), {"drupal": report()})
        run = {"skipped_lines": [{"project": "drupal", "line": "7", "tried": [f"7.10{i} (no composer.lock)" for i in range(4)]}]}

        section = bw.lines_section([], releases, {}, None, run, 3)

        self.assertIn("acme/drupal 7.x (tried 7.100, 7.101 and 2 more)", section)

    def test_the_plan_window_must_be_lockrots(self):
        rep = with_run()
        rep["run"]["thresholds"]["release-warn-years"] = 3

        self.assertEqual(3, bw.run_settings({"one": rep}, {"run": {"line_window_years": 3}})["window"])
        with self.assertRaises(SystemExit):
            bw.run_settings({"one": rep}, {"run": {"line_window_years": 2}})


class FixesTest(unittest.TestCase):
    def test_a_line_that_just_became_older_is_compared_with_the_projects_row(self):
        # Drupal 12.0.0 shipped: last week's `drupal` row read 11.x, this week's drupal-v11 reads it.
        m = manifest("drupal", tag="12.0.0")
        m["projects"].append(line_manifest(tag="11.4.9"))
        rows = bw.rows(m, {"drupal": report(), "drupal-v11": report({"silent": 3})})
        previous = {"drupal": history_row("drupal", tag="11.4.8", silent=2)}
        lines_ = [r for r in rows if r["kind"] == "line"]

        table = bw.table(lines_, previous, "2026-09-15", label="older line")

        self.assertIn('title="+1 since 2026-09-15">+1</span>', table)
        self.assertIn(">new</span>", table)

    def test_the_summary_sums_the_applications_only(self):
        m = manifest("one")
        m["projects"].append(line_manifest(parent="one", tag="0.9.0"))
        m["projects"] += starter_manifest()["projects"]
        rows = bw.rows(m, {"one": report({"silent": 2}), "one-v0": report({"silent": 9}), "new-laravel": report({"silent": 5})})
        previous = {
            "one": history_row("one", silent=1),
            "one-v0": {**history_row("one-v0", tag="0.8.0"), "kind": "line"},
            "new-laravel": {**history_row("new-laravel"), "kind": "starter", "version": "v13.0.0"},
        }

        line = bw.since_line(rows, previous, "2026-09-15")

        self.assertIn("across the 1 application: flagged 1 → 2; `silent` 1 → 2.", line)
        self.assertIn("moved to a new release or starter version: new-laravel.", line)
        self.assertNotIn("one-v0", line)

    def test_a_share_rounds_half_up(self):
        self.assertIn(">13%<", bw.share(1, 8))

    def test_a_section_with_only_skipped_lines_counts_them_and_prints_no_table(self):
        releases = bw.rows(manifest("drupal"), {"drupal": report()})
        run = {"skipped_lines": [{"project": "drupal", "line": "7", "tried": ["7.103 (no composer.lock)"]}]}

        section = bw.lines_section([], releases, {}, None, run, 3)

        self.assertIn("1 of the 1 application maintain more than one release line", section)
        self.assertNotIn("<table>", section)
        self.assertNotIn("This one reads", section)

    def test_a_starter_can_name_its_project_for_the_prose(self):
        projects = {"starters": [{"name": "new-typo3", "title": "TYPO3", "no_lock_in_repository": True, "prose_name": "TYPO3's distribution"}]}

        self.assertEqual("TYPO3's distribution", bw.lockless(projects, [{"name": "new-typo3"}]))


class ReadCapsulesTest(unittest.TestCase):
    def test_reads_each_report_and_what_composer_audit_named_beside_it(self):
        view = {"version": "2.10.3", "abandoned": ["a/old"], "advisories": []}
        with tempfile.TemporaryDirectory() as tmp:
            caps = Path(tmp)
            (caps / "manifest.json").write_text(json.dumps({"run": {}}), encoding="utf-8")
            (caps / "one.json").write_text(json.dumps({"data": {"report": {"n": 1}}, "composer": view}), encoding="utf-8")
            (caps / "two.json").write_text(json.dumps({"data": {"report": {"n": 2}}}), encoding="utf-8")

            reports, composer = bw.read_capsules(caps)

        self.assertEqual({"one": {"n": 1}, "two": {"n": 2}}, reports)
        self.assertEqual({"one": view}, composer)

    def test_refuses_a_capsule_without_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "one.json").write_text(json.dumps({"data": {}}), encoding="utf-8")

            with self.assertRaises(SystemExit):
                bw.read_capsules(Path(tmp))


class MainTest(unittest.TestCase):
    """main(), end to end over files: what the unit tests above cannot see is the wiring."""

    def test_older_lines_are_in_their_own_table_and_out_of_every_total(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            caps = tmp / "caps"
            caps.mkdir()
            m = manifest("drupal", tag="11.4.8", date="2026-09-22")
            m["projects"].append(line_manifest(tag="10.6.18"))
            m["projects"] += starter_manifest()["projects"]
            m["run"].update({"target_php": "8.4", "line_window_years": 3, "skipped_lines": []})
            (caps / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
            for name, counts in (("drupal", {"silent": 2}), ("drupal-v10", {"silent": 40}), ("new-laravel", {"silent": 1})):
                rep = with_run()
                rep["counts"].update(counts)
                (caps / f"{name}.json").write_text(json.dumps({"data": {"report": rep}}), encoding="utf-8")
            projects = tmp / "projects.json"
            projects.write_text(json.dumps({"starters": [{"name": "new-laravel", "title": "Laravel", "no_lock_in_repository": True}]}), encoding="utf-8")
            page, history = tmp / "watch.md", tmp / "history.csv"

            bw.main(["build_watch_page.py", "--manifest", str(caps / "manifest.json"), "--capsules", str(caps),
                     "--history", str(history), "--page", str(page), "--projects", str(projects)])
            text = page.read_text(encoding="utf-8")
            kinds = [r["kind"] for r in bw.read_history(history)]

        applications = text[text.index("## What these applications ship"):text.index("## Older lines still releasing")]
        self.assertIn("<td>1 project</td><td></td><td>10</td>", applications)
        self.assertIn('<td class="lockrot-flagged">2 ', applications)
        self.assertNotIn(">40<", applications)
        self.assertIn('<span class="lockrot-line">10.x</span>', text)
        self.assertIn("+1 line</a>", applications)
        self.assertEqual(["release", "line", "starter"], kinds)

    def test_a_report_2_run_writes_the_page_in_report_2_words(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            caps = tmp / "caps"
            caps.mkdir()
            m = manifest("magento2", date="2026-10-19")
            m["projects"] += starter_manifest(date="2026-10-19")["projects"]
            (caps / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
            for name, doc in (("magento2", "magento2-0.14.0.json.gz"), ("new-laravel", "B.json")):
                (caps / f"{name}.json").write_text(json.dumps({"data": {"report": fixture(doc)}}), encoding="utf-8")
            projects = tmp / "projects.json"
            projects.write_text(json.dumps({"starters": [{"name": "new-laravel", "title": "Laravel", "no_lock_in_repository": True}]}), encoding="utf-8")
            page, history = tmp / "watch.md", tmp / "history.csv"

            bw.main(["build_watch_page.py", "--manifest", str(caps / "manifest.json"), "--capsules", str(caps),
                     "--history", str(history), "--page", str(page), "--projects", str(projects)])
            text = page.read_text(encoding="utf-8")
            written = bw.read_history(history)

        self.assertIn("*Flagged for maintenance*", text)
        self.assertIn("A flag is an observation", text)
        self.assertIn("<td>1 project</td><td></td><td>148</td><td>26</td>", text)
        self.assertEqual(["model1", "model1"], [r["grade_basis"] for r in written])


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

        self.assertIn("Compared with the run of 2026-09-15, across the 1 application: flagged 6 → 4; `stale` 6 → 4.", line)
        self.assertIn("lockrot itself moved from 0.10.0 to 0.11.0", line)

    def test_the_summary_names_the_projects_that_released(self):
        rows = bw.rows(manifest("one", tag="v1.1.0"), {"one": report()})

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
    def test_a_row_without_a_name_is_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            path.write_text("date,name\n2026-09-15,one\n2026-09-15,\n", encoding="utf-8")

            with self.assertRaises(SystemExit) as raised:
                bw.read_history(path)

        self.assertIn("lines 3", str(raised.exception))

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


class ReportSchemaTest(unittest.TestCase):
    """The guard: a document the page has not been taught to read stops the build before any count."""

    def test_reads_report_1_and_report_2(self):
        self.assertEqual(1, bw.report_schema(fixture("magento2-0.13.0.json.gz")))
        self.assertEqual(2, bw.report_schema(fixture("magento2-0.14.0.json.gz")))

    def test_a_report_1_without_its_schema_url_is_read_by_its_number(self):
        rep = fixture("magento2-0.13.0.json.gz")
        del rep["$schema"]

        self.assertEqual(1, bw.report_schema(rep))

    def test_stops_on_a_report_2_without_its_schema_url(self):
        rep = fixture("magento2-0.14.0.json.gz")
        del rep["$schema"]

        with self.assertRaises(SystemExit) as raised:
            bw.report_schema(rep)

        self.assertIn("carries no $schema", str(raised.exception))

    def test_stops_on_a_run_whose_reports_mix_schema_numbers(self):
        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"old": fixture("magento2-0.13.0.json.gz"), "new": fixture("magento2-0.14.0.json.gz")})

        self.assertIn("new: 2", str(raised.exception))
        self.assertIn("old: 1", str(raised.exception))

    def test_stops_on_a_report_schema_it_does_not_know(self):
        rep = fixture("magento2-0.14.0.json.gz")
        rep["$schema"] = "https://lockrot.dev/schema/report-3.json"
        rep["lockrot"]["schema"] = 3

        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"magento2": rep})

        self.assertIn("report schema 3 needs build_watch_page update", str(raised.exception))

    def test_stops_on_an_explain_or_a_baseline_document(self):
        for name in ("explain-2.json", "baseline-2.json"):
            with self.subTest(name), self.assertRaises(SystemExit) as raised:
                bw.run_settings({"doc": fixture(name)})
            self.assertIn("is not a lockrot report", str(raised.exception))

    def test_stops_when_the_url_and_the_number_disagree(self):
        rep = fixture("magento2-0.14.0.json.gz")
        rep["lockrot"]["schema"] = 1

        with self.assertRaises(SystemExit) as raised:
            bw.report_schema(rep)

        self.assertIn("says lockrot.schema 1", str(raised.exception))

    def test_stops_on_a_schema_number_that_is_not_an_integer(self):
        for number in (True, [2], "2", None):
            rep = fixture("B.json")
            rep["lockrot"]["schema"] = number
            with self.subTest(number=number), self.assertRaises(SystemExit):
                bw.report_schema(rep)

    def test_stops_on_a_score_model_it_does_not_know(self):
        rep = fixture("magento2-0.14.0.json.gz")
        rep["run"]["score_model"]["id"] = 2

        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"magento2": rep})

        self.assertIn("score model 2 needs build_watch_page update", str(raised.exception))

    def test_stops_before_any_count_is_read(self):
        rep = fixture("magento2-0.14.0.json.gz")
        rep["lockrot"]["schema"] = 3
        rep["$schema"] = "https://lockrot.dev/schema/report-3.json"
        del rep["counts"]

        with self.assertRaises(SystemExit) as raised:
            bw.rows(manifest("magento2"), {"magento2": rep})

        self.assertIn("report schema 3", str(raised.exception))

    def test_reads_the_maintenance_flags_from_the_score_model_not_by_position(self):
        rep = fixture("magento2-0.14.0.json.gz")
        parts = rep["run"]["score_model"]["parts"]
        rep["run"]["score_model"]["parts"] = list(reversed(parts))

        self.assertEqual(bw.VERDICTS, bw.maintenance_flags(rep))

    def test_stops_when_the_maintenance_flags_are_not_the_columns(self):
        rep = fixture("magento2-0.14.0.json.gz")
        maintenance = next(p for p in rep["run"]["score_model"]["parts"] if p["id"] == "maintenance")
        maintenance["flag_ids"] = [*maintenance["flag_ids"], "unmaintained"]

        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"magento2": rep})

        self.assertIn("unmaintained", str(raised.exception))

    def test_stops_when_lockrot_writes_a_flag_the_history_has_no_column_for(self):
        rep = fixture("magento2-0.14.0.json.gz")
        rep["run"]["flag_ids"] = [*rep["run"]["flag_ids"], "unlicensed"]

        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"magento2": rep})

        self.assertIn("unlicensed", str(raised.exception))

    def test_reads_the_run_settings_of_a_report_2(self):
        settings = bw.run_settings({"magento2": fixture("magento2-0.14.0.json.gz")})

        self.assertEqual("8.4", settings["target_php"])
        self.assertEqual(3, settings["window"])


class Report2RowsTest(unittest.TestCase):
    """A report-2 document through rows(): the six columns are each flag's `leading` count."""

    def test_magento2_reads_11_flagged_for_maintenance_and_26_graded(self):
        row = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")})[0]

        self.assertEqual(
            {"abandoned": 4, "silent": 0, "pinned": 0, "left-behind": 1, "old-promise": 1, "stale": 5},
            {c: row[c] for c in bw.VERDICTS},
        )
        self.assertEqual(11, bw.flagged(row))
        self.assertEqual(26, row["graded"])

    def test_the_six_columns_continue_the_0_13_series_on_the_same_data(self):
        before = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.13.0.json.gz")})[0]
        after = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")})[0]

        self.assertEqual({c: before[c] for c in bw.VERDICTS}, {c: after[c] for c in bw.VERDICTS})
        self.assertEqual(before["unknown"], after["unknown"])
        self.assertEqual(before["marked_on_packagist"], after["marked_on_packagist"])

    def test_composer_missed_is_unchanged_on_the_same_data(self):
        r1, r2 = fixture("magento2-0.13.0.json.gz"), fixture("magento2-0.14.0.json.gz")
        abandoned = [f["package"] for f in r1["findings"] if f["verdict"] == "abandoned"]
        audit = view(abandoned=abandoned[:2], advisories=[f["package"] for f in r1["findings"] if f["verdict"] == "stale"][:1])

        missed_013 = bw.composer_missed(r1, audit)

        self.assertEqual(11 - 3, missed_013)
        self.assertEqual(missed_013, bw.composer_missed(r2, audit))

    def test_composer_missed_reads_lead_and_never_the_verdict(self):
        rep = fixture("magento2-0.14.0.json.gz")
        # A grade is not a 0.13 verdict: rewriting every grade changes nothing.
        for finding in rep["findings"]:
            finding["verdict"] = "critical"

        self.assertEqual(11, bw.composer_missed(rep, view()))

    def test_composer_missed_refuses_findings_that_do_not_add_up_to_the_leading_counts(self):
        rep = fixture("magento2-0.14.0.json.gz")
        rep["flags"]["stale"]["leading"] += 1

        with self.assertRaises(SystemExit):
            bw.composer_missed(rep, view())

    def test_the_advisories_column_is_the_vulnerable_flags_carrying_count(self):
        rep = fixture("B.json")

        row = bw.rows(manifest("b"), {"b": rep})[0]

        self.assertEqual(rep["flags"]["vulnerable"]["carrying"], row["advisories"])
        self.assertEqual(1, row["advisories"])

    def test_an_ignored_packagist_marking_still_counts_as_marked(self):
        rep = fixture("ignored-marking-archived-dagger.json")
        signals = [s["id"] for f in rep["findings"] for s in f.get("signals", [])]

        row = bw.rows(manifest("x"), {"x": rep})[0]

        self.assertNotIn("S1", signals)
        self.assertEqual(1, row["marked_on_packagist"])


class Report2HistoryTest(unittest.TestCase):
    def test_a_report_1_row_and_a_report_2_row_side_by_side(self):
        r1 = bw.rows(manifest("magento2", date="2026-10-12"), {"magento2": fixture("magento2-0.13.0.json.gz")})
        r2 = bw.rows(manifest("magento2", date="2026-10-19"), {"magento2": fixture("magento2-0.14.0.json.gz")})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            bw.write_history(path, r1)
            bw.write_history(path, r2)
            with path.open(newline="", encoding="utf-8") as fh:
                header = next(csv.reader(fh))
            old, new = bw.read_history(path)

        self.assertEqual(
            ["date", "lockrot", "kind", "repo", "package", "tag", "version", "commit", "packages",
             "advisories", "abandoned", "silent", "pinned", "left-behind", "old-promise", "stale",
             "unknown", "marked_on_packagist", "name", "composer_missed"],
            header[:20],
        )
        self.assertEqual(
            {"graded": "11", "critical": "0", "high": "6", "medium": "2", "low": "3", "vulnerable": "",
             "carrying_stale": "", "multi_flag": "", "score_model": "0", "report_schema": "1",
             "grade_basis": "priority013"},
            {k: old[k] for k in ("graded", "critical", "high", "medium", "low", "vulnerable", "carrying_stale",
                                 "multi_flag", "score_model", "report_schema", "grade_basis")},
        )
        self.assertEqual(
            {"graded": "26", "critical": "1", "high": "13", "medium": "6", "low": "6", "vulnerable": "15",
             "carrying_stale": "6", "multi_flag": "1", "score_model": "1", "report_schema": "2",
             "grade_basis": "model1"},
            {k: new[k] for k in ("graded", "critical", "high", "medium", "low", "vulnerable", "carrying_stale",
                                 "multi_flag", "score_model", "report_schema", "grade_basis")},
        )
        self.assertEqual(
            ["carrying_abandoned", "carrying_silent", "carrying_pinned", "carrying_left-behind",
             "carrying_old-promise", "carrying_stale", "carrying_vulnerable", "carrying_capped"],
            [h for h in header if h.startswith("carrying_")],
        )
        self.assertFalse(any("depth" in h for h in header))
        self.assertNotIn("advisories_basis", header)

    def test_rows_written_before_the_new_columns_read_back_as_report_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            path.write_text(",".join(bw.HISTORY_FIELDS[:20]) + "\n" + ",".join(history_row("one").get(f, "") for f in bw.HISTORY_FIELDS[:20]) + "\n", encoding="utf-8")
            bw.write_history(path, bw.rows(manifest("one", date="2026-10-19"), {"one": fixture("B.json")}))
            old, new = bw.read_history(path)

        self.assertEqual(1, bw.row_schema(old))
        self.assertEqual(2, bw.row_schema(new))


class Report2PageTest(unittest.TestCase):
    def test_a_report_2_table_says_flagged_for_maintenance_and_shows_graded(self):
        table = bw.table(bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")}))

        self.assertIn('aria-sort="descending">Flagged for maintenance</th>', table)
        self.assertIn(">Graded</th>", table)
        self.assertIn('<td data-sort="26">26</td>', table)
        self.assertIn('<td data-sort="11" class="lockrot-flagged">11 ', table)

    def test_a_report_1_table_is_the_page_it_was(self):
        table = bw.table(bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.13.0.json.gz")}))

        self.assertIn('aria-sort="descending">Flagged</th>', table)
        self.assertNotIn("Graded", table)

    def test_graded_is_not_compared_across_a_score_model_change(self):
        rows = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")})
        before = {**history_row("magento2", abandoned=4, left_behind=1, old_promise=1, stale=5),
                  "graded": "11", "grade_basis": "priority013", "report_schema": "1", "score_model": "0"}

        table = bw.table(rows, {"magento2": before}, "2026-10-12")

        self.assertIn('<td data-sort="26">26</td>', table)
        self.assertNotIn("+15", table)

    def test_graded_is_compared_on_the_same_score_model(self):
        rows = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")})
        before = {**history_row("magento2", abandoned=4, left_behind=1, old_promise=1, stale=5),
                  "graded": "24", "grade_basis": "model1", "report_schema": "2", "score_model": "1"}

        table = bw.table(rows, {"magento2": before}, "2026-10-12")

        self.assertIn('title="+2 since 2026-10-12">+2</span>', table)

    def test_advisories_are_not_compared_across_the_report_schema_change(self):
        m = starter_manifest()
        rows = bw.rows(m, {"new-laravel": fixture("B.json")})
        before = {**history_row("new-laravel", advisories=4, left_behind=1), "kind": "starter", "version": "v13.10.1"}

        table = bw.starter_table(rows, {"new-laravel": before}, "2026-10-12")
        body = table[table.index("<tbody>"):table.index("</tbody>")]

        self.assertNotIn(f"{bw.MINUS}3", body)
        self.assertNotIn(f"{bw.MINUS}3", table[table.index("<tfoot>"):])

    def test_the_prose_names_the_grade_and_the_flags_under_report_2(self):
        r2 = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")})
        r1 = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.13.0.json.gz")})

        self.assertIn("*Graded*", bw.flagged_note(r2))
        self.assertIn("`lead`", bw.flagged_note(r2))
        self.assertNotIn("Graded", bw.flagged_note(r1))
        self.assertIn("each package has exactly one", bw.flagged_note(r1))


# lockrot 0.14.0's flag set with `capped` (S11) after `stale`: mautic/core-lib is led by capped alone.
CAPPED = "capped-local-dagger.json"


class CappedRunTest(unittest.TestCase):
    """Both flag sets are read, so the site can merge before or after lockrot."""

    def test_reads_a_run_whose_flags_carry_capped_after_stale(self):
        rep = fixture(CAPPED)

        settings = bw.run_settings({"mautic": rep})
        row = bw.rows(manifest("mautic"), {"mautic": rep})[0]

        self.assertEqual("8.4", settings["target_php"])
        self.assertEqual((1, 1, 1), (row["capped"], row["carrying_capped"], bw.flagged(row)))

    def test_reads_a_run_whose_flags_have_no_capped_and_leaves_its_cells_empty(self):
        rep = fixture("magento2-0.14.0.json.gz")

        bw.run_settings({"magento2": rep})
        row = bw.rows(manifest("magento2"), {"magento2": rep})[0]

        self.assertEqual(("", ""), (row["capped"], row["carrying_capped"]))
        self.assertEqual(11, bw.flagged(row))

    def test_a_report_1_row_has_no_capped_count(self):
        row = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.13.0.json.gz")})[0]

        self.assertEqual(("", ""), (row["capped"], row["carrying_capped"]))

    def test_a_package_capped_carries_but_does_not_lead_counts_only_as_carried(self):
        row = bw.rows(manifest("x"), {"x": fixture("stale-capped.json")})[0]

        self.assertEqual((0, 1, 1), (row["capped"], row["carrying_capped"], row["stale"]))

    def test_stops_on_a_run_that_mixes_the_two_flag_sets(self):
        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"magento2": fixture("magento2-0.14.0.json.gz"), "mautic": fixture(CAPPED)})

        self.assertIn("different flag sets", str(raised.exception))
        self.assertIn("magento2", str(raised.exception))
        self.assertIn("mautic", str(raised.exception))

    def test_stops_when_capped_is_not_after_stale(self):
        rep = fixture(CAPPED)
        maintenance = next(p for p in rep["run"]["score_model"]["parts"] if p["id"] == "maintenance")
        order = ["abandoned", "silent", "pinned", "left-behind", "old-promise", "capped", "stale"]
        maintenance["flag_ids"] = order
        rep["run"]["flag_ids"] = [*order, "vulnerable"]

        with self.assertRaises(SystemExit):
            bw.run_settings({"mautic": rep})

    def test_stops_when_the_flag_ids_and_the_maintenance_flags_disagree_on_capped(self):
        rep = fixture(CAPPED)
        rep["run"]["flag_ids"] = [f for f in rep["run"]["flag_ids"] if f != "capped"]

        with self.assertRaises(SystemExit) as raised:
            bw.run_settings({"mautic": rep})

        self.assertIn("carrying_ columns", str(raised.exception))

    def test_a_report_1_that_flags_capped_is_refused(self):
        with self.assertRaises(SystemExit):
            bw.run_settings({"one": with_run(flagged=list(bw.COLUMNS))})

    def test_a_report_whose_flag_ids_name_capped_without_its_counts_is_refused(self):
        rep = fixture(CAPPED)
        del rep["flags"]["capped"]

        with self.assertRaises(KeyError):
            bw.rows(manifest("mautic"), {"mautic": rep})

    def test_composer_missed_counts_a_package_that_capped_leads(self):
        self.assertEqual(1, bw.composer_missed(fixture(CAPPED), view()))


class CappedPageTest(unittest.TestCase):
    def test_the_capped_column_follows_stale_when_the_run_measures_it(self):
        table = bw.table(bw.rows(manifest("mautic"), {"mautic": fixture(CAPPED)}))

        self.assertIn(
            '<code>stale</code></th><th class="lockrot-num" data-sort-method="number" data-sort-reverse>'
            "<code>capped</code></th></tr></thead>",
            table,
        )
        self.assertTrue(table.split("</tr></tbody>")[0].endswith('<td data-sort="1">1</td>'))

    def test_a_run_without_capped_has_no_capped_column(self):
        for doc in ("magento2-0.14.0.json.gz", "magento2-0.13.0.json.gz"):
            with self.subTest(doc):
                table = bw.table(bw.rows(manifest("magento2"), {"magento2": fixture(doc)}))
                self.assertNotIn("capped", table)

    def test_the_starter_table_carries_the_capped_column_too(self):
        table = bw.starter_table(bw.rows(starter_manifest(), {"new-laravel": fixture(CAPPED)}))

        self.assertIn("<code>capped</code></th></tr></thead>", table)

    def test_capped_is_not_compared_with_a_run_that_did_not_measure_it(self):
        rows = bw.rows(manifest("mautic"), {"mautic": fixture(CAPPED)})
        before = {**history_row("mautic"), "capped": ""}

        table = bw.table(rows, {"mautic": before}, "2026-10-19")
        body = table[table.index("<tbody>"):table.index("</tbody>")]
        foot = table[table.index("<tfoot>"):]

        self.assertTrue(body.endswith('<td data-sort="1">1</td></tr>'), body[-80:])
        self.assertTrue(foot.endswith("<td>1</td></tr></tfoot></table></div>"), foot[-80:])

    def test_capped_is_compared_with_a_run_that_measured_it(self):
        rows = bw.rows(manifest("mautic"), {"mautic": fixture(CAPPED)})
        before = {**history_row("mautic"), "capped": "3"}

        table = bw.table(rows, {"mautic": before}, "2026-10-19")

        self.assertIn(f'<td data-sort="1">1 <span class="lockrot-delta lockrot-delta-down" title="{bw.MINUS}2 since 2026-10-19">', table)

    def test_the_summary_names_capped_only_when_both_runs_measured_it(self):
        rows = bw.rows(manifest("mautic"), {"mautic": fixture(CAPPED)})

        unmeasured = bw.since_line(rows, {"mautic": {**history_row("mautic"), "capped": ""}}, "2026-10-19")
        measured = bw.since_line(rows, {"mautic": {**history_row("mautic"), "capped": "3"}}, "2026-10-19")

        self.assertIn("across the 1 application: no total moved.", unmeasured)
        self.assertNotIn("capped", unmeasured)
        self.assertIn("flagged 3 → 1; `capped` 3 → 1.", measured)

    def test_flagged_is_not_compared_with_a_run_that_did_not_measure_capped(self):
        rows = bw.rows(manifest("mautic"), {"mautic": fixture(CAPPED)}, {"mautic": view()})
        before = {**history_row("mautic"), "packages": "128", "capped": "", "composer_missed": "0"}

        table = bw.table(rows, {"mautic": before}, "2026-10-19")
        line = bw.since_line(rows, {"mautic": before}, "2026-10-19")

        self.assertNotIn("lockrot-delta", table)
        self.assertNotIn("flagged", line)
        self.assertNotIn("composer audit", line)

    def test_flagged_is_not_compared_with_a_run_that_measured_capped_when_this_one_did_not(self):
        rows = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")}, {"magento2": view()})
        before = {**history_row("magento2", abandoned=4, left_behind=1, old_promise=1, stale=5),
                  "packages": "148", "capped": "5", "composer_missed": "16", "graded": "26", "grade_basis": "model1",
                  "report_schema": "2", "score_model": "1"}

        table = bw.table(rows, {"magento2": before}, "2026-10-19")
        line = bw.since_line(rows, {"magento2": before}, "2026-10-19")

        self.assertNotIn("lockrot-delta", table)
        self.assertIn("across the 1 application: no total moved.", line)

    def test_the_note_counts_the_flags_the_run_measures(self):
        capped = bw.rows(manifest("mautic"), {"mautic": fixture(CAPPED)})
        without = bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")})

        self.assertIn("one of the seven flags to its right", bw.flagged_note(capped))
        self.assertIn("one of the six flags to its right", bw.flagged_note(without))


class CappedHistoryTest(unittest.TestCase):
    def test_rows_written_before_capped_read_an_empty_cell_and_keep_every_value(self):
        old_fields = [f for f in bw.HISTORY_FIELDS if f not in ("capped", "carrying_capped")]
        old = {**{f: "" for f in old_fields}, **history_row("mautic", date="2026-10-19", stale=4),
               "graded": "7", "carrying_stale": "5", "report_schema": "2", "grade_basis": "model1"}
        old = {f: old[f] for f in old_fields}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=old_fields, lineterminator="\n")
                writer.writeheader()
                writer.writerow(old)

            bw.write_history(path, bw.rows(manifest("mautic", date="2026-10-26"), {"mautic": fixture(CAPPED)}))
            kept, new = bw.read_history(path)

        self.assertEqual(old, {f: kept[f] for f in old_fields})
        self.assertEqual(("", ""), (kept["capped"], kept["carrying_capped"]))
        self.assertEqual(("1", "1"), (new["capped"], new["carrying_capped"]))

    def test_a_run_without_capped_writes_empty_cells_not_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "history.csv"
            bw.write_history(path, bw.rows(manifest("magento2"), {"magento2": fixture("magento2-0.14.0.json.gz")}))
            (row,) = bw.read_history(path)

        self.assertEqual(("", ""), (row["capped"], row["carrying_capped"]))

    def test_the_new_columns_are_appended_after_every_existing_one(self):
        self.assertEqual(["capped", "carrying_capped"], bw.HISTORY_FIELDS[-2:])
        self.assertEqual("grade_basis", bw.HISTORY_FIELDS[-3])


class CappedMainTest(unittest.TestCase):
    def test_builds_the_page_from_a_lockrot_document_that_carries_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            caps = tmp / "caps"
            caps.mkdir()
            m = manifest("mautic", date="2026-10-26")
            m["projects"] += starter_manifest(date="2026-10-26")["projects"]
            (caps / "manifest.json").write_text(json.dumps(m), encoding="utf-8")
            for name in ("mautic", "new-laravel"):
                (caps / f"{name}.json").write_text(json.dumps({"data": {"report": fixture(CAPPED)}}), encoding="utf-8")
            projects = tmp / "projects.json"
            projects.write_text(json.dumps({"starters": [{"name": "new-laravel", "title": "Laravel", "no_lock_in_repository": True}]}), encoding="utf-8")
            page, history = tmp / "watch.md", tmp / "history.csv"

            bw.main(["build_watch_page.py", "--manifest", str(caps / "manifest.json"), "--capsules", str(caps),
                     "--history", str(history), "--page", str(page), "--projects", str(projects)])
            text = page.read_text(encoding="utf-8")
            written = bw.read_history(history)

        self.assertIn("one of the seven flags to its right", text)
        self.assertEqual(2, text.count("<code>capped</code></th>"))
        self.assertIn('<td data-sort="1" class="lockrot-flagged">1 ', text)
        self.assertEqual([("1", "1"), ("1", "1")], [(r["capped"], r["carrying_capped"]) for r in written])


if __name__ == "__main__":
    unittest.main()
