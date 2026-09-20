"""python3 -m unittest scripts/test_mkdocs_hooks.py — pins the rendered-HTML contract the FAQ
hook depends on (toc permalinks, code tags, entities), which a Material or Python-Markdown upgrade
can change without any other build error, and the sitemap dates, where a wrong answer is invisible
in the built site and only shows up as pages re-announced to the search engines."""
import unittest

from mkdocs_hooks import dates_from_git_log, faq_from_html, last_modified

PAGE = """
<h2 id="install">Install<a class="headerlink" href="#install" title="Permanent link">&para;</a></h2>
<p>Not a question.</p>
<h2 id="questions">Questions<a class="headerlink" href="#questions" title="Permanent link">&para;</a></h2>
<h3 id="does-it-change">Does it change <code>composer.lock</code>?<a class="headerlink" href="#does-it-change" title="Permanent link">&para;</a></h3>
<p>No. It reads both and writes to
neither &amp; never will.</p>
<h3 class="x" id="token">Do I need a token?<a href="#token" class="headerlink">&para;</a></h3>
<p>No, but it sees more with one.</p>
<ul><li>60 requests an hour</li></ul>
<h2 id="read-on">Read on<a class="headerlink" href="#read-on">&para;</a></h2>
<h3 id="not-a-question">Outside the section</h3><p>Ignored.</p>
"""


class FaqFromHtml(unittest.TestCase):
    def test_extracts_each_question_and_its_plain_text_answer(self):
        faq = faq_from_html(PAGE)
        self.assertEqual(
            faq,
            [
                {"question": "Does it change composer.lock?", "answer": "No. It reads both and writes to neither & never will."},
                {"question": "Do I need a token?", "answer": "No, but it sees more with one. 60 requests an hour"},
            ],
        )

    def test_headerlink_and_tags_never_leak(self):
        for item in faq_from_html(PAGE):
            for value in item.values():
                self.assertNotIn("¶", value)
                self.assertNotIn("<", value)

    def test_page_without_section_gives_nothing(self):
        self.assertEqual(faq_from_html("<h2 id=\"faq\">FAQ</h2><h3 id=\"q\">Q?</h3><p>A.</p>"), [])


GIT_LOG = """\
\x002026-09-20T05:17:00Z

content/blog/posts/2026-09-19-composer-audit-abandoned-misses.md
content/index.md
\x002026-09-18T11:02:00Z

content/changelog.md
content/index.md
content/llms.txt
"""

DATES = {
    "content/index.md": "2026-09-20T05:17:00Z",
    "content/blog/posts/2026-09-19-composer-audit-abandoned-misses.md": "2026-09-20T05:17:00Z",
    "content/llms.txt": "2026-09-18T11:02:00Z",
}


# Everything the log names except content/changelog.md, which that commit deleted.
def on_disk(path: str) -> bool:
    return path != "content/changelog.md"


class DatesFromGitLog(unittest.TestCase):
    def test_a_path_keeps_the_date_of_the_newest_commit_that_touched_it(self):
        self.assertEqual(dates_from_git_log(GIT_LOG, on_disk), DATES)

    def test_a_deleted_file_dates_nothing(self):
        # It is still in the log, and the page of that name is now published from .lockrot/docs.
        self.assertNotIn("content/changelog.md", dates_from_git_log(GIT_LOG, on_disk))

    def test_nothing_to_read_is_no_dates_rather_than_an_error(self):
        self.assertEqual(dates_from_git_log("", on_disk), {})


LOCKROT = {
    "docs/index.md": "2026-09-11T09:00:00Z",
    "docs/verdicts.md": "2026-09-11T09:00:00Z",
    "docs/ci.md": "2026-08-30T14:20:00Z",
    "docs/changelog.md": "2026-07-01T07:00:00Z",
    "CHANGELOG.md": "2026-09-11T09:00:00Z",
}


class LastModified(unittest.TestCase):
    def test_a_page_this_repository_owns_gets_its_commit_date(self):
        # index.md is in both places; the one in content/ is the one the build publishes.
        self.assertEqual(last_modified("index.md", DATES, LOCKROT, "x"), "2026-09-20T05:17:00Z")

    def test_a_reference_page_gets_the_date_of_its_own_file_in_lockrot(self):
        # Not the release date: v0.8.0 left ci.md alone, so the page did not change with it.
        self.assertEqual(last_modified("ci.md", DATES, LOCKROT, "x"), "2026-08-30T14:20:00Z")

    def test_the_changelog_page_follows_the_changelog_it_includes(self):
        # docs/changelog.md is a two-line include; the entries are in CHANGELOG.md next to it.
        self.assertEqual(last_modified("changelog.md", DATES, LOCKROT, "x"), "2026-09-11T09:00:00Z")

    def test_a_page_the_blog_plugin_generates_gets_the_newest_post_date(self):
        newest = "2026-09-20T05:17:00Z"
        self.assertEqual(last_modified("blog/archive/2026.md", DATES, LOCKROT, newest), newest)

    def test_a_page_nothing_can_date_keeps_the_build_date(self):
        self.assertEqual(last_modified("404.md", {}, {}, ""), "")


if __name__ == "__main__":
    unittest.main()
