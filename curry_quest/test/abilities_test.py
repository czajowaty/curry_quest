import unittest
from unittest.mock import patch, Mock
from curry_quest.abilities import BreakObstaclesAbility
from curry_quest.config import Config
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit_traits import UnitTraits


class SelfTargetTester:
    def test_select_target(self):
        self.assertEqual(self._call_select_target('SELF', 'OTHER_UNIT'), 'SELF')


class OtherUnitTargetTester:
    def test_select_target(self):
        self.assertEqual(self._call_select_target('SELF', 'OTHER_UNIT'), 'OTHER_UNIT')


class AbilityTestBase(unittest.TestCase):
    def setUp(self):
        self._sut = self._create_ability()
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
        self._action_context = UnitActionContext()
        self._action_context.state_machine_context = self._state_machine_context

    def _call_select_target(self, caster, other_unit):
        return self._sut.select_target(caster, other_unit)

    def _call_use(self):
        return self._sut.use(self._action_context)

    def _test_use_ability(self, performer=None, target=None, other_than_target=None):
        self._action_context.performer = performer or self._familiar
        self._action_context.target = target or self._enemy
        return self._call_use()


def create_ability_tester_class(
        mp_cost,
        select_target_tester,
        can_target_self,
        can_target_other_unit,
        can_have_no_target):
    class AbilityTester(AbilityTestBase, select_target_tester):
        def test_mp_use(self):
            self.assertEqual(self._sut.mp_cost, mp_cost)

        def test_can_target_self(self):
            self.assertEqual(self._sut.can_target_self(), can_target_self)

        def test_can_target_other_unit(self):
            self.assertEqual(self._sut.can_target_other_unit(), can_target_other_unit)

        def test_can_have_no_target(self):
            self.assertEqual(self._sut.can_have_no_target(), can_have_no_target)

    return AbilityTester


class BreakObstaclesAbilityTest(
        create_ability_tester_class(
            mp_cost=4,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True)):

    def _create_ability(self):
        return BreakObstaclesAbility()

    def _test_physical_attack_executor_args(self, attacker=None, defender=None, response=''):
        with patch('curry_quest.abilities.PhysicalAttackExecutor') as PhysicalAttackExecutorMock:
            physical_attack_executor_mock = PhysicalAttackExecutorMock.return_value
            physical_attack_executor_mock.execute.return_value = response
            response = self._test_use_ability(performer=attacker, target=defender)
            physical_attack_executor_mock.execute.assert_called_once()
            return response, physical_attack_executor_mock, PhysicalAttackExecutorMock.call_args.args

    def test_break_obstacles_returns_response_from_PhysicalAttackExecutor(self):
        response, _, _ = self._test_physical_attack_executor_args(response='Ability used.')
        self.assertEqual(response, 'Ability used.')

    def test_break_obstacles_PhysicalAttackExecutor_creation_args(self):
        _, _, creation_args = self._test_physical_attack_executor_args()
        self.assertEqual(creation_args, (self._action_context,))

    def test_break_obstacles_uses_attacker_attack_stat_multiplied_by_1_5_as_weapon_damage(self):
        self._familiar.attack = 18
        self._enemy.attack = 6
        _, physical_attack_executor_mock, _ = self._test_physical_attack_executor_args(
            attacker=self._enemy,
            defender=self._familiar)
        physical_attack_executor_mock.set_weapon_damage.assert_called_with(9)


if __name__ == '__main__':
    unittest.main()
