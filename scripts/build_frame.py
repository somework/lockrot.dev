#!/usr/bin/env python3
"""Fill lockrot's report template for the viewer's frame instead of for a finished report.

`HtmlFormatter` fills the same five placeholders with a document baked in and both scripts
inlined. The frame wants the opposite: an empty `#lockrot-data`, and the scripts as files, so the
frame's `script-src 'self'` holds without `'unsafe-inline'`. Everything else — the markup, the
stylesheet, the renderer — is lockrot's, byte for byte.

Every substitution is checked. A template that stops carrying one of these placeholders, or starts
carrying two of the script block, means the renderer moved under us, and a viewer built from a
guess would fail in the browser instead of here.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The tag that inlines the renderer in a real report. The frame loads it from files instead.
INLINE_SCRIPT = "<script>\n{{JS}}\n</script>"
FILE_SCRIPTS = '<script src="frame.js"></script>'

# This page is a real URL on the viewer's host, so it says what it is when it is opened on its own
# or linked, and asks not to be indexed — here the site is the publisher, and the decision the
# report template leaves to the publisher is ours to make.
TITLE = "lockrot report renderer"
DESCRIPTION = (
    "The renderer the lockrot report viewer loads a document into. "
    "On its own it holds no document and shows nothing."
)
ROBOTS = '<meta name="robots" content="noindex">'
HEAD_ANCHOR = "<title>"


def fill(template: str, css: str) -> str:
    if template.count(INLINE_SCRIPT) != 1:
        raise SystemExit(
            "build_frame: the template does not carry exactly one inline <script>{{JS}}</script>; "
            "lockrot's report.html changed shape"
        )
    out = template.replace(INLINE_SCRIPT, FILE_SCRIPTS)

    for placeholder, value in (
        ("{{TITLE}}", TITLE),
        ("{{DESCRIPTION}}", DESCRIPTION),
        ("{{CSS}}", css),
        # The document arrives by postMessage, so the tag is present and empty. report.js reads it
        # at load, which is why frame.js fills it before appending the renderer.
        ("{{DATA}}", ""),
    ):
        if placeholder not in out:
            raise SystemExit(f"build_frame: the template has no {placeholder}")
        out = out.replace(placeholder, value)

    if HEAD_ANCHOR not in out:
        raise SystemExit("build_frame: the template has no <title> to anchor the robots meta to")
    out = out.replace(HEAD_ANCHOR, ROBOTS + "\n" + HEAD_ANCHOR, 1)

    if "{{" in out:
        raise SystemExit("build_frame: a placeholder was left unfilled")
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        raise SystemExit("usage: build_frame.py <report.html> <report.css> <out.html>")
    template = Path(argv[1]).read_text(encoding="utf-8")
    css = Path(argv[2]).read_text(encoding="utf-8")
    Path(argv[3]).write_text(fill(template, css), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
