#!/usr/bin/env bash
# Check the lockrot repository out into .lockrot/ at the ref the site should document.
#
# Default: the newest release tag, so the reference pages describe what people download and not
# what sits on main. Only plain vX.Y.Z tags count: `sort -V` ranks v0.6.0-rc1 above v0.6.0, and a
# pre-release is not what people download. LOCKROT_REF=main (or any tag/branch) overrides it, for
# a preview of unreleased docs. The checkout is shallow and disposable; nothing here is ever
# committed.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="${LOCKROT_REPO:-https://github.com/somework/lockrot.git}"
REF="${LOCKROT_REF:-}"
if [ -z "$REF" ]; then
  REF="$(git ls-remote --tags --refs "$REPO" 'v*' | awk -F/ '{print $NF}' \
    | grep -E '^v[0-9]+\.[0-9]+\.[0-9]+$' | sort -V | tail -n 1 || true)"
  [ -n "$REF" ] || { echo "fetch-lockrot: no release tag found at $REPO" >&2; exit 1; }
fi

rm -rf .lockrot
git clone --quiet --depth 1 --branch "$REF" "$REPO" .lockrot
# The date of the ref, read while there is still a .git to ask: the reference pages carry it as
# their <lastmod> in the sitemap (see scripts/mkdocs_hooks.py). A shallow clone has one commit, so
# this is the only date available for them, and it is the right one — they change on a release.
TZ=UTC git -C .lockrot log -1 --format=%cd --date=iso-strict-local > .lockrot/REF_DATE
rm -rf .lockrot/.git
echo "$REF" > .lockrot/REF
echo "fetch-lockrot: $REPO at $REF"
