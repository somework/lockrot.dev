"""Unit tests for viewer/frame.html, the frame page for a released renderer.

From lockrot 0.12.0 the frame is this site's own page rather than lockrot's report.html filled
differently: the released report.html pins its inline script by hash, which would refuse the files
the frame loads. What the page has to carry is what frame.js and the renderer rely on, and what the
frame's policy in viewer/_headers allows — so each is asserted here, where a mistake fails the build
instead of leaving the viewer blank.
"""

import re
import unittest
from pathlib import Path

PAGE = (Path(__file__).resolve().parent.parent / "viewer" / "frame.html").read_text(encoding="utf-8")


class FrameTemplateTest(unittest.TestCase):
    def test_has_the_empty_data_element_frame_js_fills(self):
        self.assertEqual(1, PAGE.count('<script id="lockrot-data" type="application/json"></script>'))

    def test_has_the_element_the_renderer_mounts_into(self):
        self.assertEqual(1, PAGE.count('<div id="lockrot-app"></div>'))

    def test_loads_the_stylesheet_and_names_the_renderer_as_same_origin_files(self):
        self.assertIn('<link rel="stylesheet" href="lockrot-report.css">', PAGE)
        self.assertIn('<script src="frame.js" data-renderer="lockrot-report.js"></script>', PAGE)

    def test_the_data_element_comes_before_frame_js(self):
        self.assertLess(PAGE.index('id="lockrot-data"'), PAGE.index('src="frame.js"'))

    def test_carries_no_inline_script_or_style(self):
        # The frame's policy is script-src 'self': an inline script would be refused, and this page
        # needs none.
        scripts = re.findall(r"<script([^>]*)>(.*?)</script>", PAGE, re.S)
        for attributes, body in scripts:
            self.assertTrue('src="' in attributes or 'type="application/json"' in attributes, attributes)
            self.assertEqual("", body.strip())
        self.assertNotIn("<style", PAGE)
        self.assertNotIn("style=", PAGE)

    def test_asks_not_to_be_indexed(self):
        self.assertIn('<meta name="robots" content="noindex">', PAGE)

    def test_loads_nothing_from_another_origin(self):
        self.assertIsNone(re.search(r'(src|href)="(https?:)?//', PAGE))


if __name__ == "__main__":
    unittest.main()
