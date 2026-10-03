import unittest

from buildwraith.sprites import Mood, classify, render, sprite_for
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


if __name__ == "__main__":
    unittest.main()
