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
# The renderer is not rewritten here. It is the page lockrot itself writes: from lockrot 0.12.0 a
# release of somework/lockrot-report, which lockrot vendors and scripts/fetch-renderer.sh downloads
# at the same version, with its provenance verified; before that, the hand-written report.html,
# report.css, lib.js and report.js in the lockrot checkout. Either way the frame gets the document
# the same way: frame.js waits for the parent to post one, writes it into the empty
# #lockrot-data element, and only then appends the renderer, which reads it at load.
#
# A checkout older than 0.10.0 has no renderer at all. That is not an error — the site still
# builds from such a tag, it just cannot build a viewer, and the deploy step skips a missing
# viewer-site/ rather than publishing an empty one over the live viewer.
set -euo pipefail
cd "$(dirname "$0")/.."

REPORT_SRC=.lockrot/resources/report

rm -rf viewer-site
mkdir -p viewer-site/frame

scripts/fetch-renderer.sh
if [ -f .renderer/REF ]; then
  # The released renderer (lockrot 0.12.0 and later vendor it). Its report.html pins its own inline
  # script by hash, which would refuse the frame's files, so the frame is this site's own page,
  # viewer/frame.html: the stylesheet and the renderer as same-origin files, and frame.js to put the
  # document in before the renderer reads it. Published reports are the renderer's report.html
  # filled with each capsule, the page lockrot writes byte for byte.
  cp viewer/frame.html viewer-site/frame/index.html
  cp .renderer/lockrot-report.js .renderer/lockrot-report.css viewer-site/frame/
  RENDERER=.renderer
  RENDERER_NAME="lockrot-report $(cat .renderer/REF)"
else
  # lockrot 0.11.0 and older: the hand-written renderer, four files in the checkout. A checkout
  # older than 0.10.0 has none, and then there is no viewer to build.
  if [ ! -d "$REPORT_SRC" ]; then
    rm -rf viewer-site
    echo "build-viewer: $REPORT_SRC is missing (lockrot $(cat .lockrot/REF 2>/dev/null || echo '?') predates --format=html); viewer not built"
    exit 0
  fi
  for file in report.html report.css report.js lib.js; do
    [ -f "$REPORT_SRC/$file" ] || { echo "build-viewer: $REPORT_SRC/$file is missing" >&2; exit 1; }
  done
  python3 scripts/build_frame.py "$REPORT_SRC/report.html" "$REPORT_SRC/report.css" viewer-site/frame/index.html
  cp "$REPORT_SRC/lib.js" "$REPORT_SRC/report.js" viewer-site/frame/
  RENDERER=$REPORT_SRC
  RENDERER_NAME="the renderer of lockrot $(cat .lockrot/REF 2>/dev/null || echo '?')"
fi
cp viewer/frame.js viewer-site/frame/frame.js

# The published reports: one page per project of a data run, built from the capsules in
# data/reports/ with the renderer chosen above. They sit on this host rather than on lockrot.dev
# for the same reason the frame does — the renderer draws documents derived from other people's
# lock files, and lockrot.dev's header rules cannot be narrowed per path. See
# scripts/build_reports.py and the /reports/* rule in viewer/_headers.
python3 scripts/build_reports.py --capsules data/reports --renderer "$RENDERER" \
  --html-out viewer-site/reports

cp viewer/app.html viewer-site/index.html
cp viewer/app.css viewer/app.js viewer-site/
cp viewer/_headers viewer-site/_headers
cp viewer/robots.txt viewer-site/robots.txt

echo "build-viewer: viewer-site/ built with $RENDERER_NAME"
