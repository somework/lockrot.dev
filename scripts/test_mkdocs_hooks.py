"""python3 -m unittest scripts/test_mkdocs_hooks.py — pins the rendered-HTML contract the FAQ
hook depends on (toc permalinks, code tags, entities), which a Material or Python-Markdown upgrade
can change without any other build error, and the sitemap dates, where a wrong answer is invisible
in the built site and only shows up as pages re-announced to the search engines."""
import unittest

from mkdocs_hooks import dates_from_git_log, faq_from_html, last_modified, llms_without, prune_nav, schema_note

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

    def test_a_nested_reference_page_gets_the_date_of_its_own_file(self):
        lockrot = {**LOCKROT, "docs/verdicts/model-1.md": "2026-10-10T00:00:00Z"}
        self.assertEqual(last_modified("verdicts/model-1.md", DATES, lockrot, "x"), "2026-10-10T00:00:00Z")

    def test_the_report_2_page_follows_the_schema_page_it_includes(self):
        lockrot = {**LOCKROT, "docs/schema.md": "2026-10-10T00:00:00Z"}
        self.assertEqual(last_modified("schema/report-2.md", DATES, lockrot, "x"), "2026-10-10T00:00:00Z")

    def test_the_report_1_page_follows_its_frozen_copy(self):
        own = {**DATES, "frozen/v0.13.0/docs/schema.md": "2026-10-16T00:00:00Z"}
        self.assertEqual(last_modified("schema/report-1.md", own, LOCKROT, "x"), "2026-10-16T00:00:00Z")


NAV = [
    {"Home": "index.md"},
    {"What it reports": "verdicts.md"},
    {"Score model 1": "verdicts/model-1.md"},
    {"JSON schemas": "schema.md"},
    {"Report schema 1": "schema/report-1.md"},
    {"Report schema 2": "schema/report-2.md"},
    {"Upgrading to 0.14": "changes/0.14.md"},
    {"Blog": ["blog/index.md"]},
]


class OptionalPages(unittest.TestCase):
    def test_drops_an_optional_page_the_build_does_not_hold(self):
        built = {"index.md", "verdicts.md", "schema.md", "schema/report-1.md", "blog/index.md"}

        nav = prune_nav(NAV, built.__contains__)

        self.assertEqual(
            [{"Home": "index.md"}, {"What it reports": "verdicts.md"}, {"JSON schemas": "schema.md"},
             {"Report schema 1": "schema/report-1.md"}, {"Blog": ["blog/index.md"]}],
            nav,
        )

    def test_keeps_a_page_that_is_not_optional_even_when_missing_so_strict_still_fails(self):
        nav = prune_nav(NAV, lambda path: False)

        self.assertIn({"Home": "index.md"}, nav)
        self.assertIn({"Blog": ["blog/index.md"]}, nav)
        self.assertNotIn({"Score model 1": "verdicts/model-1.md"}, nav)

    def test_drops_the_llms_rows_of_the_pages_the_build_does_not_hold(self):
        text = (
            "- [Verdicts](https://lockrot.dev/verdicts/): the verdicts\n"
            "- [Score model 1](https://lockrot.dev/verdicts/model-1/): the model\n"
            "- [Upgrading to 0.14](https://lockrot.dev/changes/0.14/): the upgrade\n"
        )

        out = llms_without(text, ["verdicts/model-1.md", "changes/0.14.md"])

        self.assertEqual("- [Verdicts](https://lockrot.dev/verdicts/): the verdicts\n", out)


class SchemaNote(unittest.TestCase):
    def test_lists_each_number_with_its_page_and_its_file(self):
        note = schema_note({"schema/report-1.json", "schema/report-2.json", "schema/report-1.md", "schema/report-2.md"})

        self.assertIn("[field tables](schema/report-1.md)", note)
        self.assertIn("[`report-2.json`](schema/report-2.json)", note)

    def test_names_the_file_alone_for_a_number_without_a_page_yet(self):
        note = schema_note({"schema/report-1.json", "schema/report-2.json", "schema/report-1.md"})

        self.assertIn("- report-2: [`report-2.json`](schema/report-2.json)", note)
        self.assertNotIn("schema/report-2.md", note)

    def test_says_nothing_while_one_number_is_published(self):
        self.assertEqual("", schema_note({"schema/report-1.json", "schema/explain-1.json"}))


if __name__ == "__main__":
    unittest.main()
