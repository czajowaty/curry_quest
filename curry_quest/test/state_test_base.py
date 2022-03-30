from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.levels_config import Levels
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.unit import Unit
from curry_quest.unit_traits import UnitTraits
from random import Random
import unittest
from unittest.mock import Mock


class StateTestBase(unittest.TestCase):
    def setUp(self):
        self._game_config = Config()
        for level in range(100):
            self._game_config.levels.add_level(level * 10)
        self._context = StateMachineContext(self._game_config)
        self._rng = Mock()
        self._rng.getstate.return_value = Random().getstate()
        self._context._rng = self._rng
        self._context.random_selection_with_weights = Mock(side_effect=self._select_key_with_greatest_value)
        self._responses = []
        self._context.add_response = Mock(side_effect=lambda response: self._responses.append(response))
        self._context.generate_action = Mock()
        self._context.generate_delayed_action = Mock()
        self._familiar_unit_traits = UnitTraits()
        self._familiar = Unit(self._familiar_unit_traits, Levels())
        self._familiar.name = 'Familiar'
        self._context.familiar = self._familiar

    def _select_key_with_greatest_value(self, d):
        selected_key, greatest_value = next(iter(d.items()))
        for key, value in d.items():
            if value > greatest_value:
                selected_key = key
                greatest_value = value
        return selected_key

    def _test_on_enter(self, *args):
        state = self._create_state(*args)
        state.on_enter()
        return state

    def _create_state(self, *args):
        return self._state_class().create(self._context, args)

    @classmethod
    def _state_class(cls):
        pass

    def _test_create_state_failure(self, *args):
        with self.assertRaises(InvalidOperation) as cm:
            self._create_state(*args)
        return cm.exception.args[0]

    def _assert_action(self, action, *args):
        self._context.generate_action.assert_called_once_with(action, *args)

    def _assert_delayed_action(self, delay, action, *args):
        self._context.generate_delayed_action.assert_called_once_with(delay, action, *args)

    def _assert_actions(self, *calls):
        self._context.generate_action.assert_has_calls(calls)

    def _assert_responses(self, *responses):
        self.assertEqual(self._responses, list(responses))

    def _assert_any_response(self, response):
        try:
            self._responses.index(response)
        except ValueError:
            self.fail(f'No response "{response}"')

    def _assert_does_not_have_response(self, response):
        try:
            self._responses.index(response)
            self.fail(f'Response "{response}" exists.')
        except ValueError:
            pass
