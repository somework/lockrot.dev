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


def node(tag, date, oid=None, **flags):
    """A GitHub release as the GraphQL query returns it."""
    return {
        "name": tag, "isDraft": flags.get("draft", False), "isPrerelease": flags.get("pre", False),
        "publishedAt": f"{date}T00:00:00Z", "tagCommit": {"oid": oid or f"sha-{tag}", "committedDate": f"{date}T00:00:00Z"},
    }


def tag_node(tag, date, annotated=False):
    commit = {"oid": f"sha-{tag}", "committedDate": f"{date}T00:00:00Z"}
    return {"name": tag, "target": {"target": commit} if annotated else commit}


def connection(nodes, more=False):
    return {"repository": {"connection": {"nodes": nodes, "pageInfo": {"hasNextPage": more, "endCursor": "c"}}}}


def answering(releases, tags=()):
    """A graphql stand-in: the releases query answers `releases`, the tags query `tags`."""
    def answer(query, variables, token):
        return connection(list(releases) if query is wp.RELEASES else list(tags))
    return answer


PROJECT = {"name": "app", "repo": "acme/app", "lock": "composer.lock", "target_php": "8.4"}


class VersionsTest(unittest.TestCase):
    def test_reads_releases_and_leaves_out_drafts_and_flagged_prereleases(self):
        releases = [node("2.0.0", "2026-09-01", pre=True), node("1.9.0", "2026-08-01", draft=True), node("1.8.0", "2026-07-01")]
        with mock.patch.object(wp, "graphql", answering(releases)):
            found = wp.versions("acme/app", "t", wp.STABLE_TAG, "2023-10-01")

        self.assertEqual([("1.8.0", "sha-1.8.0", "2026-07-01")], [(v["tag"], v["commit"], v["date"]) for v in found])

    def test_a_project_without_releases_is_read_from_its_tags(self):
        tags = [tag_node("v2.0.0", "2026-09-01", annotated=True), tag_node("start", "2020-01-01")]
        with mock.patch.object(wp, "graphql", answering([], tags)):
            found = wp.versions("acme/app", "t", wp.STABLE_TAG, "2023-10-01")

        self.assertEqual([("v2.0.0", "sha-v2.0.0")], [(v["tag"], v["commit"]) for v in found])

    def test_needs_a_token(self):
        with self.assertRaises(SystemExit):
            wp.graphql("query", {}, None)


class LineTest(unittest.TestCase):
    def test_draws_a_branch_the_way_a_caret_constraint_does(self):
        self.assertEqual(
            ["11", "2", "0.3", "0.0.3", "5"],
            [wp.release_line(t) for t in ("11.4.8", "v2.4.8-p3", "0.3.9", "0.0.3", "RELEASE_5_2_3")],
        )

    def test_groups_versions_by_line_highest_first(self):
        found = [{"tag": t, "commit": t, "date": "2026-01-01"} for t in ("10.6.17", "11.4.8", "10.6.18")]

        grouped = wp.lines(found)

        self.assertEqual({"11": ["11.4.8"], "10": ["10.6.18", "10.6.17"]}, {k: [v["tag"] for v in vs] for k, vs in grouped.items()})

    def test_a_line_name_carries_no_dot(self):
        self.assertEqual(("drupal-v10", "lib-v0-3"), (wp.line_name("drupal", "10"), wp.line_name("lib", "0.3")))

    def test_counts_years_back_from_the_run(self):
        self.assertEqual(("2023-10-01", "2025-02-28"), (wp.years_before("2026-10-01", 3), wp.years_before("2028-02-29", 3)))


class ResolveTest(unittest.TestCase):
    def resolve(self, releases, with_lock, cutoff="2023-10-01"):
        def files(repo, sha, lock, token):
            return sha in {f"sha-{t}" for t in with_lock}
        with mock.patch.object(wp, "graphql", answering(releases)), mock.patch.object(wp, "has_files", files):
            return wp.resolve(PROJECT, "t", cutoff)

    def test_a_backport_published_last_does_not_become_the_row(self):
        # 7.4.5 is the newest release by date; the row is still the 8.x line.
        entries, _ = self.resolve(
            [node("7.4.5", "2026-09-20"), node("8.3.0", "2026-09-01"), node("8.2.0", "2026-06-01")],
            with_lock={"7.4.5", "8.3.0", "8.2.0"},
        )

        self.assertEqual(("release", "8.3.0", "8"), (entries[0]["kind"], entries[0]["tag"], entries[0]["line"]))

    def test_never_steps_down_to_an_older_line_for_the_row(self):
        with self.assertRaises(SystemExit) as raised:
            self.resolve([node("8.3.0", "2026-09-01"), node("7.4.5", "2026-09-20")], with_lock={"7.4.5"})

        self.assertIn("newest line 8.x", str(raised.exception))

    def test_takes_the_highest_release_of_the_line_that_carries_a_lock(self):
        entries, _ = self.resolve([node("8.3.0", "2026-09-01"), node("8.2.0", "2026-06-01")], with_lock={"8.2.0"})

        self.assertEqual("8.2.0", entries[0]["tag"])

    def test_reads_every_older_line_still_releasing_and_no_other(self):
        entries, skipped = self.resolve(
            [
                node("8.3.0", "2026-09-01"),
                node("7.4.5", "2026-09-20"),
                node("6.9.9", "2022-01-01"),   # last released before the window
            ],
            with_lock={"8.3.0", "7.4.5", "6.9.9"},
        )

        self.assertEqual(
            [("release", "app", "8.3.0"), ("line", "app-v7", "7.4.5")],
            [(e["kind"], e["name"], e["tag"]) for e in entries],
        )
        self.assertEqual("app", entries[1]["parent"])
        self.assertEqual([], skipped)

    def test_an_older_line_without_a_lock_is_listed_as_skipped(self):
        entries, skipped = self.resolve([node("8.3.0", "2026-09-01"), node("7.4.5", "2026-09-20")], with_lock={"8.3.0"})

        self.assertEqual(1, len(entries))
        self.assertEqual([{"project": "app", "line": "7", "tried": ["7.4.5 (no composer.lock)"]}], skipped)

    def test_a_project_with_no_stable_release_fails_the_run(self):
        with self.assertRaises(SystemExit):
            self.resolve([node("1.0.0-rc1", "2026-09-01")], with_lock=set())


def http_error(code):
    return wp.urllib.error.HTTPError("https://api.github.com/x", code, "x", {}, None)


class Response:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        import io
        return io.BytesIO(wp.json.dumps(self.body).encode())

    def __exit__(self, *exc):
        return False


def answers(*outcomes):
    """A urlopen stand-in that answers each call with the next outcome: an exception or a body."""
    queue = list(outcomes)

    def urlopen(request, timeout):
        outcome = queue.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return Response(outcome)
    return urlopen


class FetchTest(unittest.TestCase):
    def setUp(self):
        patcher = mock.patch.object(wp.time, "sleep")
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_a_server_error_is_tried_again(self):
        with mock.patch.object(wp.urllib.request, "urlopen", answers(http_error(502), {"ok": 1})):
            self.assertEqual({"ok": 1}, wp.get("/repos/acme/app/contents/composer.lock", "t"))

    def test_a_server_error_that_lasts_stops_the_run_rather_than_reading_as_no_file(self):
        with mock.patch.object(wp.urllib.request, "urlopen", answers(*[http_error(502)] * wp.RETRIES)):
            with self.assertRaises(SystemExit):
                wp.has_files("acme/app", "sha", "composer.lock", "t")

    def test_not_found_is_an_answer(self):
        with mock.patch.object(wp.urllib.request, "urlopen", answers(http_error(404))):
            self.assertIsNone(wp.get("/repos/acme/app/contents/composer.lock", "t"))

    def test_a_spent_allowance_names_the_token(self):
        with mock.patch.object(wp.urllib.request, "urlopen", answers(http_error(403))):
            with self.assertRaises(SystemExit) as raised:
                wp.get("/x", "t")
        self.assertIn("ROT_WATCH_TOKEN", str(raised.exception))

    def test_a_graphql_timeout_reported_as_an_error_is_tried_again(self):
        timeout = {"errors": [{"message": "Something went wrong while executing your query. This may be the result of a timeout"}]}
        with mock.patch.object(wp.urllib.request, "urlopen", answers(timeout, {"data": {"ok": 1}})):
            self.assertEqual({"ok": 1}, wp.graphql("q", {}, "t"))

    def test_a_missing_repository_is_not_retried(self):
        missing = {"data": {"repository": None}, "errors": [{"type": "NOT_FOUND", "message": "nope"}]}
        with mock.patch.object(wp.urllib.request, "urlopen", answers(missing)):
            self.assertEqual({"repository": None}, wp.graphql("q", {}, "t"))


class PagingTest(unittest.TestCase):
    def test_releases_with_no_stable_one_fall_back_to_the_tags(self):
        # phpBB publishing its first GitHub release, an alpha, beside years of tags.
        answer = answering([node("release-4.0.0-a1", "2026-09-01", pre=True)], [tag_node("release-3.3.19", "2026-09-24")])
        pattern = wp.re.compile(r"^release-\d+(\.\d+)*$")
        with mock.patch.object(wp, "graphql", answer):
            found = wp.versions("acme/app", "t", pattern, "2023-10-01")

        self.assertEqual(["release-3.3.19"], [v["tag"] for v in found])

    def test_a_project_deeper_than_the_page_limit_stops_the_run(self):
        page = connection([node(f"1.0.{i}", "2026-09-01") for i in range(3)], more=True)
        with mock.patch.object(wp, "graphql", lambda q, v, t: page), self.assertRaises(SystemExit) as raised:
            wp.versions("acme/app", "t", wp.STABLE_TAG, "2023-10-01")
        self.assertIn("PAGES", str(raised.exception))

    def test_an_undated_tag_does_not_end_the_reading_early(self):
        first = connection([tag_node("v2.0.0", "2026-09-01"), {"name": "v1.9.9", "target": {"target": {}}}], more=True)
        second = connection([tag_node("v1.0.0", "2025-01-01"), tag_node("v0.9.0", "2022-01-01")])
        pages = [first, second]
        with mock.patch.object(wp, "graphql", lambda q, v, t: connection([]) if q is wp.RELEASES else pages.pop(0)):
            found = wp.versions("acme/app", "t", wp.STABLE_TAG, "2023-10-01")

        self.assertIn("v1.0.0", [v["tag"] for v in found])


class StillReleasingTest(unittest.TestCase):
    def grouped(self, *versions):
        return wp.lines([{"tag": t, "commit": t, "date": d} for t, d in versions])

    def test_a_line_kept_beside_a_newer_one_is_read(self):
        # Drupal: 10.x keeps releasing long after 11.0.0.
        by_line = self.grouped(("11.0.0", "2024-08-01"), ("11.4.8", "2026-09-26"), ("10.6.18", "2026-09-26"))

        self.assertTrue(wp.still_releasing("10", by_line, "2023-10-01"))

    def test_a_line_that_ended_when_the_next_began_is_not(self):
        # BookStack: v25's last release three days before v26's first.
        by_line = self.grouped(("v26.03", "2026-03-15"), ("v26.09.1", "2026-09-29"), ("v25.12.9", "2026-03-12"))

        self.assertFalse(wp.still_releasing("25", by_line, "2023-10-01"))

    def test_a_line_quiet_since_before_the_window_is_not(self):
        by_line = self.grouped(("8.0.0", "2020-01-01"), ("8.3.0", "2026-09-01"), ("7.4.5", "2023-01-01"))

        self.assertFalse(wp.still_releasing("7", by_line, "2023-10-01"))


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
