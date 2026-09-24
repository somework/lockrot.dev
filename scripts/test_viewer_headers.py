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


class ViewerHeadersTest(unittest.TestCase):
    def test_every_response_forbids_the_proxy_to_rewrite_it(self):
        # Without no-transform, Cloudflare Web Analytics injects its beacon script into the viewer,
        # the frame and every published report.
        cache = [h for h in rules()["/*"] if h.lower().startswith("cache-control:")]

        self.assertEqual(1, len(cache))
        self.assertIn("no-transform", cache[0])

    def test_no_narrower_rule_sends_a_second_cache_control(self):
        for path, headers in rules().items():
            if path == "/*":
                continue
            with self.subTest(path=path):
                self.assertFalse(any(h.lower().startswith("cache-control:") for h in headers))


if __name__ == "__main__":
    unittest.main()
