#!/usr/bin/env python3
"""Unit tests for the schema publishing: scripts/copy-schemas.sh and scripts/fetch-schemas.sh over a
scratch checkout, scripts/schema_pages.py, and scripts/check_schema_live.py against a local server."""

from __future__ import annotations

import functools
import http.server
import json
import os
import shutil
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path

import check_schema_live
import schema_pages

SCRIPTS = Path(__file__).resolve().parent
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def schema(kind: str, number: int, note: str = "") -> str:
    return json.dumps({"id": f"https://lockrot.dev/schema/{kind}-{number}.json", "note": note})


def site(root: Path, *scripts: str) -> Path:
    """A scratch copy of this repository's layout: the named scripts and nothing else."""
    (root / "scripts").mkdir(parents=True)
    for name in scripts:
        shutil.copy2(SCRIPTS / name, root / "scripts" / name)
    return root


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, env=ENV, check=True, capture_output=True, text=True).stdout.strip()


class CopySchemasTest(unittest.TestCase):
    def run_copy(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run([root / "scripts" / "copy-schemas.sh"], capture_output=True, text=True)

    def test_publishes_the_numbers_the_tag_lacks_from_the_schemas_ref(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = site(Path(tmp), "copy-schemas.sh")
            write(root / ".lockrot/resources/lockrot-report-1.schema.json", schema("report", 1, "tag"))
            write(root / ".schemas/resources/lockrot-report-1.schema.json", schema("report", 1, "ref"))
            write(root / ".schemas/resources/lockrot-report-2.schema.json", schema("report", 2, "ref"))

            result = self.run_copy(root)
            published = {p.name: json.loads(p.read_text())["note"] for p in (root / "build/docs/schema").glob("*.json")}

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual({"report-1.json": "tag", "report-2.json": "ref"}, published)

    def test_a_ref_that_holds_nothing_new_changes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = site(Path(tmp), "copy-schemas.sh")
            for number in (1, 2):
                write(root / f".lockrot/resources/lockrot-report-{number}.schema.json", schema("report", number, "tag"))
                write(root / f".schemas/resources/lockrot-report-{number}.schema.json", schema("report", number, "ref"))

            result = self.run_copy(root)
            notes = sorted(json.loads(p.read_text())["note"] for p in (root / "build/docs/schema").glob("*.json"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["tag", "tag"], notes)

    def test_without_a_schemas_ref_publishes_the_tag_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = site(Path(tmp), "copy-schemas.sh")
            write(root / ".lockrot/resources/lockrot-report-1.schema.json", schema("report", 1))

            result = self.run_copy(root)
            names = sorted(p.name for p in (root / "build/docs/schema").glob("*.json"))

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(["report-1.json"], names)

    def test_refuses_an_id_from_the_schemas_ref_that_is_not_a_plain_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = site(Path(tmp), "copy-schemas.sh")
            write(root / ".lockrot/resources/lockrot-report-1.schema.json", schema("report", 1))
            write(root / ".schemas/resources/x.schema.json", json.dumps({"id": "https://lockrot.dev/schema/../x.json"}))

            result = self.run_copy(root)

        self.assertNotEqual(0, result.returncode)


class FetchSchemasTest(unittest.TestCase):
    def lockrot_repo(self, tmp: Path) -> tuple[Path, str]:
        """A scratch lockrot repository whose newest commit holds a docs page and two schemas."""
        repo = tmp / "lockrot"
        write(repo / "resources/lockrot-report-2.schema.json", schema("report", 2))
        write(repo / "resources/lockrot-explain-2.schema.json", schema("explain", 2))
        write(repo / "resources/report/manifest.json", "{}")
        write(repo / "docs/schema.md", "# unreleased\n")
        git(repo, "init", "--quiet")
        git(repo, "config", "uploadpack.allowAnySHA1InWant", "true")
        git(repo, "add", ".")
        git(repo, "commit", "--quiet", "-m", "release")
        return repo, git(repo, "rev-parse", "HEAD")

    def fetch(self, root: Path, repo: Path, ref: str) -> subprocess.CompletedProcess:
        env = {**ENV, "LOCKROT_REPO": repo.as_uri(), "SCHEMAS_REF": ref}
        return subprocess.run([root / "scripts" / "fetch-schemas.sh"], capture_output=True, text=True, env=env)

    def test_fetches_the_schema_files_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo, sha = self.lockrot_repo(tmp)
            root = site(tmp / "site", "fetch-schemas.sh")

            result = self.fetch(root, repo, sha)
            files = sorted(str(p.relative_to(root / ".schemas")) for p in (root / ".schemas").rglob("*") if p.is_file())

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertEqual(
            ["REF", "resources/lockrot-explain-2.schema.json", "resources/lockrot-report-2.schema.json"], files
        )

    def test_an_empty_ref_fetches_nothing_and_clears_what_an_earlier_build_left(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo, _ = self.lockrot_repo(tmp)
            root = site(tmp / "site", "fetch-schemas.sh")
            write(root / ".schemas/resources/lockrot-report-2.schema.json", schema("report", 2))

            result = self.fetch(root, repo, "")

            self.assertEqual(0, result.returncode, result.stderr)
            self.assertFalse((root / ".schemas").exists())

    def test_refuses_a_ref_that_is_not_a_full_commit_sha(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            repo, sha = self.lockrot_repo(tmp)
            root = site(tmp / "site", "fetch-schemas.sh")

            for ref in ("main", sha[:12], f"{sha} --upload-pack=x"):
                with self.subTest(ref=ref):
                    self.assertNotEqual(0, self.fetch(root, repo, ref).returncode)


class SchemaPagesTest(unittest.TestCase):
    def test_writes_the_report_2_page_when_the_newest_docs_describe_report_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write(tmp / "docs/schema.md", "# JSON schemas\n\nhttps://lockrot.dev/schema/report-2.json\n")

            written = schema_pages.report_2_page(tmp / "docs", tmp / "build")
            page = (tmp / "build/schema/report-2.md").read_text(encoding="utf-8")
            source = (tmp / "build" / schema_pages.CURRENT_NAME).read_text(encoding="utf-8")

        self.assertTrue(written)
        self.assertIn(f'{{% include-markdown "../{schema_pages.CURRENT_NAME}" %}}', page)
        self.assertEqual("# JSON schemas\n\nhttps://lockrot.dev/schema/report-2.json\n", source)

    def test_writes_no_report_2_page_from_report_1_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write(tmp / "docs/schema.md", "# JSON schemas\n\nhttps://lockrot.dev/schema/report-1.json\n")

            written = schema_pages.report_2_page(tmp / "docs", tmp / "build")

            self.assertFalse(written)
            self.assertFalse((tmp / "build/schema/report-2.md").exists())

    def test_writes_the_frozen_report_1_page_once_report_2_is_published(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write(tmp / "frozen.md", "# JSON schemas\n\n[Run notes](notes.md)\n")
            write(tmp / "build/schema/report-2.json", "{}")

            written = schema_pages.report_1_page(tmp / "frozen.md", tmp / "build")
            page = (tmp / "build/schema/report-1.md").read_text(encoding="utf-8")
            frozen = (tmp / "build" / schema_pages.FROZEN_NAME).read_text(encoding="utf-8")

        self.assertTrue(written)
        self.assertIn(f'{{% include-markdown "../{schema_pages.FROZEN_NAME}" %}}', page)
        self.assertIn("v0.13.0", page)
        self.assertEqual("# JSON schemas\n\n[Run notes](notes.md)\n", frozen)

    def test_writes_no_report_1_page_while_report_1_is_the_only_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            write(tmp / "frozen.md", "# JSON schemas\n")
            write(tmp / "build/schema/report-1.json", "{}")

            self.assertFalse(schema_pages.report_1_page(tmp / "frozen.md", tmp / "build"))
            self.assertFalse((tmp / "build/schema/report-1.md").exists())

    def test_the_frozen_copy_is_lockrot_v0_13_0_s_schema_page(self):
        frozen = schema_pages.body((SCRIPTS.parent / schema_pages.FROZEN_SOURCE).read_text(encoding="utf-8"))

        self.assertTrue(frozen.startswith("# JSON schemas"), frozen[:40])
        self.assertIn("https://lockrot.dev/schema/report-1.json", frozen)
        self.assertNotIn("report-2.json", frozen)


class BodyTest(unittest.TestCase):
    def test_drops_the_front_matter_and_keeps_the_page(self):
        self.assertEqual("# Page\n\ntext\n", schema_pages.body("---\ntitle: x\n---\n\n# Page\n\ntext\n"))

    def test_a_page_without_front_matter_is_kept_whole(self):
        self.assertEqual("# Page\n---\n", schema_pages.body("# Page\n---\n"))

    def test_refuses_front_matter_that_never_closes(self):
        with self.assertRaises(SystemExit):
            schema_pages.body("---\ntitle: x\n# Page\n")


class _Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class CheckSchemaLiveTest(unittest.TestCase):
    def serve(self, directory: Path) -> str:
        server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(_Quiet, directory=str(directory)))
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return f"http://127.0.0.1:{server.server_address[1]}"

    def test_passes_a_schema_served_at_its_own_id(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.serve(Path(tmp))
            url = f"{base}/schema/report-2.json"
            write(Path(tmp) / "schema/report-2.json", json.dumps({"id": url}))

            self.assertIn(url, check_schema_live.check(url))

    def test_stops_on_a_404(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.serve(Path(tmp))

            with self.assertRaises(SystemExit) as raised:
                check_schema_live.check(f"{base}/schema/report-2.json")

        self.assertIn("404", str(raised.exception))

    def test_stops_on_a_file_that_is_another_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = self.serve(Path(tmp))
            write(Path(tmp) / "schema/report-2.json", json.dumps({"id": f"{base}/schema/report-1.json"}))

            with self.assertRaises(SystemExit):
                check_schema_live.check(f"{base}/schema/report-2.json")


if __name__ == "__main__":
    unittest.main()
