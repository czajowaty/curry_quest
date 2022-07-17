import unittest
from unittest.mock import patch, Mock
from curry_quest.config import Config
from curry_quest.physical_attack_unit_action import PhysicalAttackUnitActionHandler
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.unit_traits import UnitTraits
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit import Unit


class PhysicalAttackUnitActionHandlerTest(unittest.TestCase):
    ACTION_MP_COST = 5

    def setUp(self):
        self._sut = PhysicalAttackUnitActionHandler(mp_cost=self.ACTION_MP_COST)
        self._config = Config()
        self._rng = Mock()
        self._rng.getstate.return_value = ''
        self._does_action_succeed_mock = Mock(return_value=True)
        self._state_machine_context = StateMachineContext(self._config)
        self._state_machine_context.does_action_succeed = self._does_action_succeed_mock
        self._state_machine_context._rng = self._rng
        unit_traits = UnitTraits()
        unit_traits.base_luck = 10
        unit_traits.base_hp = 30
        self._familiar = Unit(unit_traits, self._config.levels)
        self._state_machine_context.familiar = self._familiar
        self._enemy = Unit(unit_traits, self._config.levels)
        self._enemy.luck = 1
        self._state_machine_context.start_battle(self._enemy)
        self._unit_action_context = UnitActionContext()
        self._unit_action_context.state_machine_context = self._state_machine_context

    def _test_can_perform(self, performer):
        self._unit_action_context.performer = performer
        can_perform, response = self._sut.can_perform(self._unit_action_context)
        return can_perform, response

    def _test_whether_can_perform(self, performer):
        can_perform, _ = self._test_can_perform(performer)
        return can_perform

    def _test_can_perform_response(self, performer):
        _, response = self._test_can_perform(performer)
        return response

    def _set_unit_can_perform_action(self, performer):
        performer.mp = self.ACTION_MP_COST

    def _set_unit_cannot_perform_action(self, performer):
        performer.mp = self.ACTION_MP_COST - 1

    def test_when_unit_does_not_have_enough_mp_then_action_cannot_be_performed(self):
        self._set_unit_cannot_perform_action(self._familiar)
        self.assertFalse(self._test_whether_can_perform(performer=self._familiar))

    def test_when_unit_has_enough_mp_then_action_can_be_performed(self):
        self._set_unit_can_perform_action(self._familiar)
        self.assertTrue(self._test_whether_can_perform(performer=self._familiar))

    def test_familiar_cannot_perform_action_response(self):
        self._set_unit_cannot_perform_action(self._familiar)
        self.assertEqual(
            self._test_can_perform_response(performer=self._familiar),
            'You do not have enough MP.')

    def test_enemy_cannot_perform_action_response(self):
        self._enemy.name = 'monster'
        self._set_unit_cannot_perform_action(self._enemy)
        self.assertEqual(
            self._test_can_perform_response(performer=self._enemy),
            'Monster does not have enough MP.')

    def _call_perform(self):
        return self._sut.perform(self._unit_action_context)

    def _test_perform_action(self, performer=None, target=None, other_than_target=None):
        self._unit_action_context.performer = performer or self._familiar
        self._unit_action_context.target = target or self._enemy
        return self._call_perform()

    def _test_physical_attack_executor_args(self, attacker=None, defender=None, response=''):
        with patch('curry_quest.physical_attack_unit_action.PhysicalAttackExecutor') as PhysicalAttackExecutorMock:
            physical_attack_executor_mock = PhysicalAttackExecutorMock.return_value
            physical_attack_executor_mock.execute.return_value = response
            response = self._test_perform_action(performer=attacker, target=defender)
            physical_attack_executor_mock.execute.assert_called_once()
            return response, physical_attack_executor_mock, PhysicalAttackExecutorMock.call_args.args

    def test_performing_attack_returns_response_from_PhysicalAttackExecutor(self):
        response, _, _ = self._test_physical_attack_executor_args(response='Attack used.')
        self.assertEqual(response, 'Attack used.')

    def test_performing_attack_PhysicalAttackExecutor_creation_args(self):
        _, _, creation_args = self._test_physical_attack_executor_args()
        self.assertEqual(creation_args, (self._unit_action_context,))

    def test_when_action_is_performed_then_mp_is_consumed(self):
        self._familiar.max_mp = 15
        self._familiar.mp = 15
        self._test_physical_attack_executor_args(attacker=self._familiar, defender=self._enemy)
        self.assertEqual(self._familiar.mp, 10)


if __name__ == '__main__':
    unittest.main()
