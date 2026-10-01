#!/usr/bin/env python3
"""Write the weekly watch page and append the week's row to its history.

The page is generated rather than hand-written because its source file is what dates it: the
sitemap's <lastmod> is the commit date of the file a page is built from (scripts/mkdocs_hooks.py),
and a page whose numbers change weekly while its file does not would tell every crawler it had not
moved since the day it was written. So the prose lives here, the run writes the page, and the
commit that changes the numbers is the commit that dates them.

The history file is append-only and keyed by (date, repo): a rerun of the same day's run rewrites
that day's rows rather than doubling them. Each row carries the lockrot version that produced it,
because a number can move when a project changes and it can move when the tool learns something,
and a trend that cannot tell those apart is not a trend.

The tables are written as HTML rather than Markdown, because a Markdown cell can carry no attribute:
the sort value a column is ordered by (assets/watch.js), the class that shades a non-zero count, and
the note on a number that moved since the previous run all live on the cell. Every number is compared
with the run before it, read back out of the history, and every run in the history is listed with a
link to the reports it published (scripts/watch_archive.py builds the pages behind those links).
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import sys
from collections import Counter
from pathlib import Path

from watch_plan import release_line

# Cloudflare serves reports/<name>.html at reports/<name> and redirects the .html form there
# (`html_handling: auto-trailing-slash` in wrangler.viewer.jsonc), so the link skips the 307.
VIEWER = "https://viewer.lockrot.dev/reports/watch"

HISTORY_FIELDS = [
    "date", "lockrot", "kind", "repo", "package", "tag", "version", "commit", "packages",
    "advisories", "abandoned", "silent", "pinned", "left-behind", "old-promise", "stale",
    "unknown", "marked_on_packagist", "name", "composer_missed",
]

# The verdicts the page has a column for, in the order the tool ranks them.
COLUMNS = ["abandoned", "silent", "pinned", "left-behind", "old-promise", "stale"]

# The counts a row is compared with the previous run on: the verdicts and the advisories.
COUNTED = ["advisories", *COLUMNS]

# The counts that are shaded: a maintainer's own word, years of silence, a branch instead of a
# release, a known vulnerability. left-behind, old-promise and stale are large in nearly every row
# and say something milder; shading them too turned the page into one block of colour.
SHADED = {"advisories", "abandoned", "silent", "pinned"}

# A count's shade, by the smallest value that earns it. Absolute rather than relative to the column,
# so a shade means the same number of packages in every column and every week.
HEAT = [(10, 4), (5, 3), (2, 2), (1, 1)]

# U+2212 MINUS SIGN: a hyphen next to a number reads as a dash.
MINUS = "\u2212"

PAGE = """---
title: Dependency rot in {count} open-source PHP applications and {starters} fresh installs
head_title: Dependency rot in {count} PHP applications — a weekly lockrot run
description: >-
  Every week lockrot reads the composer.lock of the newest release of {count} widely used
  open-source PHP applications, and of {starters} projects created that day with composer
  create-project: what is abandoned, silent for years, pinned to a branch or carrying an advisory.
  Last run {date}.
hide:
  - navigation
  - toc
---

# Dependency rot in {count} PHP applications, and in {starters} fresh installs

Every Monday lockrot {version} reads two kinds of `composer.lock` and reports the packages in them
that stopped being maintained: the lock the **newest stable release** of {count} open-source PHP
applications ships, and the lock {starters} **new projects** get when they are created that morning
with `composer create-project`. This page is the last run, {date}. Nothing is installed, no script
or plugin from any package is run, and no project is contacted: the run reads lock files, then asks
Packagist and the repository host about the packages in them.

{headline}{since}

## What these applications ship

{table}

A project's name opens the full report lockrot wrote for it; a column heading sorts the table.
*Flagged* is every package with one of the six verdicts to its right — each package has exactly one,
so they add up — and is the number at the top of that report; the percentage is its share of the
lock. {composer_note}A small number beside a count is how far it moved since the previous run, and *new* marks a project
that cut a release in between; *moved* marks one whose newest line changed, and that row is not
compared with the previous run. Each row names the release it read and the commit that release points
at, so any number here can be
checked against the same two files lockrot read. A release rather than a branch head on purpose: a
release is what people install, and it is the only version of a project that two weeks of this page
can be compared across — the tip of a development branch moves for reasons that have nothing to do
with dependency rot.

{lines_section}## What a new project gets today

A project started this morning has no history to rot in, and that is exactly why it is worth
measuring: its dependency tree is whatever the current constraints resolve to, and the answer
changes weekly without anyone touching the project. This half of the run creates each one from
scratch — `composer create-project`, with the starter package pinned to its newest stable version,
nothing installed and no script or plugin executed — and reads the lock file that falls out.

{starter_table}

The advisories column counts packages with a security advisory against the installed version, from
the same feed `composer audit` reads. It is here and not in the table above because these reports
are made with `--all`: every package is in the document, so an advisory on an otherwise healthy one
is visible. The applications are read without `--all`, where a healthy package is not a finding and
never reaches the page.

Several projects in this table cannot be in the one above, and for one reason: {lockless} do not
commit a lock file to their repository. Their lock is born at `create-project` time, which is the only place it can be read —
and is the version their users actually run.

A verdict is an observation, not a judgement, and the two that carry most of the table say
different things. `abandoned` is the Packagist marker or an archived repository — someone said so.
`silent` is {silent_span}, which is lockrot's default threshold and not a law of nature: a package that encodes base64url does not need a release in 2035
either. That is what the [allowlist](configuration.md#the-allowlist) is for, and a project that has
looked at one of these and decided it is fine can say so in its own `composer.json` in one line.

`old-promise` counts against PHP {target_php} for {target_scope}, whatever each one actually targets,
because a column has to mean the same thing in every row. On a real project it is
`--target-php` that decides it.

## Why these projects

The {count} are applications people deploy, chosen on two public signals and one hard constraint.
The signals: how widely a thing is actually run, where someone else measures it — W3Techs, 21
September 2026, puts Joomla on 1.1% of all websites, Drupal on 0.6% and Adobe's Magento on 0.6% —
and GitHub stars, which is what puts Coolify, Appwrite and Bagisto at the top of any list of PHP
applications today.

The constraint decided more of the first table than either signal: **a project has to commit
`composer.json` and `composer.lock` at a tagged release.** Of the 300 most-starred PHP repositories
and a hand list of the widely-deployed ones — 109 looked at — 61 came through that filter, and
these {count} are chosen from those 61 for spread across what the applications actually do: CMS,
shop, forum, LMS, analytics, marketing, accounting, asset management, the rest.

The second table is where the rest of them turn up. {lockless} commit no lock file at all — nor,
among the applications looked at, do Dolibarr, Roundcube, osTicket, SilverStripe, Contao, October,
MODX, ProcessWire and Vanilla; their dependency tree exists only once someone installs them, so
that is where it is read. The starters are the ways people actually begin a PHP project —
the framework skeletons and the vendor-recommended distributions — each pinned to its newest stable
version so the row names something checkable. The list, the reasoning and the near misses are in
[`data/watch/projects.json`](https://github.com/somework/lockrot.dev/blob/main/data/watch/projects.json).

## What moves these numbers

Three things, and they are worth telling apart. A project cuts a release, and the row moves because
the project moved — the release column says when that happened. A maintainer marks a package
abandoned on Packagist, and the row moves although the release did not change at all, which is the
[gap this post](blog/posts/2026-09-19-composer-audit-abandoned-misses.md) is about and the reason
`composer audit` does not see most of what is here. Or lockrot learns to measure something it
skipped before, and the row moves because the tool moved; every row in
[`history.csv`]({history}) carries the release, the commit and the lockrot version that produced it
for exactly that reason.

## Earlier runs

Every run stays readable: each one below links the reports it published, rendered with the same
lockrot renderer as this week's, from the document that run wrote. The numbers behind all of them are
in [`history.csv`]({history}).

{archive}

## Running it on your own lock

```console
$ composer require --dev somework/lockrot
$ composer lockrot --target-php={target_php} --fail-on=silent
```

The PHAR does the same without touching the lock ([download and verify](phar.md)), and the
[GitHub Action](ci.md#github-action) is what this page runs. A project with a long list starts
from a [baseline](baseline.md) and fails on what arrives next, rather than on what is already
there.
"""


def read_capsules(directory: Path) -> dict:
    capsules = {}
    for path in sorted(directory.glob("*.json")):
        # The run's manifest sits beside its capsules and is not one of them.
        if path.name == "manifest.json":
            continue
        capsule = json.loads(path.read_text(encoding="utf-8"))
        report = capsule.get("data", {}).get("report")
        if report is None:
            raise SystemExit(f"build_watch_page: {path} carries no report")
        capsules[path.stem] = report
    if not capsules:
        raise SystemExit(f"build_watch_page: no reports under {directory}")
    return capsules


def read_composer(directory: Path) -> dict:
    """What composer audit named in each project's lock, for the runs that measured it."""
    views = {}
    for path in sorted(directory.glob("*.json")):
        if path.name == "manifest.json":
            continue
        view = json.loads(path.read_text(encoding="utf-8")).get("composer")
        if view is not None:
            views[path.stem] = view
    return views


def composer_missed(report: dict, view: dict | None) -> int | str:
    """The flagged packages composer audit does not name at all, as abandoned or as carrying an
    advisory. Empty when the run did not ask composer audit.

    The findings are checked against the counts first: a report that lists fewer flagged packages
    than it counts would make this number quietly small.
    """
    if view is None:
        return ""
    flagged_names = [f["package"] for f in report["findings"] if f["verdict"] in COLUMNS]
    if len(flagged_names) != sum(report["counts"][c] for c in COLUMNS):
        raise SystemExit("build_watch_page: a report's findings do not add up to its counts")
    named = set(view["abandoned"]) | set(view["advisories"])
    return sum(1 for package in flagged_names if package not in named)


def marked(report: dict) -> int:
    """Packages carrying Packagist's own abandoned marker (signal S1), out of the findings."""
    return sum(
        1
        for finding in report["findings"]
        if any(signal.get("id") == "S1" for signal in finding.get("signals", []))
    )


def advisories(report: dict) -> int:
    """Packages carrying at least one security advisory (signal S9), out of the findings."""
    return sum(
        1
        for finding in report["findings"]
        if any(signal.get("id") == "S9" for signal in finding.get("signals", []))
    )


def rows(manifest: dict, capsules: dict, composer: dict | None = None) -> list[dict]:
    composer = composer or {}
    out = []
    for project in manifest["projects"]:
        name = project["name"]
        if name not in capsules:
            raise SystemExit(f"build_watch_page: the run left no report for {name}")
        report = capsules[name]
        counts = report["counts"]
        out.append(
            {
                "date": manifest["run"]["date"],
                "lockrot": report["lockrot"]["version"],
                "kind": project.get("kind", "release"),
                "repo": project.get("repo", ""),
                "title": project.get("title", ""),
                "package": project.get("package", ""),
                "packagist_url": project.get("packagist_url", ""),
                "version": project.get("version", ""),
                "line": project.get("line") or (release_line(project["tag"]) if project.get("tag") else ""),
                "parent": project.get("parent", ""),
                "command": project.get("command", ""),
                "advisories": advisories(report),
                "tag": project.get("tag", ""),
                "tag_url": project.get("tag_url", ""),
                "commit": project.get("commit", ""),
                "commit_url": project.get("commit_url", ""),
                "packages": report["packages_checked"],
                "marked_on_packagist": marked(report),
                "name": name,
                **{column: counts[column] for column in COLUMNS},
                # No column of its own on the page — a package lockrot could not check is a note,
                # not a finding — but the history keeps it, because a week where it jumps means
                # the run could not reach a host, not that a project changed.
                "unknown": counts["unknown"],
                "composer_missed": composer_missed(report, composer.get(name)),
                "composer": (composer.get(name) or {}).get("version", ""),
            }
        )
    return out


def order(rows_: list[dict]) -> list[dict]:
    """The order a table is printed in, which is the order a reader without JavaScript gets.

    Most flagged first, the column the heading marks as sorted; on a tie, a package abandoned by its
    own maintainer outweighs one silent for years, and the name settles the rest so a week with no
    change prints the same page.
    """
    return sorted(
        rows_, key=lambda r: (-flagged(r), -int(r["abandoned"]), -int(r["silent"]), r["name"])
    )


def previous_run(history: list[dict], date: str) -> tuple[str | None, dict]:
    """The newest run before `date` in the history, as its date and its rows by project name."""
    earlier = sorted({r["date"] for r in history if r["date"] < date})
    if not earlier:
        return None, {}
    last = earlier[-1]
    return last, {r["name"]: r for r in history if r["date"] == last}


def read_history(path: Path) -> list[dict]:
    """The history's rows. Every row needs its run's name: the previous run is looked up by it and
    the archive links each report by it, so a row without one is refused rather than published as a
    link to nothing."""
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        rows_ = list(csv.DictReader(fh))
    unnamed = [i for i, row in enumerate(rows_, start=2) if not (row.get("name") or "").strip()]
    if unnamed:
        raise SystemExit(
            f"build_watch_page: {path} has rows with no name (lines {', '.join(map(str, unnamed[:5]))}); "
            "fill them from that run's manifest"
        )
    return rows_


def plural(count: int, word: str) -> str:
    """`1 project`, `2 projects`; `older line` the same way."""
    return f"{count} {word}{'' if count == 1 else 's'}"


def heat(value: int) -> str:
    for floor, level in HEAT:
        if value >= floor:
            return f"lockrot-heat-{level}"
    return "lockrot-zero"


def delta(now: int, before: str | int | None, since: str | None, neutral: bool = False) -> str:
    """The change since the previous run, as a small mark after a count; nothing when it held.

    Up is worse for a verdict and an advisory, so the colour says which way the project went;
    `neutral` is for a package count, which moving says nothing good or bad about.
    """
    if before is None or before == "":
        return ""
    moved = now - int(before)
    if moved == 0:
        return ""
    sign = "+" if moved > 0 else MINUS
    tone = "lockrot-delta" if neutral else f"lockrot-delta lockrot-delta-{'up' if moved > 0 else 'down'}"
    return (
        f' <span class="{tone}" title="{sign}{abs(moved)} since {html.escape(since or "")}">'
        f"{sign}{abs(moved)}</span>"
    )


def count_cell(
    value: int, before: str | int | None, since: str | None, column: str = "packages"
) -> str:
    """One count. A shaded column takes its shade; the rest only let a zero recede."""
    if column in SHADED:
        shade = f' class="{heat(value)}"'
    else:
        shade = ' class="lockrot-zero"' if value == 0 and column != "packages" else ""
    moved = delta(value, before, since, neutral=column == "packages")
    return f'<td data-sort="{value}"{shade}>{value}{moved}</td>'


def flagged(row: dict) -> int:
    """The packages lockrot flags: one verdict per package, so the six columns add up without
    counting anything twice. It is lockrot's own number — `Verdict::flagged()` is every verdict from
    `stale` up, and a report's title reads "101 of 210 packages flagged" — and it leaves out
    `unknown`, `finished` and `ok`. Works on a run's row and on a history row alike."""
    return sum(int(row[c] or 0) for c in COLUMNS)


def share(part: int, whole: int) -> str:
    return f'<span class="lockrot-share">{int(100 * part / whole + 0.5) if whole else 0}%</span>'


def flagged_cell(row: dict, before: dict | None, since: str | None) -> str:
    """How many packages are flagged, and what share of the lock that is: 30 of 50 and 30 of 300
    are different projects."""
    value = flagged(row)
    tone = "lockrot-flagged lockrot-zero" if value == 0 else "lockrot-flagged"
    moved = delta(value, flagged(before) if before else None, since)
    return f'<td data-sort="{value}" class="{tone}">{value} {share(value, int(row["packages"]))}{moved}</td>'


def missed_cell(row: dict, before: dict | None, since: str | None) -> str:
    """The flagged packages composer audit does not name, and their share of the flagged ones.
    A dash for a run that did not ask it; it sorts below every measured count."""
    value = row["composer_missed"]
    if value == "":
        return '<td data-sort="-1" class="lockrot-missed lockrot-zero" title="Not measured in this run">—</td>'
    tone = "lockrot-missed lockrot-zero" if value == 0 else "lockrot-missed"
    moved = delta(value, (before or {}).get("composer_missed"), since)
    return f'<td data-sort="{value}" class="{tone}">{value} {share(value, flagged(row))}{moved}</td>'


def new_mark(moved: bool, was: str, since: str | None) -> str:
    if not moved:
        return ""
    return f' <span class="lockrot-new" title="{html.escape(was)} on {html.escape(since or "")}">new</span>'


def previous_of(row: dict, previous: dict) -> dict | None:
    """The previous run's row for this one: by name, or — for an older line that was the project's
    newest line last week, Drupal 11 the week 12.0.0 ships — the project's own row, when it read
    this line."""
    before = previous.get(row["name"])
    if before is None and row["kind"] == "line":
        parent = previous.get(row["parent"])
        if parent and parent.get("tag") and release_line(parent["tag"]) == row["line"]:
            return parent
    return before


def same_line(row: dict, before: dict | None) -> dict | None:
    """The previous run's row, when it read the same release line; otherwise nothing to compare.

    A project whose newest line changed — Drupal 11 to 12 — reports a different lock, and every
    number on its row moved for that reason alone. The history has no line column: a line is read
    off the tag, the same way the plan drew it.
    """
    if before is None or row["kind"] == "starter" or not before.get("tag"):
        return before
    return before if release_line(before["tag"]) == row["line"] else None


def line_moved(row: dict, before: dict | None) -> bool:
    return before is not None and same_line(row, before) is None


def project_cell(row: dict, older: int = 0) -> str:
    owner, _, repo = row["repo"].partition("/")
    line = f' <span class="lockrot-line">{html.escape(row["line"])}.x</span>' if row["kind"] == "line" else ""
    more = (
        f' <a class="lockrot-lines" href="#older-lines-still-releasing">+{older} '
        f"line{'' if older == 1 else 's'}</a>"
        if older else ""
    )
    sort = f'{row["repo"].lower()} {row["line"]:>8}' if row["kind"] == "line" else row["repo"].lower()
    return (
        f'<td data-sort="{html.escape(sort, quote=True)}">'
        f'<a href="{VIEWER}/{html.escape(row["name"], quote=True)}" title="Open the report lockrot wrote">'
        f'<span class="lockrot-owner">{html.escape(owner)}/</span>{html.escape(repo)}</a>{line}{more}</td>'
    )


def release_cell(row: dict, before: dict | None, since: str | None) -> str:
    """The release and its commit. `before` is the previous run's row, whatever line it read."""
    repo_url = f"https://github.com/{row['repo']}"
    tag_url = row.get("tag_url") or f"{repo_url}/releases/tag/{row['tag']}"
    commit_url = row.get("commit_url") or f"{repo_url}/tree/{row['commit']}"
    if line_moved(row, before):
        was = f"{before['tag']} ({release_line(before['tag'])}.x) on {since or ''}"
        mark = f' <span class="lockrot-new" title="{html.escape(was)}">moved</span>'
    else:
        mark = new_mark(before is not None and before.get("tag") != row["tag"], (before or {}).get("tag", ""), since)
    return (
        f'<td class="lockrot-release"><a href="{html.escape(tag_url, quote=True)}">{html.escape(row["tag"])}</a>'
        f' <a class="lockrot-commit" href="{html.escape(commit_url, quote=True)}">'
        f"<code>{html.escape(row['commit'][:7])}</code></a>{mark}</td>"
    )


def starter_cells(row: dict, before: dict | None, since: str | None) -> str:
    url = row.get("packagist_url") or f"https://packagist.org/packages/{row['package']}"
    moved = before is not None and before.get("version") != row["version"]
    return (
        f'<td data-sort="{html.escape(row["title"].lower(), quote=True)}">'
        f'<a href="{VIEWER}/{html.escape(row["name"], quote=True)}" title="Open the report lockrot wrote">'
        f"{html.escape(row['title'])}</a></td>"
        f'<td class="lockrot-created"><a href="{html.escape(url, quote=True)}">{html.escape(row["package"])}</a>'
        f" <code>{html.escape(row['version'])}</code>"
        f"{new_mark(moved, (before or {}).get('version', ''), since)}</td>"
    )


def header(first: list[str], counted: list[str]) -> str:
    """The heading row. Every count sorts as a number; the text columns sort as text."""
    cells = [f"<th>{name}</th>" for name in first[:1]]
    cells += [f'<th data-sort-method="none">{name}</th>' for name in first[1:]]
    cells.append('<th class="lockrot-num" data-sort-method="number" data-sort-reverse>Packages</th>')
    # The rows arrive in Flagged order (order()), and the heading says so with aria-sort. Not
    # data-sort-default: tablesort would re-sort on load and break every tie the other way round.
    # assets/watch.js tells tablesort this heading is the current sort, so a click elsewhere clears it.
    cells.append(
        '<th class="lockrot-num lockrot-flagged" data-sort-method="number" data-sort-reverse'
        ' aria-sort="descending">Flagged</th>'
    )
    cells.append(
        '<th class="lockrot-num lockrot-missed" data-sort-method="number" data-sort-reverse'
        ' title="Flagged packages composer audit does not name at all, as abandoned or with an advisory">'
        "Not in<br><code>composer&nbsp;audit</code></th>"
    )
    for column in counted:
        label = "Advisories" if column == "advisories" else "<code>" + column.replace("-", "-<wbr>") + "</code>"
        cells.append(f'<th class="lockrot-num" data-sort-method="number" data-sort-reverse>{label}</th>')
    return "<thead><tr>" + "".join(cells) + "</tr></thead>"


def totals(rows_: list[dict], previous: dict, since: str | None, label: str, counted: list[str]) -> str:
    """The totals row, compared with the same projects' totals in the previous run.

    Only when the previous run had every one of them: a total that moved because the list grew is
    not a change in any project.
    """
    comparable = all(r["name"] in previous for r in rows_)

    def before(column: str) -> int | None:
        return sum(int(previous[r["name"]][column] or 0) for r in rows_) if comparable else None

    cells = [f"<td>{label}</td>", "<td></td>"]
    packages = sum(int(r["packages"]) for r in rows_)
    cells.append(f"<td>{packages}{delta(packages, before('packages'), since, neutral=True)}</td>")
    total = sum(flagged(r) for r in rows_)
    total_before = sum(flagged(previous[r["name"]]) for r in rows_) if comparable else None
    cells.append(f'<td class="lockrot-flagged">{total} {share(total, packages)}{delta(total, total_before, since)}</td>')
    if all(r["composer_missed"] != "" for r in rows_):
        missed = sum(int(r["composer_missed"]) for r in rows_)
        measured_before = comparable and all(previous[r["name"]].get("composer_missed") for r in rows_)
        missed_before = (
            sum(int(previous[r["name"]]["composer_missed"]) for r in rows_) if measured_before else None
        )
        cells.append(
            f'<td class="lockrot-missed">{missed} {share(missed, total)}{delta(missed, missed_before, since)}</td>'
        )
    else:
        cells.append('<td class="lockrot-missed">—</td>')
    for column in counted:
        value = sum(int(r[column]) for r in rows_)
        cells.append(f"<td>{value}{delta(value, before(column), since)}</td>")
    return "<tfoot><tr>" + "".join(cells) + "</tr></tfoot>"


def comparable(rows_: list[dict], previous: dict) -> dict:
    """The previous run's rows these rows can be compared with: same project, same line."""
    found = {r["name"]: same_line(r, previous_of(r, previous)) for r in rows_}
    return {name: before for name, before in found.items() if before is not None}


def table(
    rows_: list[dict],
    previous: dict | None = None,
    since: str | None = None,
    label: str = "project",
    older: dict | None = None,
) -> str:
    """The applications, one row per project, read from the release it names; or, with
    label="older lines", one row per older line still releasing."""
    raw = previous or {}
    previous = comparable(rows_, raw)
    older = older or {}
    body = []
    for row in order(rows_):
        before = previous.get(row["name"])
        cells = [project_cell(row, older.get(row["name"], 0)), release_cell(row, previous_of(row, raw), since)]
        cells.append(count_cell(int(row["packages"]), (before or {}).get("packages"), since))
        cells.append(flagged_cell(row, before, since))
        cells.append(missed_cell(row, before, since))
        cells += [count_cell(int(row[c]), (before or {}).get(c), since, c) for c in COLUMNS]
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        # Material styles, and makes scrollable, only a table with no class of its own.
        '<div class="lockrot-watch"><table>'
        + header(["Project", "Release"], COLUMNS)
        + "<tbody>" + "".join(body) + "</tbody>"
        + totals(rows_, previous, since, plural(len(rows_), label), COLUMNS)
        + "</table></div>"
    )


def starter_table(rows_: list[dict], previous: dict | None = None, since: str | None = None) -> str:
    """The second table: a project created on the day of the run, not one that shipped.

    It carries an advisories column the first table cannot: starters are read with `--all`, so a
    package that is perfectly healthy apart from a CVE is in the document. The applications are
    read without it, where such a package is not a finding and never reaches the page.
    """
    previous = comparable(rows_, previous or {})
    body = []
    for row in order(rows_):
        before = previous.get(row["name"])
        cells = [starter_cells(row, before, since)]
        cells.append(count_cell(int(row["packages"]), (before or {}).get("packages"), since))
        cells.append(flagged_cell(row, before, since))
        cells.append(missed_cell(row, before, since))
        cells += [count_cell(int(row[c]), (before or {}).get(c), since, c) for c in COUNTED]
        body.append("<tr>" + "".join(cells) + "</tr>")
    label = plural(len(rows_), "starter")
    return (
        # Material styles, and makes scrollable, only a table with no class of its own.
        '<div class="lockrot-watch"><table>'
        + header(["New project", "Created from"], COUNTED)
        + "<tbody>" + "".join(body) + "</tbody>"
        + totals(rows_, previous, since, label, COUNTED)
        + "</table></div>"
    )


def since_line(rows_: list[dict], previous: dict, since: str | None) -> str:
    """One paragraph on what moved since the previous run, and which of the three causes it was.

    The causes are the ones "What moves these numbers" names: a project released, the tool changed,
    or the ecosystem moved under both. The first two can be read off the history; the third is
    whatever is left.

    The sums are the applications table's, so they are numbers a reader finds in its totals row —
    not the starters', which have their own, and not the older lines', which the page keeps out of
    every total. Only rows read on the same line both times are summed; when that is not all of
    them, the sentence says how many it covers.
    """
    if since is None:
        return "This is the first run; the next one is compared with it."

    then = {r["lockrot"] for r in previous.values()}
    now = rows_[0]["lockrot"]
    releases = [r for r in rows_ if r["kind"] == "release"]
    # A row whose newest line changed is named, and left out of every sum below.
    moved_lines = [(r, previous[r["name"]]) for r in releases if line_moved(r, previous.get(r["name"]))]
    same = comparable([r for r in rows_ if r["kind"] != "line"], previous)

    common = [r for r in releases if r["name"] in same]
    scope = (
        "the " + plural(len(common), "application")
        if len(common) == len(releases)
        else f"the {len(common)} of {plural(len(releases), 'application')} read on the same line both times"
    )
    parts = [f"Compared with the run of {since}, across {scope}:"]
    was, now_flagged = sum(flagged(same[r["name"]]) for r in common), sum(flagged(r) for r in common)
    moved = [f"flagged {was} → {now_flagged}"] if was != now_flagged else []
    measured = [r for r in common if r["composer_missed"] != "" and same[r["name"]].get("composer_missed")]
    if common and len(measured) == len(common):
        a = sum(int(same[r["name"]]["composer_missed"]) for r in measured)
        b = sum(int(r["composer_missed"]) for r in measured)
        if a != b:
            moved.append(f"not in `composer audit` {a} → {b}")
    for column in COLUMNS:
        a = sum(int(same[r["name"]][column] or 0) for r in common)
        b = sum(int(r[column]) for r in common)
        if a != b:
            moved.append(f"`{column}` {a} → {b}")
    parts.append(("; ".join(moved) + ".") if moved else "no total moved.")

    released = sorted(
        r["name"] for r in rows_
        if r["kind"] != "line" and r["name"] in same
        and (same[r["name"]].get("tag"), same[r["name"]].get("version")) != (r["tag"], r["version"])
    )
    if released:
        parts.append(
            f"Since then {len(released)} {'project' if len(released) == 1 else 'projects'} moved to a "
            "new release or starter version: " + ", ".join(released) + "."
        )
    if moved_lines:
        parts.append(
            " ".join(
                f"{r['name']} moved from {release_line(before['tag'])}.x to {r['line']}.x, so its row is not compared."
                for r, before in moved_lines
            )
        )
    if then != {now}:
        parts.append(
            f"lockrot itself moved from {', '.join(sorted(then))} to {now} between the two runs, so part "
            "of any change is the tool's."
        )
    return " ".join(parts)


def archive(history: list[dict]) -> str:
    """Every run in the history, newest first, each with a link to every report it published.

    The links are to /reports/watch/<date>/<name> on the viewer's host, which
    scripts/watch_archive.py builds out of the capsules each run committed.
    """
    runs = sorted({r["date"] for r in history}, reverse=True)
    blocks = []
    for date in runs:
        day = [r for r in history if r["date"] == date]
        version = day[0]["lockrot"]
        abandoned = sum(int(r["abandoned"] or 0) for r in day)
        silent = sum(int(r["silent"] or 0) for r in day)
        links = ", ".join(
            f'<a href="{VIEWER}/{date}/{html.escape(r["name"], quote=True)}">{html.escape(r["name"])}</a>'
            for r in day
        )
        blocks.append(
            f'<details class="lockrot-run"><summary><span class="lockrot-run-mark" aria-hidden="true"></span>'
            f'<strong>{date}</strong> · lockrot {html.escape(version)}'
            f" · {len(day)} reports · {abandoned} abandoned, {silent} silent</summary>"
            f"<p>{links}</p></details>"
        )
    return "\n".join(blocks)


def headline(releases: list[dict]) -> str:
    """The page's one-sentence answer to why it exists: of what lockrot flags in the applications,
    how much Composer's own check names. Only when composer audit was asked about every one of
    them; a total over some of them would be a different claim."""
    if not releases or any(r["composer_missed"] == "" for r in releases):
        return ""
    total = sum(flagged(r) for r in releases)
    missed = sum(int(r["composer_missed"]) for r in releases)
    return (
        f"Of the **{total}** packages lockrot flags in these {len(releases)} applications, "
        f"`composer audit` names {total - missed}. It says nothing at all about the other "
        f"**{missed}**.\n\n"
    )


def composer_note(rows_: list[dict]) -> str:
    """The sentence that says what the composer audit column measured, and with which Composer.

    Written from the run, so it names the version that ran, and says nothing for a run that did not
    ask composer audit at all.
    """
    versions = sorted({r["composer"] for r in rows_ if r["composer"]})
    if not versions:
        return ""
    unmeasured = [r for r in rows_ if r["composer_missed"] == ""]
    if not unmeasured:
        gap = ""
    elif all(r["kind"] == "starter" for r in unmeasured):
        gap = " The fresh installs below show a dash: this run did not ask composer audit about them."
    else:
        gap = f" A dash marks the {len(unmeasured)} projects this run did not ask composer audit about."
    return (
        "*Not in `composer audit`* is the flagged packages that `composer audit --locked "
        f"--abandoned=report` (Composer {', '.join(versions)}), run on the same lock file, does not "
        "name at all — as abandoned or as carrying an advisory; its percentage is their share of the "
        "flagged ones. Composer reads the `abandoned` marker the lock file carries, so a "
        "package marked on Packagist after the lock was written is missed as well "
        f"([what that adds up to](blog/posts/2026-09-19-composer-audit-abandoned-misses.md)).{gap} "
    )


def lines_section(
    lines_: list[dict], releases: list[dict], previous: dict, since: str | None, run: dict, window: int
) -> str:
    """The older release lines still releasing: a table of their own, kept out of the totals above.

    Empty when the run read none and skipped none, so a run from before lines were read prints no
    heading over nothing. A line skipped because its releases carry no lock file is named here, not
    dropped: a project that seems to have one line may have two the run could not read.
    """
    skipped = run.get("skipped_lines", [])
    if not lines_ and not skipped:
        return ""
    repos = {r["name"]: r["repo"] for r in releases}
    projects = {r["parent"] for r in lines_} | {m["project"] for m in skipped}
    intro = (
        f"{len(projects)} of the {plural(len(releases), 'application')} maintain more than one release "
        "line at a time. The table above reads each one's newest line."
    )
    if lines_:
        intro += (
            " This one reads every older line still kept beside a newer one: it has released in the "
            f"last {window} years — the window lockrot gives a release branch before it calls the "
            "branch left behind (`left-behind`, signal S8) — and after the next line up first did, "
            "which is what makes two lines concurrent rather than one following the other. A project "
            "counts once in the totals above; these rows are not in them."
        )
    parts = ["## Older lines still releasing\n\n" + intro]
    if lines_:
        parts.append(table(lines_, previous, since, label="older line"))
    if skipped:
        def tried(attempts: list[str]) -> str:
            tags = [attempt.split(" (", 1)[0] for attempt in attempts]
            rest = f" and {len(tags) - 2} more" if len(tags) > 2 else ""
            return ", ".join(tags[:2]) + rest

        named = "; ".join(
            f"{repos.get(m['project'], m['project'])} {m['line']}.x (tried {tried(m['tried'])})"
            for m in skipped
        )
        parts.append(
            "Released inside the window, but with no lock file at the releases the run tried, so "
            f"with no row: {named}."
        )
    return "\n\n".join(parts) + "\n\n"


def _common(values: dict, what: str) -> tuple:
    """The value most reports carry, and the projects whose report carries another.

    A project can set lockrot's thresholds in its own composer.json (`extra.lockrot`), and lockrot
    honours that over its defaults; the workflow passes none. So one project's own setting is a fact
    the prose names, not a reason to publish nothing.
    """
    if any(value is None for value in values.values()):
        missing = sorted(name for name, value in values.items() if value is None)
        raise SystemExit(f"build_watch_page: no {what} in the reports of {', '.join(missing)}")
    common = Counter(values.values()).most_common(1)[0][0]
    return common, sorted(name for name, value in values.items() if value != common)


def _but(names: list[str]) -> str:
    return "" if not names else " but " + (names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1])


def run_settings(reports: dict, manifest: dict | None = None) -> dict:
    """What the page says about how the run was made, read from the run rather than written into
    the prose: the PHP version the reports were measured against, the years `silent` takes, and the
    window lockrot gives a release branch — each the value most reports carry, with the projects
    that differ named.

    lockrot's own list of flagged verdicts, which no project can change, has to be the page's
    columns in order: Flagged adds those columns up, and a release that flags one more verdict would
    otherwise make every total on the page quietly short. The plan's window for older lines has to
    be lockrot's default `release-warn-years`, which is what most reports carry.
    """
    runs = {name: report.get("run", {}) for name, report in reports.items()}
    for run in runs.values():
        if run.get("flagged_verdicts") != COLUMNS:
            raise SystemExit(
                f"build_watch_page: lockrot flags {run.get('flagged_verdicts')}, the page has columns "
                f"for {COLUMNS}; give the page the new verdict before publishing it"
            )

    def threshold(run: dict, key: str):
        return (run.get("thresholds") or {}).get(key)

    target, other_targets = _common({n: r.get("target_php") for n, r in runs.items()}, "target PHP")
    span, own_span = _common(
        {n: (threshold(r, "release-high-years"), threshold(r, "push-high-years")) for n, r in runs.items()},
        "silent thresholds",
    )
    if None in span:
        raise SystemExit("build_watch_page: the reports carry no release-high-years or push-high-years")
    window, _ = _common({n: threshold(r, "release-warn-years") for n, r in runs.items()}, "release-warn-years")
    planned = (manifest or {}).get("run", {}).get("line_window_years")
    if planned is not None and planned != window:
        raise SystemExit(
            f"build_watch_page: the plan read older lines back {planned} years, lockrot's "
            f"release-warn-years is {window}; change LINE_WINDOW_YEARS in watch_plan.py to match"
        )

    release, push = span
    silent = (
        f"no stable release and no push to any branch for {release} years"
        if release == push
        else f"no stable release for {release} years and no push to any branch for {push}"
    )
    if own_span:
        silent += f" ({', '.join(own_span)} set their own in `extra.lockrot`)"
    return {
        "target_php": target,
        "target_scope": "every project here" + _but(other_targets),
        "silent_span": silent,
        "window": window,
    }


def lockless(projects: dict, rows_: list[dict]) -> str:
    """The starters in this run whose project commits no lock file, as the prose names them.

    From the flag in data/watch/projects.json, so the sentence follows the list instead of being a
    second copy of it.
    """
    names = {r["name"] for r in rows_}
    titles = [
        s.get("prose_name") or s["title"] for s in projects.get("starters", [])
        if s.get("no_lock_in_repository") and s["name"] in names
    ]
    if not titles:
        raise SystemExit("build_watch_page: no starter in the run is marked no_lock_in_repository")
    return titles[0] if len(titles) == 1 else ", ".join(titles[:-1]) + " and " + titles[-1]


def write_history(path: Path, rows_: list[dict]) -> None:
    kept = []
    if path.is_file():
        date = rows_[0]["date"]
        kept = [r for r in read_history(path) if r["date"] != date]

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        # csv writes CRLF by default; the rest of the repository's data files are LF, and a weekly
        # commit that flipped the endings would be unreadable as a diff.
        writer = csv.DictWriter(fh, fieldnames=HISTORY_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(kept)
        writer.writerows({k: row[k] for k in HISTORY_FIELDS} for row in rows_)


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("data/reports/watch/manifest.json"))
    parser.add_argument("--capsules", type=Path, default=Path("data/reports/watch"))
    parser.add_argument("--history", type=Path, default=Path("content/assets/data/watch/history.csv"))
    parser.add_argument("--page", type=Path, default=Path("content/watch.md"))
    parser.add_argument("--projects", type=Path, default=Path("data/watch/projects.json"))
    args = parser.parse_args(argv[1:])

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    reports = read_capsules(args.capsules)
    settings = run_settings(reports, manifest)
    rows_ = rows(manifest, reports, read_composer(args.capsules))
    since, previous = previous_run(read_history(args.history), manifest["run"]["date"])
    write_history(args.history, rows_)

    releases = [row for row in rows_ if row["kind"] == "release"]
    lines_ = [row for row in rows_ if row["kind"] == "line"]
    starters = [row for row in rows_ if row["kind"] == "starter"]
    if not releases:
        raise SystemExit("build_watch_page: the run read no releases")
    older = {}
    for row in lines_:
        older[row["parent"]] = older.get(row["parent"], 0) + 1

    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(
        PAGE.format(
            count=len(releases),
            starters=len(starters),
            date=manifest["run"]["date"],
            version=rows_[0]["lockrot"],
            since=since_line(rows_, previous, since),
            table=table(releases, previous, since, older=older),
            lines_section=lines_section(lines_, releases, previous, since, manifest["run"], settings["window"]),
            starter_table=starter_table(starters, previous, since) if starters else "",
            history="assets/data/watch/history.csv",
            archive=archive(read_history(args.history)),
            composer_note=composer_note(rows_),
            headline=headline(releases),
            lockless=lockless(json.loads(args.projects.read_text(encoding="utf-8")), rows_),
            target_php=settings["target_php"],
            target_scope=settings["target_scope"],
            silent_span=settings["silent_span"],
        ),
        encoding="utf-8",
    )
    print(
        f"build-watch-page: {len(releases)} releases, {len(lines_)} older lines and {len(starters)} starters, "
        f"run {manifest['run']['date']}, compared with {since or 'nothing'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
