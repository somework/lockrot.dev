#!/usr/bin/env python3
"""Store a `--format=html` report as data, and put it back together on the next build.

A lockrot report page is one file with three things in it: the document, the renderer, and the two
sentences the formatter wrote about the run. Only the first of those is worth keeping in git — the
renderer is 110 KB of the same JavaScript on every page, and a weekly run over twenty projects
would commit it twenty times a week forever.

So the pipeline splits a report: {@see extract} pulls the document and the two sentences out of the
page lockrot wrote and stores them as one JSON file ("a capsule"), and {@see render} fills the same
template again at build time with the renderer of whatever release the site is being built from.

The sentences are stored exactly as they appear in the page, HTML escapes and all, and are put back
verbatim. They are lockrot's wording about lockrot's verdicts, and a copy of `HtmlFormatter`'s
phrasing here would be a second source of truth that drifts at the next release.

Every step asserts. A release that reshapes `report.html` fails a build here rather than rendering
a blank page in someone's browser, which is the same bargain scripts/build_frame.py makes.
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

# The template's five placeholders, as HtmlFormatter fills them (src/Output/HtmlFormatter.php).
TITLE = "{{TITLE}}"
DESCRIPTION = "{{DESCRIPTION}}"
CSS = "{{CSS}}"
JS = "{{JS}}"
DATA = "{{DATA}}"
PLACEHOLDER = re.compile(r"\{\{[A-Z]+\}\}")

# This site is the publisher of these pages, and the report template leaves the robots directive to
# whoever publishes. The pages are twenty near-identical shells whose content lives in a JSON
# script tag and changes every week; the page that carries the same findings as text, and is meant
# to be found, is the site's own. The header rule in viewer/_headers says the same thing to a
# crawler that never parses the document.
ROBOTS = '<meta name="robots" content="noindex">'
HEAD_ANCHOR = "<title>"

# Where the band below goes: the first thing inside the document, above lockrot's own header.
BODY_ANCHOR = "<body>"

# A published report says what it was made from. lockrot's page names the project and the day it
# was generated, because that is all a report knows about itself; a page published by someone else
# has to say the rest — which release, which commit, and whose run this was. The colours are
# lockrot's own custom properties, so the band follows its light and dark themes instead of
# fighting them.
BAND_STYLE = (
    "font:13px/1.5 var(--sans);background:var(--surface);color:var(--muted);"
    "border-bottom:1px solid var(--border);padding:8px 16px"
)

# An HTML parser ends a <script> element at the first `</script`, and stops parsing at `<!--`, and
# both can reach the payload through a package's own name, description or advisory title. lockrot
# writes them as JSON escapes that read back as the same string; so does this.
PAYLOAD_ESCAPES = (("</", "<\\/"), ("<!--", "<\\u0021--"))

_TITLE_TAG = re.compile(r"<title>(.*?)</title>", re.S)
_DESCRIPTION_TAG = re.compile(r'<meta name="description" content="(.*?)">', re.S)
_PAYLOAD_TAG = re.compile(
    r'<script id="lockrot-data" type="application/json">(.*?)</script>', re.S
)


def extract(page: str) -> dict:
    """One page from `composer lockrot --format=html`, as the three things worth keeping."""
    title = _only(_TITLE_TAG, page, "a <title>")
    description = _only(_DESCRIPTION_TAG, page, 'a <meta name="description">')
    payload = _only(_PAYLOAD_TAG, page, 'the <script id="lockrot-data"> payload')

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as err:
        raise SystemExit(f"report_page: the page's payload is not JSON: {err}") from err
    if "report" not in data:
        raise SystemExit("report_page: the payload carries no report key")

    return {"title": title, "description": description, "data": data}


def render(
    capsule: dict, template: str, css: str | None, js: str | None, provenance: dict | None = None
) -> str:
    """The capsule, the template and this release's renderer, back into one self-contained page.

    `css` and `js` are the hand-written renderer's sources, and None for a released renderer, whose
    template already carries both. Which one this is follows from the template: one that still has
    {{JS}} splices the renderer in.
    """
    for key in ("title", "description", "data"):
        if key not in capsule:
            raise SystemExit(f"report_page: the capsule has no {key}")

    spliced = JS in template
    if spliced and (css is None or js is None):
        raise SystemExit("report_page: this template splices the renderer in, and none was given")

    fills = [(TITLE, capsule["title"]), (DESCRIPTION, capsule["description"])]
    if spliced:
        fills += [(CSS, css), (JS, js)]
    fills.append((DATA, payload(capsule["data"])))

    out = template
    for placeholder, value in fills:
        if placeholder not in out:
            raise SystemExit(f"report_page: the template has no {placeholder}")
        out = out.replace(placeholder, value)

    if HEAD_ANCHOR not in out:
        raise SystemExit("report_page: the template has no <title> to anchor the robots meta to")
    out = out.replace(HEAD_ANCHOR, ROBOTS + "\n" + HEAD_ANCHOR, 1)

    if provenance is not None:
        if BODY_ANCHOR not in out:
            raise SystemExit("report_page: the template has no <body> to anchor the band to")
        out = out.replace(BODY_ANCHOR, BODY_ANCHOR + "\n" + band(provenance, inline=spliced), 1)

    # A placeholder is {{NAME}}. Anything else with two braces is the renderer's own code or a
    # comment in its stylesheet, which a released template carries inline.
    if PLACEHOLDER.search(out):
        raise SystemExit("report_page: a placeholder was left unfilled")
    return out


def band(provenance: dict, inline: bool = False) -> str:
    """One line above the report saying what it was read from, and by whom.

    Two shapes, because there are two kinds of report here. One was read from a project's own
    repository, and then `repo` and `commit` are required while a `tag` is not — a page that
    claimed a release it did not read would be worse than one that names only the commit. The other
    has no repository to name: it is a project created by `composer create-project` on the day of
    the run, and what it can be checked against is the command. Everything printed is escaped; a
    tag name and a package name are both written upstream.

    `inline` styles the band with style attributes, for the hand-written renderer. A released
    renderer's page refuses those under its Content-Security-Policy, and styles the
    `lockrot-provenance` class itself instead.
    """
    if provenance.get("command"):
        return _starter_band(provenance, inline)

    for key in ("repo", "commit", "date"):
        if not provenance.get(key):
            raise SystemExit(f"report_page: the provenance has no {key}")

    repo = provenance["repo"]
    commit = provenance["commit"]
    where = _link(f"https://github.com/{repo}", repo, inline)
    if provenance.get("tag"):
        tag_url = provenance.get("tag_url") or f"https://github.com/{repo}/releases/tag/{provenance['tag']}"
        where += " " + _link(tag_url, provenance["tag"], inline)
    where += " (" + _link(
        provenance.get("commit_url") or f"https://github.com/{repo}/tree/{commit}",
        f"<code>{html.escape(commit[:7])}</code>",
        inline,
    ) + ")"

    return (
        f"{_open(inline)}This report was produced by "
        f'{_link("https://lockrot.dev/watch/", "lockrot.dev", inline)} on {html.escape(provenance["date"])}, '
        f"reading {where}. It is lockrot's output, published by this site; the project did not "
        "write it.</div>"
    )


def _starter_band(provenance: dict, inline: bool) -> str:
    """The band for a report on a project that did not exist before the run created it."""
    for key in ("package", "date", "command"):
        if not provenance.get(key):
            raise SystemExit(f"report_page: the starter provenance has no {key}")

    package = _link(
        provenance.get("packagist_url") or f"https://packagist.org/packages/{provenance['package']}",
        provenance["package"],
        inline,
    )
    return (
        f"{_open(inline)}This report was produced by "
        f'{_link("https://lockrot.dev/watch/", "lockrot.dev", inline)} on {html.escape(provenance["date"])} '
        f"from a project created that day out of {package}, with "
        f"<code>{html.escape(provenance['command'])}</code> — nothing was installed, and no script "
        "or plugin from any package was run. It is lockrot's output, published by this site.</div>"
    )


def _open(inline: bool) -> str:
    return f'<div style="{BAND_STYLE}">' if inline else '<div class="lockrot-provenance">'


def _link(url: str, text: str, inline: bool) -> str:
    style = ' style="color:var(--accent)"' if inline else ""
    return (
        f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer"'
        f'{style}>{text if text.startswith("<code>") else html.escape(text)}</a>'
    )


def payload(data: dict) -> str:
    """The document, encoded to sit inside `<script type="application/json">`."""
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    for plain, escaped in PAYLOAD_ESCAPES:
        text = text.replace(plain, escaped)
    return text


def _only(pattern: re.Pattern, page: str, what: str) -> str:
    found = pattern.findall(page)
    if len(found) != 1:
        raise SystemExit(
            f"report_page: the page carries {len(found)} of {what}, expected exactly one; "
            "lockrot's report.html changed shape"
        )
    return found[0]


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        raise SystemExit("usage: report_page.py <report.html> <capsule.json>")
    capsule = extract(Path(argv[1]).read_text(encoding="utf-8"))
    Path(argv[2]).write_text(
        json.dumps(capsule, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
