"""MkDocs build hooks (mkdocs.yml `hooks:`), plain Python, no plugin package.

- The landing page's "Questions" section is lifted from the rendered HTML into page.meta["faq"],
  which overrides/partials/jsonld.html renders as schema.org FAQPage. Reading the rendered page,
  rather than a second copy of the questions in front matter, keeps the structured data equal to
  what the page shows: a question edited or removed in content/index.md changes the FAQ the same
  build. A home page without the section is a warning, which --strict turns into a failure.
- A post's `og_image` must name a file in the build; a card that 404s on every share is a warning
  for the same reason (lychee checks href/src, not <meta content>).
"""
import html
import logging
import re

log = logging.getLogger("mkdocs.hooks.lockrot")

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


def on_page_content(content: str, page, config, files) -> str:
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
