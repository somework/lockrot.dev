# lockrot.dev

Source of [lockrot.dev](https://lockrot.dev): the landing page, the blog and the rendered reference
documentation of [lockrot](https://github.com/somework/lockrot), a Composer plugin and PHAR that
finds abandoned and unmaintained packages in `composer.lock`.

The reference pages are **not** kept here. The build checks lockrot out at its newest release tag
and renders its `docs/` next to this repository's own pages, so the site always describes the
version people download. Documentation fixes go to `somework/lockrot`; posts, the landing page and
the theme live here.

## Build locally

```bash
python3.12 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt
export PATH=$PWD/.venv/bin:$PATH
scripts/build.sh          # site/ from lockrot's newest tag, mkdocs --strict
scripts/build.sh serve    # live preview on http://127.0.0.1:8000, drafts included
```

`requirements.txt` is a pip-compile lock of `requirements.in` (every transitive package pinned and
hashed); after editing `requirements.in`, regenerate it under Python 3.12 with
`pip-compile --generate-hashes --strip-extras --output-file=requirements.txt requirements.in`.

`LOCKROT_REF=main scripts/fetch-lockrot.sh` previews unreleased documentation; delete `.lockrot/`
to go back to the newest tag.

## Deploy

GitHub Actions (`.github/workflows/deploy.yml`) builds the site and runs `wrangler deploy` against
the Cloudflare Worker `lockrot` on every push to `main`, on a `repository_dispatch` of type
`lockrot-release`, weekly, and on demand. The Worker serves `site/` as static assets; `content/_redirects`
keeps `https://lockrot.dev/lockrot.phar` pointing at the newest GitHub release.

### Cutover from the lockrot repository

Today the same Worker is deployed by Cloudflare Workers Builds connected to `somework/lockrot`.
To move it here, in this order:

1. Create the GitHub environment `production` with the secrets `CLOUDFLARE_API_TOKEN` (an API
   token with *Workers Scripts: Edit* on the account) and `CLOUDFLARE_ACCOUNT_ID`.
2. Run the `Deploy` workflow by hand once and check https://lockrot.dev and
   https://lockrot.dev/lockrot.phar.
3. Disconnect Workers Builds from `somework/lockrot` in the Cloudflare dashboard, so a push there
   no longer deploys the site.
4. In `somework/lockrot`: keep `docs/` and a `mkdocs build --strict` job as the docs linter; remove
   `wrangler.jsonc`, `docs/overrides/`, `docs/_redirects`, `docs/robots.txt`, `docs/requirements.txt`
   and the site-only parts of `mkdocs.yml`; add to `phar.yml`, after the release is published, a
   step that sends the rebuild signal:

   ```yaml
   - if: startsWith(github.ref, 'refs/tags/')
     run: gh api repos/somework/lockrot.dev/dispatches -f event_type=lockrot-release
     env: {GH_TOKEN: '${{ secrets.SITE_DISPATCH_TOKEN }}'}
   ```

   `SITE_DISPATCH_TOKEN` is a fine-grained token with *Contents: Read and write* on
   `somework/lockrot.dev` only.

## Licence

MIT, like lockrot. See [LICENSE](LICENSE).
