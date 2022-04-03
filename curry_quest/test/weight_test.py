from curry_quest.config import Config
from curry_quest.levels_config import Levels
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.weight import FloorProgressionProratedWeight, LevelProratedWeight, StaticWeight, \
    NoWeightPenaltyHandler, StaticWeightPenaltyHandler, MaxWeightPenaltyHandler, WeightPenaltyHandler, WeightHandler
from curry_quest.unit import Unit
from curry_quest.unit_traits import UnitTraits
import unittest


class WeightTestBase(unittest.TestCase):
    def setUp(self):
        self._game_config = Config()
        self._context = StateMachineContext(self._game_config)

    def _call_sut(self):
        return self._sut.value(self._context)


class FloorProgressionProratedWeightTest(WeightTestBase):
    def setUp(self):
        super().setUp()
        self._game_config.eq_settings.floor_collapse_turn = 10
        self._sut = WeightHandler(FloorProgressionProratedWeight(min_weight=2, max_weight=200))

    def _set_turns_counter(self, value):
        self._context.reset_current_climb_records()
        self._context.floor = 1
        for _ in range(value):
            self._context.increase_turns_counter()

    def test_when_turn_counter_is_0_then_weight_is_min(self):
        self._set_turns_counter(0)
        self.assertEqual(self._call_sut(), 2)

    def test_when_floor_progression_is_0_then_weight_is_min(self):
        self._set_turns_counter(1)
        self.assertEqual(self._call_sut(), 2)

    def test_floor_progression_is_right_above_0(self):
        self._set_turns_counter(2)
        self.assertEqual(self._call_sut(), 27)

    def test_floor_progression_is_right_below_1(self):
        self._set_turns_counter(self._game_config.eq_settings.floor_collapse_turn - 2)
        self.assertEqual(self._call_sut(), 175)

    def test_when_floor_progression_is_1_then_weight_is_max(self):
        self._set_turns_counter(self._game_config.eq_settings.floor_collapse_turn - 1)
        self.assertEqual(self._call_sut(), 200)

    def test_when_turn_counter_is_at_floor_collapse_turn_then_weight_is_max(self):
        self._set_turns_counter(self._game_config.eq_settings.floor_collapse_turn)
        self.assertEqual(self._call_sut(), 200)


class LevelProratedWeightTest(WeightTestBase):
    def setUp(self):
        super().setUp()
        self._context.familiar = Unit(UnitTraits(), Levels())
        self._sut = WeightHandler(LevelProratedWeight(min_weight=10, max_weight=50, level_for_max_weight=15))

    def _set_level(self, value):
        self._context.familiar.level = value

    def test_when_level_is_0_then_weight_is_min(self):
        self._set_level(0)
        self.assertEqual(self._call_sut(), 10)

    def test_when_level_is_1_then_weight_is_min(self):
        self._set_level(1)
        self.assertEqual(self._call_sut(), 10)

    def test_level_is_2(self):
        self._set_level(2)
        self.assertEqual(self._call_sut(), 13)

    def test_level_is_14(self):
        self._set_level(14)
        self.assertEqual(self._call_sut(), 47)

    def test_when_level_is_15_then_weight_is_max(self):
        self._set_level(15)
        self.assertEqual(self._call_sut(), 50)

    def test_when_level_is_above_15_then_weight_is_max(self):
        self._set_level(16)
        self.assertEqual(self._call_sut(), 50)


class WeightPenaltyHandlerTestBase(WeightTestBase):
    def setUp(self):
        super().setUp()
        self._sut = WeightHandler(StaticWeight(10))


class WeightPenaltyHandlerTest(WeightPenaltyHandlerTestBase):
    class DummyPenaltyHandler(WeightPenaltyHandler):
        def __init__(self):
            self.weight_with_penalty = 0
            self._penalty_duration = 0

        def apply_penalty(self, value) -> int:
            return self.weight_with_penalty

        @property
        def penalty_duration(self) -> int:
            return self._penalty_duration

        def set_penalty_duration(self, value):
            self._penalty_duration = value

    def setUp(self):
        super().setUp()
        self._penalty_handler = self.DummyPenaltyHandler()
        self._sut.set_penalty_handler(self._penalty_handler)

    def test_penalty_is_applied_while_weight_has_penalty(self):
        self._penalty_handler.weight_with_penalty = 3
        self._penalty_handler.set_penalty_duration(4)
        self._sut.set_penalty()
        self.assertEqual(self._call_sut(), 3)
        self._sut.decrease_penalty_timer()
        self.assertEqual(self._call_sut(), 3)
        self._sut.decrease_penalty_timer()
        self.assertEqual(self._call_sut(), 3)
        self._sut.decrease_penalty_timer()
        self.assertEqual(self._call_sut(), 3)
        self._sut.decrease_penalty_timer()
        self.assertEqual(self._call_sut(), 10)

    def test_penalty_is_not_applied_after_being_cleared(self):
        self._penalty_handler.weight_with_penalty = 3
        self._penalty_handler.set_penalty_duration(4)
        self._sut.set_penalty()
        self._sut.clear_penalty()
        self.assertEqual(self._call_sut(), 10)


class NoWeightPenaltyHandlerTest(WeightPenaltyHandlerTestBase):
    def setUp(self):
        super().setUp()
        self._sut.set_penalty_handler(NoWeightPenaltyHandler())

    def test_weight_with_penalty(self):
        self._sut.set_penalty()
        self.assertEqual(self._call_sut(), 10)


class StaticWeightPenaltyHandlerTest(WeightPenaltyHandlerTestBase):
    def setUp(self):
        super().setUp()
        self._sut.set_penalty_handler(StaticWeightPenaltyHandler(penalty=4, penalty_duration=1))

    def test_weight_with_penalty(self):
        self._sut.set_penalty()
        self.assertEqual(self._call_sut(), 6)


class MaxWeightPenaltyHandlerTest(WeightPenaltyHandlerTestBase):
    def setUp(self):
        super().setUp()
        self._sut.set_penalty_handler(MaxWeightPenaltyHandler(penalty_duration=1))

    def test_weight_with_penalty(self):
        self._sut.set_penalty()
        self.assertEqual(self._call_sut(), 0)


if __name__ == '__main__':
    unittest.main()
