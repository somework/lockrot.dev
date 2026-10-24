# report-2 fixtures

Documents lockrot wrote, kept byte for byte, for the tests of `scripts/build_watch_page.py`.

From lockrot `release/0.14.0` at commit `1cf33bc1` (lockrot-report v0.14.0-rc.2 vendored):

| File | Source in that commit |
|---|---|
| `B.json` | `tests/fixtures/contract/report-2/B.json` |
| `ignored-marking-archived-dagger.json` | `tests/fixtures/contract/report-2/ignored-marking-archived-dagger.json` |
| `explain-2.json` | `tests/fixtures/contract/explain-2/A-baselined-dagger.json` |
| `baseline-2.json` | `tests/fixtures/contract/baseline-2/01-left-behind-direct-a-new-high-advisory.json` |

The two magento2 documents read the same lock with the same recorded answers, so a 0.13 count and
its 0.14 counterpart can be compared on one set of data:

- the lock: `tests/fixtures/apps/magento_magento2/` in that commit;
- the answers: `tests/fixtures/corpus/cache/`, read offline through `Lockrot\Tests\Support\FixtureCliRun`
  the way `tools/corpus/differential.php` reads them, at the clock `2026-10-14T00:00:00+00:00`;
- the options: `--target-php=8.4 --format=json`.

| File | Written by |
|---|---|
| `magento2-0.13.0.json.gz` | the v0.13.0 PHAR, sha256 `935883f2d2f52ce0f801f9ede846ee5eb42565aa5fd57b47137a82db8c611b1f` (report-1) |
| `magento2-0.14.0.json.gz` | `bin/lockrot` of commit `1cf33bc1` (report-2). The branch had not yet set its version, so the document says `"version": "0.13.0"` beside `"schema": 2` |

From lockrot `integration/0.14-php-window` at commit `0cfbd1c4`, whose report-2 flag set carries
`capped` (S11) after `stale`:

| File | Source in that commit |
|---|---|
| `capped-local-dagger.json` | `tests/fixtures/contract/report-2/capped-local-dagger.json`: `capped` leads a package |
| `stale-capped.json` | `tests/fixtures/contract/report-2/stale-capped.json`: `capped` beside a `stale` lead |
