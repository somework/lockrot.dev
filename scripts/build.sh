#!/usr/bin/env bash
# Assemble build/docs and build the site. Reference pages and their assets come from .lockrot/docs;
# everything in content/ is copied over them, so a file of the same name in content/ wins
# (index.md, the landing page, is the one that does).
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .lockrot/docs ] || scripts/fetch-lockrot.sh
scripts/check-nav.sh

rm -rf build/docs
mkdir -p build/docs
# Only what the site renders: pages and assets. Not lockrot's own overrides, requirements or
# redirects — the site owns those under content/.
cp .lockrot/docs/*.md build/docs/
mkdir -p build/docs/assets
cp .lockrot/docs/assets/* build/docs/assets/
cp -R content/. build/docs/

export LOCKROT_REF="$(cat .lockrot/REF)"
if [ "${1:-build}" = "serve" ]; then
  exec mkdocs serve --strict "${@:2}"
fi
mkdocs build --strict
echo "build: site/ built from lockrot $LOCKROT_REF"
