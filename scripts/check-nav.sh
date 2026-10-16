#!/usr/bin/env bash
# Every Markdown page lockrot ships in docs/ must be in this site's nav. MkDocs only logs an INFO
# line for a page missing from the nav, so a page added upstream would otherwise build fine and
# be reachable by nobody. Pages in subdirectories count too, named by their path below docs/
# (verdicts/model-1.md), which is how the nav names them.
set -euo pipefail
cd "$(dirname "$0")/.."
[ -d .lockrot/docs ] || { echo "check-nav: run scripts/fetch-lockrot.sh first" >&2; exit 1; }

missing=0
while IFS= read -r page; do
  name="${page#.lockrot/docs/}"
  # The name as an ERE: a dot matches only a dot. A slash needs no escape.
  pattern="${name//./\\.}"
  if ! grep -Eq "^\s+- [^:]+: ${pattern}\$" mkdocs.yml; then
    echo "check-nav: .lockrot/docs/$name is not in mkdocs.yml nav" >&2
    missing=1
  fi
  # content/llms.txt is a second, hand-kept list of the same pages (the landing page is its header).
  slug="${name%.md}"
  if [ "$slug" != index ] && ! grep -Fq "https://lockrot.dev/$slug/" content/llms.txt; then
    echo "check-nav: .lockrot/docs/$name is not in content/llms.txt" >&2
    missing=1
  fi
done < <(find .lockrot/docs -name '*.md' -not -path '.lockrot/docs/overrides/*' | LC_ALL=C sort)
exit $missing
