---
title: Read a lockrot report — what the verdicts and signals mean
description: Someone sent you a lockrot report. What it says, how a verdict is decided against a priority, and where to open one in the browser.
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

## What a report is

Three kinds of file get called "the report", and the viewer takes any of them.

| What you were sent | What it is |
| --- | --- |
| `report.json` | The document `composer lockrot --format=json` writes. Validates against the [published schema](schema.md). |
| `report.html` | The whole run as one page, from `--format=html`. Opens on its own, no viewer needed. |
| A link to the viewer | The document travels inside the link. Nothing is fetched from anywhere. |

The JSON is the one worth keeping. It carries every finding with the dates the verdict was decided
on, the requirement chain that pulled the package in, and — from 0.10.0 — a `run` block saying what
the run was told to do: the project's name, the target PHP, the thresholds and the `fail-on`. Two
reports can therefore be compared without wondering whether they differ because the locks differ or
because the settings did.

## The verdict is not the whole answer

A finding has a verdict and a priority, and they answer different questions. The verdict says what
was observed — `abandoned`, `silent`, `pinned`, `left-behind`, `old-promise`, `stale`. The priority
says how much it should matter here: a package nothing requires directly drops a step, one installed
only for development drops another, an advisory that no release will fix raises it one.

So a `silent` package three levels deep in your development dependencies is not the same problem as
a `silent` package your application calls directly, and the report says so without you having to
work it out. [What it reports](verdicts.md) has the full ladder, and every signal `S1` to `S9` with
the evidence it needs.

## What it does not claim

lockrot reads release dates, repository activity and the lock file. It does not read your code, and
it cannot know that a package is finished rather than abandoned — an interface package or a polyfill
changes only when the interface does. Those are in an allowlist, with a reason attached to each
entry, and a project can add its own in [configuration](configuration.md).

A verdict is an observation with its evidence attached, not a judgement about whether you are safe.
It is meant to be argued with, which is why every finding carries the dates rather than a score.

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
