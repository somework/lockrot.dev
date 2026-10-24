---
title: lockrot — find abandoned and unmaintained Composer packages
og_description: Composer warns about packages whose maintainers said they stopped. lockrot finds the ones that just stopped.
hide:
  - toc
---

# lockrot

**Finds abandoned, unmaintained and branch-pinned packages in `composer.lock` — and releases that
promise a PHP version they were never tested against.**

## Install

=== "Composer plugin"

    ```bash
    composer require --dev somework/lockrot
    composer config allow-plugins.somework/lockrot true
    composer lockrot --target-php=8.4
    ```

    Adds one dev dependency and one command. It also prints a short summary during
    `composer require`, `update` and `install`, above the operations list — see
    [Install-time summary](install-time.md).

=== "PHAR"

    ```bash
    curl -fsSL -o lockrot.phar https://lockrot.dev/lockrot.phar
    php lockrot.phar --target-php=8.4
    ```

    Nothing is added to your project. For the checksum-verified download and how
    `self-update` works, see [PHAR and self-update](phar.md).

=== "Global plugin"

    ```bash
    composer global require somework/lockrot
    composer global config allow-plugins.somework/lockrot true
    ```

    `composer global update` keeps it current. Because it is a plugin rather than a
    PHAR, the install-time summary then runs in every project you touch;
    [Install-time summary](install-time.md) explains how to turn that off.

Requires PHP 7.4 or newer and Composer 2.2 or newer.

## What a run looks like

<pre class="lockrot-term"><span class="b">critical (3)</span>
  javibravo/simpleue 2.1.0  direct  ·  <span class="r">silent · old-promise</span>
      36 = silent 32 + old-promise 4 [¼ of 16]
      do: find a maintained alternative: nothing released for 8.9 years
      silent       last release 2017-11-15 (8.9 years ago); last push 2017-11-18 (8.9 years ago)
      old-promise  released 2017-11-15 for PHP 5 (php &quot;&gt;=5.5&quot;), before PHP 8 existed (8.0 GA 2020-11-26); admits 8.4
                   untested
  mnapoli/piwik-twig-extension 3.0.0  direct  ·  <span class="r">silent · old-promise</span>
      36 = silent 32 + old-promise 4 [¼ of 16]
      do: find a maintained alternative: nothing released for 6.5 years
      silent       last release 2020-04-24 (6.5 years ago); last push 2020-04-28 (6.5 years ago)
      old-promise  released 2020-04-24 for PHP 7 (php &quot;&gt;=7.0&quot;), before PHP 8 existed (8.0 GA 2020-11-26); admits 8.4
                   untested
  sensio/framework-extra-bundle v6.2.10  direct  ·  <span class="r">abandoned</span>
      32 = abandoned 32
      do: replace it: its registry suggests &quot;Symfony&quot;
      abandoned    marked abandoned by its registry, replacement: Symfony; its repository is archived on GitHub; last
                   release 2023-02-24 (3.7 years ago); last push 2023-02-24 (3.7 years ago)
      pulls in 1 flagged package: doctrine/annotations (abandoned)</pre>

The first 19 lines of a real run against wallabag's 200-package lock file, at 120 columns. They hold
three of its 58 graded findings — [read the whole report](example-run.md).
{ .lockrot-caption }

A run on a smaller project, 156 packages, from the command to the summary block and the footer:

![lockrot in a terminal: the command, then the last findings, each with its flags, its score and a do: line, then the summary block with the counts by grade and by flag, and the "Data as of" footer](assets/lockrot-demo.gif){ .lockrot-demo width="1214" height="889" loading="lazy" }

## What it looks for

- **`abandoned`** — the package's own repository says so: Packagist carries the `abandoned` marker a
  maintainer set by hand, or the repository is archived on GitHub or GitLab.
- **`silent`** — five years with no stable release *and* five years with no push to the repository,
  on the default thresholds. Nobody announced anything; the package simply stopped.
- **`pinned`** — your lock file holds a branch snapshot (`dev-master`, `dev-main`, `2.x-dev`)
  instead of a released version. The thing you installed then has no version number anyone else can
  ask for. A package with no tagged release at all is `pinned` too.
- **`old-promise`** — the release predates the GA of your target PHP's major (8.0 for any 8.x).
  Its `require.php` constraint is open-ended (`>=7.2`), so Composer accepted it on a PHP nobody
  released it against. `composer check-platform-reqs` is satisfied too: `>=7.2` is true on 8.4.
- **`left-behind`** — the release branch you installed from has had no release for years while a
  higher branch of the same package keeps shipping. `composer outdated --major-only` says a newer
  major exists; this says the branch you are on gets no fixes, and its `do:` line names the
  constraint that follows the fixes (`require doctrine/event-manager ^2.1`), written as
  `composer require` writes it.
- **`capped`** — from 0.14.0 on: the installed release's `require.php` stops below the newest PHP
  minor that the project allows. That minor is the newest released one that the project's php
  admits: `composer.json`'s `require.php`, else the lock's `platform.php`, else any.

Two more flags complete the eight. `stale` catches a package with no release or no push for three
years by default, short of `silent` — worth knowing, rarely worth acting on. `vulnerable` says that
a counted security advisory affects the installed version.

From 0.14.0 on, the flags are the facts and the verdict is a grade. The flags add up to a score, and
the score's band is `critical`, `high`, `medium` or `low`. A score of 0 reads `unknown`, `finished`
or `ok`, a word that says why. `lead` is the first counted maintenance flag, which heads the score
line: the 0.13 verdict word, or `capped`, which 0.13 did not have. It is null when only `vulnerable`
counts.

Every finding prints the sum behind its score and the evidence behind each flag. It also prints the
date the data was read and the chain of requirements that pulled the package in. That is what
`composer why` shows for one package, for every finding at once. It names every direct requirement
that the package is reachable from, not only the shortest chain. The table names three and counts
the rest, and each direct requirement says what it pulls in. [What it reports](verdicts.md) has
every flag, the score and the verdicts.

## "Composer already warns me about abandoned packages"

It does: `Package X is abandoned, you should avoid using it` on every install, and
`composer audit --abandoned` reports the same packages. Both read one field: the `abandoned` marker
a maintainer sets by hand on Packagist, as Composer copied it into `composer.lock` the last time it
resolved the package. Most packages that stop being maintained never get it, because setting it is
the last act of someone who has already walked away — so the field is accurate when it is there,
and silent the rest of the time. Across the lock files of 31 open-source PHP applications,
[`composer audit --abandoned` reported 62 of 129 abandoned or silent packages](blog/posts/2026-09-19-composer-audit-abandoned-misses.md).
`composer outdated` answers a different question, whether a newer version exists: a package can be
fully up to date and dead, or two majors behind and fine.

lockrot reads that field too, and then keeps going. It asks when the last stable release actually
landed, when the repository was last pushed to, whether your lock file is holding a branch snapshot
rather than a version, and whether a release made an open-ended PHP promise it was never tested
against. It reads `composer.lock` and `composer.json`, and it writes to neither.

`composer audit` reports the vulnerability. From 0.14.0 on, lockrot flags the package `vulnerable`
and adds the advisory to its score. It says which release fixes the advisory and what holds that
release, and names the move. An advisory that no release fixes, or whose fix the target PHP does not
run, counts twice.

## In CI

Nothing fails a build until you ask it to: `fail-on` is `none` by default, exit `1` means a finding
reached the threshold you chose, and exit `2` is reserved for lockrot's own errors. On GitHub
Actions, `uses: somework/lockrot-action@v1` is the whole step. Recipes for that, GitLab CI and PR
comments are in [In CI](ci.md); a [baseline](baseline.md) lets you accept what you have today and
fail only on what arrives tomorrow.

## Reading a report someone sent you

`--format=html` writes the whole run as one page that opens from a file and needs no server. When
what you have is the JSON instead, the [report viewer](https://viewer.lockrot.dev/) draws it the
same way: paste it, or drop either file in. Nothing is uploaded — the rendering happens in your
browser, in a sandbox with no way to reach the network — and it is on a host of its own rather than
this one, because a page that draws documents written by strangers does not belong on the domain
that hands out the archive. [Reading a report](viewer.md) is what the flags and the grades in one
mean.

## Questions

### Does it change `composer.json` or `composer.lock`?

No. It reads both and writes to neither. Outside its cache under Composer's `cache-dir`, it writes
only the files you ask for: a [baseline](baseline.md) with `--generate-baseline`, and a report with
[`--output`](configuration.md#writing-reports-to-files).

### Can it break `composer install`?

Not unless you ask it to. The [install-time summary](install-time.md) prints at most 10 lines
within a 5-second budget and never stops the transaction; a failed lookup is reported, not raised.
`install-time-strict` is the opt-in that lets it stop one, `"install-time": "off"` turns the summary
off for a project, and `LOCKROT_DISABLE=1` silences lockrot for one command.

### Do I need a GitHub token?

No, but it sees more with one. Without a token, lockrot checks repository activity only for
packages whose releases already look stale, at most 50 per host per run. It reports how many the
cap affected. With `GITHUB_TOKEN` set, or Composer's own
`github-oauth`, every package is checked.
[Data sources](internals.md#repository-hosts-and-credentials) has the GitLab and
Bitbucket rules.

### Does it work with Private Packagist, Satis or a mirror?

Yes, with nothing to configure. lockrot reads the repositories already in your `composer.json`
through Composer's own repository layer, with Composer's authentication and proxy settings.

### Does it work offline, and what happens when the network fails?

`--offline` reads metadata from Composer's cache and repository activity from lockrot's own, and
checks no advisories. A network failure never
turns into a non-zero exit code on its own: the check that could not run is reported as a note.
`--strict-network` makes it exit `1` instead.

### The project already has dozens of findings. Where do I start?

With a [baseline](baseline.md): `--generate-baseline` records what is there today, and CI then
fails only on findings that are new or have got worse.

### Why is this package flagged — or why is it not?

`composer lockrot --explain=vendor/package` prints that one package with everything it was decided
on. It prints the verdict, the flags and the score with each step of the sum. It prints the move,
what holds it, and how the package is reached. It prints every signal with its raw data and the dates
behind it, and the `composer.lock` entry. It prints the release branches the repository lists with
their dates, the repository activity, and the thresholds the run measured against.

`composer why` answers who requires it; this answers why lockrot judged it so. Exit `0`, it does not gate —
[Explaining one package](configuration.md#explaining-one-package).

### A package is finished, not abandoned. How do I say so?

Interface packages, frozen polyfills and metapackages are not rot. `psr/*`, `fig/*`,
`symfony/polyfill-*` and a few more are on the built-in allowlist: it accepts their maintenance flags,
and a package with nothing else that counts reads `finished`. For anything else, add an entry with a
reason to `extra.lockrot.ignore` —
[the allowlist](configuration.md#the-allowlist).

## Read on

| Page | What is on it |
|---|---|
| [What it reports](verdicts.md) | The flags, the signals behind them, the score that adds them up, and the verdicts |
| [Configuration](configuration.md) | `extra.lockrot`, every option, and the command-line flags |
| [In CI](ci.md) | GitHub Actions, GitLab CI, SARIF, PR comments |
| [Reading a report](viewer.md) | What a report says, and the viewer that opens one |
| [Baseline](baseline.md) | Accept today's findings, fail on new and worsened ones |
| [Install-time summary](install-time.md) | What the plugin prints during `install`/`update`, and how to silence it |
| [PHAR and self-update](phar.md) | Verified and signed download, PHIVE, `self-update`, the global-plugin alternative |
| [Example run](example-run.md) | The full 200-package report the sample above is cut from |
| [Data sources](internals.md) | Composer repositories, the GitHub, GitLab and Bitbucket APIs, caching, `--offline` |
| [Changelog](changelog.md) | What changed, release by release |
| [Weekly watch](watch.md) | What lockrot finds in the newest release of widely used PHP applications, and in projects created from scratch that morning — and how much of it `composer audit` names |
| [Blog](blog/index.md) | Notes from building lockrot: dependency rot, Composer internals, release engineering |

Source and issues live on [GitHub](https://github.com/somework/lockrot); the package is
[`somework/lockrot` on Packagist](https://packagist.org/packages/somework/lockrot). Released under
the MIT licence.
