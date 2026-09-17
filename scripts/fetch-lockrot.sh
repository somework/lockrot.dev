#!/usr/bin/env bash
# Check the lockrot repository out into .lockrot/ at the ref the site should document.
#
# Default: the newest release tag, so the reference pages describe what people download and not
# what sits on main. LOCKROT_REF=main (or any tag/branch) overrides it, for a preview of unreleased
# docs. The checkout is shallow and disposable; nothing here is ever committed.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="${LOCKROT_REPO:-https://github.com/somework/lockrot.git}"
REF="${LOCKROT_REF:-}"
if [ -z "$REF" ]; then
  REF="$(git ls-remote --tags --refs "$REPO" 'v*' | awk -F/ '{print $NF}' | sort -V | tail -n 1)"
  [ -n "$REF" ] || { echo "fetch-lockrot: no release tag found at $REPO" >&2; exit 1; }
fi

rm -rf .lockrot
git clone --quiet --depth 1 --branch "$REF" "$REPO" .lockrot
rm -rf .lockrot/.git
echo "$REF" > .lockrot/REF
echo "fetch-lockrot: $REPO at $REF"
