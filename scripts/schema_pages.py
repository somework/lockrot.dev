#!/usr/bin/env python3
"""Write the pages of the report schema numbers into build/docs/schema/: one prose page per number.

lockrot's docs/schema.md describes the newest schema number, and the site follows the newest tag,
so /schema/ moves to report-2 with the release that writes it. Users pinned to an older lockrot
still need the field tables of the number they read:

  /schema/report-1/  lockrot v0.13.0's docs/schema.md, frozen in frozen/v0.13.0/docs/schema.md.
                     Written once report-2.json is published, so a build with report-1 as the only
                     number is the site it was.
  /schema/report-2/  the newest tag's docs/schema.md, written only when that page describes
                     report-2 (it names report-2.json): until the tag, it does not.

Each page is a short page of this site that includes the source with include-markdown, which
rewrites the source's relative links. The source is copied to the root of build/docs, where its
links resolve, without its front matter, which include-markdown would print as text; mkdocs.yml
`exclude_docs` keeps that copy from being a page of its own. scripts/mkdocs_hooks.py drops a nav
row and an llms.txt row for a page this script did not write, and dates each page by its source.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

FROZEN_SOURCE = "frozen/v0.13.0/docs/schema.md"
FROZEN_NAME = "schema-report-1.include.md"
CURRENT_NAME = "schema-report-2.include.md"

REPORT_1 = f"""---
title: Report schema 1 — the fields of report-1, lockrot 0.13 and older
description: The JSON report of lockrot 0.13 and older (report-1), frozen from lockrot v0.13.0's schema page.
---

!!! note "Frozen from lockrot v0.13.0"

    lockrot 0.13 and older write report-1. This page is lockrot v0.13.0's schema page, kept as it
    was for the projects still on 0.13. The current page is [JSON schemas](../schema.md).

{{% include-markdown "../{FROZEN_NAME}" %}}
"""

REPORT_2 = f"""---
title: Report schema 2 — the fields of report-2, lockrot 0.14.0 and later
description: The JSON report of lockrot 0.14.0 and later (report-2), from the schema page of the release this site documents.
---

{{% include-markdown "../{CURRENT_NAME}" %}}
"""


def body(text: str) -> str:
    """The page without its YAML front matter."""
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end == -1:
            raise SystemExit("schema_pages: a front matter block that never closes")
        return text[end + len("\n---\n"):].lstrip("\n")
    return text


def _write(build_docs: Path, source: str, name: str, page: str, slug: str) -> None:
    (build_docs / "schema").mkdir(parents=True, exist_ok=True)
    (build_docs / name).write_text(body(source), encoding="utf-8")
    (build_docs / "schema" / f"{slug}.md").write_text(page, encoding="utf-8")


def report_2_page(lockrot_docs: Path, build_docs: Path) -> bool:
    """/schema/report-2/, when the newest docs describe report-2."""
    source = (lockrot_docs / "schema.md").read_text(encoding="utf-8")
    if "report-2.json" not in source:
        return False
    _write(build_docs, source, CURRENT_NAME, REPORT_2, "report-2")
    return True


def report_1_page(frozen: Path, build_docs: Path) -> bool:
    """/schema/report-1/, once report-2.json is published beside report-1.json."""
    if not (build_docs / "schema" / "report-2.json").is_file():
        return False
    _write(build_docs, frozen.read_text(encoding="utf-8"), FROZEN_NAME, REPORT_1, "report-1")
    return True


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lockrot-docs", type=Path, default=Path(".lockrot/docs"))
    parser.add_argument("--frozen", type=Path, default=Path(FROZEN_SOURCE))
    parser.add_argument("--build-docs", type=Path, default=Path("build/docs"))
    args = parser.parse_args(argv[1:])

    written = [
        slug
        for slug, done in (
            ("report-1", report_1_page(args.frozen, args.build_docs)),
            ("report-2", report_2_page(args.lockrot_docs, args.build_docs)),
        )
        if done
    ]
    print(f"schema-pages: {', '.join('/schema/' + s + '/' for s in written) or 'no number pages'}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
