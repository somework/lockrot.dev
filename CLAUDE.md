# lockrot.dev

The website at https://lockrot.dev: landing page, blog and the rendered reference docs of
[lockrot](https://github.com/somework/lockrot). MkDocs + Material, static, served by a Cloudflare
Worker. Chat with the maintainer is in Russian; everything committed here is English.

## The one rule

**Reference docs are not edited here.** `scripts/fetch-lockrot.sh` checks lockrot out at its newest
release tag into `.lockrot/` and `scripts/build.sh` copies `.lockrot/docs/*.md` into `build/docs/`
before laying `content/` over it. A change to a verdict, an option or a CLI flag belongs in
`somework/lockrot` `docs/`, next to the code that changed. This repo owns: the landing page
(`content/index.md`), the blog, the theme, the redirects, the deploy.

## Commands

| Command | What it does |
|---|---|
| `python3.12 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements.txt` | One-time setup (Python 3.12, see `.python-version`; the lock file is compiled for it) |
| `export PATH=$PWD/.venv/bin:$PATH` | Put `mkdocs` on the path for the commands below |
| `scripts/build.sh` | Fetch lockrot (if `.lockrot/` is missing), check the nav, build `site/` with `--strict` |
| `scripts/build.sh serve` | Same assembly, then `mkdocs serve --strict` on http://127.0.0.1:8000 (drafts visible) |
| `LOCKROT_REF=main scripts/fetch-lockrot.sh` | Re-fetch lockrot at `main` (or any tag) to preview unreleased docs |
| `rm -rf .lockrot && scripts/build.sh` | Back to the newest release tag |
| `scripts/check-nav.sh` | Fail if a page in `.lockrot/docs/` is missing from `mkdocs.yml` `nav` |
| `pip-compile --generate-hashes --strip-extras --output-file=requirements.txt requirements.in` | Re-lock after editing `requirements.in` (needs `pip install pip-tools`, run under Python 3.12) |

Dependencies: `requirements.in` names the three packages the site asks for; `requirements.txt` is
the pip-compile lock with every transitive package pinned and hashed. Edit the first, regenerate the
second, never hand-edit it. Dependabot updates both.

`--strict` turns every MkDocs warning into a failure: a broken relative link, a page outside the
nav that another page links to, an unknown `!ENV`. Fix the cause, never drop the flag.

## Layout

```
content/               # the site's own docs_dir overlay, copied over .lockrot/docs at build
  index.md             # landing page (overrides lockrot's docs/index.md)
  changelog.md         # include-markdown of ../../.lockrot/CHANGELOG.md
  blog/index.md        # blog landing; the Material blog plugin renders the list
  blog/.authors.yml    # author ids used in post front matter
  blog/posts/          # one file per post, see "Writing a post"
  assets/              # extra.css (the coloured terminal sample, link colours), og.png
  overrides/main.html  # <title> rule and OpenGraph tags (Material's social plugin needs Cairo)
  overrides/partials/copyright.html  # footer: Material's partial plus "built from lockrot <ref>"
  _redirects           # /lockrot.phar -> GitHub latest release, 302 on purpose (see the file)
  _headers             # CSP and security headers; a new external origin must be added to the CSP
  robots.txt
mkdocs.yml             # theme, nav, plugins (blog, rss, include-markdown); docs_dir is build/docs
scripts/               # fetch-lockrot.sh, check-nav.sh, build.sh
wrangler.jsonc         # Cloudflare Worker "lockrot", static assets from ./site
.github/workflows/     # ci.yml (PRs: build + internal link check), deploy.yml (main, lockrot release,
                       # weekly, manual), links.yml (weekly external link check)
.lockrot/ build/ site/ # generated, git-ignored, safe to delete
```

## The blog is hidden for now

Until the first post is finished the blog is not built: `blog/` is in `exclude_docs`, the blog
plugin has `enabled: false`, the rss plugin is commented out, and the nav entry, the RSS icon in
`extra.social` and the "Read on" row in `content/index.md` are removed. The files under
`content/blog/` stay. To bring it back, revert the hiding commit
(`git log --grep='hide the blog'`), then finish the draft. While hidden, `scripts/build.sh serve`
does not render posts either.

## Writing a post

`content/blog/posts/YYYY-MM-DD-slug.md`, front matter first:

```yaml
---
draft: true                 # drop when publishing; drafts render only under `serve`
date: 2026-09-17
authors: [igor]             # ids from content/blog/.authors.yml
categories: [Releases]      # one of the categories_allowed list in mkdocs.yml, or extend the list
slug: signed-releases       # URL: /blog/2026/09/17/signed-releases/
description: One sentence for search and the OpenGraph card.
---
```

Then a `# Title`, one or two paragraphs, `<!-- more -->` (required: `post_excerpt: required`), the
rest. A post with a future `date` stays a draft on its own.

Voice, same as the docs and README: plain, specific, evidence first. Name the version a claim is
true for (`from 0.5.0 on`), show the real command and its real output, no marketing adjectives, no
"we're excited". Facts about lockrot are checked against `.lockrot/` (the tagged source) before
they go in — the reference pages there are the source of truth, not memory.

## Coupling with lockrot, in both directions

- `nav` in `mkdocs.yml` lists every page under `.lockrot/docs/`. A page added there fails
  `scripts/check-nav.sh` here until it is added to the nav — on purpose, so it is never silently
  unreachable.
- The landing page `content/index.md` started as a copy of lockrot's `docs/index.md` and now lives
  here; its "Read on" table names the reference pages, keep it in step with the nav.
- `content/changelog.md` includes `.lockrot/CHANGELOG.md`; the `[Unreleased]` section of a tagged
  checkout is usually empty, which is correct for a site that documents releases.
- `edit_uri` points at lockrot's `docs/`; the edit button is not enabled, so it is inert.
- The site follows the **newest `vX.Y.Z` tag** (pre-release tags are skipped), not `main`: a doc
  change in lockrot appears here after the next release. `LOCKROT_REF=main` is for previewing,
  never for deploying.

## Deploy

`deploy.yml` builds and runs `wrangler deploy` on: a push to `main`, a `repository_dispatch` with
`event_type: lockrot-release` (to be sent by lockrot's `phar.yml` after a release), a weekly
schedule (the safety net for a dispatch that never arrived), or a manual run.
Secrets on the `production` environment: `CLOUDFLARE_API_TOKEN` (Workers Scripts: Edit on the
account), `CLOUDFLARE_ACCOUNT_ID`. Until the Cloudflare side is switched over, the old Workers
Builds connection on the lockrot repo still deploys the same Worker — see README "Cutover".

## Do not

- Do not push, deploy, or change Cloudflare settings without the maintainer's explicit yes.
- Do not commit `site/`, `build/`, `.lockrot/` or `.venv/`.
- Do not edit files under `build/` or `.lockrot/`; they are overwritten by the next build.
- Do not drop `--strict`, `check-nav.sh` or an action's SHA pin to get a build green.
- Do not hand-edit `requirements.txt`; change `requirements.in` and re-run pip-compile.
- Do not paste tokens, deploy hook URLs or account ids into committed files.
