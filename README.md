# buildwraith

A daemon that tails your test runner's output and commit log and drives a
deterministic virtual creature's health, mood, and energy, rendered as
animated ASCII pixel-art that visibly sickens when the build stays red and
perks up on green commits. It is a tamagotchi whose life is literally your
CI status.

## Install

Requires Python 3.9+. No external dependencies.

```
git clone <this repository>
cd buildwraith
```

## Usage

The core of the project is a pure state reducer: given the creature's
current vitals and a build event, it returns the creature's next vitals.
No daemon, filesystem, or clock is required to use it:

```python
from buildwraith import BuildEvent, EventType, initial_state, reduce

state = initial_state()
state = reduce(state, BuildEvent(EventType.TEST_FAIL))
state = reduce(state, BuildEvent(EventType.TEST_FAIL))
state = reduce(state, BuildEvent(EventType.TEST_PASS))

print(state.health, state.mood, state.energy)
```

Event types recognized by the reducer:

- `TEST_PASS` -- a test run finished green
- `TEST_FAIL` -- a test run finished red
- `COMMIT` -- a commit landed in the watched repository
- `IDLE` -- a tick of inactivity (no new build or commit observed)

Health, mood, and energy are each clamped to the range 0-100. A failure
streak hurts health more the longer it runs (up to a cap); a pass streak
lifts mood more the longer it runs (up to a cap). The reducer is pure and
deterministic: the same state and event always produce the same result,
which is what the transition-table unit tests in `tests/test_state.py`
exercise.

Run the tests with:

```
python -m unittest discover
```

## Status

This project is built autonomously, one milestone at a time, and each
milestone is only kept if its automated tests pass. The current milestone
implements the creature state reducer described above; the daemon that
tails real test runner output and commit logs, and the ASCII pixel-art
renderer, are not built yet.
