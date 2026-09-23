---
title: Dependency rot in 20 open-source PHP applications and 15 fresh installs
head_title: Dependency rot in 20 PHP applications — a weekly lockrot run
description: >-
  Every week lockrot reads the composer.lock of the newest release of 20 widely used
  open-source PHP applications, and of 15 projects created that day with composer
  create-project: what is abandoned, silent for years, pinned to a branch or carrying an advisory.
  Last run 2026-09-23.
---

# Dependency rot in 20 PHP applications, and in 15 fresh installs

Every Monday lockrot 0.11.0 reads two kinds of `composer.lock` and reports the packages in them
that stopped being maintained: the lock the **newest stable release** of 20 open-source PHP
applications ships, and the lock 15 **new projects** get when they are created that morning
with `composer create-project`. This page is the last run, 2026-09-23. Nothing is installed, no script
or plugin from any package is run, and no project is contacted: the run reads lock files, then asks
Packagist and the repository host about the packages in them.

## What these applications ship

| Project | Release | Packages | `abandoned` | `silent` | `pinned` | `left-behind` | `old-promise` | `stale` | Report |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| [coollabsio/coolify](https://github.com/coollabsio/coolify) | [v4.3.23](https://github.com/coollabsio/coolify/releases/tag/v4.3.23)&nbsp;· [`e2e2d40`](https://github.com/coollabsio/coolify/tree/e2e2d4010bcd590084b66d6f748f3eec8e2bbee9) | 161 | 0 | 2 | 0 | 0 | 0 | 5 | [open](https://viewer.lockrot.dev/reports/watch/coolify) |
| [appwrite/appwrite](https://github.com/appwrite/appwrite) | [2.2.0](https://github.com/appwrite/appwrite/releases/tag/2.2.0)&nbsp;· [`5105525`](https://github.com/appwrite/appwrite/tree/51055258e99ba4b96398c7fc1180afb281fe3402) | 91 | 2 | 1 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/appwrite) |
| [bagisto/bagisto](https://github.com/bagisto/bagisto) | [v2.4.12](https://github.com/bagisto/bagisto/releases/tag/v2.4.12)&nbsp;· [`805b670`](https://github.com/bagisto/bagisto/tree/805b67013134ebc53f1da1285f0aa6632f5dde62) | 167 | 0 | 0 | 0 | 2 | 1 | 6 | [open](https://viewer.lockrot.dev/reports/watch/bagisto) |
| [monicahq/monica](https://github.com/monicahq/monica) | [v4.1.2](https://github.com/monicahq/monica/releases/tag/v4.1.2)&nbsp;· [`32028ce`](https://github.com/monicahq/monica/tree/32028ce3ce79cef38df5d27a297e5b20680f0065) | 181 | 7 | 2 | 1 | 16 | 2 | 6 | [open](https://viewer.lockrot.dev/reports/watch/monica) |
| [firefly-iii/firefly-iii](https://github.com/firefly-iii/firefly-iii) | [v6.7.3](https://github.com/firefly-iii/firefly-iii/releases/tag/v6.7.3)&nbsp;· [`99f9b74`](https://github.com/firefly-iii/firefly-iii/tree/99f9b7477d064b1d1729a4348e43fffef1b385ce) | 132 | 0 | 1 | 1 | 0 | 0 | 6 | [open](https://viewer.lockrot.dev/reports/watch/firefly-iii) |
| [matomo-org/matomo](https://github.com/matomo-org/matomo) | [5.14.0](https://github.com/matomo-org/matomo/releases/tag/5.14.0)&nbsp;· [`9499b8a`](https://github.com/matomo-org/matomo/tree/9499b8a35efce4bb2d655ca24d9153576dcae39c) | 55 | 1 | 4 | 2 | 6 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/matomo) |
| [BookStackApp/BookStack](https://github.com/BookStackApp/BookStack) | [v26.05.5](https://github.com/BookStackApp/BookStack/releases/tag/v26.05.5)&nbsp;· [`771a2d0`](https://github.com/BookStackApp/BookStack/tree/771a2d04927dab0ce07edc5874aeb18896f830c4) | 113 | 0 | 0 | 0 | 0 | 0 | 3 | [open](https://viewer.lockrot.dev/reports/watch/bookstack) |
| [grokability/snipe-it](https://github.com/grokability/snipe-it) | [v8.7.2](https://github.com/grokability/snipe-it/releases/tag/v8.7.2)&nbsp;· [`f3f1dd7`](https://github.com/grokability/snipe-it/tree/f3f1dd722b167587c7819f3c518cc5b14475f89f) | 166 | 1 | 5 | 1 | 5 | 1 | 5 | [open](https://viewer.lockrot.dev/reports/watch/snipe-it) |
| [wallabag/wallabag](https://github.com/wallabag/wallabag) | [2.6.14](https://github.com/wallabag/wallabag/releases/tag/2.6.14)&nbsp;· [`74cbfd9`](https://github.com/wallabag/wallabag/tree/74cbfd945bc316b5cf0308ba56e32fd2ed3443c0) | 210 | 27 | 10 | 1 | 54 | 3 | 7 | [open](https://viewer.lockrot.dev/reports/watch/wallabag) |
| [magento/magento2](https://github.com/magento/magento2) | [2.4.9](https://github.com/magento/magento2/releases/tag/2.4.9)&nbsp;· [`755e34d`](https://github.com/magento/magento2/tree/755e34dd689021c5165db9d35ecff74f7dc51527) | 148 | 4 | 0 | 0 | 1 | 1 | 5 | [open](https://viewer.lockrot.dev/reports/watch/magento2) |
| [mautic/mautic](https://github.com/mautic/mautic) | [7.2.0](https://github.com/mautic/mautic/releases/tag/7.2.0)&nbsp;· [`504af18`](https://github.com/mautic/mautic/tree/504af18cf90d8fbe701fde55cb1a94603db9e21a) | 193 | 2 | 2 | 1 | 10 | 2 | 6 | [open](https://viewer.lockrot.dev/reports/watch/mautic) |
| [akaunting/akaunting](https://github.com/akaunting/akaunting) | [3.2.4](https://github.com/akaunting/akaunting/releases/tag/3.2.4)&nbsp;· [`3940b76`](https://github.com/akaunting/akaunting/tree/3940b76b12cb86592dcb44147e8912742945a4c9) | 183 | 16 | 0 | 0 | 7 | 2 | 10 | [open](https://viewer.lockrot.dev/reports/watch/akaunting) |
| [invoiceninja/invoiceninja](https://github.com/invoiceninja/invoiceninja) | [v5.13.43](https://github.com/invoiceninja/invoiceninja/releases/tag/v5.13.43)&nbsp;· [`3820200`](https://github.com/invoiceninja/invoiceninja/tree/382020072bc79e8c7ede49f7e9ce91b0aeb1a051) | 245 | 0 | 0 | 2 | 7 | 2 | 9 | [open](https://viewer.lockrot.dev/reports/watch/invoiceninja) |
| [PrestaShop/PrestaShop](https://github.com/PrestaShop/PrestaShop) | [9.1.5](https://github.com/PrestaShop/PrestaShop/releases/tag/9.1.5)&nbsp;· [`aee413e`](https://github.com/PrestaShop/PrestaShop/tree/aee413eedd5fdc5053f28fb998da4b7e286cf641) | 227 | 4 | 3 | 0 | 8 | 3 | 17 | [open](https://viewer.lockrot.dev/reports/watch/prestashop) |
| [moodle/moodle](https://github.com/moodle/moodle) | [v5.2.3](https://github.com/moodle/moodle/releases/tag/v5.2.3)&nbsp;· [`344232c`](https://github.com/moodle/moodle/tree/344232c15336c71b80f9aca8359ce0e0a9f3d116) | 48 | 0 | 1 | 0 | 0 | 2 | 1 | [open](https://viewer.lockrot.dev/reports/watch/moodle) |
| [phpmyadmin/phpmyadmin](https://github.com/phpmyadmin/phpmyadmin) | [RELEASE_5_2_3](https://github.com/phpmyadmin/phpmyadmin/releases/tag/RELEASE_5_2_3)&nbsp;· [`962857e`](https://github.com/phpmyadmin/phpmyadmin/tree/962857e4f63d42e38f11ff4d63f5e722018add76) | 58 | 2 | 1 | 0 | 9 | 2 | 0 | [open](https://viewer.lockrot.dev/reports/watch/phpmyadmin) |
| [phpbb/phpbb](https://github.com/phpbb/phpbb) | [release-3.3.17](https://github.com/phpbb/phpbb/releases/tag/release-3.3.17)&nbsp;· [`3508484`](https://github.com/phpbb/phpbb/tree/3508484fdc18cd97eeab229da830055c79fcc59e) | 40 | 4 | 1 | 0 | 16 | 1 | 2 | [open](https://viewer.lockrot.dev/reports/watch/phpbb) |
| [joomla/joomla-cms](https://github.com/joomla/joomla-cms) | [6.1.3](https://github.com/joomla/joomla-cms/releases/tag/6.1.3)&nbsp;· [`0f2d4de`](https://github.com/joomla/joomla-cms/tree/0f2d4de4729eb951e0878fec98c7990da07915b2) | 89 | 2 | 0 | 2 | 2 | 0 | 4 | [open](https://viewer.lockrot.dev/reports/watch/joomla-cms) |
| [drupal/drupal](https://github.com/drupal/drupal) | [11.4.7](https://github.com/drupal/drupal/releases/tag/11.4.7)&nbsp;· [`e0e7bfb`](https://github.com/drupal/drupal/tree/e0e7bfbc2d29f74e97ce98fd33df79aa97bed4e4) | 66 | 0 | 1 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/drupal) |
| [TYPO3/typo3](https://github.com/TYPO3/typo3) | [v14.3.7](https://github.com/TYPO3/typo3/releases/tag/v14.3.7)&nbsp;· [`07f4dc8`](https://github.com/TYPO3/typo3/tree/07f4dc8267d1824a3021c00cd36c5ad8ee7f84a1) | 77 | 0 | 0 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/typo3) |
| **20 projects** | | **2650** | **72** | **34** | **11** | **143** | **22** | **96** | |

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

| New project | Created from | Packages | Advisories | `abandoned` | `silent` | `pinned` | `left-behind` | `old-promise` | `stale` | Report |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Laravel | [laravel/laravel v13.10.1](https://packagist.org/packages/laravel/laravel) | 76 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/new-laravel) |
| Symfony (skeleton) | [symfony/skeleton v8.1.99](https://packagist.org/packages/symfony/skeleton) | 1 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | [open](https://viewer.lockrot.dev/reports/watch/new-symfony) |
| Symfony (--webapp) | [symfony/skeleton v8.1.99](https://packagist.org/packages/symfony/skeleton) | 133 | 0 | 0 | 0 | 0 | 0 | 0 | 2 | [open](https://viewer.lockrot.dev/reports/watch/new-symfony-webapp) |
| API Platform | [symfony/skeleton v8.1.99](https://packagist.org/packages/symfony/skeleton) | 47 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/new-api-platform) |
| Drupal | [drupal/recommended-project 11.4.7](https://packagist.org/packages/drupal/recommended-project) | 68 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/new-drupal) |
| WordPress (Bedrock) | [roots/bedrock 1.31.6](https://packagist.org/packages/roots/bedrock) | 15 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | [open](https://viewer.lockrot.dev/reports/watch/new-wordpress) |
| Shopware | [shopware/production v6.7.14.2](https://packagist.org/packages/shopware/production) | 173 | 0 | 0 | 0 | 0 | 0 | 0 | 5 | [open](https://viewer.lockrot.dev/reports/watch/new-shopware) |
| Sylius | [sylius/sylius-standard v2.2.4](https://packagist.org/packages/sylius/sylius-standard) | 195 | 0 | 3 | 0 | 0 | 1 | 1 | 4 | [open](https://viewer.lockrot.dev/reports/watch/new-sylius) |
| TYPO3 | [typo3/cms-base-distribution v14.3.0](https://packagist.org/packages/typo3/cms-base-distribution) | 106 | 0 | 0 | 0 | 0 | 0 | 0 | 1 | [open](https://viewer.lockrot.dev/reports/watch/new-typo3) |
| Craft CMS | [craftcms/craft 5.8.0](https://packagist.org/packages/craftcms/craft) | 111 | 0 | 0 | 2 | 0 | 1 | 2 | 7 | [open](https://viewer.lockrot.dev/reports/watch/new-craft) |
| Statamic | [statamic/statamic v6.5.1](https://packagist.org/packages/statamic/statamic) | 123 | 0 | 0 | 1 | 0 | 0 | 0 | 6 | [open](https://viewer.lockrot.dev/reports/watch/new-statamic) |
| Pimcore | [pimcore/skeleton v2026.2.0](https://packagist.org/packages/pimcore/skeleton) | 187 | 0 | 1 | 1 | 0 | 0 | 2 | 6 | [open](https://viewer.lockrot.dev/reports/watch/new-pimcore) |
| Slim | [slim/slim-skeleton 4.5.0](https://packagist.org/packages/slim/slim-skeleton) | 16 | 0 | 0 | 1 | 0 | 1 | 0 | 0 | [open](https://viewer.lockrot.dev/reports/watch/new-slim) |
| CakePHP | [cakephp/app 5.4.0](https://packagist.org/packages/cakephp/app) | 20 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | [open](https://viewer.lockrot.dev/reports/watch/new-cakephp) |
| Yii 2 | [yiisoft/yii2-app-basic 2.0.55](https://packagist.org/packages/yiisoft/yii2-app-basic) | 25 | 0 | 0 | 0 | 0 | 1 | 1 | 0 | [open](https://viewer.lockrot.dev/reports/watch/new-yii2) |
| **15 starters** | | **1296** | **0** | **4** | **6** | **0** | **4** | **7** | **34** | |

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

The 20 are applications people deploy, chosen on two public signals and one hard constraint.
The signals: how widely a thing is actually run, where someone else measures it — W3Techs, 21
September 2026, puts Joomla on 1.1% of all websites, Drupal on 0.6% and Adobe's Magento on 0.6% —
and GitHub stars, which is what puts Coolify, Appwrite and Bagisto at the top of any list of PHP
applications today.

The constraint decided more of the first table than either signal: **a project has to commit
`composer.json` and `composer.lock` at a tagged release.** Of the 300 most-starred PHP repositories
and a hand list of the widely-deployed ones — 109 looked at — 61 came through that filter, and
these 20 are chosen from those 61 for spread across what the applications actually do: CMS,
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
[`history.csv`](assets/data/watch/history.csv) carries the release, the commit and the lockrot version that produced it
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
