#!/usr/bin/env python3
"""Check a lockrot commit before the maintainer approves publishing its schemas.

.github/workflows/schemas.yml runs this in its `check` job, before the `schemas` environment asks
for approval, so a wrong commit is refused there and never stored in SCHEMAS_REF, where it would
stop every later deploy (scripts/fetch-schemas.sh refuses it at build time too).

    python3 scripts/check_schemas_ref.py <sha>

The commit must be a full sha, be on lockrot's main (GitHub serves any commit of a repository's
fork network by its sha, an unmerged pull request's too), and hold at least one
resources/lockrot-<kind>-<N>.schema.json with N of 2 or more. The last line printed names the
schema files and the commit's subject, for the reviewer.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Callable

API = "https://api.github.com/repos/somework/lockrot"
TIMEOUT_SECONDS = 30
SHA = re.compile(r"[0-9a-f]{40}")
NUMBERED = re.compile(r"lockrot-[a-z]+-(\d+)\.schema\.json")


def get_json(url: str):
    """One GitHub API answer; GH_TOKEN, when set, raises the rate limit."""
    headers = {"Accept": "application/vnd.github+json"}
    if os.environ.get("GH_TOKEN"):
        headers["Authorization"] = f"Bearer {os.environ['GH_TOKEN']}"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as error:
        error.close()
        raise SystemExit(f"check_schemas_ref: {url} answers {error.code}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"check_schemas_ref: {url} did not answer: {error.reason}") from error


def check(sha: str, get: Callable[[str], object] = get_json) -> str:
    if not SHA.fullmatch(sha):
        raise SystemExit(f"check_schemas_ref: {sha!r} is not a full commit sha")
    status = get(f"{API}/compare/main...{sha}")["status"]
    # identical: main's head. behind: an older commit of main.
    if status not in ("identical", "behind"):
        raise SystemExit(f"check_schemas_ref: {sha} is not on lockrot's main (compare: {status})")
    names = [entry["name"] for entry in get(f"{API}/contents/resources?ref={sha}") if entry.get("type") == "file"]
    numbered = sorted(name for name in names if (m := NUMBERED.fullmatch(name)) and int(m[1]) >= 2)
    if not numbered:
        raise SystemExit(f"check_schemas_ref: {sha} holds no resources/lockrot-<kind>-<N>.schema.json with N of 2 or more")
    subject = get(f"{API}/commits/{sha}")["commit"]["message"].splitlines()[0]
    # The line starts with the script's name, so a subject cannot open a workflow command.
    return f"check_schemas_ref: {sha} is on lockrot's main and holds {', '.join(numbered)}: {subject!r}"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("usage: check_schemas_ref.py <sha>")
    print(check(argv[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
