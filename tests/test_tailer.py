import os
import shutil
import subprocess
import tempfile
import unittest

from buildwraith.state import BuildEvent, EventType
from buildwraith.tailer import FileTailer, GitCommitTailer, classify_test_line, poll_events


class ClassifyTestLineTests(unittest.TestCase):
    def test_unittest_style_ok_is_a_pass(self):
        line = "test_adds_numbers (tests.MathTest) ... ok"
        self.assertEqual(classify_test_line(line), EventType.TEST_PASS)

    def test_unittest_style_fail_is_a_failure(self):
        line = "test_subtracts_numbers (tests.MathTest) ... FAIL"
        self.assertEqual(classify_test_line(line), EventType.TEST_FAIL)

    def test_unittest_style_error_is_a_failure(self):
        line = "test_divides_numbers (tests.MathTest) ... ERROR"
        self.assertEqual(classify_test_line(line), EventType.TEST_FAIL)

    def test_pytest_style_passed_is_a_pass(self):
        line = "tests/test_math.py::test_adds_numbers PASSED"
        self.assertEqual(classify_test_line(line), EventType.TEST_PASS)

    def test_pytest_style_failed_is_a_failure(self):
        line = "tests/test_math.py::test_subtracts_numbers FAILED"
        self.assertEqual(classify_test_line(line), EventType.TEST_FAIL)

    def test_unrecognized_line_is_not_classified(self):
        self.assertIsNone(classify_test_line("collecting tests..."))

    def test_blank_line_is_not_classified(self):
        self.assertIsNone(classify_test_line("   "))


class FileTailerTests(unittest.TestCase):
    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        self.addCleanup(os.remove, self.path)

    def _write(self, text, mode="a"):
        with open(self.path, mode, encoding="utf-8") as handle:
            handle.write(text)

    def test_reads_lines_written_before_construction(self):
        self._write("one ok\ntwo FAIL\n")
        tailer = FileTailer(self.path)
        self.assertEqual(tailer.read_new_lines(), ["one ok", "two FAIL"])

    def test_second_read_only_returns_newly_appended_lines(self):
        self._write("one ok\n")
        tailer = FileTailer(self.path)
        tailer.read_new_lines()

        self._write("two FAIL\n")
        self.assertEqual(tailer.read_new_lines(), ["two FAIL"])

    def test_partial_trailing_line_is_held_back_until_completed(self):
        self._write("one ok\n")
        tailer = FileTailer(self.path)
        tailer.read_new_lines()

        self._write("partial line no newline yet")
        self.assertEqual(tailer.read_new_lines(), [])

        self._write(" ... ok\n")
        self.assertEqual(tailer.read_new_lines(), ["partial line no newline yet ... ok"])

    def test_truncated_file_is_read_from_the_start_again(self):
        self._write("one ok\ntwo ok\n")
        tailer = FileTailer(self.path)
        tailer.read_new_lines()

        self._write("hi FAIL\n", mode="w")
        self.assertEqual(tailer.read_new_lines(), ["hi FAIL"])

    def test_missing_file_returns_no_lines(self):
        tailer = FileTailer(os.path.join(tempfile.gettempdir(), "buildwraith-does-not-exist"))
        self.assertEqual(tailer.read_new_lines(), [])


class FakeGitLog:
    """A canned stand-in for `git log` keyed by (repo_path, rev_range)."""

    def __init__(self, history):
        self.history = list(history)
        self.calls = []

    def __call__(self, repo_path, rev_range=None):
        self.calls.append((repo_path, rev_range))
        if rev_range is None:
            return list(self.history)
        last_seen, _, _head = rev_range.partition("..")
        index = self.history.index(last_seen)
        return self.history[index + 1 :]


class GitCommitTailerTests(unittest.TestCase):
    def test_existing_history_is_not_reported_as_new(self):
        fake_log = FakeGitLog(["a", "b", "c"])
        tailer = GitCommitTailer("/repo", list_commit_hashes=fake_log)
        self.assertEqual(tailer.poll_new_commits(), [])

    def test_commits_landed_after_construction_are_reported_once(self):
        fake_log = FakeGitLog(["a", "b", "c"])
        tailer = GitCommitTailer("/repo", list_commit_hashes=fake_log)

        fake_log.history.extend(["d", "e"])
        self.assertEqual(tailer.poll_new_commits(), ["d", "e"])
        self.assertEqual(tailer.poll_new_commits(), [])

    def test_empty_repository_reports_its_first_commit_once_seen(self):
        fake_log = FakeGitLog([])
        tailer = GitCommitTailer("/repo", list_commit_hashes=fake_log)
        self.assertEqual(tailer.poll_new_commits(), [])

        fake_log.history.append("first")
        self.assertEqual(tailer.poll_new_commits(), ["first"])
        self.assertEqual(tailer.poll_new_commits(), [])


def _run(args, cwd):
    env = dict(os.environ)
    env.update(
        {
            "GIT_AUTHOR_NAME": "buildwraith-test",
            "GIT_AUTHOR_EMAIL": "buildwraith-test@example.com",
            "GIT_COMMITTER_NAME": "buildwraith-test",
            "GIT_COMMITTER_EMAIL": "buildwraith-test@example.com",
        }
    )
    subprocess.run(args, cwd=cwd, env=env, check=True, capture_output=True, text=True)


@unittest.skipIf(shutil.which("git") is None, "git not installed")
class GitCommitTailerIntegrationTests(unittest.TestCase):
    """Exercises the real `git log` subprocess call against a throwaway repo."""

    def setUp(self):
        self.repo = tempfile.mkdtemp()
        self.addCleanup(self._cleanup)
        _run(["git", "init"], cwd=self.repo)
        self._commit("first.txt", "first commit")

    def _cleanup(self):
        shutil.rmtree(self.repo)

    def _commit(self, filename, message):
        with open(os.path.join(self.repo, filename), "w", encoding="utf-8") as handle:
            handle.write(message)
        _run(["git", "add", filename], cwd=self.repo)
        _run(["git", "commit", "-m", message], cwd=self.repo)

    def test_commits_made_after_construction_are_detected(self):
        tailer = GitCommitTailer(self.repo)
        self.assertEqual(tailer.poll_new_commits(), [])

        self._commit("second.txt", "second commit")
        new_commits = tailer.poll_new_commits()
        self.assertEqual(len(new_commits), 1)
        self.assertEqual(len(new_commits[0]), 40)

        self.assertEqual(tailer.poll_new_commits(), [])


class PollEventsTests(unittest.TestCase):
    class _StubTestTailer:
        def __init__(self, lines):
            self._lines = lines

        def read_new_lines(self):
            return self._lines

    class _StubCommitTailer:
        def __init__(self, commits):
            self._commits = commits

        def poll_new_commits(self):
            return self._commits

    def test_nothing_new_yields_a_single_idle_event(self):
        events = poll_events(self._StubTestTailer([]), self._StubCommitTailer([]))
        self.assertEqual(events, [BuildEvent(EventType.IDLE)])

    def test_test_log_lines_become_pass_and_fail_events(self):
        lines = ["test_a ... ok", "noise", "test_b ... FAIL"]
        events = poll_events(self._StubTestTailer(lines), self._StubCommitTailer([]))
        self.assertEqual(
            events,
            [BuildEvent(EventType.TEST_PASS), BuildEvent(EventType.TEST_FAIL)],
        )

    def test_each_new_commit_becomes_a_commit_event(self):
        events = poll_events(self._StubTestTailer([]), self._StubCommitTailer(["a", "b"]))
        self.assertEqual(events, [BuildEvent(EventType.COMMIT), BuildEvent(EventType.COMMIT)])

    def test_test_events_and_commit_events_combine(self):
        events = poll_events(
            self._StubTestTailer(["test_a ... ok"]), self._StubCommitTailer(["a"])
        )
        self.assertEqual(events, [BuildEvent(EventType.TEST_PASS), BuildEvent(EventType.COMMIT)])


if __name__ == "__main__":
    unittest.main()
