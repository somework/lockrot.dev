---
draft: false
date: 2026-09-20
authors: [igor]
categories: [Dependency rot]
slug: composer-audit-abandoned-misses
description: 129 packages in 31 open-source PHP projects are abandoned, archived or five years silent. composer audit --abandoned reports 62, and the lock file explains why.
---

# What composer audit --abandoned misses in 31 PHP projects

129 of the 4,109 production packages in 31 open-source PHP applications are marked abandoned on
Packagist, archived on GitHub, or have gone five years without a stable release or a push.
`composer audit --abandoned` reports 62 of them. The lock files are wallabag's, Matomo's,
Magento's, Drupal's, Joomla's, phpBB's, Moodle's, PrestaShop's and 23 more, read on 2026-09-19
with `--no-dev`.

<!-- more -->

The other 67 split two ways. 56 carry no `abandoned` marker anywhere, so no Composer command has
anything to say about them. 11 *are* marked abandoned on Packagist, and `composer audit` still
does not report them, because it never asks Packagist.

## The numbers

Every lock file is the project's default branch as of 2026-09-19, read with `--no-dev`, so only
what runs in production counts. The middle column is lockrot 0.8.0's `abandoned` and `silent`
verdicts together (lockrot is the tool this site documents: it reads `composer.lock` and asks
Packagist and the repository host about each package). `abandoned` is the Packagist marker or an
archived repository; `silent` is no stable release *and* no push to any branch for five years, the
default thresholds. "Marked" is the subset with the marker. The last column is what
`composer audit --abandoned=report --no-dev --locked` (Composer 2.10.3) printed for the same file;
it never named a package outside the middle column.

| Project | Packages | abandoned + silent | Marked | `composer audit` |
|---|---:|---:|---:|---:|
| wallabag/wallabag | 200 | 27 | 19 | 16 |
| akaunting/akaunting | 183 | 16 | 16 | 16 |
| concretecms/concretecms | 158 | 13 | 11 | 10 |
| humhub/humhub | 210 | 12 | 1 | 1 |
| PrestaShop/PrestaShop | 228 | 7 | 4 | 0 |
| phpbb/phpbb | 86 | 7 | 5 | 5 |
| salesagility/SuiteCRM-Core | 210 | 7 | 5 | 3 |
| snipe/snipe-it | 167 | 6 | 1 | 1 |
| chamilo/chamilo-lms | 271 | 6 | 0 | 0 |
| matomo-org/matomo | 52 | 4 | 1 | 1 |
| magento/magento2 | 148 | 4 | 4 | 4 |
| mautic/mautic | 193 | 4 | 2 | 2 |
| pixelfed/pixelfed | 147 | 4 | 0 | 0 |
| librenms/librenms | 138 | 4 | 1 | 1 |
| monicahq/monica | 165 | 2 | 1 | 1 |
| joomla/joomla-cms | 93 | 2 | 2 | 1 |
| firefly-iii/firefly-iii | 132 | 1 | 0 | 0 |
| moodle/moodle | 61 | 1 | 0 | 0 |
| drupal/drupal | 64 | 1 | 0 | 0 |
| espocrm/espocrm | 125 | 1 | 0 | 0 |
| 11 projects with none | 1,078 | 0 | 0 | 0 |
| **31 projects** | **4,109** | **129** | **73** | **62** |

The eleven with none are BookStack, koel, Cachet, Invoice Ninja, Kanboard, Pterodactyl, OpenCart,
phpMyAdmin, Ampache, symfony/demo and TYPO3. The commit each lock file was read at, the per-project
reports and a summary with the `abandoned` / `silent` split per project are in
[the data](../../assets/data/2026-09-19-abandoned-in-31-projects/manifest.json).

Three projects account for 56 of the 129 rows, and the rows overcount the problems: the 129 are 97
distinct packages, and 26 of the rows are `hoa/*`, one upstream whose last releases are from 2017
with no push since 2021, pulled into wallabag through `wallabag/rulerz` and into akaunting
through `lorisleiva/laravel-search-string`. wallabag requires one of its 19 marked packages
directly (`sensio/framework-extra-bundle`); the rest arrive through something else.

## Three commands, one of which asks Packagist

`composer audit --abandoned` and the `Package X is abandoned, you should avoid using it` line on
every `composer install` read the same thing, and it is not Packagist. It is the `abandoned` field
Composer writes into `composer.lock` for a package that was abandoned when it last resolved it; for
every other package there is no field at all.
[`Installer.php:356`](https://github.com/composer/composer/blob/2.10.3/src/Composer/Installer.php#L356)
takes the locked repository and asks each package `isAbandoned()`;
[`AuditCommand.php:124`](https://github.com/composer/composer/blob/2.10.3/src/Composer/Command/AuditCommand.php#L124)
audits the locked packages under `--locked`, and otherwise `vendor/composer/installed.json`, which
is a copy of the lock written at install time. Packagist is contacted for security advisories, not
for the marker.

This is by design: a lock file is a snapshot, and `composer install` must produce the same
`vendor/` next year. Since Composer 2.7 (2024-02) `audit.abandoned` defaults to `fail`, so the 62
already break a build that runs `composer audit`; the question is which packages ever reach that
check. A package marked abandoned *after* its lock entry was written is invisible until something
makes Composer resolve it again. `doctrine/annotations` in wallabag's lock:

```text
$ jq '.packages[] | select(.name == "doctrine/annotations") | .abandoned' composer.lock
null
$ curl -s https://repo.packagist.org/p2/doctrine/annotations.json | jq '.packages["doctrine/annotations"][0].abandoned'
true
```

Eleven lock entries in the sample sit in that gap: four in PrestaShop, three in wallabag, two in
SuiteCRM, one each in Concrete CMS and Joomla. They are eight distinct packages, and three of the
eight a PHP developer will already know about: `doctrine/annotations` gave way to attributes,
`composer/package-versions-deprecated` says so in its name, `symfony/security-guard` was removed
in Symfony 6. `microsoft/azure-storage-blob` is not one of those: marked abandoned and archived by
Microsoft with no replacement named, an Azure storage client that handles account keys, in
SuiteCRM's production lock, and invisible to `composer audit`. The other four are
`doctrine/cache`, `behat/transliterator`, `jakeasmith/http_build_url` and
`marcusschwarz/lesserphp`.

"Just run `composer update`" closes the gap for the entries it resolves, and that is also where
the gap comes from: you learn about the marker when you update, on your laptop, and not in CI on a
release branch that on purpose does not update. A partial update rewrites only the entries it
resolved. On a throwaway project with `doctrine/annotations` 2.0.2 and the field removed from its entry, Composer
2.10.3 (funding and plugin lines trimmed):

```console
$ composer update psr/log --no-install
Loading composer repositories with package information
Updating dependencies
Nothing to modify in lock file
Writing lock file
$ jq '.packages[] | select(.name == "doctrine/annotations") | .abandoned' composer.lock
null
$ composer update doctrine/annotations --no-install
Loading composer repositories with package information
Updating dependencies
Lock file operations: 0 installs, 1 update, 0 removals
  - Upgrading doctrine/annotations (2.0.2 => 2.0.2)
Writing lock file
Package doctrine/annotations is abandoned, you should avoid using it. No replacement was suggested.
$ jq '.packages[] | select(.name == "doctrine/annotations") | .abandoned' composer.lock
true
```

PrestaShop's lock carries no `abandoned` field on any of its 228 entries, and four of those
packages are marked on Packagist; its `doctrine/cache` entry has read 2.2.0 since the first quarter
of 2024.

The third command is the one that does ask: `composer outdated` (and `composer show --latest`)
fetches current metadata and prints the warning for all three wallabag packages, whatever the lock
says, and `--strict` exits 1 for them too, since an abandoned package counts as outdated even at
its newest release. So does every package with a newer version, which makes it a noisy gate, and it
says nothing about the 56 below.

`composer audit` already accepts that one property of a locked package changes after the lock is
written; the advisory request exists for exactly that. Abandonment is the same kind of property: it
describes the package upstream today, not the version installed. lockrot asks because it reads each
package's repository metadata for the release dates anyway, through Composer's own repository layer
and cache; the marker is in the same file.

## The 56 nobody marked

I expected the marker to cover most of the dead packages; it covers 73 of the 129. The maintainer
sets it on Packagist, and nothing derives it from the repository: two
packages in the sample are archived on GitHub and carry no marker (`pear/console_color2`,
`sebastian/resource-operations`). The other 54 have had no stable release and no push to any
branch for at least five years, lockrot's `silent`. None of the 31 projects gets a word about any
of the 56 from Composer.

Three of the 54, as the report prints them (the `--target-php=8.4` clause is on the rows because
it was passed; it is not what makes them `silent`):

```text
  silent       namshi/jose 7.2.3  via lexik/jwt-authentication-bundle
               last release 2016-12-05 (9.8 years ago); last push 2021-06-18
               (5.3 years ago); released 2016-12-05, before PHP 8.4 GA
               (2024-11-21); php constraint ">=5.5" has no upper bound
  silent       grandt/phpzipmerge 1.0.4  via wallabag/phpepub › phpzip/phpzip
               last release 2015-08-18 (11.1 years ago); last push 2015-08-18
               (11.1 years ago); released 2015-08-18, before PHP 8.4 GA
               (2024-11-21); php constraint ">=5.3.0" has no upper bound
  silent       raoul2000/yii2-jcrop-widget 1.0.0  direct
               last release 2014-07-30 (12.1 years ago); last push 2018-01-28
               (8.6 years ago)
```

`namshi/jose` signs and verifies JWTs; its last release is from 2016 and it is in Chamilo LMS's
production lock through `lexik/jwt-authentication-bundle`. `grandt/phpzipmerge` is in wallabag's
through its EPUB export. `raoul2000/yii2-jcrop-widget` is a direct requirement of HumHub.

Five years is lockrot's default, and it sets the number. Counting the rows that are not marked or
archived and have both a last release and a last push older than the threshold: 114 at three
years, 54 at the default five, 33 at seven, 11 at ten.

`silent` is an observation, not a judgement. `ircmaxell/random-lib` does what `random_bytes()`
has done in core since PHP 7; `spomky-labs/base64url` encodes base64url and will not need a
release in 2035 either. That is what the [allowlist](../../configuration.md#the-allowlist) is
for: name the package, say why, and the report calls it `finished` from then on. Both take
someone looking at the package; the marker does not.

## In CI

lockrot lists all 129 under the two verdicts, with the evidence, the requirement chain and a
priority: `critical` for a direct production requirement, `high` for a transitive one.
`composer lockrot --fail-on=silent` fails on both verdicts (`abandoned` is the more severe and
`--fail-on` is inclusive); `--fail-on=abandoned` on the marked and archived ones only. A project
with a wallabag-sized list starts from a [baseline](../../baseline.md) and fails on what arrives
next; the [CI page](../../ci.md) has the GitHub Action and the GitLab recipe.

## Reproducing this

lockrot 0.8.0 (`lockrot.phar`, sha256 verified against the release), Composer 2.10.3, PHP 8.5.10,
default thresholds (`release-high-years` and `push-high-years` both 5), `--no-dev`, run on
2026-09-19 with `GITHUB_TOKEN` set. Each project's `composer.json` and `composer.lock` were taken
from the commit named in
[`manifest.json`](../../assets/data/2026-09-19-abandoned-in-31-projects/manifest.json); nothing was
installed. `--target-php=8.4` was passed but affects only the `old-promise` verdict, which this
post does not count. The per-project reports (`--format=json`, with the `ok` and `finished` rows
removed) and a
[`summary.csv`](../../assets/data/2026-09-19-abandoned-in-31-projects/summary.csv) are next to
the manifest.

129 is a floor. Of the 4,109 packages, 77 came from path or VCS repositories (58 of them
HumHub's) and were not checked: 63 of those returned no data from any repository and are reported
`unknown`, the other 14 are branch snapshots and reported `pinned`; none of the 77 is counted
here. Ten of the 46 distinct `silent` packages, drawn at random, were re-checked against Packagist's
metadata and the GitHub repository API
([`spot-check.txt`](../../assets/data/2026-09-19-abandoned-in-31-projects/spot-check.txt)); all
ten release and push dates matched.

The same numbers on any project, with the PHAR so that the lock file is not touched
([download and verify](../../phar.md)):

```console
$ GITHUB_TOKEN=... php lockrot.phar --fail-on=silent
$ composer audit --abandoned=report --no-dev --locked --format=json | jq '.abandoned | keys'
```

Without a token, GitHub allows 60 requests an hour and lockrot checks repository activity for at
most 50 packages per host per run, among those already old on release age, so a large lock
reports fewer `silent` findings than it has; see
[How it fetches metadata](../../internals.md). This run had a token, and none of the 31 reports
carries the note lockrot prints when the cap applied.
