#!/usr/bin/env bash
# Fetch lockrot's JSON schemas, and nothing else, at the commit SCHEMAS_REF names, into .schemas/.
#
# The site follows lockrot's newest release tag, and a schema number has to be online before the
# release that writes it is tagged: every document of that release names its schema's URL, and the
# rebuild after the tag comes later. So the merge of a lockrot release pull request sends the
# `lockrot-schemas` dispatch with its commit, .github/workflows/schemas.yml stores the commit in the
# repository variable SCHEMAS_REF once the maintainer approves, and every build reads the variable.
# scripts/copy-schemas.sh publishes a file from here only under a name the tag does not publish, so
# the tag's file wins for every number both hold, and a variable left set after the release changes
# nothing. Only resources/*.schema.json leaves the fetch: the docs at that commit are unreleased.
#
# An empty SCHEMAS_REF clears .schemas/ and fetches nothing, so a checkout an earlier build left
# behind is never published by accident.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO="${LOCKROT_REPO:-https://github.com/somework/lockrot.git}"
REF="${SCHEMAS_REF:-}"

rm -rf .schemas
if [ -z "$REF" ]; then
  echo "fetch-schemas: SCHEMAS_REF is not set; publishing the tag's schemas only"
  exit 0
fi
# A full sha and nothing else: a branch name would publish whatever that branch holds at build time.
[[ "$REF" =~ ^[0-9a-f]{40}$ ]] || { echo "fetch-schemas: SCHEMAS_REF '$REF' is not a full commit sha" >&2; exit 1; }

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
git -C "$work" init --quiet
git -C "$work" fetch --quiet --depth 1 "$REPO" "$REF"

mkdir -p .schemas/resources
count=0
while IFS= read -r path; do
  git -C "$work" show "FETCH_HEAD:$path" > ".schemas/$path"
  count=$((count + 1))
done < <(git -C "$work" ls-tree --name-only FETCH_HEAD resources/ | grep -E '^resources/[^/]+\.schema\.json$' || true)
echo "$REF" > .schemas/REF
echo "fetch-schemas: $count schema file(s) of $REPO at $REF in .schemas/"
