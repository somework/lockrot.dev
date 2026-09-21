#!/usr/bin/env bash
# Assemble viewer-site/ — the report viewer, deployed to its own host, not to lockrot.dev.
#
# Why a second site at all: Cloudflare emits *every* matching rule from _headers rather than
# letting a narrow one override a broad one. Measured on a local worker with a /* rule and a
# /frame/* rule, the frame path came back carrying two Content-Security-Policy headers and two
# X-Frame-Options. Browsers enforce two policies as their intersection, so lockrot.dev's
# `frame-ancestors 'none'` would forbid the frame and its `default-src 'self'` would narrow to
# nothing usable. The viewer also has to fetch a document from a host the reader names, which
# lockrot.dev's `connect-src` does not allow and cannot be widened to allow per-path for the same
# reason. Both problems disappear on a site whose header rules are written for it alone.
#
# The renderer is not rewritten here. resources/report/ in the lockrot checkout is the same
# report.html, report.css, lib.js and report.js that go inside every --format=html report, and this
# script only fills the template's placeholders differently: no document baked in, and the two
# scripts loaded as files so `script-src 'self'` holds without 'unsafe-inline'.
#
# report.js reads #lockrot-data once, at load, and renders immediately — there is no re-render
# entry point. So the document has to be in the DOM before it runs, which is what frame.js is for:
# it waits for the parent to post one, writes it into the empty script tag, and only then appends
# lib.js and report.js.
#
# A checkout older than 0.10.0 has no resources/report/. That is not an error — the site still
# builds from such a tag, it just cannot build a viewer, and the deploy step skips a missing
# viewer-site/ rather than publishing an empty one over the live viewer.
set -euo pipefail
cd "$(dirname "$0")/.."

REPORT_SRC=.lockrot/resources/report

if [ ! -d "$REPORT_SRC" ]; then
  echo "build-viewer: $REPORT_SRC is missing (lockrot $(cat .lockrot/REF 2>/dev/null || echo '?') predates --format=html); viewer not built"
  exit 0
fi

for file in report.html report.css report.js lib.js; do
  [ -f "$REPORT_SRC/$file" ] || { echo "build-viewer: $REPORT_SRC/$file is missing" >&2; exit 1; }
done

rm -rf viewer-site
mkdir -p viewer-site/frame

python3 scripts/build_frame.py "$REPORT_SRC/report.html" "$REPORT_SRC/report.css" viewer-site/frame/index.html

cp "$REPORT_SRC/lib.js" "$REPORT_SRC/report.js" viewer-site/frame/
cp viewer/frame.js viewer-site/frame/frame.js

# The published reports: one page per project of a data run, built from the capsules in
# data/reports/ with the renderer of the release this build is running against. They sit on this
# host rather than on lockrot.dev for the same reason the frame does — the renderer draws documents
# derived from other people's lock files, and lockrot.dev's header rules cannot be narrowed per
# path. See scripts/build_reports.py and the /reports/* rule in viewer/_headers.
python3 scripts/build_reports.py --capsules data/reports --renderer "$REPORT_SRC" \
  --html-out viewer-site/reports

cp viewer/app.html viewer-site/index.html
cp viewer/app.css viewer/app.js viewer-site/
cp viewer/_headers viewer-site/_headers
cp viewer/robots.txt viewer-site/robots.txt

echo "build-viewer: viewer-site/ built from lockrot $(cat .lockrot/REF 2>/dev/null || echo '?')"
