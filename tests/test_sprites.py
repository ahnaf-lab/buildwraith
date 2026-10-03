import unittest

from buildwraith.sprites import (
    ANIMATION_FRAMES,
    Mood,
    animated_sprite_for,
    classify,
    render,
    render_animated,
    sprite_for,
)
from buildwraith.state import CreatureState

IDLE_SPRITE = (
    " ___ \n"
    "(o_o)\n"
    "(   )\n"
    "/| |\\\n"
    " \" \" \n"
)

HAPPY_SPRITE = (
    " ___ \n"
    "(^_^)\n"
    "( w )\n"
    "/| |\\\n"
    " \" \" \n"
)

SICK_SPRITE = (
    " ___ \n"
    "(x_x)\n"
    "( ~ )\n"
    "/| |\\\n"
    " . . \n"
)

DEAD_SPRITE = (
    " ___ \n"
    "(X_X)\n"
    "( _ )\n"
    "/   \\\n"
    " RIP \n"
)


class GoldenSpriteTests(unittest.TestCase):
    """Pin the exact sprite text for each mood so art changes are caught."""

    def test_idle_sprite_matches_golden_text(self):
        self.assertEqual(sprite_for(Mood.IDLE), IDLE_SPRITE)

    def test_happy_sprite_matches_golden_text(self):
        self.assertEqual(sprite_for(Mood.HAPPY), HAPPY_SPRITE)

    def test_sick_sprite_matches_golden_text(self):
        self.assertEqual(sprite_for(Mood.SICK), SICK_SPRITE)

    def test_dead_sprite_matches_golden_text(self):
        self.assertEqual(sprite_for(Mood.DEAD), DEAD_SPRITE)

    def test_every_mood_has_a_distinct_sprite(self):
        rendered = {mood: sprite_for(mood) for mood in Mood}
        self.assertEqual(len(set(rendered.values())), len(Mood))


class ClassifyThresholdTests(unittest.TestCase):
    def test_zero_health_is_dead_regardless_of_other_stats(self):
        state = CreatureState(health=0, mood=100, energy=100)
        self.assertEqual(classify(state), Mood.DEAD)

    def test_health_just_below_sick_threshold_is_sick(self):
        state = CreatureState(health=39, mood=100, energy=100)
        self.assertEqual(classify(state), Mood.SICK)

    def test_health_at_sick_threshold_is_not_sick(self):
        state = CreatureState(health=40, mood=40, energy=40)
        self.assertNotEqual(classify(state), Mood.SICK)

    def test_high_health_mood_and_energy_is_happy(self):
        state = CreatureState(health=70, mood=70, energy=30)
        self.assertEqual(classify(state), Mood.HAPPY)

    def test_high_health_but_low_energy_is_idle_not_happy(self):
        state = CreatureState(health=70, mood=70, energy=29)
        self.assertEqual(classify(state), Mood.IDLE)

    def test_high_health_but_low_mood_is_idle_not_happy(self):
        state = CreatureState(health=70, mood=69, energy=100)
        self.assertEqual(classify(state), Mood.IDLE)

    def test_mid_range_stats_are_idle(self):
        state = CreatureState(health=50, mood=50, energy=50)
        self.assertEqual(classify(state), Mood.IDLE)

    def test_render_follows_classify(self):
        healthy = CreatureState(health=100, mood=100, energy=100)
        dying = CreatureState(health=1, mood=1, energy=1)

        self.assertEqual(render(healthy), sprite_for(Mood.HAPPY))
        self.assertEqual(render(dying), sprite_for(Mood.SICK))


class AnimationFrameTests(unittest.TestCase):
    """The idle animation cycles frames without disturbing the golden art."""

    def test_first_frame_matches_the_static_golden_sprite(self):
        for mood in Mood:
            self.assertEqual(animated_sprite_for(mood, tick=0), sprite_for(mood))

    def test_every_mood_has_at_least_two_frames(self):
        for mood in Mood:
            self.assertGreaterEqual(len(ANIMATION_FRAMES[mood]), 2)

    def test_tick_cycles_back_to_the_first_frame(self):
        frames = ANIMATION_FRAMES[Mood.IDLE]
        self.assertEqual(animated_sprite_for(Mood.IDLE, tick=len(frames)), frames[0])

    def test_second_frame_differs_from_the_first_for_live_moods(self):
        for mood in (Mood.IDLE, Mood.HAPPY, Mood.SICK):
            frames = ANIMATION_FRAMES[mood]
            self.assertNotEqual(frames[0], frames[1])

    def test_dead_creature_does_not_animate(self):
        frames = ANIMATION_FRAMES[Mood.DEAD]
        self.assertEqual(frames[0], frames[1])

    def test_render_animated_follows_classify(self):
        happy = CreatureState(health=100, mood=100, energy=100)
        self.assertEqual(render_animated(happy, tick=1), animated_sprite_for(Mood.HAPPY, 1))


if __name__ == "__main__":
    unittest.main()
