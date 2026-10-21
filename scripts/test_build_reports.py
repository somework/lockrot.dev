#!/usr/bin/env python3
"""Unit tests for scripts/build_reports.py: each capsule is drawn by the renderer that reads its
report schema number."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import build_reports

TEMPLATE = (
    "<!doctype html>\n<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'\">\n"
    "<title>{{TITLE}}</title>\n"
    '<meta name="description" content="{{DESCRIPTION}}">\n'
    "<body>\n<!-- renderer {version} -->\n"
    '<script id="lockrot-data" type="application/json">{{DATA}}</script>\n'
)


def renderer(root: Path, version: str, reads: list[int] | None) -> Path:
    """A released renderer's two files that matter here: its page, and the manifest naming the
    report schema numbers it reads. None leaves the manifest out."""
    root.mkdir(parents=True)
    (root / "report.html").write_text(TEMPLATE.replace("{version}", version), encoding="utf-8")
    if reads is not None:
        (root / "manifest.json").write_text(json.dumps({"version": version, "schema": {"report": reads}}), encoding="utf-8")
    return root


def capsule(root: Path, name: str, number: int) -> None:
    report = {"$schema": f"https://lockrot.dev/schema/report-{number}.json", "lockrot": {"schema": number}, "findings": []}
    path = root / "run" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"title": name, "description": "d", "data": {"report": report}}), encoding="utf-8")


class RendererChoiceTest(unittest.TestCase):
    def test_a_report_1_capsule_is_drawn_by_the_renderer_that_reads_report_1(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "old", 1)
            renderers = [renderer(tmp / "r014", "0.14.0", [2]), renderer(tmp / "r013", "0.13.0", [1])]

            build_reports.build(tmp / "caps", renderers, tmp / "out", None)
            page = (tmp / "out/run/old.html").read_text(encoding="utf-8")

        self.assertIn("<!-- renderer 0.13.0 -->", page)

    def test_a_report_2_capsule_is_drawn_by_the_renderer_that_reads_report_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "new", 2)
            renderers = [renderer(tmp / "r014", "0.14.0", [2]), renderer(tmp / "r013", "0.13.0", [1])]

            build_reports.build(tmp / "caps", renderers, tmp / "out", None)
            page = (tmp / "out/run/new.html").read_text(encoding="utf-8")

        self.assertIn("<!-- renderer 0.14.0 -->", page)

    def test_stops_on_a_renderer_without_a_manifest(self):
        # lockrot 0.11.0's hand-written renderer had none; the site no longer builds from it.
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            build_reports.reads(renderer(Path(tmp) / "r011", "0.11.0", None))

    def test_stops_on_a_manifest_that_names_no_report_schema_list(self):
        for schema in ({"report": 2}, [2], {"report": []}, None):
            with self.subTest(schema=schema), tempfile.TemporaryDirectory() as tmp:
                root = renderer(Path(tmp) / "r", "0.14.0", [2])
                (root / "manifest.json").write_text(json.dumps({"schema": schema}), encoding="utf-8")

                with self.assertRaises(SystemExit):
                    build_reports.reads(root)

    def test_stops_when_no_renderer_reads_a_capsule_s_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "old", 1)

            with self.assertRaises(SystemExit) as raised:
                build_reports.build(tmp / "caps", [renderer(tmp / "r014", "0.14.0", [2])], tmp / "out", None)

        self.assertIn("report schema 1", str(raised.exception))

    def test_stops_on_a_capsule_whose_number_is_not_an_integer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "odd", 1)
            path = tmp / "caps/run/odd.json"
            data = json.loads(path.read_text())
            data["data"]["report"]["lockrot"]["schema"] = True
            path.write_text(json.dumps(data))

            with self.assertRaises(SystemExit):
                build_reports.build(tmp / "caps", [renderer(tmp / "r013", "0.13.0", [1])], tmp / "out", None)

    def test_stops_when_two_renderers_read_the_same_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "old", 1)
            renderers = [renderer(tmp / "a", "0.13.0", [1]), renderer(tmp / "b", "0.12.0", [1])]

            with self.assertRaises(SystemExit):
                build_reports.build(tmp / "caps", renderers, tmp / "out", None)

    def test_the_json_out_needs_no_renderer(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "new", 2)

            build_reports.build(tmp / "caps", [], None, tmp / "json")

            self.assertEqual(2, json.loads((tmp / "json/run/new.json").read_text())["lockrot"]["schema"])


def manifest(root: Path, *names: str) -> None:
    projects = [
        {"kind": "release", "name": n, "repo": f"acme/{n}", "tag": "1.0.0", "commit": "6b9bd67bef2dbfcb71446960dc5616e3552d4532"}
        for n in names
    ]
    (root / "run" / build_reports.MANIFEST).write_text(
        json.dumps({"run": {"date": "2026-10-01"}, "projects": projects}), encoding="utf-8"
    )


class ProvenanceTest(unittest.TestCase):
    def test_refuses_a_report_its_run_manifest_does_not_describe(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "alpha", 2)
            capsule(tmp / "caps", "beta", 2)
            manifest(tmp / "caps", "alpha")

            with self.assertRaises(SystemExit) as raised:
                build_reports.build(tmp / "caps", [renderer(tmp / "r", "0.14.0", [2])], tmp / "out", None)

        self.assertIn("beta", str(raised.exception))

    def test_every_page_of_a_described_run_says_what_it_was_read_from(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "alpha", 2)
            manifest(tmp / "caps", "alpha")

            build_reports.build(tmp / "caps", [renderer(tmp / "r", "0.14.0", [2])], tmp / "out", None)
            page = (tmp / "out/run/alpha.html").read_text(encoding="utf-8")

        self.assertIn(">acme/alpha</a>", page)
        self.assertIn("2026-10-01", page)

    def test_a_run_without_a_manifest_builds_without_a_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            capsule(tmp / "caps", "alpha", 2)

            build_reports.build(tmp / "caps", [renderer(tmp / "r", "0.14.0", [2])], tmp / "out", None)
            page = (tmp / "out/run/alpha.html").read_text(encoding="utf-8")

        self.assertNotIn("This report was produced by", page)


if __name__ == "__main__":
    unittest.main()
