#!/usr/bin/env python3
"""Check that a schema URL answers with the schema it names, on the live site.

Run at the lockrot release order's schema step: after the `schemas` job published the -2 files,
and again before the tag. A released document's `$schema` must never answer 404.

    python3 scripts/check_schema_live.py [URL ...]

With no URL it checks https://lockrot.dev/schema/report-2.json. Exit 0 when every URL answers 200
with a JSON document whose `id` is that URL; otherwise the first failure stops it.
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

DEFAULT = "https://lockrot.dev/schema/report-2.json"
TIMEOUT_SECONDS = 30


def check(url: str) -> str:
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=TIMEOUT_SECONDS) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        error.close()
        raise SystemExit(f"check_schema_live: {url} answers {error.code}") from error
    except urllib.error.URLError as error:
        raise SystemExit(f"check_schema_live: {url} did not answer: {error.reason}") from error
    try:
        found = json.loads(raw).get("id")
    except (json.JSONDecodeError, AttributeError) as error:
        raise SystemExit(f"check_schema_live: {url} answers with something that is not a JSON schema") from error
    if found != url:
        raise SystemExit(f"check_schema_live: {url} answers with the schema {found!r}")
    return f"check_schema_live: {url} answers 200 with its own schema"


def main(argv: list[str]) -> int:
    for url in argv[1:] or [DEFAULT]:
        print(check(url))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
