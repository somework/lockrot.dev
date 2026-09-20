#!/usr/bin/env bash
# Check the lockrot repository out into .lockrot/ at the ref the site should document, with the
# history that ref carries (see the clone below).
#
# Default: the newest release tag, so the reference pages describe what people download and not
# what sits on main. Only plain vX.Y.Z tags count: `sort -V` ranks v0.6.0-rc1 above v0.6.0, and a
# pre-release is not what people download. LOCKROT_REF=main (or any tag/branch) overrides it, for
# a preview of unreleased docs. The checkout is disposable; nothing here is ever committed.
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
# Blobless rather than shallow, and the .git is kept: scripts/mkdocs_hooks.py asks this history for
# the date each reference page last changed, which is its <lastmod> in the sitemap. A --depth 1
# clone can only answer "the release", one date for all of them. The history costs 3 seconds and
# 5 MB here, because --filter=blob:none fetches the commits and trees and only the blobs checked
# out; `git log --name-only` over all of it then reads trees alone and never touches the network.
git clone --quiet --filter=blob:none --single-branch --branch "$REF" "$REPO" .lockrot
echo "$REF" > .lockrot/REF
echo "fetch-lockrot: $REPO at $REF"
