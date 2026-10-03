"""Live curses animation of the creature's sprite and stat bars.

The loop redraws every "tick" (a short, fixed interval) so the idle
animation in `sprites.render_animated` keeps moving smoothly, but it only
polls the real test-log and git tailers every `poll_seconds` -- a much
longer interval -- so the creature visibly breathes or blinks between
real build events instead of sitting frozen until the next one arrives.

The drawing itself (`_draw`, `run`) is side-effecting curses code and is
exercised by hand, not by the unit tests. Everything it depends on --
the stat-bar text, the combined frame text, and the tick/poll scheduling
math -- is a small pure function below, and those are what the tests in
tests/test_ui.py pin down.
"""

import argparse
import curses
import time

from .sprites import render_animated
from .state import CreatureState, initial_state, reduce
from .tailer import FileTailer, GitCommitTailer, poll_events

BAR_WIDTH = 20
DEFAULT_TICK_SECONDS = 0.25
DEFAULT_POLL_SECONDS = 2.0


def render_bar(label: str, value: int, width: int = BAR_WIDTH, max_value: int = 100) -> str:
    """Render one fixed-width `label [#####-----] value/max` stat bar.

    `value` is clamped into `[0, max_value]` before the bar is drawn, so a
    stat that is momentarily out of range (it should not happen, but the
    bar is purely a display, not a source of truth) never overflows it.
    """
    clamped = max(0, min(max_value, value))
    filled = round(width * clamped / max_value) if max_value else 0
    bar = "#" * filled + "-" * (width - filled)
    return f"{label:<7}[{bar}] {clamped:3d}/{max_value}"


def render_frame(state: CreatureState, tick: int) -> str:
    """Compose the animated sprite and all three stat bars for one tick."""
    lines = [
        render_animated(state, tick),
        render_bar("health", state.health),
        render_bar("mood", state.mood),
        render_bar("energy", state.energy),
    ]
    return "\n".join(lines) + "\n"


def ticks_per_poll(poll_seconds: float, tick_seconds: float) -> int:
    """How many animation ticks make up one real poll interval.

    Always at least 1, so a `poll_seconds` shorter than or equal to
    `tick_seconds` just polls on every tick instead of dividing by zero
    or never polling.
    """
    return max(1, round(poll_seconds / tick_seconds))


def is_poll_tick(tick: int, poll_every: int) -> bool:
    """Whether animation tick `tick` is one that should poll the tailers."""
    return tick % poll_every == 0


def _draw(stdscr, state: CreatureState, tick: int) -> None:
    stdscr.erase()
    for row, line in enumerate(render_frame(state, tick).splitlines()):
        stdscr.addstr(row, 0, line)
    stdscr.refresh()


def run(
    stdscr,
    test_log_path: str,
    repo_path: str,
    tick_seconds: float = DEFAULT_TICK_SECONDS,
    poll_seconds: float = DEFAULT_POLL_SECONDS,
) -> None:
    """Drive the curses screen: redraw every tick, poll every `poll_seconds`.

    Returns (so `curses.wrapper` can restore the terminal) when the user
    presses `q` or Escape.
    """
    curses.curs_set(0)
    stdscr.nodelay(True)
    test_tailer = FileTailer(test_log_path)
    commit_tailer = GitCommitTailer(repo_path)
    state = initial_state()
    poll_every = ticks_per_poll(poll_seconds, tick_seconds)

    tick = 0
    while True:
        key = stdscr.getch()
        if key in (ord("q"), 27):
            return
        if is_poll_tick(tick, poll_every):
            for event in poll_events(test_tailer, commit_tailer):
                state = reduce(state, event)
        _draw(stdscr, state, tick)
        time.sleep(tick_seconds)
        tick += 1


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Animate the creature live in the terminal with curses, polling a "
            "test-runner log and a git repository's commits. Press q to quit."
        )
    )
    parser.add_argument("test_log_path", help="path to the test runner's output log")
    parser.add_argument("repo_path", help="path to the git repository to watch for commits")
    parser.add_argument(
        "--tick",
        type=float,
        default=DEFAULT_TICK_SECONDS,
        help=f"seconds between animation frames (default: {DEFAULT_TICK_SECONDS})",
    )
    parser.add_argument(
        "--poll",
        type=float,
        default=DEFAULT_POLL_SECONDS,
        help=f"seconds between polls of the real tailers (default: {DEFAULT_POLL_SECONDS})",
    )
    args = parser.parse_args(argv)
    curses.wrapper(run, args.test_log_path, args.repo_path, args.tick, args.poll)


if __name__ == "__main__":
    main()
