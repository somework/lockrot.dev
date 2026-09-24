"""Unit tests for viewer/_headers.

Cloudflare sends the headers of every rule that matches a path, so which rule carries a header is
as much a part of the policy as the header itself. These are the rules a quiet edit would break.
"""

import unittest
from pathlib import Path

HEADERS = (Path(__file__).resolve().parent.parent / "viewer" / "_headers").read_text(encoding="utf-8")


def rules() -> dict[str, list[str]]:
    """Path pattern → its header lines, comments dropped."""
    out: dict[str, list[str]] = {}
    current = None
    for line in HEADERS.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            current = line.strip()
            out[current] = []
        elif current is not None:
            out[current].append(line.strip())
    return out


def matching(path: str) -> list[str]:
    """Every rule pattern Cloudflare applies to a request path: exact, or a splat prefix."""
    out = []
    for pattern in rules():
        if pattern.endswith("*"):
            if path.startswith(pattern[:-1]):
                out.append(pattern)
        elif pattern == path:
            out.append(pattern)
    return out


def header(pattern: str, name: str) -> list[str]:
    return [h.split(":", 1)[1].strip() for h in rules()[pattern] if h.lower().startswith(name.lower() + ":")]


# Paths that stand for each kind of response the host serves.
PAGES_WITH_A_STRANGERS_DOCUMENT = ["/frame/"]
EVERYTHING_ELSE = ["/", "/app.js", "/frame/lockrot-report.js", "/frame/lib.js", "/reports/run/project"]


class ViewerHeadersTest(unittest.TestCase):
    def test_no_path_gets_cache_control_from_two_rules(self):
        # Cloudflare sends every matching rule's headers, so two rules would mean two headers.
        for path in PAGES_WITH_A_STRANGERS_DOCUMENT + EVERYTHING_ELSE:
            with self.subTest(path=path):
                sources = [p for p in matching(path) if header(p, "Cache-Control")]
                self.assertLessEqual(len(sources), 1, sources)

    def test_the_pages_holding_a_strangers_document_keep_the_beacon_out(self):
        # no-transform stops Cloudflare Web Analytics injecting its script beside that document.
        for path in PAGES_WITH_A_STRANGERS_DOCUMENT:
            with self.subTest(path=path):
                values = [v for p in matching(path) for v in header(p, "Cache-Control")]
                self.assertEqual(1, len(values))
                self.assertIn("no-transform", values[0])

    def test_everything_else_stays_compressible(self):
        # no-transform also stops compression: a published report went from ~30 KB to 137 KB.
        for path in EVERYTHING_ELSE:
            with self.subTest(path=path):
                values = [v for p in matching(path) for v in header(p, "Cache-Control")]
                self.assertFalse(any("no-transform" in v for v in values), values)

    def test_published_reports_let_the_beacon_in_and_nothing_else(self):
        policy = header("/reports/*", "Content-Security-Policy")[0]
        directives = dict(d.strip().split(" ", 1) for d in policy.split(";") if d.strip())

        self.assertIn("https://static.cloudflareinsights.com", directives["script-src"])
        self.assertEqual("https://cloudflareinsights.com", directives["connect-src"])
        self.assertEqual("'none'", directives["img-src"])

    def test_the_viewer_page_lets_the_beacon_in(self):
        policy = header("/", "Content-Security-Policy")[0]
        directives = dict(d.strip().split(" ", 1) for d in policy.split(";") if d.strip())

        self.assertIn("https://static.cloudflareinsights.com", directives["script-src"])
        # Where the beacon reports; the page's own feature (#url= fetches) already needs https:.
        self.assertEqual("https:", directives["connect-src"])

    def test_the_frame_still_reaches_nothing(self):
        policy = header("/frame/*", "Content-Security-Policy")[0]

        self.assertIn("connect-src 'none'", policy)
        self.assertNotIn("cloudflareinsights", policy)


if __name__ == "__main__":
    unittest.main()
