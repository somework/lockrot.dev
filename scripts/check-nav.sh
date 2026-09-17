#!/usr/bin/env bash
# Every Markdown page lockrot ships in docs/ must be in this site's nav. MkDocs only logs an INFO
# line for a page missing from the nav, so a page added upstream would otherwise build fine and
# be reachable by nobody.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .lockrot/docs ] || { echo "check-nav: run scripts/fetch-lockrot.sh first" >&2; exit 1; }

missing=0
for page in .lockrot/docs/*.md; do
  name="$(basename "$page")"
  if ! grep -Eq "^\s+- [^:]+: ${name//./\\.}\$" mkdocs.yml; then
    echo "check-nav: .lockrot/docs/$name is not in mkdocs.yml nav" >&2
    missing=1
  fi
done
exit $missing
