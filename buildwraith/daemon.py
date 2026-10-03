"""CLI entry point: either poll the tailers live, or replay a finished log.

This module is the thin, side-effecting shell around the pure pieces
defined elsewhere in the package -- `tailer.poll_events` for turning live
logs into events, `replay.replay_file` for turning a finished log into a
whole history in one shot, `state.reduce` for folding events into vitals,
and `sprites.render` for drawing the result. It is intentionally small.

Two subcommands share this one entry point:

- `buildwraith run <test-log> <repo>` -- the live daemon: polls on a timer
  forever, exactly like earlier milestones.
- `buildwraith feed <ci-log>` -- batch replay: reads one already-finished
  CI log and deterministically reconstructs the creature's whole history
  from it, for demos and tests that need a repeatable run without a live
  process to drive it.
"""

import argparse
import sys
import time

from .replay import replay_file
from .sprites import render
from .state import initial_state, reduce
from .tailer import FileTailer, GitCommitTailer, poll_events

DEFAULT_INTERVAL_SECONDS = 2.0
DEFAULT_FEED_INTERVAL_SECONDS = 0.0


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


def feed(ci_log_path: str, interval_seconds: float = DEFAULT_FEED_INTERVAL_SECONDS, out=sys.stdout) -> None:
    """Deterministically replay a finished CI log, printing each resulting state.

    Unlike `run`, nothing is polled live: the whole log is read up front and
    folded through the reducer in one pass (see `replay.replay_file`), so the
    same log file always replays to the same printed history. `interval_seconds`
    only paces how fast that fixed history is printed, for demos; it has no
    effect on the states themselves or the order they are produced in.
    """
    for step in replay_file(ci_log_path):
        state = step.state
        out.write(render(state))
        out.write(f"health={state.health} mood={state.mood} energy={state.energy}\n")
        out.flush()
        if interval_seconds > 0:
            time.sleep(interval_seconds)


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description="Drive a creature from a test runner's log and a git repository's commits."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser(
        "run", help="poll a live test log and git repository on a timer, forever"
    )
    run_parser.add_argument("test_log_path", help="path to the test runner's output log")
    run_parser.add_argument("repo_path", help="path to the git repository to watch for commits")
    run_parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_INTERVAL_SECONDS,
        help=f"seconds between polls (default: {DEFAULT_INTERVAL_SECONDS})",
    )

    feed_parser = subparsers.add_parser(
        "feed", help="deterministically replay a finished CI log to reconstruct creature history"
    )
    feed_parser.add_argument("ci_log_path", help="path to a recorded, already-finished CI log")
    feed_parser.add_argument(
        "--interval",
        type=float,
        default=DEFAULT_FEED_INTERVAL_SECONDS,
        help=(
            "seconds to pause between replayed steps, for demos "
            f"(default: {DEFAULT_FEED_INTERVAL_SECONDS}, no pause)"
        ),
    )

    args = parser.parse_args(argv)
    if args.command == "run":
        run(args.test_log_path, args.repo_path, args.interval)
    else:
        feed(args.ci_log_path, args.interval)


if __name__ == "__main__":
    main()
