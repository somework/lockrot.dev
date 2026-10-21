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
# The renderer is not rewritten here. It is the page lockrot itself writes: a release of
# somework/lockrot-report, which lockrot 0.12.0 and later vendor and scripts/fetch-renderer.sh
# downloads at the same version, with its provenance verified. Its report.html pins its own inline
# script by hash, which would refuse the frame's files, so the frame is this site's own page,
# viewer/frame.html: the stylesheet and the renderer as same-origin files, and frame.js, which
# waits for the parent to post a document, writes it into the empty #lockrot-data element, and
# only then appends the renderer, which reads it at load. Published reports are the renderer's
# report.html filled with each capsule, the page lockrot writes byte for byte.
set -euo pipefail
cd "$(dirname "$0")/.."

# The renderer for the stored report-1 capsules once lockrot vendors one that reads report-2 only
# (lockrot-report 0.14.0 and later show report-1 a "rerun or open with 0.13" screen). 0.13.0 is the
# last lockrot-report release that reads report-1.
REPORT_1_RENDERER=v0.13.0

rm -rf viewer-site
mkdir -p viewer-site/frame

scripts/fetch-renderer.sh
cp viewer/frame.html viewer-site/frame/index.html
cp .renderer/lockrot-report.js .renderer/lockrot-report.css viewer/frame.js viewer-site/frame/
RENDERERS=(--renderer .renderer)
RENDERER_NAME="lockrot-report $(cat .renderer/REF)"
# Each capsule is drawn by the renderer that reads its report schema number (build_reports.py):
# when the vendored one does not read report-1, lockrot-report 0.13.0 draws the report-1 capsules.
if ! python3 -c 'import json,sys; sys.exit(1 not in json.load(open(sys.argv[1]))["schema"]["report"])' .renderer/manifest.json; then
  RENDERER_REF="$REPORT_1_RENDERER" RENDERER_DIR=.renderer-report-1 scripts/fetch-renderer.sh
  RENDERERS+=(--renderer .renderer-report-1)
  RENDERER_NAME="$RENDERER_NAME, and lockrot-report $REPORT_1_RENDERER for report-1"
else
  rm -rf .renderer-report-1
fi

# The published reports: one page per project of a data run, built from the capsules in
# data/reports/ with the renderers chosen above. They sit on this host rather than on lockrot.dev
# for the same reason the frame does — the renderer draws documents derived from other people's
# lock files, and lockrot.dev's header rules cannot be narrowed per path. See
# scripts/build_reports.py and the /reports/* rule in viewer/_headers.
python3 scripts/build_reports.py --capsules data/reports "${RENDERERS[@]}" \
  --html-out viewer-site/reports

# Every earlier weekly run as well, at reports/watch/<date>/<project>: /watch/ links each run the
# history names. The capsules come out of git rather than out of the tree, which keeps one week of
# them; see scripts/watch_archive.py.
python3 scripts/watch_archive.py --out build/watch-archive
python3 scripts/build_reports.py --capsules build/watch-archive "${RENDERERS[@]}" \
  --html-out viewer-site/reports/watch

cp viewer/app.html viewer-site/index.html
cp viewer/app.css viewer/app.js viewer-site/
cp viewer/_headers viewer-site/_headers
cp viewer/robots.txt viewer-site/robots.txt

echo "build-viewer: viewer-site/ built with $RENDERER_NAME"
