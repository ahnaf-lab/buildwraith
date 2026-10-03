import unittest

from buildwraith.state import (
    BuildEvent,
    CreatureState,
    EventType,
    initial_state,
    reduce,
)


class InitialStateTests(unittest.TestCase):
    def test_starts_at_full_vitals(self):
        state = initial_state()
        self.assertEqual(state.health, 100)
        self.assertEqual(state.mood, 100)
        self.assertEqual(state.energy, 100)
        self.assertEqual(state.consecutive_failures, 0)
        self.assertEqual(state.consecutive_passes, 0)


class ReduceTests(unittest.TestCase):
    def test_is_pure_and_does_not_mutate_input(self):
        before = CreatureState(health=50, mood=50, energy=50)
        snapshot = CreatureState(**before.__dict__)

        reduce(before, BuildEvent(EventType.TEST_FAIL))

        self.assertEqual(before, snapshot)

    def test_test_pass_raises_health_mood_and_energy(self):
        state = CreatureState(health=50, mood=50, energy=50)
        after = reduce(state, BuildEvent(EventType.TEST_PASS))

        self.assertGreater(after.health, state.health)
        self.assertGreater(after.mood, state.mood)
        self.assertGreater(after.energy, state.energy)
        self.assertEqual(after.consecutive_passes, 1)
        self.assertEqual(after.consecutive_failures, 0)

    def test_test_fail_lowers_health_mood_and_energy(self):
        state = CreatureState(health=50, mood=50, energy=50)
        after = reduce(state, BuildEvent(EventType.TEST_FAIL))

        self.assertLess(after.health, state.health)
        self.assertLess(after.mood, state.mood)
        self.assertLess(after.energy, state.energy)
        self.assertEqual(after.consecutive_failures, 1)
        self.assertEqual(after.consecutive_passes, 0)

    def test_commit_costs_energy_but_lifts_mood(self):
        state = CreatureState(health=50, mood=50, energy=50)
        after = reduce(state, BuildEvent(EventType.COMMIT))

        self.assertEqual(after.health, state.health)
        self.assertGreater(after.mood, state.mood)
        self.assertLess(after.energy, state.energy)

    def test_idle_drains_energy_and_mood_slowly(self):
        state = CreatureState(health=50, mood=50, energy=50)
        after = reduce(state, BuildEvent(EventType.IDLE))

        self.assertEqual(after.health, state.health)
        self.assertLess(after.mood, state.mood)
        self.assertLess(after.energy, state.energy)

    def test_health_never_drops_below_zero(self):
        state = CreatureState(health=1, mood=1, energy=1)
        after = reduce(state, BuildEvent(EventType.TEST_FAIL))

        self.assertEqual(after.health, 0)
        self.assertEqual(after.mood, 0)
        self.assertEqual(after.energy, 0)

    def test_vitals_never_exceed_one_hundred(self):
        state = CreatureState(health=100, mood=100, energy=100)
        after = reduce(state, BuildEvent(EventType.TEST_PASS))

        self.assertEqual(after.health, 100)
        self.assertEqual(after.mood, 100)
        self.assertEqual(after.energy, 100)

    def test_longer_failure_streak_hurts_more(self):
        state = CreatureState(health=100, mood=100, energy=100)

        first_fail = reduce(state, BuildEvent(EventType.TEST_FAIL))
        single_drop = state.health - first_fail.health

        streaky = state
        for _ in range(5):
            streaky = reduce(streaky, BuildEvent(EventType.TEST_FAIL))
        fifth_fail = reduce(streaky, BuildEvent(EventType.TEST_FAIL))
        sixth_drop = streaky.health - fifth_fail.health

        self.assertGreater(sixth_drop, single_drop)

    def test_pass_streak_resets_on_failure(self):
        state = initial_state()
        state = reduce(state, BuildEvent(EventType.TEST_PASS))
        state = reduce(state, BuildEvent(EventType.TEST_PASS))
        self.assertEqual(state.consecutive_passes, 2)

        state = reduce(state, BuildEvent(EventType.TEST_FAIL))
        self.assertEqual(state.consecutive_passes, 0)
        self.assertEqual(state.consecutive_failures, 1)

    def test_transition_table_sequence(self):
        """A scripted sequence of events lands on an exact expected state."""
        state = initial_state()
        sequence = [
            EventType.TEST_FAIL,
            EventType.TEST_FAIL,
            EventType.COMMIT,
            EventType.TEST_PASS,
            EventType.IDLE,
        ]
        for event_type in sequence:
            state = reduce(state, BuildEvent(event_type))

        # health: 100 -> fail1 (-8-2=90) -> fail2 (-8-4=78) -> commit (78)
        #   -> pass (78+5=83) -> idle (83)
        self.assertEqual(state.health, 83)
        # mood: 100 -> fail1 (-12=88) -> fail2 (-12=76) -> commit (+2=78)
        #   -> pass (+10+1=89) -> idle (-1=88)
        self.assertEqual(state.mood, 88)
        # energy: 100 -> fail1 (-5=95) -> fail2 (-5=90) -> commit (-3=87)
        #   -> pass (+5=92) -> idle (-2=90)
        self.assertEqual(state.energy, 90)
        self.assertEqual(state.consecutive_failures, 0)
        self.assertEqual(state.consecutive_passes, 1)


if __name__ == "__main__":
    unittest.main()
