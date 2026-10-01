#!/usr/bin/env python3
"""Unit tests for scripts/watch_plan.py. No network: the GitHub API is a dictionary here."""

from __future__ import annotations

import unittest
from unittest import mock

import watch_plan as wp


def api(responses: dict):
    """A stand-in for watch_plan.get that answers from `responses`, keyed by path."""
    return lambda path, token: responses.get(path)


def releases(*tags, prerelease=()):
    return [{"tag_name": t, "draft": False, "prerelease": t in prerelease} for t in tags]


class VersionKeyTest(unittest.TestCase):
    def test_compares_numbers_not_strings(self):
        self.assertGreater(wp.version_key("v10.0.0"), wp.version_key("v9.9.9"))

    def test_a_patch_suffix_sits_between_its_release_and_the_next(self):
        self.assertGreater(wp.version_key("2.4.8-p3"), wp.version_key("2.4.8"))
        self.assertLess(wp.version_key("2.4.8-p3"), wp.version_key("2.4.9"))

    def test_reads_a_project_pattern_spelled_with_underscores(self):
        self.assertEqual(wp.version_key("RELEASE_5_2_3"), wp.version_key("5.2.3"))

    def test_a_missing_part_counts_as_zero(self):
        self.assertEqual(wp.version_key("v26.09"), wp.version_key("26.9.0"))
        self.assertGreater(wp.version_key("v26.09.1"), wp.version_key("v26.09"))


class CandidatesTest(unittest.TestCase):
    def test_a_backport_made_after_the_newest_release_does_not_come_first(self):
        # The API lists releases by creation date: 2.3.9 was published last.
        responses = {
            "/repos/acme/app/releases/latest": None,
            "/repos/acme/app/releases?per_page=30": releases("2.3.9", "2.4.12", "2.4.11"),
        }
        with mock.patch.object(wp, "get", api(responses)):
            found = wp.candidates("acme/app", None, wp.STABLE_TAG)

        self.assertEqual(["2.4.12", "2.4.11", "2.3.9"], found)

    def test_a_latest_release_that_is_a_beta_is_passed_over(self):
        responses = {
            "/repos/acme/app/releases/latest": {"tag_name": "v2.5.0-beta5"},
            "/repos/acme/app/releases?per_page=30": releases("v2.5.0-beta5", "v2.4.12"),
        }
        with mock.patch.object(wp, "get", api(responses)):
            found = wp.candidates("acme/app", None, wp.STABLE_TAG)

        self.assertEqual(["v2.4.12"], found)

    def test_tags_are_put_in_version_order_whatever_order_they_arrive_in(self):
        responses = {
            "/repos/acme/app/releases?per_page=30": [],
            "/repos/acme/app/tags?per_page=100": [
                {"name": n} for n in ("v9.9.9", "start", "v10.0.0-rc1", "v10.0.0", "v10.0.1")
            ],
        }
        with mock.patch.object(wp, "get", api(responses)):
            found = wp.candidates("acme/app", None, wp.STABLE_TAG)

        self.assertEqual(["v10.0.1", "v10.0.0", "v9.9.9"], found)

    def test_tries_no_more_than_the_cap(self):
        tags = [f"1.0.{i}" for i in range(20)]
        responses = {"/repos/acme/app/releases?per_page=30": releases(*tags)}
        with mock.patch.object(wp, "get", api(responses)):
            found = wp.candidates("acme/app", None, wp.STABLE_TAG)

        self.assertEqual(wp.CANDIDATES, len(found))
        self.assertEqual("1.0.19", found[0])


class ResolveTest(unittest.TestCase):
    def test_takes_the_highest_release_that_carries_both_files(self):
        responses = {
            "/repos/acme/app/releases?per_page=30": releases("3.0.0", "2.9.0"),
            "/repos/acme/app/git/ref/tags/3.0.0": {"object": {"type": "commit", "sha": "aaa"}},
            "/repos/acme/app/git/ref/tags/2.9.0": {"object": {"type": "commit", "sha": "bbb"}},
            # 3.0.0 stopped committing its lock file.
            "/repos/acme/app/contents/composer.json?ref=aaa": {},
            "/repos/acme/app/contents/composer.lock?ref=bbb": {},
            "/repos/acme/app/contents/composer.json?ref=bbb": {},
        }
        project = {"name": "app", "repo": "acme/app", "lock": "composer.lock", "target_php": "8.4"}
        with mock.patch.object(wp, "get", api(responses)):
            resolved = wp.resolve(project, None)

        self.assertEqual(("2.9.0", "bbb"), (resolved["tag"], resolved["commit"]))

    def test_a_project_with_no_usable_release_fails_the_run(self):
        responses = {"/repos/acme/app/releases?per_page=30": releases("1.0.0")}
        project = {"name": "app", "repo": "acme/app", "lock": "composer.lock", "target_php": "8.4"}
        with mock.patch.object(wp, "get", api(responses)), self.assertRaises(SystemExit):
            wp.resolve(project, None)


class StarterVersionTest(unittest.TestCase):
    def test_takes_the_highest_stable_version_whatever_order_packagist_lists(self):
        body = {"packages": {"acme/skeleton": [{"version": v} for v in ("v2.0.0-RC1", "v1.9.0", "v1.10.0")]}}
        with mock.patch.object(wp.urllib.request, "urlopen") as urlopen, mock.patch.object(
            wp.json, "load", return_value=body
        ):
            urlopen.return_value.__enter__.return_value = None
            self.assertEqual("v1.10.0", wp.newest_package_version("acme/skeleton"))


if __name__ == "__main__":
    unittest.main()
