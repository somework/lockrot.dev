#!/usr/bin/env bash
# Assemble build/docs and build the site. Reference pages and their assets come from .lockrot/docs;
# everything in content/ is copied over them, so a file of the same name in content/ wins
# (index.md, the landing page, is the one that does).
set -euo pipefail
cd "$(dirname "$0")/.."

# .git as well as docs: scripts/mkdocs_hooks.py dates the reference pages from that history, and a
# checkout left by an older fetch-lockrot.sh does not have it.
{ [ -d .lockrot/docs ] && [ -d .lockrot/.git ]; } || scripts/fetch-lockrot.sh
# The schemas of the commit the repository variable SCHEMAS_REF names, or nothing when it is empty:
# see scripts/fetch-schemas.sh. deploy.yml and ci.yml pass the variable in.
scripts/fetch-schemas.sh
scripts/check-nav.sh

rm -rf build/docs
mkdir -p build/docs
# Only what the site renders: pages and assets. Not lockrot's own overrides, requirements or
# redirects — the site owns those under content/. Pages in subdirectories too (verdicts/model-1.md),
# at the same path, which is the URL their links and the nav give them.
rsync -a --prune-empty-dirs --exclude='/overrides/' --exclude='/assets/' --include='*/' --include='*.md' --exclude='*' \
  .lockrot/docs/ build/docs/
cp -R .lockrot/docs/assets build/docs/assets
# lockrot's docs/changelog.md includes "../CHANGELOG.md", which from build/docs is build/CHANGELOG.md.
# Putting the file there keeps the page, and its front matter, lockrot's own.
cp .lockrot/CHANGELOG.md build/CHANGELOG.md
cp -R content/. build/docs/
scripts/copy-schemas.sh
# One page per report schema number, after copy-schemas.sh: the report-1 page waits for report-2.json.
python3 scripts/schema_pages.py
# The JSON behind each published report, unpacked from the capsules in data/reports/ so that git
# holds one copy of a run and not two. A post links these; the pages that render them are built by
# scripts/build-viewer.sh onto the viewer's host.
python3 scripts/build_reports.py --capsules data/reports --json-out build/docs/assets/data

export LOCKROT_REF="$(cat .lockrot/REF)"
if [ "${1:-build}" = "serve" ]; then
  exec mkdocs serve --strict "${@:2}"
fi
mkdocs build --strict
echo "build: site/ built from lockrot $LOCKROT_REF"
