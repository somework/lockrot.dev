"""MkDocs hook: lift the landing page's "Questions" section into page.meta["faq"].

overrides/partials/jsonld.html renders it as schema.org FAQPage. Reading the rendered HTML, rather
than a second copy of the questions in front matter, keeps the structured data equal to what the
page shows: a question edited or removed in content/index.md changes the FAQ the same build.
"""
import html
import re

_SECTION = re.compile(r'<h2 id="questions">.*?</h2>(.*?)(?=<h2 |\Z)', re.S)
_ITEM = re.compile(r'<h3 id="[^"]*">(.*?)</h3>(.*?)(?=<h3 |\Z)', re.S)
_TAG = re.compile(r"<[^>]+>")
_HEADERLINK = re.compile(r'<a class="headerlink".*?</a>', re.S)


def _text(fragment: str) -> str:
    fragment = _HEADERLINK.sub("", fragment)
    return re.sub(r"\s+", " ", html.unescape(_TAG.sub("", fragment))).strip()


def on_page_content(content: str, page, config, files) -> str:
    if not page.is_homepage:
        return content
    section = _SECTION.search(content)
    if not section:
        return content
    faq = [
        {"question": _text(q), "answer": _text(a)}
        for q, a in _ITEM.findall(section.group(1))
        if _text(q) and _text(a)
    ]
    if faq:
        page.meta["faq"] = faq
    return content
