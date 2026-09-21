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
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

VIEWER = "https://viewer.lockrot.dev/reports/watch"

HISTORY_FIELDS = [
    "date", "lockrot", "kind", "repo", "package", "tag", "version", "commit", "packages",
    "advisories", "abandoned", "silent", "pinned", "left-behind", "old-promise", "stale",
    "unknown", "marked_on_packagist",
]

# The verdicts the page has a column for, in the order the tool ranks them.
COLUMNS = ["abandoned", "silent", "pinned", "left-behind", "old-promise", "stale"]

PAGE = """---
title: Dependency rot in {count} open-source PHP applications and {starters} fresh installs
head_title: Dependency rot in {count} PHP applications — a weekly lockrot run
description: >-
  Every week lockrot reads the composer.lock of the newest release of {count} widely used
  open-source PHP applications, and of {starters} projects created that day with composer
  create-project: what is abandoned, silent for years, pinned to a branch or carrying an advisory.
  Last run {date}.
---

# Dependency rot in {count} PHP applications, and in {starters} fresh installs

Every Monday lockrot {version} reads two kinds of `composer.lock` and reports the packages in them
that stopped being maintained: the lock the **newest stable release** of {count} open-source PHP
applications ships, and the lock {starters} **new projects** get when they are created that morning
with `composer create-project`. This page is the last run, {date}. Nothing is installed, no script
or plugin from any package is run, and no project is contacted: the run reads lock files, then asks
Packagist and the repository host about the packages in them.

## What these applications ship

{table}

Each row names the release it read and the commit that release points at, so any number here can be
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


def table(rows_: list[dict]) -> str:
    # The release and the commit share a cell. Both have to be here — a tag can be moved, a commit
    # cannot — but eleven columns is a table nobody can read without scrolling it sideways.
    head = (
        "| Project | Release | Packages | "
        + " | ".join(f"`{c}`" for c in COLUMNS)
        + " | Report |"
    )
    rule = "|---|---|---:|" + "---:|" * len(COLUMNS) + "---|"
    lines = [head, rule]
    for row in rows_:
        repo_url = f"https://github.com/{row['repo']}"
        tag_url = row.get("tag_url") or f"{repo_url}/releases/tag/{row['tag']}"
        commit_url = row.get("commit_url") or f"{repo_url}/tree/{row['commit']}"
        cells = " | ".join(str(row[c]) or "0" for c in COLUMNS)
        lines.append(
            f"| [{row['repo']}]({repo_url}) "
            f"| [{row['tag']}]({tag_url})&nbsp;· [`{row['commit'][:7]}`]({commit_url}) "
            f"| {row['packages']} | {cells} | [open]({VIEWER}/{row['name']}.html) |"
        )
    totals = {c: sum(int(r[c]) for r in rows_) for c in COLUMNS}
    lines.append(
        f"| **{len(rows_)} projects** | | **{sum(int(r['packages']) for r in rows_)}** | "
        + " | ".join(f"**{totals[c]}**" for c in COLUMNS)
        + " | |"
    )
    return "\n".join(lines)


def starter_table(rows_: list[dict]) -> str:
    """The second table: a project created on the day of the run, not one that shipped.

    It carries an advisories column the first table cannot: starters are read with `--all`, so a
    package that is perfectly healthy apart from a CVE is in the document. The applications are
    read without it, where such a package is not a finding and never reaches the page.
    """
    head = (
        "| New project | Created from | Packages | Advisories | "
        + " | ".join(f"`{c}`" for c in COLUMNS)
        + " | Report |"
    )
    rule = "|---|---|---:|---:|" + "---:|" * len(COLUMNS) + "---|"
    lines = [head, rule]
    for row in rows_:
        package = row["package"]
        url = row.get("packagist_url") or f"https://packagist.org/packages/{package}"
        cells = " | ".join(str(row[c]) or "0" for c in COLUMNS)
        advisories_cell = f"**{row['advisories']}**" if row["advisories"] else "0"
        lines.append(
            f"| {row['title']} | [{package} {row['version']}]({url}) | {row['packages']} "
            f"| {advisories_cell} | {cells} | [open]({VIEWER}/{row['name']}.html) |"
        )
    totals = {c: sum(int(r[c]) for r in rows_) for c in COLUMNS}
    lines.append(
        f"| **{len(rows_)} starter{'' if len(rows_) == 1 else 's'}** "
        f"| | **{sum(int(r['packages']) for r in rows_)}** "
        f"| **{sum(int(r['advisories']) for r in rows_)}** | "
        + " | ".join(f"**{totals[c]}**" for c in COLUMNS)
        + " | |"
    )
    return "\n".join(lines)


def write_history(path: Path, rows_: list[dict]) -> None:
    kept = []
    if path.is_file():
        date = rows_[0]["date"]
        with path.open(newline="", encoding="utf-8") as fh:
            kept = [r for r in csv.DictReader(fh) if r["date"] != date]

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
            table=table(releases),
            starter_table=starter_table(starters) if starters else "",
            history="assets/data/watch/history.csv",
        ),
        encoding="utf-8",
    )
    print(
        f"build-watch-page: {len(releases)} releases and {len(starters)} starters, "
        f"run {manifest['run']['date']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
