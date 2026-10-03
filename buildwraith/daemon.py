"""CLI entry point: poll the tailers on a timer and drive the creature.

This module is the thin, side-effecting shell around the pure pieces
defined elsewhere in the package -- `tailer.poll_events` for turning
logs into events, `state.reduce` for folding events into vitals, and
`sprites.render` for drawing the result. It is intentionally small: the
loop just polls, reduces, prints, and sleeps.
"""

import argparse
import sys
import time

from .sprites import render
from .state import initial_state, reduce
from .tailer import FileTailer, GitCommitTailer, poll_events

DEFAULT_INTERVAL_SECONDS = 2.0


def run(test_log_path: str, repo_path: str, interval_seconds: float, out=sys.stdout) -> None:
    """Poll `test_log_path` and the `repo_path` git log forever, printing the creature."""
    test_tailer = FileTailer(test_log_path)
    commit_tailer = GitCommitTailer(repo_path)
    state = initial_state()

    while True:
        for event in poll_events(test_tailer, commit_tailer):
            state = reduce(state, event)
        out.write(render(state))
        out.write(f"health={state.health} mood={state.mood} energy={state.energy}\n")
        out.flush()
        time.sleep(interval_seconds)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Tail a test-runner log and a git repository's commits to drive the creature."
    )
    parser.add_argument("test_log_path", help="path to the test runner's output log")
    parser.add_argument("repo_path", help="path to the git repository to watch for commits")
    parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"seconds between polls (default: {DEFAULT_INTERVAL_SECONDS})",
    )
    args = parser.parse_args(argv)
    run(args.test_log_path, args.repo_path, args.interval)


if __name__ == "__main__":
    main()
