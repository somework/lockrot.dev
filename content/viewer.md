---
title: Read a lockrot report — what the flags, the score and the grades mean
description: Someone sent you a lockrot report. What it says, how its flags add up to a score and a grade, and where to open one in the browser.
---

# Reading a lockrot report

Someone ran lockrot over a `composer.lock` and sent you the result. This page is what that
document says and how to argue with it.

[Open a report in the viewer](https://viewer.lockrot.dev/){ .md-button .md-button--primary }

The viewer takes the JSON a `--format=json` run writes, or the single-file page `--format=html`
writes, and draws it in your browser. Nothing is uploaded: the document is rendered in a sandbox
that has no way to reach the network, on a host of its own rather than this one, because a page
that draws documents written by other people should not sit on the domain that hands out the
archive.

The viewer draws report-2, the document of lockrot 0.14.0 and later. For a report-1 document, from
lockrot 0.13 or older, rerun lockrot 0.14, or open the document with
[lockrot-report](https://github.com/somework/lockrot-report) 0.13.

## What a report is

Three kinds of file get called "the report", and the viewer takes any of them.

| What you were sent | What it is |
| --- | --- |
| `report.json` | The document `composer lockrot --format=json` writes. Validates against the [published schema](schema.md). |
| `report.html` | The whole run as one page, from `--format=html`. Opens on its own, no viewer needed. |
| A link to the viewer | The document travels inside the link. Nothing is fetched from anywhere. |

The JSON is the one worth keeping. It carries every finding with its flags, the evidence behind
them, its score and the requirement chain that pulled the package in. From 0.10.0 on it also carries a
`run` block with what the run was told to do. That is the project's name, the target PHP, the
thresholds and the `fail-on`. Two
reports can therefore be compared without wondering whether they differ because the locks differ or
because the settings did.

Every report this site publishes is that page and nothing else. The reports of the
[weekly watch](watch.md) and the thirty-one behind
[what `composer audit --abandoned` misses](blog/posts/2026-09-19-composer-audit-abandoned-misses.md)
open with no server, no upload and no viewer in front of them.

## The flags, the score and the grade

A finding has flags and a verdict, and they answer different questions. The flags say what was
observed: `abandoned`, `silent`, `pinned`, `left-behind`, `old-promise`, `stale`, `capped` and
`vulnerable`. Each one is a claim that is true whenever it shows. The verdict says how much the
finding matters to this project. The flags add up to a score, and the score's band is the grade,
from `critical` to `low`. A score of 0 reads `unknown`, `finished` or `ok`, a word that says why.

Where the package sits changes the score. A package that `composer.json` does not require directly
halves its maintenance points. A package in packages-dev halves the whole score. An advisory that no release fixes, or whose fix the
target PHP does not run, counts twice.

So a `silent` package three levels deep in your development dependencies is not the same problem as
a `silent` package your application calls directly. The report says so without you having to work
it out: each finding prints the sum behind its score. `lead` is the first counted maintenance flag,
which heads the score line: the 0.13 verdict word, or `capped`, which 0.13 did not have. It is null
when only `vulnerable` counts. [What it reports](verdicts.md) has the
score, every flag, and every signal with the evidence it needs.

lockrot 0.13 printed the observation as the verdict and its weight as a priority.
lockrot-report 0.13.0, the renderer that reads them, draws the reports that this site published
from runs of lockrot 0.13 and older.

## What it does not claim

lockrot reads release dates, repository activity, security advisories, `composer.json` and the
lock file. It does not read your code. It cannot know that a package is finished rather than
abandoned — an interface package or a polyfill changes only when the interface does. Those are in an allowlist, with a reason attached to each
entry, and a project can add its own in [configuration](configuration.md).

A flag is an observation with its evidence attached, and a grade is not a judgement about whether
you are safe. Both are meant to be argued with, which is why every finding carries the evidence
behind each flag and the sum behind its score.

## Producing one yourself

```bash
composer require --dev somework/lockrot
composer lockrot --target-php=8.4 --format=html > report.html
```

Or without installing anything into the project, with the [PHAR](phar.md):

```bash
curl -fsSLO https://lockrot.dev/lockrot.phar
php lockrot.phar --target-php=8.4 --format=html > report.html
```

In CI the same run becomes an artifact your reviewers can open, and `--fail-on` decides whether it
also fails the build. [In CI](ci.md) has the recipes; a [baseline](baseline.md) lets a project
accept what it has today and fail only on what arrives tomorrow.
