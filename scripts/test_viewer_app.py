"""Unit tests for viewer/app.js, the viewer page's own half.

app.js is where the viewer's threat-model rules live (CLAUDE.md, "The viewer"): a #url= is fetched
over https only, with no credentials, no referrer and no redirect, and what arrives from elsewhere
is capped while it is read. None of that shows in a page that renders fine, so each rule is
asserted on the source, where removing it fails the build instead of passing unnoticed.
"""

import re
import unittest
from pathlib import Path

SOURCE = (Path(__file__).resolve().parent.parent / "viewer" / "app.js").read_text(encoding="utf-8")


def fetch_options() -> str:
    """The options object of the one fetch() the page makes."""
    calls = re.findall(r"\bfetch\(\s*url\.href\s*,\s*\{([^}]*)\}\s*\)", SOURCE)
    if len(calls) != 1:
        raise AssertionError(f"expected one fetch(url.href, {{...}}) in app.js, found {len(calls)}")
    return calls[0]


class RemoteFetchTest(unittest.TestCase):
    def test_refuses_a_redirect_the_reader_did_not_approve(self):
        self.assertRegex(fetch_options(), r'\bredirect:\s*"error"')

    def test_sends_no_credentials_and_no_referrer(self):
        options = fetch_options()

        self.assertRegex(options, r'\bcredentials:\s*"omit"')
        self.assertRegex(options, r'\breferrerPolicy:\s*"no-referrer"')

    def test_fetches_https_only(self):
        self.assertRegex(SOURCE, r'url\.protocol\s*!==\s*"https:"')

    def test_makes_no_other_request(self):
        self.assertEqual(1, len(re.findall(r"\bfetch\(", SOURCE)))
        self.assertNotIn("XMLHttpRequest", SOURCE)


class CapTest(unittest.TestCase):
    def test_caps_the_response_body_while_reading_it(self):
        self.assertRegex(SOURCE, r"readCapped\(\s*response\.body\s*,\s*MAX_REMOTE\b")

    def test_caps_a_compressed_link_while_decompressing_it(self):
        self.assertRegex(SOURCE, r"readCapped\(\s*new Blob\(\[bytes\]\)\.stream\(\)\.pipeThrough\(new DecompressionStream")

    def test_measures_pasted_text_before_parsing_it(self):
        self.assertRegex(SOURCE, r"text\.length\s*>\s*MAX_TEXT")


class AddressAndClipboardTest(unittest.TestCase):
    def test_never_writes_a_document_into_the_address_bar(self):
        self.assertIsNone(re.search(r"location\.hash\s*=[^=]", SOURCE))
        self.assertNotIn("pushState", SOURCE)
        # The one rewrite drops the fragment: it closes a document, it never opens one.
        self.assertEqual(
            ['history.replaceState(null, "", location.pathname)'],
            re.findall(r"history\.replaceState\([^)]*\)", SOURCE),
        )

    def test_never_copies_to_the_clipboard_on_its_own(self):
        self.assertNotIn("navigator.clipboard", SOURCE)
        self.assertNotIn("execCommand", SOURCE)


if __name__ == "__main__":
    unittest.main()
