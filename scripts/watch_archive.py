#!/usr/bin/env python3
"""Lay out every weekly run's capsules, out of git, so each run's reports can be published again.

The weekly run rewrites `data/reports/watch/` in place: a run's capsules are 5–6 MB, and keeping
every week beside the last would grow the checkout by that much every Monday, forever. Git keeps
them anyway. So the archive is built rather than stored: for every run the history names, this
reads the capsules and the manifest out of the newest commit that holds that run, and writes them to
`<out>/<date>/`, which is the layout scripts/build_reports.py turns into pages — one per project
under /reports/watch/<date>/ on the viewer's host. The run in the working tree is laid out too, and
wins over the committed copy of the same date, so a run not yet committed previews correctly.

Every date in history.csv has to come out of this with its reports, because /watch/ links each of
them; a run the history names and git cannot produce fails the build. So does a shallow clone, which
would otherwise quietly publish an archive one week deep.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

RUN_DIR = "data/reports/watch"
MANIFEST = "manifest.json"


def git(*args: str, cwd: Path, stdin: bytes | None = None) -> bytes:
    try:
        return subprocess.run(
            ["git", *args], cwd=cwd, input=stdin, capture_output=True, check=True
        ).stdout
    except (OSError, subprocess.CalledProcessError) as err:
        detail = getattr(err, "stderr", b"") or b""
        raise SystemExit(f"watch_archive: git {' '.join(args)} failed: {detail.decode().strip() or err}") from err


def runs_in_git(repo: Path) -> dict[str, str]:
    """Each run's date, mapped to the newest commit that holds that run's manifest."""
    if git("rev-parse", "--is-shallow-repository", cwd=repo).strip() == b"true":
        raise SystemExit(
            "watch_archive: this is a shallow clone, so the earlier runs are not in it; "
            "check out with fetch-depth: 0"
        )

    runs: dict[str, str] = {}
    for commit in git("log", "--format=%H", "--", f"{RUN_DIR}/{MANIFEST}", cwd=repo).decode().split():
        manifest = json.loads(git("show", f"{commit}:{RUN_DIR}/{MANIFEST}", cwd=repo))
        # git log lists newest first, so the first commit seen for a date is the one that won.
        runs.setdefault(manifest["run"]["date"], commit)
    return runs


def files_at(repo: Path, commit: str) -> dict[str, bytes]:
    """Every JSON file of the run directory at `commit`, read in one `git cat-file --batch`."""
    names = [
        name
        for name in git("ls-tree", "--name-only", commit, f"{RUN_DIR}/", cwd=repo).decode().split("\n")
        if name.endswith(".json")
    ]
    request = "".join(f"{commit}:{name}\n" for name in names).encode()
    out = git("cat-file", "--batch", cwd=repo, stdin=request)

    files, pos = {}, 0
    for name in names:
        end = out.index(b"\n", pos)
        _, kind, size = out[pos:end].decode().split(" ")
        if kind != "blob":
            raise SystemExit(f"watch_archive: {commit}:{name} is a {kind}, not a file")
        start = end + 1
        files[Path(name).name] = out[start : start + int(size)]
        pos = start + int(size) + 1
    return files


def history_dates(path: Path) -> set[str]:
    with path.open(newline="", encoding="utf-8") as fh:
        return {row["date"] for row in csv.DictReader(fh)}


def lay_out(repo: Path, out: Path, history: Path) -> dict[str, int]:
    """Write every run to `<out>/<date>/`; return how many reports each date has."""
    shutil.rmtree(out, ignore_errors=True)
    written: dict[str, int] = {}

    for date, commit in sorted(runs_in_git(repo).items()):
        run = out / date
        run.mkdir(parents=True)
        for name, content in files_at(repo, commit).items():
            (run / name).write_bytes(content)
        written[date] = sum(1 for name in run.iterdir() if name.name != MANIFEST)

    current = repo / RUN_DIR / MANIFEST
    if current.is_file():
        date = json.loads(current.read_text(encoding="utf-8"))["run"]["date"]
        run = out / date
        shutil.rmtree(run, ignore_errors=True)
        run.mkdir(parents=True)
        for file in (repo / RUN_DIR).glob("*.json"):
            shutil.copyfile(file, run / file.name)
        written[date] = sum(1 for name in run.iterdir() if name.name != MANIFEST)

    missing = sorted(history_dates(history) - set(written))
    if missing:
        raise SystemExit(
            f"watch_archive: history.csv names runs git does not hold: {', '.join(missing)}"
        )
    return written


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--out", type=Path, default=Path("build/watch-archive"))
    parser.add_argument("--history", type=Path, default=Path("content/assets/data/watch/history.csv"))
    args = parser.parse_args(argv[1:])

    written = lay_out(args.repo, args.out, args.history)
    print(
        f"watch-archive: {len(written)} run(s), {sum(written.values())} report(s): "
        + ", ".join(f"{date} ({n})" for date, n in sorted(written.items()))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
