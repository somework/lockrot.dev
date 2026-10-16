"""MkDocs build hooks (mkdocs.yml `hooks:`), plain Python, no plugin package.

- The landing page's "Questions" section is lifted from the rendered HTML into page.meta["faq"],
  which overrides/partials/jsonld.html renders as schema.org FAQPage. Reading the rendered page,
  rather than a second copy of the questions in front matter, keeps the structured data equal to
  what the page shows: a question edited or removed in content/index.md changes the FAQ the same
  build. A home page without the section is a warning, which --strict turns into a failure.
- A post's `og_image` must name a file in the build; a card that 404s on every share is a warning
  for the same reason (lychee checks href/src, not <meta content>).
- `<lastmod>` in sitemap.xml is the date the page last changed, not the date of the build. MkDocs
  stamps every page with the build date (`Page.update_date`), which makes the whole sitemap look
  rewritten every morning: the IndexNow step in deploy.yml then announces all of it, and a crawler
  reading `lastmod` learns nothing. Here a page's date is the newest commit that touched the file it
  is built from: in content/ for the pages this repository owns, in the lockrot checkout for the
  reference pages.
- A few pages exist only in some builds: the pages lockrot 0.14.0 adds, and the report schema
  numbers' pages, which scripts/schema_pages.py writes when their source holds them. The nav and
  content/llms.txt name them all, and a build without one drops its nav row and its llms.txt row
  instead of failing --strict on a page that is not there. Any other missing page still fails.
- /schema/ links each report schema number's page and file, once more than one number is published.
"""
import html
import logging
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger("mkdocs.hooks.lockrot")

ROOT = Path(__file__).resolve().parent.parent

# What on_config reads once and on_page_content spends: see last_modified().
_LASTMOD: dict[str, object] = {"own_dates": {}, "lockrot_dates": {}, "blog_date": ""}

# The pages a build may lack (see the module docstring), by their path below docs_dir.
OPTIONAL_PAGES = ("verdicts/model-1.md", "changes/0.14.md", "schema/report-1.md", "schema/report-2.md")

# A page built from a file of another name is dated by that file: one of this repository's, or one in
# the lockrot checkout. changelog.md includes lockrot's CHANGELOG.md; scripts/schema_pages.py builds
# the schema number pages.
OWN_SOURCES = {"schema/report-1.md": "frozen/v0.13.0/docs/schema.md"}
LOCKROT_SOURCES = {"changelog.md": "CHANGELOG.md", "schema/report-2.md": "docs/schema.md"}

_SCHEMA_FILE = re.compile(r"schema/report-(\d+)\.json")

_SECTION = re.compile(r'<h2\b[^>]*\bid="questions"[^>]*>.*?</h2>(.*?)(?=<h2\b|\Z)', re.S)
_ITEM = re.compile(r"<h3\b[^>]*>(.*?)</h3>(.*?)(?=<h3\b|\Z)", re.S)
_TAG = re.compile(r"<[^>]+>")
_HEADERLINK = re.compile(r'<a\b[^>]*\bclass="headerlink"[^>]*>.*?</a>', re.S)


def _text(fragment: str) -> str:
    """Plain text of an HTML fragment: permalink anchor gone, tags gone, whitespace collapsed."""
    fragment = _HEADERLINK.sub("", fragment)
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment))).strip()


def faq_from_html(content: str) -> list[dict[str, str]]:
    """The (question, answer) pairs under <h2 id="questions">; [] when there is no such section."""
    section = _SECTION.search(content)
    if not section:
        return []
    return [
        {"question": _text(q), "answer": _text(a)}
        for q, a in _ITEM.findall(section.group(1))
        if _text(q) and _text(a)
    ]


def dates_from_git_log(output: str, exists: Callable[[str], bool]) -> dict[str, str]:
    """{path: the date of the newest commit that touched it} from `git log --name-only`.

    The log is newest first and every commit is introduced by a NUL-prefixed date line, so the
    first time a path appears is the last time it changed. It also lists what commits deleted, and
    a page deleted from content/ can still be published from the lockrot checkout — changelog.md is
    one — so `exists` keeps out the paths that are no longer there.
    """
    dates: dict[str, str] = {}
    date = ""
    for line in output.splitlines():
        if line.startswith("\0"):
            date = line[1:]
        elif line and date and line not in dates and exists(line):
            dates[line] = date
    return dates


def git_dates(repo: Path, pathspec: str) -> dict[str, str]:
    """The commit dates of everything under `pathspec` in `repo`, in UTC; {} when git cannot say.

    `--name-only` reads trees, never blobs, so this answers as fast in .lockrot/ (a blobless clone,
    see scripts/fetch-lockrot.sh) as it does here, and without a network round trip.
    """
    try:
        log_output = subprocess.run(
            ["git", "-C", str(repo), "log", "--format=%x00%cd", "--date=iso-strict-local",
             "--name-only", "--no-renames", "--", pathspec],
            capture_output=True, text=True, timeout=60, check=True,
            env={**os.environ, "TZ": "UTC"},
        ).stdout
    except (OSError, subprocess.SubprocessError) as error:
        log.warning("mkdocs_hooks: no git dates in %s for %s (%s); those pages keep the build date", repo, pathspec, error)
        return {}
    return dates_from_git_log(log_output, lambda path: (repo / path).is_file())


def last_modified(src_uri: str, own_dates: dict[str, str], lockrot_dates: dict[str, str], blog_date: str) -> str:
    """The date a page last changed, '' when no source can answer for it.

    Three kinds of page, in the order they are ruled out: one this repository owns (a commit under
    content/ — index.md is in both places and content/ wins, as it does in the build), one copied
    from the lockrot checkout (a commit under its docs/, so a release that did not touch the page
    does not move its date), and one the blog plugin generates — the blog index, the archive and the
    category lists, which change when a post does.

    A page built from a file of another name takes that file's date: OWN_SOURCES for one of this
    repository's (the frozen report-1 schema page), LOCKROT_SOURCES for one of the lockrot
    checkout's. changelog.md includes lockrot's CHANGELOG.md, and the release that writes a changelog
    entry usually leaves docs/changelog.md alone.
    """
    own = own_dates.get(f"content/{src_uri}") or own_dates.get(OWN_SOURCES.get(src_uri, ""))
    if own:
        return own
    reference = [lockrot_dates.get(f"docs/{src_uri}", "")]
    if src_uri in LOCKROT_SOURCES:
        reference.append(lockrot_dates.get(LOCKROT_SOURCES[src_uri], ""))
    if max(reference):
        return max(reference)
    if src_uri.startswith("blog/"):
        return blog_date
    return ""


def prune_nav(nav: list, exists: Callable[[str], bool]) -> list:
    """The nav without the rows of the optional pages `exists` says the build does not hold."""
    out = []
    for item in nav:
        if isinstance(item, dict) and len(item) == 1:
            (title, value), = item.items()
            if isinstance(value, list):
                out.append({title: prune_nav(value, exists)})
                continue
            item_path = value
        else:
            item_path = item
        if item_path in OPTIONAL_PAGES and not exists(item_path):
            continue
        out.append(item)
    return out


def llms_without(text: str, absent: list[str]) -> str:
    """llms.txt without the rows whose link is a page the build does not hold. A row that only
    mentions such a URL in its text keeps its place."""
    links = [f"](https://lockrot.dev/{page.removesuffix('.md')}/)" for page in absent]
    return "".join(line for line in text.splitlines(keepends=True) if not any(link in line for link in links))


def schema_note(paths: set[str]) -> str:
    """The note at the top of /schema/: each published report schema number with its page, when it
    has one, and its file. Nothing while one number is published, which leaves that page as lockrot
    wrote it."""
    numbers = sorted(int(m[1]) for path in paths if (m := _SCHEMA_FILE.fullmatch(path)))
    if len(numbers) < 2:
        return ""
    rows = []
    for number in numbers:
        links = [f"[field tables](schema/report-{number}.md)"] if f"schema/report-{number}.md" in paths else []
        links.append(f"[`report-{number}.json`](schema/report-{number}.json)")
        rows.append(f"    - report-{number}: " + ", ".join(links))
    return '!!! note "One page per report schema number"\n\n' + "\n".join(rows) + "\n\n"


def _absent(config) -> list[str]:
    return [page for page in OPTIONAL_PAGES if not (Path(config["docs_dir"]) / page).is_file()]


def on_config(config):
    # Three git processes per build (and per rebuild under `serve`), not one per page.
    own_dates = {**git_dates(ROOT, "content"), **git_dates(ROOT, "frozen")}
    posts = [date for path, date in own_dates.items() if path.startswith("content/blog/posts/")]
    _LASTMOD.update(
        own_dates=own_dates,
        lockrot_dates=git_dates(ROOT / ".lockrot", "."),
        blog_date=max(posts, default=""),
    )
    absent = _absent(config)
    if config.get("nav") and absent:
        # INFO, not a warning: a build from a tag without these pages is a normal build.
        log.info("mkdocs_hooks: this build holds none of %s; their nav and llms.txt rows are dropped", ", ".join(absent))
        config["nav"] = prune_nav(config["nav"], lambda page: page not in absent)
    return config


def on_page_markdown(markdown: str, page, config, files) -> str:
    if page.file.src_uri != "schema.md":
        return markdown
    note = schema_note({file.src_uri for file in files})
    if not note:
        return markdown
    # Below the page's title, above everything lockrot wrote.
    lines = markdown.splitlines(keepends=True)
    title = next((i for i, line in enumerate(lines) if line.startswith("# ")), -1)
    return "".join(lines[: title + 1]) + "\n" + note + "".join(lines[title + 1 :])


def on_post_build(config):
    llms = Path(config["site_dir"]) / "llms.txt"
    absent = _absent(config)
    if absent and llms.is_file():
        llms.write_text(llms_without(llms.read_text(encoding="utf-8"), absent), encoding="utf-8")


def on_page_content(content: str, page, config, files) -> str:
    lastmod = last_modified(page.file.src_uri, **_LASTMOD)
    if lastmod:
        page.update_date = lastmod
    if page.is_homepage:
        faq = faq_from_html(content)
        if faq:
            page.meta["faq"] = faq
        else:
            log.warning("mkdocs_hooks: the home page has no 'Questions' section; FAQPage markup dropped")
    og_image = page.meta.get("og_image")
    if og_image and files.get_file_from_path(og_image) is None:
        log.warning("mkdocs_hooks: %s names og_image %r, which is not in the build", page.file.src_uri, og_image)
    return content
