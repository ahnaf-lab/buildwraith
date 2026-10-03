import io
import os
import tempfile
import unittest

from buildwraith.daemon import feed
from buildwraith.replay import (
    ReplayStep,
    classify_log_line,
    replay_file,
    replay_lines,
)
from buildwraith.state import BuildEvent, EventType, initial_state, reduce


class ClassifyLogLineTests(unittest.TestCase):
    def test_recognizes_a_bare_commit_header(self):
        line = "commit " + "a" * 40
        self.assertEqual(classify_log_line(line), EventType.COMMIT)

    def test_recognizes_a_commit_header_with_ref_decoration(self):
        line = "commit " + "b" * 40 + " (HEAD -> master, origin/master)"
        self.assertEqual(classify_log_line(line), EventType.COMMIT)

    def test_rejects_a_commit_header_with_a_short_hash(self):
        self.assertIsNone(classify_log_line("commit abc123"))

    def test_still_classifies_test_result_lines(self):
        self.assertEqual(classify_log_line("test_a ... ok"), EventType.TEST_PASS)
        self.assertEqual(
            classify_log_line("tests/test_b.py::test_b FAILED"), EventType.TEST_FAIL
        )

    def test_unrecognized_line_is_not_classified(self):
        self.assertIsNone(classify_log_line("Author: someone <someone@example.com>"))


class ReplayLinesTests(unittest.TestCase):
    def test_empty_log_produces_no_steps(self):
        self.assertEqual(replay_lines([]), [])

    def test_unrecognized_lines_are_skipped(self):
        lines = ["collecting tests...", "Date:   Mon Jan 1 00:00:00 2026 +0000", ""]
        self.assertEqual(replay_lines(lines), [])

    def test_matches_folding_the_same_events_through_reduce_directly(self):
        lines = [
            "commit " + "c" * 40,
            "test_a ... ok",
            "test_b ... FAIL",
            "test_c PASSED",
        ]
        steps = replay_lines(lines)

        expected_state = initial_state()
        expected_state = reduce(expected_state, BuildEvent(EventType.COMMIT))
        expected_state = reduce(expected_state, BuildEvent(EventType.TEST_PASS))
        expected_state = reduce(expected_state, BuildEvent(EventType.TEST_FAIL))
        expected_state = reduce(expected_state, BuildEvent(EventType.TEST_PASS))

        self.assertEqual(len(steps), 4)
        self.assertEqual(steps[-1].state, expected_state)
        self.assertEqual(steps[0].event, BuildEvent(EventType.COMMIT))
        self.assertEqual(steps[-1].event, BuildEvent(EventType.TEST_PASS))

    def test_replaying_the_same_lines_twice_is_deterministic(self):
        lines = ["test_a ... FAIL", "test_a ... FAIL", "test_a ... ok"]
        self.assertEqual(replay_lines(lines), replay_lines(lines))

    def test_steps_are_a_strictly_growing_history_not_just_a_final_state(self):
        lines = ["test_a ... FAIL", "test_a ... FAIL"]
        steps = replay_lines(lines)

        self.assertEqual(len(steps), 2)
        self.assertNotEqual(steps[0].state, steps[1].state)
        self.assertLess(steps[1].state.health, steps[0].state.health)

    def test_result_entries_are_replay_steps(self):
        steps = replay_lines(["test_a ... ok"])
        self.assertIsInstance(steps[0], ReplayStep)


class ReplayFileTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.remove, self.path)

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_replays_a_log_file_from_disk(self):
        self._write("commit " + "d" * 40 + "\ntest_a ... ok\ntest_b ... FAIL\n")
        steps = replay_file(self.path)

        self.assertEqual(
            [step.event.type for step in steps],
            [EventType.COMMIT, EventType.TEST_PASS, EventType.TEST_FAIL],
        )

    def test_matches_replay_lines_on_the_same_content(self):
        content = "test_a ... ok\ntest_b ... FAIL\n"
        self._write(content)
        self.assertEqual(replay_file(self.path), replay_lines(content.splitlines()))


class FeedCommandTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.remove, self.path)

    def _write(self, text):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write(text)

    def test_feed_prints_one_rendered_frame_per_event(self):
        self._write("test_a ... ok\ntest_b ... FAIL\ntest_c ... ok\n")
        out = io.StringIO()

        feed(self.path, interval_seconds=0.0, out=out)

        output = out.getvalue()
        self.assertEqual(output.count("health="), 3)

    def test_feed_output_ends_with_the_final_reconstructed_state(self):
        self._write("test_a ... FAIL\ntest_b ... FAIL\n")
        out = io.StringIO()

        feed(self.path, interval_seconds=0.0, out=out)

        expected_state = replay_file(self.path)[-1].state
        last_stat_line = [line for line in out.getvalue().splitlines() if line.startswith("health=")][-1]
        self.assertEqual(
            last_stat_line,
            f"health={expected_state.health} mood={expected_state.mood} energy={expected_state.energy}",
        )

    def test_feed_on_an_empty_log_prints_nothing(self):
        self._write("")
        out = io.StringIO()

        feed(self.path, interval_seconds=0.0, out=out)

        self.assertEqual(out.getvalue(), "")


if __name__ == "__main__":
    unittest.main()
