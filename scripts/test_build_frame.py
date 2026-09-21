"""Unit tests for scripts/build_frame.py.

The frame is lockrot's own report template with three things changed: no document in it, the
renderer loaded from files rather than inlined, and a robots directive the report deliberately
leaves to whoever publishes it. Each of those is a substitution into markup this repository does
not own, so each one is asserted here — a template that stops carrying a placeholder has to fail
in the build and not in someone's browser.
"""

import unittest

from build_frame import fill

# The shape of lockrot's resources/report/report.html, reduced to the parts this script touches.
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<title>{{TITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
<style>
{{CSS}}
</style>
</head>
<body>
<p>markup</p>
<script id="lockrot-data" type="application/json">{{DATA}}</script>
<script>
{{JS}}
</script>
</body>
</html>
"""


class FillTest(unittest.TestCase):
    def setUp(self):
        self.out = fill(TEMPLATE, ":root { --bg: #F2F5F4; }")

    def test_the_renderer_is_loaded_from_a_file(self):
        # Inlined, it would need script-src 'unsafe-inline', which is the one thing the frame's
        # policy is there to refuse.
        self.assertIn('<script src="frame.js"></script>', self.out)
        self.assertNotIn("{{JS}}", self.out)

    def test_the_data_element_is_present_and_empty(self):
        # report.js reads this element at load and renders once; frame.js fills it first.
        self.assertIn('<script id="lockrot-data" type="application/json"></script>', self.out)

    def test_the_stylesheet_is_inlined(self):
        self.assertIn("--bg: #F2F5F4;", self.out)

    def test_the_page_says_what_it_is_and_asks_not_to_be_indexed(self):
        self.assertIn("<title>lockrot report renderer</title>", self.out)
        self.assertIn('<meta name="robots" content="noindex">', self.out)
        self.assertLess(self.out.index("robots"), self.out.index("<title>"))

    def test_nothing_is_left_unfilled(self):
        self.assertNotIn("{{", self.out)

    def test_a_template_without_the_inline_script_is_refused(self):
        # The substitution is positional, so a renderer that stopped being inlined — or started
        # being inlined twice — must stop the build rather than produce a frame that loads nothing.
        with self.assertRaises(SystemExit):
            fill(TEMPLATE.replace("<script>\n{{JS}}\n</script>", ""), "")
        with self.assertRaises(SystemExit):
            fill(TEMPLATE + "<script>\n{{JS}}\n</script>", "")

    def test_a_template_missing_a_placeholder_is_refused(self):
        for placeholder in ("{{TITLE}}", "{{DESCRIPTION}}", "{{CSS}}", "{{DATA}}"):
            with self.subTest(placeholder=placeholder):
                with self.assertRaises(SystemExit):
                    fill(TEMPLATE.replace(placeholder, ""), "")


if __name__ == "__main__":
    unittest.main()
