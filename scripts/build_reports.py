#!/usr/bin/env python3
"""Turn the stored report capsules back into pages, and into the JSON the site links.

`data/reports/<run>/<slug>.json` is what a `--format=html` run left behind once the renderer was
taken out of it (see scripts/report_page.py). Two things are built from it, by whichever build
needs them:

  --html-out  the self-contained report page, for the viewer's host. The renderer spliced back in
              is the one from the lockrot checkout this build is running against, so a page always
              renders with the release the rest of the site documents — for the report schema
              number that release reads. A capsule of another number gets the renderer that reads
              it: lockrot-report 0.14 reads report-2 only, and every stored report-1 capsule is
              drawn by lockrot-report 0.13.0 (scripts/build-viewer.sh passes both).
  --json-out  `capsule.data.report` on its own — the document `--format=json` writes, envelope and
              `$schema` included — so a link in a post hands the reader a file that validates
              against the published schema rather than a page's payload.

Neither output is committed. The capsule is the only copy in git, which is the point: the renderer
is 110 KB and identical on every page, and the weekly run writes twenty pages a week.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import report_page

# PHP's JSON_PRETTY_PRINT indents with four spaces, and JsonFormatter writes with unescaped slashes
# and unicode. A file offered as "the JSON that run wrote" should differ from it in no way a diff
# would show.
JSON_INDENT = 4

# Beside the capsules of a run, not one of them: what each report was read from — the repository,
# the release tag when there was one, and the commit.
MANIFEST = "manifest.json"


def reads(renderer: Path) -> set[int]:
    """The report schema numbers a renderer reads: its manifest's `schema.report`. The hand-written
    renderer of lockrot 0.11.0 and older has no manifest, and read report-1."""
    manifest = renderer / "manifest.json"
    if not manifest.is_file():
        return {1}
    numbers = json.loads(manifest.read_text(encoding="utf-8")).get("schema", {}).get("report")
    if not numbers:
        raise SystemExit(f"build_reports: {manifest} names no report schema it reads")
    return set(numbers)


def _renderers(renderers: list[Path]) -> dict[int, tuple[str, str | None, str | None]]:
    """Each report schema number, with the template and sources of the one renderer that reads it."""
    by_number: dict[int, tuple[str, str | None, str | None]] = {}
    for renderer in renderers:
        template = _read(renderer / "report.html")
        css = js = None
        if report_page.JS in template:
            # The hand-written renderer of lockrot 0.11.0 and older, spliced in at build time.
            # report.js reads LockrotLib at the top, so the DOM-free half comes first — the order
            # HtmlFormatter::SCRIPTS fixed. A released renderer's report.html carries both inline.
            css = _read(renderer / "report.css")
            js = _read(renderer / "lib.js") + "\n" + _read(renderer / "report.js")
        for number in reads(renderer):
            if number in by_number:
                raise SystemExit(f"build_reports: two renderers read report schema {number}; pass one")
            by_number[number] = (template, css, js)
    return by_number


def _schema(report: dict) -> object:
    """A capsule's report schema number. Every capsule carries lockrot.schema; report-1 made
    `$schema` optional, so the number is the key that is always there."""
    return (report.get("lockrot") or {}).get("schema")


def build(capsules: Path, renderers: list[Path], html_out: Path | None, json_out: Path | None) -> int:
    by_number = _renderers(renderers) if html_out is not None else {}

    files = sorted(f for f in capsules.glob("*/*.json") if f.name != MANIFEST)
    if not files:
        raise SystemExit(f"build_reports: no capsules under {capsules}")

    provenance = {directory.name: _provenance(directory) for directory in {f.parent for f in files}}

    for capsule_file in files:
        capsule = json.loads(capsule_file.read_text(encoding="utf-8"))
        run, slug = capsule_file.parent.name, capsule_file.stem

        if html_out is not None:
            known = provenance[run]
            if known is not None and slug not in known:
                raise SystemExit(
                    f"build_reports: {run}/{MANIFEST} does not say what {slug} was read from"
                )
            number = _schema(capsule.get("data", {}).get("report") or {})
            if number not in by_number:
                raise SystemExit(f"build_reports: no renderer given reads report schema {number} ({capsule_file})")
            template, css, js = by_number[number]
            page = report_page.render(
                capsule, template, css, js, None if known is None else known[slug]
            )
            _write(html_out / run / f"{slug}.html", page)

        if json_out is not None:
            report = capsule.get("data", {}).get("report")
            if report is None:
                raise SystemExit(f"build_reports: {capsule_file} carries no report")
            _write(
                json_out / run / f"{slug}.json",
                json.dumps(report, ensure_ascii=False, indent=JSON_INDENT) + "\n",
            )

    print(f"build-reports: {len(files)} report(s) from {capsules}")
    return 0


def _provenance(run: Path) -> dict | None:
    """What each report in this run was read from, out of the run's manifest.

    A run without a manifest still builds — the pages then say nothing about their source, which is
    honest for a capsule that arrived without one — but a run that has a manifest has to describe
    every report in it, or a page would quietly claim less than its neighbours.
    """
    manifest_file = run / MANIFEST
    if not manifest_file.is_file():
        return None

    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    date = manifest.get("run", {}).get("date")
    known = {}
    for project in manifest["projects"]:
        # A starter has a command where a release has a repository; report_page.band tells them
        # apart by that, and there is nothing to copy from the other shape.
        keys = (
            ("package", "packagist_url", "command")
            if project.get("kind") == "starter"
            else ("repo", "commit", "commit_url", "tag", "tag_url")
        )
        known[project["name"]] = {
            **{key: project.get(key) for key in keys},
            "date": project.get("date") or date,
        }
    return known


def _read(path: Path) -> str:
    if not path.is_file():
        raise SystemExit(f"build_reports: {path} is missing")
    return path.read_text(encoding="utf-8")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capsules", type=Path, default=Path("data/reports"))
    # A renderer release (.renderer/, scripts/fetch-renderer.sh) or an older lockrot's
    # hand-written one (.lockrot/resources/report/); report.html says which. Once per renderer: each
    # capsule is drawn by the one that reads its report schema number.
    parser.add_argument("--renderer", type=Path, action="append")
    parser.add_argument("--html-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv[1:])

    if args.html_out is None and args.json_out is None:
        raise SystemExit("build_reports: nothing to do; pass --html-out or --json-out")

    renderers = args.renderer or [Path(".lockrot/resources/report")]
    return build(args.capsules, renderers, args.html_out, args.json_out)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
