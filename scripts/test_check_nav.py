#!/usr/bin/env python3
"""Unit tests for scripts/check-nav.sh over a scratch checkout: nested pages are matched by their
path below docs/."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "check-nav.sh"

NAV = """nav:
  - Home: index.md
  - What it reports: verdicts.md
  - Score model 1: verdicts/model-1.md
  - JSON schemas: schema.md
  - Report schema 1: schema/report-1.md
  - Upgrading to 0.14: changes/0.14.md
"""

LLMS = """- [Verdicts](https://lockrot.dev/verdicts/)
- [Score model 1](https://lockrot.dev/verdicts/model-1/)
- [JSON schemas](https://lockrot.dev/schema/)
- [Upgrading to 0.14](https://lockrot.dev/changes/0.14/)
"""


def checkout(root: Path, pages: list[str], nav: str = NAV, llms: str = LLMS) -> Path:
    (root / "scripts").mkdir()
    shutil.copy2(SCRIPT, root / "scripts" / "check-nav.sh")
    (root / "mkdocs.yml").write_text(nav, encoding="utf-8")
    (root / "content").mkdir()
    (root / "content/llms.txt").write_text(llms, encoding="utf-8")
    for page in pages:
        path = root / ".lockrot/docs" / page
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# page\n", encoding="utf-8")
    return root


def check(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run([root / "scripts" / "check-nav.sh"], capture_output=True, text=True)


class CheckNavTest(unittest.TestCase):
    def test_passes_nested_pages_named_by_their_path_below_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = checkout(Path(tmp), ["index.md", "verdicts.md", "verdicts/model-1.md", "schema.md", "changes/0.14.md"])

            result = check(root)

        self.assertEqual(0, result.returncode, result.stderr)

    def test_fails_a_nested_page_missing_from_the_nav(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = checkout(Path(tmp), ["index.md", "verdicts.md", "verdicts/model-2.md"])

            result = check(root)

        self.assertEqual(1, result.returncode)
        self.assertIn("verdicts/model-2.md is not in mkdocs.yml nav", result.stderr)
        self.assertIn("verdicts/model-2.md is not in content/llms.txt", result.stderr)

    def test_a_nav_row_for_the_page_s_base_name_alone_does_not_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            nav = NAV.replace("verdicts/model-1.md", "model-1.md")
            root = checkout(Path(tmp), ["index.md", "verdicts.md", "verdicts/model-1.md"], nav=nav)

            result = check(root)

        self.assertEqual(1, result.returncode)
        self.assertIn("verdicts/model-1.md is not in mkdocs.yml nav", result.stderr)

    def test_a_dot_in_a_page_name_matches_only_a_dot(self):
        with tempfile.TemporaryDirectory() as tmp:
            nav = NAV.replace("changes/0.14.md", "changes/0x14.md")
            root = checkout(Path(tmp), ["index.md", "changes/0.14.md"], nav=nav)

            result = check(root)

        self.assertEqual(1, result.returncode)
        self.assertIn("changes/0.14.md is not in mkdocs.yml nav", result.stderr)


if __name__ == "__main__":
    unittest.main()
