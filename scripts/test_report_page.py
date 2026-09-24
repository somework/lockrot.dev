#!/usr/bin/env python3
"""Unit tests for scripts/report_page.py."""

from __future__ import annotations

import json
import unittest

import report_page as rp

TEMPLATE = (
    "<!doctype html>\n<title>{{TITLE}}</title>\n"
    '<meta name="description" content="{{DESCRIPTION}}">\n'
    "<style>{{CSS}}</style>\n"
    '<script id="lockrot-data" type="application/json">{{DATA}}</script>\n'
    "<script>\n{{JS}}\n</script>\n"
)


def page(title="t", description="d", payload='{"report":{"findings":[]}}'):
    return (
        TEMPLATE.replace(rp.TITLE, title)
        .replace(rp.DESCRIPTION, description)
        .replace(rp.CSS, "body{}")
        .replace(rp.DATA, payload)
        .replace(rp.JS, "void 0;")
    )


class ExtractTest(unittest.TestCase):
    def test_takes_the_three_parts_of_a_report_page(self):
        capsule = rp.extract(page(title="lockrot: 3 of 40 packages flagged"))

        self.assertEqual("lockrot: 3 of 40 packages flagged", capsule["title"])
        self.assertEqual("d", capsule["description"])
        self.assertEqual({"report": {"findings": []}}, capsule["data"])

    def test_keeps_the_sentences_escaped_as_the_page_carries_them(self):
        capsule = rp.extract(page(description="flagged 1 of 2 &amp; counting"))

        self.assertEqual("flagged 1 of 2 &amp; counting", capsule["description"])

    def test_reads_back_a_payload_escaped_for_the_script_element(self):
        name = "a/b</script><!--"
        escaped = rp.payload({"report": {"findings": [{"package": name}]}})
        self.assertNotIn("</script", escaped)
        self.assertNotIn("<!--", escaped)

        capsule = rp.extract(page(payload=escaped))

        self.assertEqual(name, capsule["data"]["report"]["findings"][0]["package"])

    def test_refuses_a_page_whose_payload_is_missing(self):
        broken = page().replace('<script id="lockrot-data" type="application/json">', "<script>")

        with self.assertRaises(SystemExit):
            rp.extract(broken)

    def test_refuses_a_payload_that_is_not_a_report(self):
        with self.assertRaises(SystemExit):
            rp.extract(page(payload='{"details":{}}'))


class RenderTest(unittest.TestCase):
    def test_puts_the_page_back_together(self):
        capsule = rp.extract(page())

        out = rp.render(capsule, TEMPLATE, "body{}", "void 0;")

        self.assertNotIn("{{", out)
        self.assertIn("<title>t</title>", out)
        self.assertIn("body{}", out)
        self.assertEqual(capsule["data"], json.loads(rp._PAYLOAD_TAG.findall(out)[0]))

    def test_asks_a_crawler_to_leave_the_page_alone_once(self):
        out = rp.render(rp.extract(page()), TEMPLATE, "", "")

        self.assertEqual(1, out.count(rp.ROBOTS))
        self.assertLess(out.index(rp.ROBOTS), out.index("<title>"))

    def test_refuses_a_template_that_lost_a_placeholder(self):
        with self.assertRaises(SystemExit):
            rp.render(rp.extract(page()), TEMPLATE.replace(rp.DATA, ""), "", "")

    def test_refuses_a_capsule_that_lost_a_part(self):
        capsule = rp.extract(page())
        del capsule["description"]

        with self.assertRaises(SystemExit):
            rp.render(capsule, TEMPLATE, "", "")


PROVENANCE = {
    "repo": "wallabag/wallabag",
    "tag": "2.6.15",
    "tag_url": "https://github.com/wallabag/wallabag/releases/tag/2.6.15",
    "commit": "6b9bd67bef2dbfcb71446960dc5616e3552d4532",
    "commit_url": "https://github.com/wallabag/wallabag/tree/6b9bd67bef2dbfcb71446960dc5616e3552d4532",
    "date": "2026-09-22",
}


class BandTest(unittest.TestCase):
    def test_says_what_the_report_was_read_from(self):
        band = rp.band(PROVENANCE)

        self.assertIn(">wallabag/wallabag</a>", band)
        self.assertIn(">2.6.15</a>", band)
        self.assertIn("<code>6b9bd67</code>", band)
        self.assertIn("2026-09-22", band)

    def test_names_only_the_commit_when_there_was_no_release(self):
        band = rp.band({k: v for k, v in PROVENANCE.items() if k not in ("tag", "tag_url")})

        self.assertNotIn("2.6.15", band)
        self.assertIn("<code>6b9bd67</code>", band)

    def test_escapes_what_upstream_wrote(self):
        band = rp.band({**PROVENANCE, "tag": '1.0"><script>alert(1)</script>'})

        self.assertNotIn("<script>alert", band)
        self.assertIn("&lt;script&gt;", band)

    def test_refuses_provenance_without_a_commit(self):
        with self.assertRaises(SystemExit):
            rp.band({k: v for k, v in PROVENANCE.items() if k != "commit"})

    def test_a_starter_names_its_command_instead_of_a_commit(self):
        band = rp.band(
            {
                "package": "laravel/laravel",
                "packagist_url": "https://packagist.org/packages/laravel/laravel",
                "command": "composer create-project laravel/laravel:v13.10.1 .",
                "date": "2026-09-22",
            }
        )

        self.assertIn("create-project laravel/laravel:v13.10.1", band)
        self.assertIn("packagist.org/packages/laravel/laravel", band)
        self.assertIn("no script", band)

    def test_refuses_a_starter_without_a_package(self):
        with self.assertRaises(SystemExit):
            rp.band({"command": "composer create-project x", "date": "2026-09-22"})

    def test_the_band_sits_above_the_report(self):
        out = rp.render(rp.extract(page()), TEMPLATE + "<body>\n", "", "", PROVENANCE)

        self.assertIn("<body>\n<div style=", out)
        self.assertEqual(1, out.count("This report was produced by"))

    def test_no_band_without_provenance(self):
        out = rp.render(rp.extract(page()), TEMPLATE + "<body>\n", "", "")

        self.assertNotIn("This report was produced by", out)


# The released renderer's template (somework/lockrot-report): script and stylesheet inline already,
# pinned by the page's own Content-Security-Policy, so only three placeholders are left.
RELEASED = (
    "<!doctype html>\n<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'\">\n"
    "<title>{{TITLE}}</title>\n"
    '<meta name="description" content="{{DESCRIPTION}}">\n'
    "<body>\n"
    '<script id="lockrot-data" type="application/json">{{DATA}}</script>\n'
    "<style>/* inline */</style>\n<script>/* inline */</script>\n"
)


class ReleasedRendererTest(unittest.TestCase):
    def test_fills_the_three_placeholders_and_needs_no_renderer_sources(self):
        out = rp.render(rp.extract(page(title="lockrot: 1 of 2")), RELEASED, None, None)

        self.assertIn("<title>lockrot: 1 of 2</title>", out)
        self.assertIn('{"report":{"findings":[]}}', out)
        self.assertNotIn("{{", out)

    def test_the_band_is_a_class_the_page_styles_not_an_inline_style(self):
        # The page's policy refuses style attributes; an inline-styled band would render unstyled
        # and log a violation on every published report.
        out = rp.render(rp.extract(page()), RELEASED, None, None, PROVENANCE)

        self.assertIn('<body>\n<div class="lockrot-provenance">', out)
        self.assertNotIn("style=", out)

    def test_braces_in_the_renderer_s_own_code_are_not_a_placeholder(self):
        # The released page carries its stylesheet inline, comments included, and one of them
        # quotes JSX: style={{flexGrow}}.
        template = RELEASED.replace("/* inline */</style>", "/* style={{flexGrow}} */</style>")
        out = rp.render(rp.extract(page()), template, None, None)

        self.assertIn("style={{flexGrow}}", out)

    def test_the_pages_own_policy_lets_the_analytics_beacon_in(self):
        out = rp.render(rp.extract(page()), RELEASED, None, None)
        policy = rp.POLICY_TAG.findall(out)[0]

        self.assertIn("default-src 'none'", policy)
        self.assertIn("script-src https://static.cloudflareinsights.com", policy)
        self.assertIn("connect-src https://cloudflareinsights.com", policy)

    def test_a_directive_keeps_what_it_had_and_loses_only_none(self):
        template = RELEASED.replace(
            "default-src 'none'", "default-src 'none'; script-src 'sha256-abc='; connect-src 'none'"
        )
        policy = rp.POLICY_TAG.findall(rp.render(rp.extract(page()), template, None, None))[0]

        self.assertIn("script-src 'sha256-abc=' https://static.cloudflareinsights.com", policy)
        self.assertIn("connect-src https://cloudflareinsights.com", policy)
        self.assertNotIn("connect-src 'none'", policy)

    def test_the_old_renderer_has_no_policy_of_its_own_to_touch(self):
        out = rp.render(rp.extract(page()), TEMPLATE, "", "")

        self.assertNotIn("Content-Security-Policy", out)

    def test_a_splicing_template_without_renderer_sources_is_refused(self):
        with self.assertRaises(SystemExit):
            rp.render(rp.extract(page()), TEMPLATE, None, None)


if __name__ == "__main__":
    unittest.main()
