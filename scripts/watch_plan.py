#!/usr/bin/env python3
"""Resolve what this week's watch run reads: the newest stable release of every project.

A release, not a branch head. What a project *ships* is what its users install, and it is also the
only thing that can be named: `2.6.15` is a fact both sides of a conversation can check, while "the
tip of master on a Monday morning" is a moving target that makes two weeks' numbers incomparable
for reasons that have nothing to do with dependency rot. It is the same rule this site follows for
lockrot's own documentation — the newest tag, never main.

Finding that release is not one API call, because projects disagree about what a release is:

  - most publish GitHub releases, and a release flagged pre-release or left in draft is not one,
    whatever its tag looks like;
  - some flag nothing, so `6.0.0-b2` sits at the top of the list looking stable. A tag is therefore
    also read: a version core, optionally with a patch suffix (`2.4.7-p3` is a Magento release),
    and never an alpha, beta, RC, dev or preview;
  - some tag without releasing at all, and then the tags are the releases.

Many maintain more than one line at once — Drupal 10 and 11, TYPO3 13 and 14, Moodle 4.5 and 5 —
and publish a fix to the older one after the newer one's latest release. So the versions are
grouped into release lines the way lockrot's S8 draws a branch, and the row is the newest line's
highest version, never the one published last: a backport would otherwise turn the row into a
different line of the project from one week to the next. Every older line still maintained beside a
newer one — it released inside the window S8 uses (`release-warn-years`), and after the next line up
first did — is read too, as a report of its own beside the table.

The chosen release then has to actually carry `composer.json` and `composer.lock`. Several projects
tag a release whose lock lives elsewhere, or is not committed at all; the run tries the highest few
versions of the line and takes the first that has both, never stepping down to another line. A
project where none does fails the run rather than being quietly dropped, because a page that is
silently one project smaller is worse than a red run.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

API = "https://api.github.com"
GRAPHQL = "https://api.github.com/graphql"

# How far back an older release line still counts as releasing: lockrot's default
# `release-warn-years`, the window S8 gives a branch before calling it left behind. The run's
# reports carry the value lockrot used, and build_watch_page.py fails when the two disagree.
LINE_WINDOW_YEARS = 3

# How many pages of 100 releases or tags to read back through before the run stops and says so.
# Matomo publishes nightly pre-releases, about six a week, and its older line has to stay in reach.
PAGES = 20

# How many times one request is tried through a server error or a dropped connection.
RETRIES = 3
# Packagist's metadata endpoint, the same one Composer reads. Versions come newest first.
PACKAGIST = "https://repo.packagist.org/p2/{package}.json"

# A stable version: a version core, optionally with a patch or point suffix that projects use for
# re-releases (`-p3`, `.1`, `-patch2`). Anything that names a pre-release is not one.
STABLE_TAG = re.compile(r"^v?\d+(\.\d+){0,3}(-(p|patch|sp)\d+)?$", re.I)

# The re-release suffix STABLE_TAG allows, read apart from the version core: `2.4.8-p3` sorts after
# `2.4.8` and before `2.4.9`.
PATCH_SUFFIX = re.compile(r"-(?:p|patch|sp)(\d+)$", re.I)

# Width of the version core a tag is compared on; `26.09` and `26.09.0` compare equal.
VERSION_PARTS = 4

# How many candidate releases to try before giving up on a project.
CANDIDATES = 6


def version_key(tag: str) -> tuple[int, ...]:
    """A tag's version as a sortable tuple: the numbers of its core, padded, then the patch suffix.

    Read from the digits rather than from one tag syntax, because a project's own `tag_pattern` can
    spell a version as `RELEASE_5_2_3` or `release-3.3.19`.
    """
    suffix = PATCH_SUFFIX.search(tag)
    core = tag[: suffix.start()] if suffix else tag
    numbers = [int(n) for n in re.findall(r"\d+", core)][:VERSION_PARTS]
    numbers += [0] * (VERSION_PARTS - len(numbers))
    return (*numbers, int(suffix.group(1)) if suffix else 0)


class NotFound(Exception):
    """GitHub answered 404: the file or the repository is not there."""


def fetch(request: urllib.request.Request, what: str):
    """The JSON one request answers, tried RETRIES times through a 5xx or a dropped connection.

    A 404 is an answer and raises NotFound. Anything else that is still failing after the last try
    stops the run, because the callers turn "no answer" into a public statement — "this release
    carries no lock file", "this line has no row" — and a 502 is not that.
    """
    for attempt in range(1, RETRIES + 1):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.load(response)
        except urllib.error.HTTPError as err:
            if err.code == 404:
                raise NotFound(what) from err
            if err.code in (401, 403, 429):
                raise SystemExit(
                    f"watch_plan: {what} answered {err.code}; the token's hourly allowance is spent, "
                    "or there is no token. Set ROT_WATCH_TOKEN."
                ) from err
            if err.code < 500 or attempt == RETRIES:
                raise SystemExit(f"watch_plan: {what} answered {err.code}") from err
        # Every transport failure: URLError and timeouts are OSErrors, and so is a connection reset;
        # a cut-off body is an http.client.HTTPException. HTTPError, an OSError too, is caught above.
        except (OSError, http.client.HTTPException, json.JSONDecodeError) as err:
            if attempt == RETRIES:
                raise SystemExit(f"watch_plan: cannot read {what}: {err}") from err
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


def get(path: str, token: str | None):
    """One GitHub REST answer, or None when GitHub says the thing is not there."""
    request = urllib.request.Request(
        f"{API}{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "lockrot.dev rot watch",
            **({"Authorization": f"Bearer {token}"} if token else {}),
        },
    )
    try:
        return fetch(request, f"GitHub {path}")
    except NotFound:
        return None


def graphql(query: str, variables: dict, token: str | None) -> dict:
    """One GitHub GraphQL query. It needs a token, which the run always has.

    GraphQL reports a server-side timeout as a 200 with `errors`, so those are tried again as well;
    a repository that does not exist comes back as data with `repository: null`, for the caller.
    """
    if not token:
        raise SystemExit("watch_plan: GitHub's GraphQL API needs a token; set ROT_WATCH_TOKEN or GH_TOKEN")
    for attempt in range(1, RETRIES + 1):
        request = urllib.request.Request(
            GRAPHQL,
            data=json.dumps({"query": query, "variables": variables}).encode(),
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "lockrot.dev rot watch",
            },
        )
        body = fetch(request, "GitHub GraphQL")
        errors = body.get("errors") or []
        if not errors or all(e.get("type") == "NOT_FOUND" for e in errors):
            return body.get("data") or {}
        if attempt == RETRIES:
            raise SystemExit(f"watch_plan: GitHub GraphQL: {errors[0].get('message')}")
        time.sleep(2 ** attempt)
    raise AssertionError("unreachable")


RELEASES = """query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    connection: releases(first: 100, after: $after, orderBy: {field: CREATED_AT, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { name: tagName isDraft isPrerelease publishedAt tagCommit { oid committedDate } }
    }
  }
}"""

TAGS = """query($owner: String!, $name: String!, $after: String) {
  repository(owner: $owner, name: $name) {
    connection: refs(refPrefix: "refs/tags/", first: 100, after: $after,
                     orderBy: {field: TAG_COMMIT_DATE, direction: DESC}) {
      pageInfo { hasNextPage endCursor }
      nodes { name target { ... on Commit { oid committedDate }
                            ... on Tag { target { ... on Commit { oid committedDate } } } } }
    }
  }
}"""


def _commit(node: dict) -> dict:
    """The commit a release or a tag points at, through an annotated tag when there is one."""
    if "tagCommit" in node:
        return node["tagCommit"] or {}
    target = node.get("target") or {}
    return target.get("target") or target


def _read(query: str, repo: str, token: str | None, pattern: re.Pattern, cutoff: str) -> tuple[bool, list[dict]]:
    """One source — releases or tags — read back past the window's start: whether it had any entry
    at all, and the stable versions in it. Stops the run rather than a list cut short in silence."""
    owner, name = repo.split("/", 1)
    found, seen_any, after = [], False, None
    for _ in range(PAGES):
        data = graphql(query, {"owner": owner, "name": name, "after": after}, token)
        if data.get("repository") is None:
            raise SystemExit(f"watch_plan: GitHub has no repository {repo}")
        connection = data["repository"]["connection"]
        dates = []
        for node in connection["nodes"]:
            seen_any = True
            commit = _commit(node)
            date = (commit.get("committedDate") or node.get("publishedAt") or "")[:10]
            if date:
                dates.append(date)
            if node.get("isDraft") or node.get("isPrerelease") or not commit.get("oid") or not date:
                continue
            if pattern.match(node["name"]):
                found.append({"tag": node["name"], "commit": commit["oid"], "date": date})
        if not connection["pageInfo"]["hasNextPage"] or (found and dates and min(dates) < cutoff):
            return seen_any, found
        after = connection["pageInfo"]["endCursor"]
    raise SystemExit(
        f"watch_plan: {repo} has more than {PAGES * 100} entries inside the window; raise PAGES in "
        "watch_plan.py rather than read part of it"
    )


def versions(repo: str, token: str | None, pattern: re.Pattern, cutoff: str) -> list[dict]:
    """Every stable version of the project, with its commit and the date of that commit, newest
    first by date, reading back until the window's start.

    From the project's GitHub releases when they hold a stable one — a release flagged pre-release or
    left in draft is not one, whatever its tag looks like — and from its tags otherwise: a project
    that tags its releases and once published a single alpha as a GitHub release still has them.
    The date is the commit's, which is how Packagist and lockrot date a tag too.
    """
    for query in (RELEASES, TAGS):
        _, found = _read(query, repo, token, pattern, cutoff)
        if found:
            return found
    return []


def release_line(tag: str) -> str:
    """The release branch a version is on, as lockrot's S8 draws it: what a caret constraint on the
    version stays inside — the major from 1.0 up, the major and minor below it, the patch below 0.1.
    """
    major, minor, patch = version_key(tag)[:3]
    if major:
        return str(major)
    return f"0.{minor}" if minor else f"0.0.{patch}"


def lines(found: list[dict]) -> dict[str, list[dict]]:
    """The versions grouped by release branch, each branch highest version first."""
    grouped: dict[str, list[dict]] = {}
    for version in found:
        grouped.setdefault(release_line(version["tag"]), []).append(version)
    return {
        line: sorted(members, key=lambda v: version_key(v["tag"]), reverse=True)
        for line, members in grouped.items()
    }


def has_files(repo: str, sha: str, lock: str, token: str | None) -> bool:
    manifest = lock[: -len("composer.lock")] + "composer.json"
    return all(
        get(f"/repos/{repo}/contents/{path}?ref={sha}", token) is not None
        for path in (lock, manifest)
    )


def pick(project: dict, members: list[dict], token: str | None) -> tuple[dict | None, list[str]]:
    """The highest version of one branch that carries composer.json and composer.lock.

    Within the branch only: falling back to an older branch would make the row report a different
    line of the project from one week to the next, and its change would be the line's, not the rot's.
    """
    repo, lock, tried = project["repo"], project["lock"], []
    for version in members[:CANDIDATES]:
        if has_files(repo, version["commit"], lock, token):
            return {
                "name": project["name"],
                "repo": repo,
                "tag": version["tag"],
                "tag_url": f"https://github.com/{repo}/releases/tag/{version['tag']}",
                "commit": version["commit"],
                "commit_url": f"https://github.com/{repo}/tree/{version['commit']}",
                "released": version["date"],
                "line": release_line(version["tag"]),
                "lock": lock,
                "target_php": project["target_php"],
            }, tried
        tried.append(f"{version['tag']} (no {lock})")
    return None, tried


def line_name(project: str, line: str) -> str:
    """A branch's own name in the run: `drupal-v10`. No dot, because the viewer's host serves
    `reports/watch/<name>` by adding `.html`, and a name that already ends in `.x` reads as a file."""
    return f"{project}-v{line.replace('.', '-')}"


def still_releasing(line: str, by_line: dict[str, list[dict]], cutoff: str) -> bool:
    """Whether an older line is maintained beside a newer one, rather than finished when it came.

    Two conditions, both lockrot's S8: the line has released inside the window, and it released
    *after* the next line up first did — S8 calls a branch left behind only once a higher branch has
    released since, and the converse is what makes two lines concurrent. BookStack's v25 shipped its
    last release three days before v26's first, so it is a line that ended, not one still kept.
    """
    last = max(v["date"] for v in by_line[line])
    if last < cutoff:
        return False
    key = version_key(by_line[line][0]["tag"])
    higher = [other for other in by_line if version_key(by_line[other][0]["tag"]) > key]
    if not higher:
        return False
    next_up = min(higher, key=lambda other: version_key(by_line[other][0]["tag"]))
    return last > min(v["date"] for v in by_line[next_up])


def resolve(project: dict, token: str | None, cutoff: str) -> tuple[list[dict], list[dict]]:
    """The project's newest release line, and every older line still releasing, as run entries.

    The newest line is the row the page totals and compares week to week; a project with no usable
    release there fails the run, as before. An older line is one more report, beside the table, when
    it is still releasing beside a newer one (`still_releasing`). An older line whose releases carry
    no lock file is not dropped quietly: it is listed in the manifest as skipped.
    """
    repo = project["repo"]
    pattern = re.compile(project["tag_pattern"]) if project.get("tag_pattern") else STABLE_TAG
    found = versions(repo, token, pattern, cutoff)
    if not found:
        raise SystemExit(
            f"watch_plan: no stable release for {repo}; its tags no longer match, fix data/watch/projects.json."
        )
    by_line = lines(found)
    newest = max(by_line, key=lambda line: version_key(by_line[line][0]["tag"]))

    main, tried = pick(project, by_line[newest], token)
    if main is None:
        raise SystemExit(
            f"watch_plan: no usable release on {repo}'s newest line {newest}.x. Tried: "
            f"{', '.join(tried) or 'nothing'}. Either the project stopped shipping a lock file at its "
            "releases, or its tags no longer match; fix data/watch/projects.json."
        )
    entries, skipped = [{"kind": "release", **main}], []

    older = [line for line in by_line if line != newest and still_releasing(line, by_line, cutoff)]
    for line in sorted(older, key=lambda line: version_key(by_line[line][0]["tag"]), reverse=True):
        entry, tried = pick(project, by_line[line], token)
        if entry is None:
            skipped.append({"project": project["name"], "line": line, "tried": tried})
            continue
        entries.append({**entry, "kind": "line", "parent": project["name"], "name": line_name(project["name"], line)})
    return entries, skipped


def years_before(date: str, years: int) -> str:
    """`date` less `years` years, as an ISO date; 29 February lands on the 28th."""
    day = datetime.strptime(date, "%Y-%m-%d").date()
    try:
        return day.replace(year=day.year - years).isoformat()
    except ValueError:
        return day.replace(year=day.year - years, day=28).isoformat()


def newest_package_version(package: str) -> str:
    """The newest stable version of a starter package, as Packagist lists it."""
    request = urllib.request.Request(
        PACKAGIST.format(package=package),
        headers={"User-Agent": "lockrot.dev rot watch", "Accept": "application/json"},
    )
    try:
        versions = fetch(request, f"Packagist {package}")["packages"][package]
    except (NotFound, KeyError, TypeError) as err:
        raise SystemExit(f"watch_plan: cannot read {package} from Packagist: {err!r}") from err

    # The highest stable version, not the first one listed: the order is Packagist's to change.
    stable = [version["version"] for version in versions if STABLE_TAG.match(version["version"])]
    if not stable:
        raise SystemExit(f"watch_plan: {package} has no stable version on Packagist")
    return max(stable, key=version_key)


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
    cutoff = years_before(date, LINE_WINDOW_YEARS)
    resolved, skipped = [], []
    for project in projects["projects"]:
        entries, missed = resolve({**project, "target_php": project.get("target_php", target_php)}, token, cutoff)
        resolved += entries
        skipped += missed
    resolved += [resolve_starter(starter, target_php) for starter in projects.get("starters", [])]
    return {
        "run": {
            "date": date,
            "target_php": target_php,
            "line_window_years": LINE_WINDOW_YEARS,
            "skipped_lines": skipped,
        },
        "projects": resolved,
    }


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
    releases = [p for p in manifest["projects"] if p["kind"] in ("release", "line")]
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
            print(
                f"watch-plan: {project['name']:22} {project['tag']:>16}  {project['commit'][:7]}"
                f"  {project['line']}.x released {project['released']}"
            )
    for miss in manifest["run"]["skipped_lines"]:
        print(f"watch-plan: skipped {miss['project']} {miss['line']}.x: {', '.join(miss['tried'])}")
    kinds = [p["kind"] for p in manifest["projects"]]
    print(
        f"watch-plan: {kinds.count('release')} releases, {kinds.count('line')} older lines and "
        f"{kinds.count('starter')} starters at {manifest['run']['date']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
