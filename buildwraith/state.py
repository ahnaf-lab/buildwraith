"""Pure state reducer for the creature.

The creature has three stats (health, mood, energy), each clamped to
0-100. A build event (a test run result, a commit, or a tick of
inactivity) is folded into the current state via `reduce`, producing a
brand new state. `reduce` never mutates its input and never touches
the filesystem, network, or clock, so the same (state, event) pair
always yields the same result -- this is what makes the transition
table unit-testable without a running daemon.
"""

from dataclasses import dataclass
from enum import Enum

MIN_STAT = 0
MAX_STAT = 100


class EventType(Enum):
    """Kinds of build events the daemon can observe."""

    TEST_PASS = "test_pass"
    TEST_FAIL = "test_fail"
    COMMIT = "commit"
    IDLE = "idle"


@dataclass(frozen=True)
class BuildEvent:
    """A single observation from the test runner or commit log."""

    type: EventType


@dataclass(frozen=True)
class CreatureState:
    """Snapshot of the creature's vitals plus streak bookkeeping."""

    health: int = MAX_STAT
    mood: int = MAX_STAT
    energy: int = MAX_STAT
    consecutive_failures: int = 0
    consecutive_passes: int = 0


# Base (health, mood, energy) deltas applied per event type before any
# streak adjustment. This is the "transition table" the daemon drives
# the creature with.
TRANSITIONS = {
    EventType.TEST_PASS: (5, 10, 5),
    EventType.TEST_FAIL: (-8, -12, -5),
    EventType.COMMIT: (0, 2, -3),
    EventType.IDLE: (0, -1, -2),
}

# A build that stays red keeps hurting more, up to a cap, so the
# creature visibly sickens the longer the failure streak runs.
FAILURE_STREAK_PENALTY = 2
FAILURE_STREAK_PENALTY_CAP = 20

# A build that stays green keeps lifting mood a bit more, up to a cap.
PASS_STREAK_BONUS = 1
PASS_STREAK_BONUS_CAP = 10


def _clamp(value: int) -> int:
    return max(MIN_STAT, min(MAX_STAT, value))


def initial_state() -> CreatureState:
    """A freshly hatched creature at full health, mood, and energy."""
    return CreatureState()


def reduce(state: CreatureState, event: BuildEvent) -> CreatureState:
    """Apply one build event to a state, returning a new state.

    Pure: `state` and `event` are left untouched; a new
    `CreatureState` is returned every time.
    """
    health_delta, mood_delta, energy_delta = TRANSITIONS[event.type]

    consecutive_failures = state.consecutive_failures
    consecutive_passes = state.consecutive_passes

    if event.type == EventType.TEST_FAIL:
        consecutive_failures += 1
        consecutive_passes = 0
        streak_penalty = min(
            consecutive_failures * FAILURE_STREAK_PENALTY,
            FAILURE_STREAK_PENALTY_CAP,
        )
        health_delta -= streak_penalty
    elif event.type == EventType.TEST_PASS:
        consecutive_passes += 1
        consecutive_failures = 0
        streak_bonus = min(
            consecutive_passes * PASS_STREAK_BONUS,
            PASS_STREAK_BONUS_CAP,
        )
        mood_delta += streak_bonus

    return CreatureState(
        health=_clamp(state.health + health_delta),
        mood=_clamp(state.mood + mood_delta),
        energy=_clamp(state.energy + energy_delta),
        consecutive_failures=consecutive_failures,
        consecutive_passes=consecutive_passes,
    )
