#!/usr/bin/env bash
# Publishes lockrot's JSON schemas at the URLs the documents themselves name.
#
# Every machine-readable document lockrot writes — the --format=json report, the --explain
# document, the baseline file — opens with a `$schema` key pointing at https://lockrot.dev/schema/…,
# and each file under lockrot's resources/ carries that same URL as its own `id`. So the id is what
# decides where the file goes here: one list, in the file being published, rather than a second one
# in this repository that could disagree with it.
#
# MkDocs copies anything that is not Markdown out of docs_dir untouched, so build/docs/schema/x.json
# is served at /schema/x.json.
#
# A tag older than 0.9.0 ships schemas without an id (they were internal then); those are skipped,
# so building the site from an older tag still works. An id that is not a lockrot.dev/schema/ URL is
# a mistake worth failing on: it would publish a file at a path nothing points at.
set -euo pipefail
cd "$(dirname "$0")/.."

[ -d .lockrot/resources ] || { echo "copy-schemas: run scripts/fetch-lockrot.sh first" >&2; exit 1; }

published=0
for schema in .lockrot/resources/*.schema.json; do
  [ -e "$schema" ] || continue
  id="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("id", ""))' "$schema")"
  case "$id" in
    '')
      continue
      ;;
    https://lockrot.dev/schema/*.json)
      target="build/docs/schema/${id#https://lockrot.dev/schema/}"
      mkdir -p "$(dirname "$target")"
      cp "$schema" "$target"
      published=$((published + 1))
      ;;
    *)
      echo "copy-schemas: $schema has id '$id', which is not a https://lockrot.dev/schema/ URL" >&2
      exit 1
      ;;
  esac
done

echo "copy-schemas: $published schema(s) published under /schema/"
