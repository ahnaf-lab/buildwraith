"""Deterministic batch replay of a recorded CI log.

`buildwraith feed <ci-log>` is the demo/test-facing counterpart to the live
daemon: instead of polling a growing log file and a git repository on a
timer, it reads a complete, already-finished CI log in one shot and folds
every line through the same pure `state.reduce` the live daemon uses,
producing the full sequence of creature states the log would have produced
if it had been tailed live. Because `reduce` is pure and the input is a
fixed file, the output is exactly reproducible -- the same log always
replays to the same history, which is what makes this useful for demos and
for golden tests of a whole run.
"""

from dataclasses import dataclass
from typing import Iterable, List

from .state import BuildEvent, CreatureState, EventType, initial_state, reduce
from .tailer import classify_test_line

_COMMIT_PREFIX = "commit "
_COMMIT_HASH_LENGTH = 40
_HEX_DIGITS = frozenset("0123456789abcdef")


def classify_log_line(line: str):
    """Classify one line of a recorded CI log as a build event, or `None`.

    Recognizes the same test-result markers `classify_test_line` does, plus
    plain `git log` commit headers ("commit <40-character-hex-sha>", with any
    trailing ref decoration ignored), since a CI log is often a straight
    capture of a checkout step's `git log` output interleaved with the test
    runner's own output. `GitCommitTailer` has no use for this (it talks to
    `git log` directly), so it lives here rather than in `tailer.py`.
    """
    stripped = line.strip()
    if stripped.startswith(_COMMIT_PREFIX):
        rest = stripped[len(_COMMIT_PREFIX):].split()
        candidate = rest[0].lower() if rest else ""
        if len(candidate) == _COMMIT_HASH_LENGTH and all(c in _HEX_DIGITS for c in candidate):
            return EventType.COMMIT
        return None
    return classify_test_line(line)


@dataclass(frozen=True)
class ReplayStep:
    """One step of a replayed history: the event that fired and the resulting state."""

    event: BuildEvent
    state: CreatureState


def replay_lines(lines: Iterable[str]) -> List[ReplayStep]:
    """Fold every classifiable line of a CI log through the reducer.

    Returns one `ReplayStep` per recognized event, in the order the events
    occurred; unrecognized lines (progress output, blank lines, summaries)
    are skipped, exactly like they are by `classify_test_line` in the live
    daemon. Always starts from `initial_state()`, which combined with
    `reduce` being pure is what makes a full replay deterministic: the same
    sequence of lines always produces the same sequence of steps.
    """
    state = initial_state()
    steps = []
    for line in lines:
        event_type = classify_log_line(line)
        if event_type is None:
            continue
        event = BuildEvent(event_type)
        state = reduce(state, event)
        steps.append(ReplayStep(event=event, state=state))
    return steps


def replay_file(path: str) -> List[ReplayStep]:
    """Replay a CI log file on disk. See `replay_lines`."""
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        return replay_lines(handle)
