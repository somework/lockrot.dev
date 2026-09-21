#!/usr/bin/env python3
"""Resolve what this week's watch run reads: the newest stable release of every project.

A release, not a branch head. What a project *ships* is what its users install, and it is also the
only thing that can be named: `2.6.15` is a fact both sides of a conversation can check, while "the
tip of master on a Monday morning" is a moving target that makes two weeks' numbers incomparable
for reasons that have nothing to do with dependency rot. It is the same rule this site follows for
lockrot's own documentation — the newest tag, never main.

Finding that release is not one API call, because projects disagree about what a release is:

  - GitHub's own `releases/latest` skips drafts and anything flagged pre-release, and is right
    whenever a project uses releases at all and flags them honestly;
  - some projects flag nothing, so `6.0.0-b2` sits at the top of the list looking stable. A tag is
    therefore also read: a version core, optionally with a patch suffix (`2.4.7-p3` is a Magento
    release), and never an alpha, beta, RC, dev or preview;
  - some tag without releasing at all, so the tag list is the last resort.

The chosen release then has to actually carry `composer.json` and `composer.lock`. Several projects
tag a release whose lock lives elsewhere, or is not committed at all; the run tries the newest few
candidates and takes the first that has both. A project where none does fails the run rather than
being quietly dropped, because a page that is silently one project smaller is worse than a red run.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
# Packagist's metadata endpoint, the same one Composer reads. Versions come newest first.
PACKAGIST = "https://repo.packagist.org/p2/{package}.json"

# A stable version: a version core, optionally with a patch or point suffix that projects use for
# re-releases (`-p3`, `.1`, `-patch2`). Anything that names a pre-release is not one.
STABLE_TAG = re.compile(r"^v?\d+(\.\d+){0,3}(-(p|patch|sp)\d+)?$", re.I)

# How many candidate releases to try before giving up on a project.
CANDIDATES = 6


def get(path: str, token: str | None):
    request = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "lockrot.dev rot watch",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as err:
        if err.code in (403, 429):
            raise SystemExit(
                f"watch_plan: GitHub answered {err.code} for {path}; the token's hourly allowance "
                "is spent, or there is no token. Set ROT_WATCH_TOKEN."
            ) from err
        return None
    except (urllib.error.URLError, TimeoutError) as err:
        raise SystemExit(f"watch_plan: cannot reach GitHub for {path}: {err}") from err


def candidates(repo: str, token: str | None, pattern: re.Pattern) -> list[str]:
    """Release tags for this project, newest first, pre-releases left out."""
    names = []
    latest = get(f"/repos/{repo}/releases/latest", token)
    if latest and pattern.match(latest["tag_name"]):
        names.append(latest["tag_name"])

    for release in get(f"/repos/{repo}/releases?per_page=30", token) or []:
        if release.get("draft") or release.get("prerelease"):
            continue
        if pattern.match(release["tag_name"]) and release["tag_name"] not in names:
            names.append(release["tag_name"])

    if not names:
        # No releases, only tags. They come back in the order the API lists them, which is the
        # order the project's refs are in — good enough, since the filter above rules out the
        # pre-release tags that would otherwise sit on top.
        for tag in get(f"/repos/{repo}/tags?per_page=50", token) or []:
            if pattern.match(tag["name"]):
                names.append(tag["name"])

    return names[:CANDIDATES]


def commit_of(repo: str, tag: str, token: str | None) -> str | None:
    ref = get(f"/repos/{repo}/git/ref/tags/{urllib.parse.quote(tag)}", token)
    if not ref:
        return None
    obj = ref["object"] if isinstance(ref, dict) else None
    if not obj:
        return None
    if obj["type"] == "commit":
        return obj["sha"]
    # An annotated tag points at a tag object, which points at the commit.
    annotated = get(f"/repos/{repo}/git/tags/{obj['sha']}", token)
    return annotated["object"]["sha"] if annotated else None


def has_files(repo: str, sha: str, lock: str, token: str | None) -> bool:
    manifest = lock[: -len("composer.lock")] + "composer.json"
    return all(
        get(f"/repos/{repo}/contents/{path}?ref={sha}", token) is not None
        for path in (lock, manifest)
    )


def resolve(project: dict, token: str | None) -> dict:
    repo, lock = project["repo"], project["lock"]
    pattern = re.compile(project["tag_pattern"]) if project.get("tag_pattern") else STABLE_TAG

    tried = []
    for tag in candidates(repo, token, pattern):
        sha = commit_of(repo, tag, token)
        if sha is None:
            tried.append(f"{tag} (no commit)")
            continue
        if not has_files(repo, sha, lock, token):
            tried.append(f"{tag} (no {lock})")
            continue
        return {
            "name": project["name"],
            "repo": repo,
            "tag": tag,
            "tag_url": f"https://github.com/{repo}/releases/tag/{tag}",
            "commit": sha,
            "commit_url": f"https://github.com/{repo}/tree/{sha}",
            "lock": lock,
            "target_php": project["target_php"],
        }

    raise SystemExit(
        f"watch_plan: no usable release for {repo}. Tried: {', '.join(tried) or 'nothing'}. "
        "Either the project stopped shipping a lock file at its releases, or its tags no longer "
        "match; fix data/watch/projects.json."
    )


def newest_package_version(package: str) -> str:
    """The newest stable version of a starter package, as Packagist lists it."""
    request = urllib.request.Request(
        PACKAGIST.format(package=package),
        headers={"User-Agent": "lockrot.dev rot watch", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            versions = json.load(response)["packages"][package]
    except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as err:
        raise SystemExit(f"watch_plan: cannot read {package} from Packagist: {err}") from err

    for version in versions:
        name = version["version"]
        if STABLE_TAG.match(name):
            return name

    raise SystemExit(f"watch_plan: {package} has no stable version on Packagist")


def resolve_starter(starter: dict, target_php: str) -> dict:
    """A starter is a command, not a commit: what `composer create-project` gives you today.

    The starter package itself is pinned to its newest stable version, so the row names something
    checkable; everything under it resolves fresh, which is the whole point — the question this
    answers is what a project started this week actually gets.
    """
    package = starter["package"]
    version = newest_package_version(package)
    steps = [f"composer create-project {package}:{version} ."]
    steps += [f"composer require {' '.join(starter['require'])}"] if starter.get("require") else []
    return {
        "kind": "starter",
        "name": starter["name"],
        "title": starter["title"],
        "package": package,
        "version": version,
        "packagist_url": f"https://packagist.org/packages/{package}",
        "require": starter.get("require", []),
        "command": " && ".join(steps),
        "target_php": starter.get("target_php", target_php),
    }


def plan(projects: dict, token: str | None, date: str) -> dict:
    target_php = projects["target_php"]
    resolved = [
        {"kind": "release", **resolve({**project, "target_php": project.get("target_php", target_php)}, token)}
        for project in projects["projects"]
    ]
    resolved += [resolve_starter(starter, target_php) for starter in projects.get("starters", [])]
    return {"run": {"date": date, "target_php": target_php}, "projects": resolved}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--projects", type=Path, default=Path("data/watch/projects.json"))
    parser.add_argument("--out", type=Path, default=Path("data/reports/watch/manifest.json"))
    args = parser.parse_args(argv[1:])

    projects = json.loads(args.projects.read_text(encoding="utf-8"))
    manifest = plan(
        projects,
        os.environ.get("ROT_WATCH_TOKEN") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN"),
        datetime.now(timezone.utc).strftime("%Y-%m-%d"),
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(manifest, indent=4, ensure_ascii=False) + "\n", encoding="utf-8")

    # Two matrices, because the two halves of the run are two different jobs: one fetches two files
    # from a repository, the other builds a project with Composer.
    releases = [p for p in manifest["projects"] if p["kind"] == "release"]
    starters = [p for p in manifest["projects"] if p["kind"] == "starter"]
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as fh:
            fh.write(f"matrix={json.dumps(releases, separators=(',', ':'))}\n")
            fh.write(f"starters={json.dumps(starters, separators=(',', ':'))}\n")

    for project in manifest["projects"]:
        if project["kind"] == "starter":
            print(f"watch-plan: {project['name']:16} {project['version']:>16}  (created fresh)")
        else:
            print(f"watch-plan: {project['name']:16} {project['tag']:>16}  {project['commit'][:7]}")
    kinds = [p["kind"] for p in manifest["projects"]]
    print(
        f"watch-plan: {kinds.count('release')} releases and {kinds.count('starter')} starters "
        f"at {manifest['run']['date']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
