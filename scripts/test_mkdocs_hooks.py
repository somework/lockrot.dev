"""python3 -m unittest scripts/test_mkdocs_hooks.py — pins the rendered-HTML contract the FAQ
hook depends on (toc permalinks, code tags, entities), which a Material or Python-Markdown upgrade
can change without any other build error."""
import unittest

from mkdocs_hooks import faq_from_html

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


if __name__ == "__main__":
    unittest.main()
