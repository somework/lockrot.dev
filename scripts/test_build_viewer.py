#!/usr/bin/env python3
"""scripts/build-viewer.sh in a scratch copy of this repository: each stored capsule is drawn by the
renderer that reads its report schema number. A report-1 capsule gets lockrot-report 0.13.0 once
lockrot vendors a renderer that reads report-2 only, and a report-2 capsule gets the vendored one.

scripts/fetch-renderer.sh is replaced by a stub that writes a renderer release from local files,
named by the version it is asked for, and scripts/watch_archive.py by a stub that lays out one
archived run; both download or read git in the real build, and neither decides the renderer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

# What each renderer release reads, as its manifest's schema.report says.
READS = {"v0.13.0": [1], "v0.14.0-rc.2": [2]}

FETCH_STUB = """#!/usr/bin/env bash
# Test stub of fetch-renderer.sh: a renderer release from local files, no download.
set -euo pipefail
cd "$(dirname "$0")/.."
DIR="${RENDERER_DIR:-.renderer}"
REF="${RENDERER_REF:-v$(python3 -c 'import json; print(json.load(open(".lockrot/resources/report/manifest.json"))["version"])')}"
rm -rf "$DIR" && mkdir -p "$DIR"
READS='%s'
python3 - "$DIR" "$REF" "$READS" <<'PY'
import json, sys
directory, ref, reads = sys.argv[1], sys.argv[2], json.loads(sys.argv[3])
open(f"{directory}/report.html", "w").write(
    "<!doctype html>\\n<meta http-equiv=\\"Content-Security-Policy\\" content=\\"default-src 'none'\\">\\n"
    "<title>{{TITLE}}</title>\\n<meta name=\\"description\\" content=\\"{{DESCRIPTION}}\\">\\n"
    f"<body>\\n<!-- renderer {ref} -->\\n<script id=\\"lockrot-data\\" type=\\"application/json\\">{{{{DATA}}}}</script>\\n"
)
open(f"{directory}/manifest.json", "w").write(json.dumps({"version": ref[1:], "schema": {"report": reads[ref]}}))
for name in ("lockrot-report.js", "lockrot-report.css"):
    open(f"{directory}/{name}", "w").write("/* stub */")
PY
echo "$REF" > "$DIR/REF"
""" % json.dumps(READS)

ARCHIVE_STUB = """#!/usr/bin/env python3
# Test stub of watch_archive.py: one archived run with one report-1 capsule.
import shutil, sys
from pathlib import Path
out = Path(sys.argv[sys.argv.index("--out") + 1])
shutil.rmtree(out, ignore_errors=True)
(out / "2026-10-12").mkdir(parents=True)
shutil.copy("data/reports/run/old.json", out / "2026-10-12" / "old.json")
"""


def capsule(path: Path, number: int) -> None:
    report = {"$schema": f"https://lockrot.dev/schema/report-{number}.json", "lockrot": {"schema": number}, "findings": []}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"title": path.stem, "description": "d", "data": {"report": report}}), encoding="utf-8")


def scratch(root: Path, vendored: str) -> None:
    shutil.copytree(REPO / "viewer", root / "viewer")
    (root / "scripts").mkdir()
    for name in ("build-viewer.sh", "build_reports.py", "report_page.py", "build_frame.py"):
        shutil.copy2(REPO / "scripts" / name, root / "scripts" / name)
    for name, text in (("fetch-renderer.sh", FETCH_STUB), ("watch_archive.py", ARCHIVE_STUB)):
        (root / "scripts" / name).write_text(text, encoding="utf-8")
        (root / "scripts" / name).chmod(0o755)
    manifest = root / ".lockrot/resources/report/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({"version": vendored[1:]}), encoding="utf-8")
    (root / ".lockrot/REF").write_text("v9.9.9\n", encoding="utf-8")
    capsule(root / "data/reports/run/old.json", 1)
    capsule(root / "data/reports/run/new.json", 2)


def build(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([root / "scripts/build-viewer.sh"], cwd=root, env=os.environ, capture_output=True, text=True, timeout=120)


def drawn_by(root: Path, page: str) -> str:
    text = (root / "viewer-site/reports" / page).read_text(encoding="utf-8")
    return text[text.index("<!-- renderer ") + len("<!-- renderer "):text.index(" -->", text.index("<!-- renderer "))]


class BuildViewerTest(unittest.TestCase):
    def test_a_report_2_renderer_leaves_report_1_capsules_to_lockrot_report_0_13_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch(root, "v0.14.0-rc.2")

            result = build(root)

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("v0.13.0", drawn_by(root, "run/old.html"))
            self.assertEqual("v0.14.0-rc.2", drawn_by(root, "run/new.html"))
            self.assertEqual("v0.13.0", drawn_by(root, "watch/2026-10-12/old.html"))
            self.assertIn("and lockrot-report v0.13.0 for report-1", result.stdout)

    def test_a_report_1_renderer_draws_report_1_alone_and_fetches_nothing_more(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch(root, "v0.13.0")
            (root / "data/reports/run/new.json").unlink()

            result = build(root)

            self.assertEqual(0, result.returncode, result.stdout + result.stderr)
            self.assertEqual("v0.13.0", drawn_by(root, "run/old.html"))
            self.assertFalse((root / ".renderer-report-1").exists())

    def test_a_report_2_capsule_with_no_renderer_for_it_stops_the_build(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch(root, "v0.13.0")

            result = build(root)

            self.assertNotEqual(0, result.returncode)
            self.assertIn("no renderer given reads report schema 2", result.stderr)


if __name__ == "__main__":
    unittest.main()
