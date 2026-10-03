"""ASCII sprites for the creature, selected by stat thresholds.

Each sprite is a fixed multi-line string ("frame") for one of four
moods. `classify` maps a `CreatureState`'s vitals to a `Mood` using
threshold rules; `render` looks up the sprite text for a mood. The
golden tests in tests/test_sprites.py pin the exact sprite text so an
accidental change to the art, or to a threshold, is caught.
"""

from enum import Enum

from .state import CreatureState

# Health below this is sick; at or above it (with mood and energy also
# healthy) the creature can be happy. Between sick and happy, the
# creature is idle -- neither thriving nor ailing.
HEALTHY_THRESHOLD = 70
SICK_THRESHOLD = 40
LOW_ENERGY_THRESHOLD = 30


class Mood(Enum):
    """The four sprite buckets a creature's vitals can fall into."""

    DEAD = "dead"
    SICK = "sick"
    HAPPY = "happy"
    IDLE = "idle"


def classify(state: CreatureState) -> Mood:
    """Map a creature's vitals to one of the four sprite moods.

    Order matters: a dead creature is dead regardless of other stats,
    and low health always means sick even if mood or energy are high.
    """
    if state.health <= 0:
        return Mood.DEAD
    if state.health < SICK_THRESHOLD:
        return Mood.SICK
    if (
        state.health >= HEALTHY_THRESHOLD
        and state.mood >= HEALTHY_THRESHOLD
        and state.energy >= LOW_ENERGY_THRESHOLD
    ):
        return Mood.HAPPY
    return Mood.IDLE


def _frame(lines):
    return "\n".join(lines) + "\n"


SPRITES = {
    Mood.IDLE: _frame(
        [
            " ___ ",
            "(o_o)",
            "(   )",
            "/| |\\",
            " \" \" ",
        ]
    ),
    Mood.HAPPY: _frame(
        [
            " ___ ",
            "(^_^)",
            "( w )",
            "/| |\\",
            " \" \" ",
        ]
    ),
    Mood.SICK: _frame(
        [
            " ___ ",
            "(x_x)",
            "( ~ )",
            "/| |\\",
            " . . ",
        ]
    ),
    Mood.DEAD: _frame(
        [
            " ___ ",
            "(X_X)",
            "( _ )",
            "/   \\",
            " RIP ",
        ]
    ),
}


def sprite_for(mood: Mood) -> str:
    """Return the fixed ASCII sprite text for a given mood."""
    return SPRITES[mood]


def render(state: CreatureState) -> str:
    """Return the exact ASCII sprite text for a creature's current vitals."""
    return sprite_for(classify(state))


# Each mood has a short cycle of frames for idle animation between real
# build events -- a blink or a breath -- so the creature looks alive even
# when nothing new has happened. Frame 0 is always the same text as
# `SPRITES[mood]`; a dead creature does not move, so both of its frames
# are identical.
ANIMATION_FRAMES = {
    Mood.IDLE: [
        SPRITES[Mood.IDLE],
        _frame(
            [
                " ___ ",
                "(-_-)",
                "(   )",
                "/| |\\",
                " \" \" ",
            ]
        ),
    ],
    Mood.HAPPY: [
        SPRITES[Mood.HAPPY],
        _frame(
            [
                " ___ ",
                "(-_-)",
                "( w )",
                "/| |\\",
                " \" \" ",
            ]
        ),
    ],
    Mood.SICK: [
        SPRITES[Mood.SICK],
        _frame(
            [
                " ___ ",
                "(x_x)",
                "( _ )",
                "/| |\\",
                " . . ",
            ]
        ),
    ],
    Mood.DEAD: [
        SPRITES[Mood.DEAD],
        SPRITES[Mood.DEAD],
    ],
}


def animated_sprite_for(mood: Mood, tick: int) -> str:
    """Return the animation frame for `mood` at animation tick `tick`.

    Ticks cycle through the mood's frame list, so passing consecutive
    ticks produces a repeating animation (e.g. a blink).
    """
    frames = ANIMATION_FRAMES[mood]
    return frames[tick % len(frames)]


def render_animated(state: CreatureState, tick: int) -> str:
    """Return the animation frame text for a creature's vitals at `tick`."""
    return animated_sprite_for(classify(state), tick)
