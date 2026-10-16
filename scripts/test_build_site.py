#!/usr/bin/env python3
"""scripts/build.sh end to end, in a scratch copy of this repository with a scratch lockrot checkout:
nested reference pages are published at their own URLs, and the pages a checkout does not hold are
left out of the nav and of llms.txt rather than failing the strict build.

Skipped where MkDocs is not installed. CI installs it before the unit tests run.
"""

from __future__ import annotations

import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from mkdocs_hooks import OPTIONAL_PAGES

REPO = Path(__file__).resolve().parent.parent
ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
    # The privacy plugin downloads the fonts; the pages under test do not need them.
    "LOCKROT_PRIVACY": "false",
    "SCHEMAS_REF": "",
    # The mkdocs that sits beside this interpreter, as in a virtual environment that is not active.
    "PATH": f"{Path(sys.executable).parent}{os.pathsep}{os.environ.get('PATH', '')}",
}


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=ENV, check=True, capture_output=True)


def nav_pages() -> list[str]:
    """The reference pages the nav names that every build needs; the scratch checkout provides
    them. The optional ones are each test's choice."""
    text = (REPO / "mkdocs.yml").read_text(encoding="utf-8")
    nav = text[text.index("\nnav:"):text.index("\nmarkdown_extensions:")]
    return [page for page in re.findall(r"^\s+- [^:]+: (\S+\.md)$", nav, re.M) if page not in OPTIONAL_PAGES]


def scratch_lockrot(root: Path, extra_pages: list[str], schema_page: str) -> None:
    docs = root / ".lockrot/docs"
    own = {p.relative_to(REPO / "content").as_posix() for p in (REPO / "content").rglob("*.md")}
    for page in [*nav_pages(), *extra_pages]:
        if page in own:
            continue
        path = docs / page
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {page}\n\nA page of the scratch checkout.\n", encoding="utf-8")
    (docs / "schema.md").write_text(schema_page, encoding="utf-8")
    (docs / "assets").mkdir()
    # The landing page shows lockrot's demo GIF; any bytes will do for a link check.
    (docs / "assets/lockrot-demo.gif").write_bytes(b"GIF89a")
    (docs / "requirements.txt").write_text("not a page\n", encoding="utf-8")
    resources = root / ".lockrot/resources"
    resources.mkdir()
    (resources / "lockrot-report-1.schema.json").write_text('{"id": "https://lockrot.dev/schema/report-1.json"}', encoding="utf-8")
    (root / ".lockrot/CHANGELOG.md").write_text("# Changelog\n", encoding="utf-8")
    (root / ".lockrot/REF").write_text("v9.9.9\n", encoding="utf-8")
    git(root / ".lockrot", "init", "--quiet")
    git(root / ".lockrot", "add", ".")
    git(root / ".lockrot", "commit", "--quiet", "-m", "docs")


def scratch_site(root: Path) -> None:
    for name in ("mkdocs.yml", "scripts", "content", "data", "frozen"):
        source = REPO / name
        if source.is_dir():
            shutil.copytree(source, root / name, ignore=shutil.ignore_patterns("__pycache__", "fixtures"))
        else:
            shutil.copy2(source, root / name)
    git(root, "init", "--quiet")
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "site")


@unittest.skipIf(importlib.util.find_spec("mkdocs") is None, "MkDocs is not installed")
class BuildSiteTest(unittest.TestCase):
    def build(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run([root / "scripts/build.sh"], cwd=root, env=ENV, capture_output=True, text=True, timeout=300)

    def test_publishes_nested_reference_pages_at_their_own_urls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch_site(root)
            scratch_lockrot(root, ["verdicts/model-1.md", "changes/0.14.md"], "# JSON schemas\n\nhttps://lockrot.dev/schema/report-2.json\n")

            result = self.build(root)

            self.assertEqual(0, result.returncode, result.stdout[-2000:] + result.stderr[-4000:])
            self.assertTrue((root / "site/verdicts/model-1/index.html").is_file())
            self.assertTrue((root / "site/changes/0.14/index.html").is_file())
            self.assertTrue((root / "site/schema/report-2/index.html").is_file())
            self.assertFalse((root / "site/requirements.txt").exists())
            llms = (root / "site/llms.txt").read_text(encoding="utf-8")
            self.assertIn("https://lockrot.dev/verdicts/model-1/", llms)
            self.assertIn("https://lockrot.dev/schema/report-2/", llms)

    def test_a_checkout_without_the_new_pages_builds_without_their_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scratch_site(root)
            scratch_lockrot(root, [], "# JSON schemas\n\nhttps://lockrot.dev/schema/report-1.json\n")

            result = self.build(root)

            self.assertEqual(0, result.returncode, result.stdout[-2000:] + result.stderr[-4000:])
            self.assertFalse((root / "site/verdicts/model-1").exists())
            self.assertFalse((root / "site/schema/report-1").exists())
            llms = (root / "site/llms.txt").read_text(encoding="utf-8")
            self.assertNotIn("https://lockrot.dev/verdicts/model-1/", llms)
            self.assertNotIn("https://lockrot.dev/schema/report-1/", llms)
            self.assertNotIn("https://lockrot.dev/changes/0.14/", llms)
            index = (root / "site/index.html").read_text(encoding="utf-8")
            self.assertNotIn("model-1", index)


if __name__ == "__main__":
    unittest.main()
