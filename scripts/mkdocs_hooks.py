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

    changelog.md is the page that is not its own file: it includes lockrot's CHANGELOG.md, and the
    release that writes a changelog entry usually leaves docs/changelog.md alone.
    """
    own = own_dates.get(f"content/{src_uri}")
    if own:
        return own
    reference = [lockrot_dates.get(f"docs/{src_uri}", "")]
    if src_uri == "changelog.md":
        reference.append(lockrot_dates.get("CHANGELOG.md", ""))
    if max(reference):
        return max(reference)
    if src_uri.startswith("blog/"):
        return blog_date
    return ""


def on_config(config):
    # Twice per build (and per rebuild under `serve`), not once per page: two git processes.
    own_dates = git_dates(ROOT, "content")
    posts = [date for path, date in own_dates.items() if path.startswith("content/blog/posts/")]
    _LASTMOD.update(
        own_dates=own_dates,
        lockrot_dates=git_dates(ROOT / ".lockrot", "."),
        blog_date=max(posts, default=""),
    )
    return config


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
