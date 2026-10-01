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
from pathlib import Path

# Cloudflare serves reports/<name>.html at reports/<name> and redirects the .html form there
# (`html_handling: auto-trailing-slash` in wrangler.viewer.jsonc), so the link skips the 307.
VIEWER = "https://viewer.lockrot.dev/reports/watch"

HISTORY_FIELDS = [
    "date", "lockrot", "kind", "repo", "package", "tag", "version", "commit", "packages",
    "advisories", "abandoned", "silent", "pinned", "left-behind", "old-promise", "stale",
    "unknown", "marked_on_packagist", "name",
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

{since}

## What these applications ship

{table}

A project's name opens the full report lockrot wrote for it; a column heading sorts the table. A
small number beside a count is how far it moved since the previous run, and *new* marks a project
that cut a release in between. Each row names the release it read and the commit that release points
at, so any number here can be
checked against the same two files lockrot read. A release rather than a branch head on purpose: a
release is what people install, and it is the only version of a project that two weeks of this page
can be compared across — the tip of a development branch moves for reasons that have nothing to do
with dependency rot.

## What a new project gets today

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

Several projects in this table cannot be in the one above, and for one reason: Shopware, Sylius,
TYPO3, Craft CMS, Statamic and WordPress-through-Bedrock do not commit a lock file to their
repository. Their lock is born at `create-project` time, which is the only place it can be read —
and is the version their users actually run.

A verdict is an observation, not a judgement, and the two that carry most of the table say
different things. `abandoned` is the Packagist marker or an archived repository — someone said so.
`silent` is no stable release and no push to any branch for five years, which is lockrot's default
threshold and not a law of nature: a package that encodes base64url does not need a release in 2035
either. That is what the [allowlist](configuration.md#the-allowlist) is for, and a project that has
looked at one of these and decided it is fine can say so in its own `composer.json` in one line.

`old-promise` counts against PHP 8.4 for every project here, whatever each one actually targets,
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

The second table is where the rest of them turn up. WordPress, Shopware, Sylius, TYPO3, Craft CMS,
Statamic, Pimcore, Dolibarr, Roundcube, osTicket, SilverStripe, Contao, October, MODX, ProcessWire
and Vanilla commit no lock file at all; their dependency tree exists only once someone installs
them, so that is where it is read. The starters are the ways people actually begin a PHP project —
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
$ composer lockrot --target-php=8.4 --fail-on=silent
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


def rows(manifest: dict, capsules: dict) -> list[dict]:
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
            }
        )
    return out


def order(rows_: list[dict]) -> list[dict]:
    """The order a table is printed in, which is the order a reader without JavaScript gets.

    Heaviest first: a package abandoned by its own maintainer is the strongest claim on the page,
    a package silent for years the next, and the name breaks the ties so a week with no change
    prints the same page.
    """
    return sorted(rows_, key=lambda r: (-int(r["abandoned"]), -int(r["silent"]), r["name"]))


def previous_run(history: list[dict], date: str) -> tuple[str | None, dict]:
    """The newest run before `date` in the history, as its date and its rows by project name."""
    earlier = sorted({r["date"] for r in history if r["date"] < date})
    if not earlier:
        return None, {}
    last = earlier[-1]
    return last, {r["name"]: r for r in history if r["date"] == last}


def read_history(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(newline="", encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


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


def new_mark(moved: bool, was: str, since: str | None) -> str:
    if not moved:
        return ""
    return f' <span class="lockrot-new" title="{html.escape(was)} on {html.escape(since or "")}">new</span>'


def project_cell(row: dict) -> str:
    owner, _, repo = row["repo"].partition("/")
    return (
        f'<td data-sort="{html.escape(row["repo"].lower(), quote=True)}">'
        f'<a href="{VIEWER}/{html.escape(row["name"], quote=True)}" title="Open the report lockrot wrote">'
        f'<span class="lockrot-owner">{html.escape(owner)}/</span>{html.escape(repo)}</a></td>'
    )


def release_cell(row: dict, before: dict | None, since: str | None) -> str:
    repo_url = f"https://github.com/{row['repo']}"
    tag_url = row.get("tag_url") or f"{repo_url}/releases/tag/{row['tag']}"
    commit_url = row.get("commit_url") or f"{repo_url}/tree/{row['commit']}"
    moved = before is not None and before.get("tag") != row["tag"]
    return (
        f'<td class="lockrot-release"><a href="{html.escape(tag_url, quote=True)}">{html.escape(row["tag"])}</a>'
        f' <a class="lockrot-commit" href="{html.escape(commit_url, quote=True)}">'
        f"<code>{html.escape(row['commit'][:7])}</code></a>"
        f"{new_mark(moved, (before or {}).get('tag', ''), since)}</td>"
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
    cells += [
        f'<th class="lockrot-num" data-sort-method="number" data-sort-reverse>{"Advisories" if c == "advisories" else f"<code>{c.replace("-", "-<wbr>")}</code>"}</th>'
        for c in counted
    ]
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
    for column in counted:
        value = sum(int(r[column]) for r in rows_)
        cells.append(f"<td>{value}{delta(value, before(column), since)}</td>")
    return "<tfoot><tr>" + "".join(cells) + "</tr></tfoot>"


def table(rows_: list[dict], previous: dict | None = None, since: str | None = None) -> str:
    """The applications: one row per project, read from the release it names."""
    previous = previous or {}
    body = []
    for row in order(rows_):
        before = previous.get(row["name"])
        cells = [project_cell(row), release_cell(row, before, since)]
        cells.append(count_cell(int(row["packages"]), (before or {}).get("packages"), since))
        cells += [count_cell(int(row[c]), (before or {}).get(c), since, c) for c in COLUMNS]
        body.append("<tr>" + "".join(cells) + "</tr>")
    return (
        # Material styles, and makes scrollable, only a table with no class of its own.
        '<div class="lockrot-watch"><table>'
        + header(["Project", "Release"], COLUMNS)
        + "<tbody>" + "".join(body) + "</tbody>"
        + totals(rows_, previous, since, f"{len(rows_)} projects", COLUMNS)
        + "</table></div>"
    )


def starter_table(rows_: list[dict], previous: dict | None = None, since: str | None = None) -> str:
    """The second table: a project created on the day of the run, not one that shipped.

    It carries an advisories column the first table cannot: starters are read with `--all`, so a
    package that is perfectly healthy apart from a CVE is in the document. The applications are
    read without it, where such a package is not a finding and never reaches the page.
    """
    previous = previous or {}
    body = []
    for row in order(rows_):
        before = previous.get(row["name"])
        cells = [starter_cells(row, before, since)]
        cells.append(count_cell(int(row["packages"]), (before or {}).get("packages"), since))
        cells += [count_cell(int(row[c]), (before or {}).get(c), since, c) for c in COUNTED]
        body.append("<tr>" + "".join(cells) + "</tr>")
    label = f"{len(rows_)} starter{'' if len(rows_) == 1 else 's'}"
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
    """
    if since is None:
        return "This is the first run; the next one is compared with it."

    then = {r["lockrot"] for r in previous.values()}
    now = rows_[0]["lockrot"]
    parts = [f"Compared with the run of {since}:"]

    moved = []
    for column in COUNTED:
        common = [r for r in rows_ if r["name"] in previous]
        a = sum(int(previous[r["name"]][column] or 0) for r in common)
        b = sum(int(r[column]) for r in common)
        if a != b:
            moved.append(f"`{column}` {a} → {b}" if column != "advisories" else f"advisories {a} → {b}")
    parts.append(("; ".join(moved) + ".") if moved else "no total moved.")

    released = sorted(
        r["name"] for r in rows_
        if r["name"] in previous
        and (previous[r["name"]].get("tag"), previous[r["name"]].get("version")) != (r["tag"], r["version"])
    )
    if released:
        parts.append(
            f"Since then {len(released)} {'project' if len(released) == 1 else 'projects'} moved to a "
            "new release or starter version: " + ", ".join(released) + "."
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
            f'<details class="lockrot-run"><summary><strong>{date}</strong> · lockrot {html.escape(version)}'
            f" · {len(day)} reports · {abandoned} abandoned, {silent} silent</summary>"
            f"<p>{links}</p></details>"
        )
    return "\n".join(blocks)


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
    args = parser.parse_args(argv[1:])

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    rows_ = rows(manifest, read_capsules(args.capsules))
    since, previous = previous_run(read_history(args.history), manifest["run"]["date"])
    write_history(args.history, rows_)

    releases = [row for row in rows_ if row["kind"] == "release"]
    starters = [row for row in rows_ if row["kind"] == "starter"]
    if not releases:
        raise SystemExit("build_watch_page: the run read no releases")

    args.page.parent.mkdir(parents=True, exist_ok=True)
    args.page.write_text(
        PAGE.format(
            count=len(releases),
            starters=len(starters),
            date=manifest["run"]["date"],
            version=rows_[0]["lockrot"],
            since=since_line(rows_, previous, since),
            table=table(releases, previous, since),
            starter_table=starter_table(starters, previous, since) if starters else "",
            history="assets/data/watch/history.csv",
            archive=archive(read_history(args.history)),
        ),
        encoding="utf-8",
    )
    print(
        f"build-watch-page: {len(releases)} releases and {len(starters)} starters, "
        f"run {manifest['run']['date']}, compared with {since or 'nothing'}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
