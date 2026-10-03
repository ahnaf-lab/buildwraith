import unittest

from buildwraith.state import CreatureState
from buildwraith.ui import (
    is_poll_tick,
    render_bar,
    render_frame,
    ticks_per_poll,
)


class RenderBarTests(unittest.TestCase):
    def test_full_bar_is_entirely_filled(self):
        bar = render_bar("health", 100, width=20, max_value=100)
        self.assertEqual(bar, "health [####################] 100/100")

    def test_empty_bar_is_entirely_unfilled(self):
        bar = render_bar("mood", 0, width=20, max_value=100)
        self.assertEqual(bar, "mood   [--------------------]   0/100")

    def test_half_full_bar_is_half_filled(self):
        bar = render_bar("energy", 50, width=20, max_value=100)
        self.assertEqual(bar, "energy [##########----------]  50/100")

    def test_value_above_max_is_clamped(self):
        bar = render_bar("health", 150, width=10, max_value=100)
        self.assertEqual(bar, "health [##########] 100/100")

    def test_value_below_zero_is_clamped(self):
        bar = render_bar("health", -20, width=10, max_value=100)
        self.assertEqual(bar, "health [----------]   0/100")


class RenderFrameTests(unittest.TestCase):
    def test_frame_contains_the_sprite_and_all_three_bars(self):
        state = CreatureState(health=80, mood=60, energy=40)
        frame = render_frame(state, tick=0)

        self.assertIn("health [", frame)
        self.assertIn("mood   [", frame)
        self.assertIn("energy [", frame)

    def test_frame_changes_between_consecutive_ticks_for_an_animated_mood(self):
        state = CreatureState(health=100, mood=100, energy=100)
        first = render_frame(state, tick=0)
        second = render_frame(state, tick=1)

        self.assertNotEqual(first, second)

    def test_frame_is_deterministic_for_the_same_state_and_tick(self):
        state = CreatureState(health=80, mood=60, energy=40)
        self.assertEqual(render_frame(state, tick=3), render_frame(state, tick=3))


class PollSchedulingTests(unittest.TestCase):
    def test_ticks_per_poll_divides_poll_interval_by_tick_interval(self):
        self.assertEqual(ticks_per_poll(poll_seconds=2.0, tick_seconds=0.25), 8)

    def test_ticks_per_poll_is_never_less_than_one(self):
        self.assertEqual(ticks_per_poll(poll_seconds=0.1, tick_seconds=1.0), 1)

    def test_tick_zero_is_always_a_poll_tick(self):
        self.assertTrue(is_poll_tick(0, poll_every=8))

    def test_non_multiple_tick_is_not_a_poll_tick(self):
        self.assertFalse(is_poll_tick(3, poll_every=8))

    def test_multiple_of_poll_every_is_a_poll_tick(self):
        self.assertTrue(is_poll_tick(16, poll_every=8))


if __name__ == "__main__":
    unittest.main()
