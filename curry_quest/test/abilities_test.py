import unittest
from unittest.mock import patch, Mock
from curry_quest.abilities import BreakObstaclesAbility, PlayTheFluteAbility, HypnotismAbility, BrainwashAbility,\
    BarkLoudlyAbility, SpinAbility
from curry_quest.config import Config
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
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
        self._familiar = Unit(unit_traits, self._config.levels)
        self._familiar.name = 'Familiar'
        self._state_machine_context.familiar = self._familiar
        self._enemy = Unit(unit_traits, self._config.levels)
        self._enemy.name = 'Enemy'
        self._state_machine_context.start_battle(self._enemy)
        self._action_context = UnitActionContext()
        self._action_context.state_machine_context = self._state_machine_context

    def _call_select_target(self, caster, other_unit):
        return self._sut.select_target(caster, other_unit)

    def _call_can_use(self):
        return self._sut.can_use(self._action_context)

    def _call_use(self):
        return self._sut.use(self._action_context)

    def _test_use_ability(self, performer=None, target=None, other_than_target=None):
        self._action_context.performer = performer or self._familiar
        self._action_context.target = target or self._enemy
        return self._call_use()


class CanAlwaysUseTester:
    def test_can_use(self):
        self.assertEqual(self._call_can_use(), (True, ''))


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


def create_static_success_chance_tester(success_chance):
    class StaticSuccessChanceTester:
        def test_success_chance(self):
            self._test_use_ability()
            self._does_action_succeed_mock.assert_called_once_with(success_chance)

        def test_response_when_action_fails(self):
            self._does_action_succeed_mock.return_value = False
            self.assertEqual(self._test_use_ability(), 'It has no effect.')

    return StaticSuccessChanceTester


def create_status_immunity_tester(status, protective_talent):
    class StatusImmunityTester:
        def test_status_immunity_on_enemy(self):
            self._enemy._talents = protective_talent
            self._test_use_ability(target=self._enemy)
            self.assertFalse(self._enemy.has_status(status))

        def test_status_immunity_on_familiar(self):
            self._familiar._talents = protective_talent
            self._test_use_ability(target=self._familiar)
            self.assertFalse(self._familiar.has_status(status))

        def test_response_when_used_on_enemy_and_enemy_is_immune(self):
            self._enemy._talents = protective_talent
            self.assertEqual(self._test_use_ability(target=self._enemy), 'Enemy is immune.')

        def test_response_when_used_on_familiar_and_familiar_is_immune(self):
            self._familiar._talents = protective_talent
            self.assertEqual(self._test_use_ability(target=self._familiar), 'You are immune.')

    return StatusImmunityTester


def create_applied_status_tester(
        status: Statuses,
        enemy_target_response: str,
        familiar_target_response: str):
    class AppliedStatusTester:
        def test_when_used_on_enemy_then_it_gets_confuse_status_for_16_turns(self):
            self._test_use_ability(target=self._enemy)
            self.assertFalse(self._familiar.has_any_status())
            self.assertTrue(self._enemy.has_status(status))

        def test_when_used_on_familiar_then_it_gets_confuse_status_for_16_turns(self):
            self._test_use_ability(target=self._familiar)
            self.assertFalse(self._enemy.has_any_status())
            self.assertTrue(self._familiar.has_status(status))

        def test_response_when_used_on_enemy(self):
            self.assertEqual(self._test_use_ability(target=self._enemy), enemy_target_response)

        def test_response_when_used_on_familiar(self):
            self.assertEqual(self._test_use_ability(target=self._familiar), familiar_target_response)

    return AppliedStatusTester


def create_applied_timed_status_tester(
        status: Statuses,
        duration: int,
        enemy_target_response: str,
        familiar_target_response: str):
    class AppliedTimedStatusTester:
        def test_when_used_on_enemy_then_it_gets_confuse_status_for_16_turns(self):
            self._test_use_ability(target=self._enemy)
            self.assertFalse(self._familiar.has_any_status())
            self.assertEqual(self._enemy.status_duration(status), {status: duration})

        def test_when_used_on_familiar_then_it_gets_confuse_status_for_16_turns(self):
            self._test_use_ability(target=self._familiar)
            self.assertFalse(self._enemy.has_any_status())
            self.assertEqual(self._familiar.status_duration(status), {status: duration})

        def test_response_when_used_on_enemy(self):
            self.assertEqual(self._test_use_ability(target=self._enemy), enemy_target_response)

        def test_response_when_used_on_familiar(self):
            self.assertEqual(self._test_use_ability(target=self._familiar), familiar_target_response)

    return AppliedTimedStatusTester


class BreakObstaclesAbilityTest(
        create_ability_tester_class(
            mp_cost=4,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester):
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


class PlayTheFluteAbilityTest(
        create_ability_tester_class(
            mp_cost=4,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester,
        create_status_immunity_tester(status=Statuses.Seal, protective_talent=Talents.SpellProof),
        create_applied_status_tester(
            status=Statuses.Seal,
            enemy_target_response='Enemy\'s magic is sealed.',
            familiar_target_response='Your magic is sealed.')):
    def _create_ability(self):
        return PlayTheFluteAbility()


class HypnotismAbilityTest(
        create_ability_tester_class(
            mp_cost=12,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester,
        create_static_success_chance_tester(0.5),
        create_status_immunity_tester(status=Statuses.Sleep, protective_talent=Talents.SleepProof),
        create_applied_timed_status_tester(
            status=Statuses.Sleep,
            duration=16,
            enemy_target_response='Enemy is put to sleep.',
            familiar_target_response='You are put to sleep.')):
    def _create_ability(self):
        return HypnotismAbility()


class BrainwashAbilityTest(
        create_ability_tester_class(
            mp_cost=16,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester,
        create_static_success_chance_tester(0.25),
        create_status_immunity_tester(status=Statuses.Confuse, protective_talent=Talents.Unbrainwashable),
        create_applied_timed_status_tester(
            status=Statuses.Confuse,
            duration=16,
            enemy_target_response='Enemy is confused.',
            familiar_target_response='You are confused.')):
    def _create_ability(self):
        return BrainwashAbility()


class BarkLoudlyAbilityTest(
        create_ability_tester_class(
            mp_cost=8,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester,
        create_static_success_chance_tester(0.125),
        create_status_immunity_tester(status=Statuses.Paralyze, protective_talent=Talents.BarkProof),
        create_applied_timed_status_tester(
            status=Statuses.Paralyze,
            duration=4,
            enemy_target_response='Enemy is paralyzed.',
            familiar_target_response='You are paralyzed.')):
    def _create_ability(self):
        return BarkLoudlyAbility()


class SpinAbilityTest(
        create_ability_tester_class(
            mp_cost=8,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester,
        create_static_success_chance_tester(0.25),
        create_status_immunity_tester(status=Statuses.Confuse, protective_talent=Talents.ConfusionProof),
        create_applied_timed_status_tester(
            status=Statuses.Confuse,
            duration=4,
            enemy_target_response='Enemy is confused.',
            familiar_target_response='You are confused.')):
    def _create_ability(self):
        return SpinAbility()


if __name__ == '__main__':
    unittest.main()
