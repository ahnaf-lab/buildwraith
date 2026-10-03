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

### Sprites

The creature's vitals are mapped to one of four ASCII sprites -- idle,
happy, sick, or dead -- based on stat thresholds:

```python
from buildwraith import CreatureState, render

print(render(CreatureState(health=100, mood=100, energy=100)))
```

- `dead` -- health has hit 0
- `sick` -- health has dropped below 40
- `happy` -- health and mood are both at least 70 and energy is at
  least 30
- `idle` -- anything in between

`buildwraith.classify` exposes the mood (as a `Mood` enum member)
without the sprite text, and `buildwraith.sprite_for` looks up the
fixed sprite text for a given `Mood`. Each sprite's exact text is
pinned by a golden test in `tests/test_sprites.py`, so an accidental
change to the art or to a threshold is caught by the test suite.

### Event tailer

The daemon turns a test runner's log file and a git repository's commit
history into the `BuildEvent`s the reducer consumes:

```python
from buildwraith import FileTailer, GitCommitTailer, poll_events

test_tailer = FileTailer("/path/to/test-runner.log")
commit_tailer = GitCommitTailer("/path/to/repo")

events = poll_events(test_tailer, commit_tailer)
```

- `FileTailer` incrementally reads lines appended to a growing log
  file. Only complete lines are returned; a line with no trailing
  newline yet is held back until it is finished. If the file shrinks
  (truncated or replaced, as log files sometimes are), the tailer
  starts over from the beginning.
- `GitCommitTailer` polls a repository's `git log` for commits made
  since it was constructed or last polled -- commits that already
  existed are the baseline, not events.
- `classify_test_line` maps one line of test-runner output to
  `TEST_PASS`/`TEST_FAIL`/`None` by checking its final
  whitespace-separated token against the status markers used by both
  unittest's verbose output (`... ok`, `... FAIL`, `... ERROR`) and
  pytest's verbose output (`PASSED`, `FAILED`, `ERROR`).
- `poll_events` runs one polling cycle across both tailers and returns
  the `BuildEvent`s it observed, falling back to a single `IDLE` event
  when nothing new happened.

Run the daemon directly against a log file and a repository:

```
python -m buildwraith.daemon run /path/to/test-runner.log /path/to/repo
```

or, once installed, via the `buildwraith` console script (`buildwraith run
...`). It polls on an interval (`--interval`, default 2 seconds), feeds
whatever events it finds into the reducer, and prints the creature's sprite
and vitals after each poll. The only network- or process-adjacent work it
does is reading the log file from disk and invoking the local `git log`
command against the given repository -- no other process is run and no
network call is made.

### Batch replay

`buildwraith feed <ci-log>` is the demo/test-facing counterpart to `run`:
instead of polling a live log and repository on a timer forever, it reads
one already-finished CI log in a single pass and deterministically
reconstructs the whole history of creature states it would have produced:

```
python -m buildwraith.daemon feed /path/to/recorded-ci.log
```

or, once installed, via `buildwraith feed /path/to/recorded-ci.log`. Each
line of the log is classified exactly like the live daemon classifies test
output (`classify_test_line`'s pass/fail markers), plus plain `git log`
commit headers (`commit <40-character-hex-sha>`, with any trailing ref
decoration such as `(HEAD -> master)` ignored) so a log that interleaves a
checkout's commit history with a test run's output drives both `COMMIT` and
`TEST_PASS`/`TEST_FAIL` events. Lines that match neither are skipped. Because
the reducer is pure and the whole log is read up front, the same log file
always replays to the exact same sequence of states -- useful for demos that
need a repeatable run, and for golden tests of a run's full history rather
than just a single step.

By default every recognized step is printed immediately, back to back;
`--interval` adds a pause (in seconds) between steps purely for pacing a
live demo -- it has no effect on the reconstructed states themselves:

```
python -m buildwraith.daemon feed /path/to/recorded-ci.log --interval 0.5
```

The pure replay logic is in `buildwraith.replay` and can be used without
going through the CLI at all:

```python
from buildwraith.replay import replay_file, replay_lines

steps = replay_file("/path/to/recorded-ci.log")
for step in steps:
    print(step.event, step.state)
```

- `classify_log_line` classifies one log line as a `BuildEvent` type, or
  `None`.
- `replay_lines` folds an iterable of lines through the reducer, returning a
  `ReplayStep` (the event plus the resulting `CreatureState`) for every
  recognized line, starting fresh from `initial_state()` every call.
- `replay_file` is `replay_lines` over a file on disk.

### Live animation

`buildwraith.ui` draws the creature and its stat bars to the terminal with
the standard library's `curses` module, redrawing on a short, fixed tick
(0.25s by default) so idle animation -- a blink, right now -- keeps the
creature looking alive, while the real test-log and git tailers are only
polled on a separate, much longer interval (2s by default). This is why a
creature's frame visibly changes between build events instead of sitting
frozen until the next one lands.

The sprite/bar composition is split into small pure functions so it can be
unit-tested without a real terminal:

```python
from buildwraith.state import initial_state
from buildwraith.ui import render_bar, render_frame

state = initial_state()
print(render_frame(state, tick=0))   # sprite art + health/mood/energy bars
print(render_bar("health", state.health))
```

- `render_bar` draws one fixed-width `label [#####-----] value/max` bar.
- `render_frame` combines the current animation frame (from
  `buildwraith.sprites.render_animated`) with all three stat bars into the
  text block drawn each tick.
- `ticks_per_poll`/`is_poll_tick` are the pure scheduling math behind "redraw
  every tick, poll every N ticks" -- the only side-effecting part is the
  `curses` loop in `buildwraith.ui.run`, which calls them.

Run it directly against a log file and a repository:

```
python -m buildwraith.ui /path/to/test-runner.log /path/to/repo
```

or, once installed, via the `buildwraith-ui` console script. Press `q` or
Escape to quit. Like the plain daemon, the only filesystem/process work it
does is reading the log file and invoking the local `git log` command
against the given repository -- no other process is run and no network
call is made.

## Status

This project is built autonomously, one milestone at a time, and each
milestone is only kept if its automated tests pass. The current milestone
adds the `buildwraith feed` batch replay mode described above, on top of the
sprites, reducer, event tailer, and curses animation loop from earlier
milestones.
