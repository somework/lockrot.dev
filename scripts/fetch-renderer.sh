#!/usr/bin/env bash
# Download the report renderer into .renderer/: the release of somework/lockrot-report that the
# lockrot checkout in .lockrot/ vendors, so the viewer draws documents with the page that release
# ships and not with whatever the renderer's newest release happens to be.
#
# lockrot 0.12.0 and later vendor the renderer as resources/report/report.html + manifest.json; the
# manifest names the version. An older checkout vendors no renderer release, and the viewer is not
# built from one. RENDERER_REF=v1.2.3 overrides the version, for a preview or for a second renderer, and RENDERER_DIR the directory
# (.renderer by default): build-viewer.sh fetches lockrot-report 0.13.0 into .renderer-report-1 for
# the stored report-1 capsules, which lockrot-report 0.14 does not read.
#
# Every file is checked twice: its build provenance with `gh attestation verify`, and its sha256
# against the release's manifest. The page itself is checked a third time, against the manifest
# lockrot vendored: the published reports are the page lockrot writes, byte for byte.
set -euo pipefail
cd "$(dirname "$0")/.."

REPO=somework/lockrot-report
VENDORED=.lockrot/resources/report/manifest.json
FILES=(report.html lockrot-report.js lockrot-report.css manifest.json)
DIR="${RENDERER_DIR:-.renderer}"
# The directory is emptied first, so it is a name of the known shape, never a path.
[[ "$DIR" =~ ^\.renderer(-[a-z0-9]+)*$ ]] || { echo "fetch-renderer: RENDERER_DIR '$DIR' is not .renderer or .renderer-<name>" >&2; exit 1; }

# manifest_value FILE KEY [KEY...]: one string out of a manifest, by its key path.
manifest_value() {
  python3 -c 'import json,sys
value = json.load(open(sys.argv[1]))
for key in sys.argv[2:]:
    value = value[key]
print(value)' "$@"
}

REF="${RENDERER_REF:-}"
if [ -z "$REF" ]; then
  if [ ! -f "$VENDORED" ]; then
    echo "fetch-renderer: lockrot $(cat .lockrot/REF 2>/dev/null || echo '?') vendors no renderer release; the viewer is built from lockrot 0.12.0 on" >&2
    exit 1
  fi
  REF="v$(manifest_value "$VENDORED" version)"
fi

rm -rf "$DIR"
mkdir -p "$DIR"
for file in "${FILES[@]}"; do
  curl --fail --silent --show-error --location --proto '=https' \
    --output "$DIR/$file" "https://github.com/$REPO/releases/download/$REF/$file"
done

if [ "${RENDERER_SKIP_ATTESTATION:-}" = "1" ]; then
  echo "fetch-renderer: RENDERER_SKIP_ATTESTATION=1, build provenance NOT verified" >&2
else
  for file in "${FILES[@]}"; do
    gh attestation verify "$DIR/$file" --repo "$REPO" >/dev/null
  done
fi

for file in report.html lockrot-report.js lockrot-report.css; do
  expected=$(manifest_value "$DIR/manifest.json" files "$file")
  actual=$(python3 -c 'import hashlib,sys; print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$DIR/$file")
  [ "$expected" = "$actual" ] || { echo "fetch-renderer: $file does not match its manifest" >&2; exit 1; }
done

if [ -z "${RENDERER_REF:-}" ]; then
  vendored=$(manifest_value "$VENDORED" files report.html)
  fetched=$(manifest_value "$DIR/manifest.json" files report.html)
  [ "$vendored" = "$fetched" ] || { echo "fetch-renderer: $REF's report.html is not the page lockrot vendored" >&2; exit 1; }
fi

echo "$REF" > "$DIR/REF"
echo "fetch-renderer: lockrot-report $REF in $DIR/"
