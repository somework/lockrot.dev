#!/usr/bin/env python3
"""Unit tests for scripts/watch_archive.py, against a throwaway git repository."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

import watch_archive as wa

ENV = {
    **os.environ,
    "GIT_AUTHOR_NAME": "test", "GIT_AUTHOR_EMAIL": "test@example.com",
    "GIT_COMMITTER_NAME": "test", "GIT_COMMITTER_EMAIL": "test@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}


def run(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, env=ENV, check=True, capture_output=True)


def write_run(repo: Path, date: str, reports: dict[str, int]) -> None:
    """One week's run as the weekly job leaves it: a manifest and a capsule per project."""
    run_dir = repo / wa.RUN_DIR
    for old in run_dir.glob("*.json"):
        old.unlink()
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / wa.MANIFEST).write_text(
        json.dumps({"run": {"date": date}, "projects": [{"name": n} for n in reports]}), encoding="utf-8"
    )
    for name, abandoned in reports.items():
        (run_dir / f"{name}.json").write_text(json.dumps({"abandoned": abandoned}), encoding="utf-8")


def commit(repo: Path, message: str) -> None:
    run(repo, "add", "-A")
    run(repo, "commit", "-q", "-m", message)


def history(repo: Path, *dates: str) -> Path:
    path = repo / "history.csv"
    path.write_text("date,name\n" + "".join(f"{d},one\n" for d in dates), encoding="utf-8")
    return path


class ArchiveTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name) / "repo"
        self.repo.mkdir()
        run(self.repo, "init", "-q")
        self.out = Path(self.tmp.name) / "out"

    def tearDown(self):
        self.tmp.cleanup()

    def read(self, date: str, name: str) -> dict:
        return json.loads((self.out / date / f"{name}.json").read_text(encoding="utf-8"))

    def test_lays_out_every_committed_run_under_its_date(self):
        write_run(self.repo, "2026-09-08", {"one": 1, "two": 2})
        commit(self.repo, "run 1")
        write_run(self.repo, "2026-09-15", {"one": 3})
        commit(self.repo, "run 2")

        written = wa.lay_out(self.repo, self.out, history(self.repo, "2026-09-08", "2026-09-15"))

        self.assertEqual({"2026-09-08": 2, "2026-09-15": 1}, written)
        self.assertEqual({"abandoned": 2}, self.read("2026-09-08", "two"))
        self.assertTrue((self.out / "2026-09-08" / wa.MANIFEST).is_file())
        # The later run removed `two`; the earlier run keeps it.
        self.assertFalse((self.out / "2026-09-15" / "two.json").exists())

    def test_a_rerun_of_the_same_day_is_read_from_its_newest_commit(self):
        write_run(self.repo, "2026-09-08", {"one": 1})
        commit(self.repo, "run")
        write_run(self.repo, "2026-09-08", {"one": 9})
        commit(self.repo, "rerun")

        wa.lay_out(self.repo, self.out, history(self.repo, "2026-09-08"))

        self.assertEqual({"abandoned": 9}, self.read("2026-09-08", "one"))

    def test_a_run_not_yet_committed_comes_from_the_tree(self):
        write_run(self.repo, "2026-09-08", {"one": 1})
        commit(self.repo, "run")
        write_run(self.repo, "2026-09-15", {"one": 4})

        written = wa.lay_out(self.repo, self.out, history(self.repo, "2026-09-08", "2026-09-15"))

        self.assertEqual({"abandoned": 4}, self.read("2026-09-15", "one"))
        self.assertEqual({"2026-09-08", "2026-09-15"}, set(written))

    def test_a_run_the_history_names_and_git_does_not_hold_fails(self):
        write_run(self.repo, "2026-09-15", {"one": 1})
        commit(self.repo, "run")

        with self.assertRaises(SystemExit) as raised:
            wa.lay_out(self.repo, self.out, history(self.repo, "2026-09-08", "2026-09-15"))

        self.assertIn("2026-09-08", str(raised.exception))

    def test_a_shallow_clone_fails_rather_than_publishing_one_week(self):
        write_run(self.repo, "2026-09-08", {"one": 1})
        commit(self.repo, "run 1")
        write_run(self.repo, "2026-09-15", {"one": 2})
        commit(self.repo, "run 2")
        shallow = Path(self.tmp.name) / "shallow"
        subprocess.run(
            ["git", "clone", "-q", "--depth", "1", f"file://{self.repo}", str(shallow)],
            env=ENV, check=True, capture_output=True,
        )

        with self.assertRaises(SystemExit) as raised:
            wa.lay_out(shallow, self.out, history(shallow, "2026-09-15"))

        self.assertIn("shallow", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
