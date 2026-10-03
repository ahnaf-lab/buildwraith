"""Tailing primitives that turn raw logs into build events.

Two independent sources are tailed: a growing test-runner log file
(`FileTailer`) and a git repository's commit history (`GitCommitTailer`).
Both only ever report what is *new* since the last time they were asked,
so a caller can poll them on a timer and feed whatever comes back into
the state reducer. `poll_events` does exactly that, falling back to a
single `IDLE` event when nothing new was observed.

Everything here is side-effecting (it reads files and runs `git`), but
the side effects are isolated behind small, swappable seams -- a custom
`list_commit_hashes` callable, or just a temp file on disk -- so the
behavior can be exercised deterministically in tests.
"""

import os
import subprocess
from typing import Callable, List, Optional

from .state import BuildEvent, EventType

# The final whitespace-separated token of a test-runner output line is
# compared against these markers to decide whether the line reports a
# pass or a failure. This covers unittest's verbose format ("... ok",
# "... FAIL", "... ERROR") and pytest's verbose format
# ("test.py::test_name PASSED"/"FAILED"/"ERROR").
_FAIL_MARKERS = frozenset({"FAIL", "FAILED", "ERROR"})
_PASS_MARKERS = frozenset({"ok", "OK", "PASSED", "PASS"})


def classify_test_line(line: str) -> Optional[EventType]:
    """Classify one line of test-runner output as a pass, a failure, or neither.

    Returns `None` for lines that do not end in a recognized status
    marker (progress output, summaries, blank lines, and so on).
    """
    tokens = line.split()
    if not tokens:
        return None
    marker = tokens[-1]
    if marker in _FAIL_MARKERS:
        return EventType.TEST_FAIL
    if marker in _PASS_MARKERS:
        return EventType.TEST_PASS
    return None


class FileTailer:
    """Incrementally reads lines appended to a growing text file.

    Only complete lines (ending in `\\n`) are ever returned; a trailing
    partial line is held back until it is completed by a later write. If
    the file shrinks since the last read (truncated or replaced, as log
    files sometimes are), the tailer starts over from the beginning.
    """

    def __init__(self, path: str):
        self._path = path
        self._offset = 0

    def read_new_lines(self) -> List[str]:
        """Return newly completed lines written since the last call."""
        try:
            size = os.path.getsize(self._path)
        except OSError:
            return []
        if size < self._offset:
            self._offset = 0
        with open(self._path, "rb") as handle:
            handle.seek(self._offset)
            chunk = handle.read()
        if not chunk:
            return []
        complete, newline, _incomplete_tail = chunk.rpartition(b"\n")
        if not newline:
            return []
        self._offset += len(complete) + len(newline)
        return [line.decode("utf-8", errors="replace") for line in complete.split(b"\n")]


def _run_git_log(repo_path: str, rev_range: Optional[str] = None) -> List[str]:
    """Return commit hashes for `rev_range` in `repo_path`, oldest first."""
    args = ["git", "log", "--format=%H"]
    if rev_range:
        args.append(rev_range)
    result = subprocess.run(
        args,
        cwd=repo_path,
        capture_output=True,
        text=True,
        check=True,
    )
    hashes = result.stdout.split()
    hashes.reverse()
    return hashes


ListCommitHashes = Callable[..., List[str]]


class GitCommitTailer:
    """Polls a local git repository's current branch for new commits.

    Commits that already exist when the tailer is constructed are the
    baseline, not events -- only commits that land afterwards are
    reported by `poll_new_commits`.
    """

    def __init__(self, repo_path: str, list_commit_hashes: ListCommitHashes = _run_git_log):
        self._repo_path = repo_path
        self._list_commit_hashes = list_commit_hashes
        history = self._list_commit_hashes(repo_path)
        self._last_seen = history[-1] if history else None

    def poll_new_commits(self) -> List[str]:
        """Return hashes of commits made since the last poll, oldest first."""
        if self._last_seen is None:
            history = self._list_commit_hashes(self._repo_path)
            if not history:
                return []
            self._last_seen = history[-1]
            return history
        new_hashes = self._list_commit_hashes(self._repo_path, f"{self._last_seen}..HEAD")
        if new_hashes:
            self._last_seen = new_hashes[-1]
        return new_hashes


def poll_events(test_tailer: FileTailer, commit_tailer: GitCommitTailer) -> List[BuildEvent]:
    """Run one polling cycle, returning the build events it observed.

    New test-log lines are classified and turned into `TEST_PASS`/
    `TEST_FAIL` events, each new commit becomes a `COMMIT` event, and if
    neither source produced anything a single `IDLE` event is returned
    so the creature still drifts during quiet periods.
    """
    events: List[BuildEvent] = []

    for line in test_tailer.read_new_lines():
        event_type = classify_test_line(line)
        if event_type is not None:
            events.append(BuildEvent(event_type))

    for _commit_hash in commit_tailer.poll_new_commits():
        events.append(BuildEvent(EventType.COMMIT))

    if not events:
        events.append(BuildEvent(EventType.IDLE))

    return events
