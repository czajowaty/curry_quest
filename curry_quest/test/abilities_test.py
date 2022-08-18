import inspect
import unittest
from unittest.mock import patch, Mock
from curry_quest.ability import Ability
from curry_quest.abilities import AbilityWithSuccessChance, ApplyStatusAbility, ApplyTimedStatusAbility, \
    BreakObstaclesAbility, PlayTheFluteAbility, HypnotismAbility, BrainwashAbility, BarkLoudlyAbility, SpinAbility, \
    DisappearAbility, GetSeriousAbility, AbductAbility, ChargedPunchAbility, FlyAbility, StealAbility, Abilities
from curry_quest.config import Config
import curry_quest.items as items
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
        self._inventory = self._state_machine_context.inventory
        self._enemy = Unit(unit_traits, self._config.levels)
        self._enemy.name = 'Enemy'
        self._state_machine_context.start_battle(self._enemy)
        self._action_context = UnitActionContext()
        self._action_context.state_machine_context = self._state_machine_context
        self._battle_context = self._state_machine_context.battle_context

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
        def test_when_used_on_enemy_then_it_gets_timed_status(self):
            self._test_use_ability(target=self._enemy)
            self.assertFalse(self._familiar.has_any_status())
            self.assertEqual(self._enemy.status_duration(status), {status: duration})

        def test_when_used_on_familiar_then_it_gets_timed_status(self):
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


class DisappearAbilityTest(
        create_ability_tester_class(
            mp_cost=8,
            select_target_tester=SelfTargetTester,
            can_target_self=True,
            can_target_other_unit=False,
            can_have_no_target=False),
        create_applied_timed_status_tester(
            status=Statuses.Invisible,
            duration=8,
            enemy_target_response='Enemy disappears.',
            familiar_target_response='You disappear.')):
    def _create_ability(self):
        return DisappearAbility()

    def test_when_target_has_invisible_status_then_cannot_use(self):
        self._action_context.target = self._enemy
        self._enemy.set_status(Statuses.Invisible)
        can_use, _ = self._call_can_use()
        self.assertFalse(can_use)

    def test_when_user_does_not_have_invisible_status_then_can_use(self):
        self._action_context.target = self._enemy
        self._enemy.clear_statuses()
        can_use, _ = self._call_can_use()
        self.assertTrue(can_use)


class GetSeriousAbilityTest(
        create_ability_tester_class(
            mp_cost=16,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester):
    def _create_ability(self):
        return GetSeriousAbility()

    def _test_physical_attack_executor_args(self, attacker=None, defender=None, response=''):
        with patch('curry_quest.abilities.PhysicalAttackExecutor') as PhysicalAttackExecutorMock:
            physical_attack_executor_mock = PhysicalAttackExecutorMock.return_value
            physical_attack_executor_mock.execute.return_value = response
            response = self._test_use_ability(performer=attacker, target=defender)
            physical_attack_executor_mock.execute.assert_called_once()
            return response, physical_attack_executor_mock, PhysicalAttackExecutorMock.call_args.args

    def test_GetSerious_returns_response_from_PhysicalAttackExecutor(self):
        response, _, _ = self._test_physical_attack_executor_args(response='Ability used.')
        self.assertEqual(response, 'Ability used.')

    def test_GetSerious_PhysicalAttackExecutor_creation_args(self):
        _, _, creation_args = self._test_physical_attack_executor_args()
        self.assertEqual(creation_args, (self._action_context,))

    def test_GetSerious_guarantees_critical_hit(self):
        _, physical_attack_executor_mock, _ = self._test_physical_attack_executor_args(
            attacker=self._enemy,
            defender=self._familiar)
        physical_attack_executor_mock.set_guaranteed_critical.assert_called()


class AbductAbilityTest(
        create_ability_tester_class(
            mp_cost=8,
            select_target_tester=SelfTargetTester,
            can_target_self=True,
            can_target_other_unit=False,
            can_have_no_target=False)):
    def _create_ability(self):
        return AbductAbility()

    def test_when_used_by_enemy_then_cannot_use(self):
        self._action_context.performer = self._enemy
        can_use, _ = self._call_can_use()
        self.assertFalse(can_use)

    def test_when_used_by_familiar_then_can_use(self):
        self._action_context.performer = self._familiar
        can_use, _ = self._call_can_use()
        self.assertTrue(can_use)

    def _test_use_ability(self):
        return super()._test_use_ability(performer=self._familiar, target=self._familiar)

    def test_ability_finishes_the_battle_without_killing_an_enemy(self):
        self._test_use_ability()
        self.assertFalse(self._battle_context.enemy.is_dead())
        self.assertTrue(self._battle_context.is_finished())

    def test_ability_response_when_used_by_familiar(self):
        self.assertEqual(self._test_use_ability(), 'You teleport away from the battle.')


class ChargedPunchAbilityTest(
        create_ability_tester_class(
            mp_cost=8,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester):
    def _create_ability(self):
        return ChargedPunchAbility()

    def _test_physical_attack_executor_args(self, attacker=None, defender=None, response=''):
        with patch('curry_quest.abilities.PhysicalAttackExecutor') as PhysicalAttackExecutorMock:
            physical_attack_executor_mock = PhysicalAttackExecutorMock.return_value
            physical_attack_executor_mock.execute.return_value = response
            response = self._test_use_ability(performer=attacker, target=defender)
            physical_attack_executor_mock.execute.assert_called_once()
            return response, physical_attack_executor_mock, PhysicalAttackExecutorMock.call_args.args

    def test_ChargedPunch_returns_response_from_PhysicalAttackExecutor(self):
        response, _, _ = self._test_physical_attack_executor_args(response='Ability used.')
        self.assertEqual(response, 'Ability used.')

    def test_ChargedPunch_PhysicalAttackExecutor_creation_args(self):
        _, _, creation_args = self._test_physical_attack_executor_args()
        self.assertEqual(creation_args, (self._action_context,))

    def test_ChargedPunch_uses_8_as_weapon_damage(self):
        _, physical_attack_executor_mock, _ = self._test_physical_attack_executor_args(
            attacker=self._enemy,
            defender=self._familiar)
        physical_attack_executor_mock.set_weapon_damage.assert_called_with(8)


class FlyAbilityTest(
        create_ability_tester_class(
            mp_cost=16,
            select_target_tester=SelfTargetTester,
            can_target_self=True,
            can_target_other_unit=False,
            can_have_no_target=False)):
    def _create_ability(self):
        return FlyAbility()

    def test_when_used_by_enemy_then_cannot_use(self):
        self._action_context.performer = self._enemy
        can_use, _ = self._call_can_use()
        self.assertFalse(can_use)

    def test_when_used_by_familiar_with_level_same_as_floor_then_cannot_use(self):
        self._familiar.level = 5
        self._state_machine_context.floor = 5
        self._action_context.performer = self._familiar
        can_use, _ = self._call_can_use()
        self.assertFalse(can_use)

    def test_when_used_by_familiar_with_level_higher_than_floor_then_can_use(self):
        self._familiar.level = 5
        self._state_machine_context.floor = 4
        self._action_context.performer = self._familiar
        can_use, _ = self._call_can_use()
        self.assertTrue(can_use)

    def _test_use_ability(self):
        return super()._test_use_ability(performer=self._familiar, target=self._familiar)

    def test_ability_finishes_the_battle_without_killing_an_enemy_and_sets_the_flag_to_go_to_next_floor(self):
        self._test_use_ability()
        self.assertFalse(self._battle_context.enemy.is_dead())
        self.assertTrue(self._battle_context.is_finished())
        self.assertTrue(self._state_machine_context.should_go_up_on_next_event_finished())

    def test_ability_response_when_used_by_familiar(self):
        self.assertEqual(self._test_use_ability(), 'You fly up to the next floor.')


class StealAbilityTest(
        create_ability_tester_class(
            mp_cost=2,
            select_target_tester=OtherUnitTargetTester,
            can_target_self=False,
            can_target_other_unit=True,
            can_have_no_target=True),
        CanAlwaysUseTester):
    def _create_ability(self):
        return StealAbility()

    def test_response_when_used_on_enemy(self):
        self.assertEqual(
            self._test_use_ability(performer=self._familiar, target=self._enemy),
            'Enemy has nothing to steal.')

    def test_response_when_used_on_familiar_and_inventory_is_empty(self):
        self.assertEqual(
            self._test_use_ability(performer=self._enemy, target=self._familiar),
            'You have nothing to steal.')

    def test_response_when_used_on_familiar_and_item_is_stolen(self):
        self._inventory.add_item(items.FireBall())
        self._inventory.add_item(items.WindSeed())
        self._inventory.add_item(items.MedicinalHerb())
        self._rng.randrange.return_value = 1
        self.assertEqual(
            self._test_use_ability(performer=self._enemy, target=self._familiar),
            'Enemy steals Wind Seed and runs away.')

    def test_ability_when_used_on_familiar_with_items_in_inventory_and_item_is_stolen(self):
        self._inventory.add_item(items.FireBall())
        self._inventory.add_item(items.WindSeed())
        self._inventory.add_item(items.MedicinalHerb())
        self._rng.randrange.return_value = 1
        self._test_use_ability(performer=self._enemy, target=self._familiar)
        self._rng.randrange.assert_called_once_with(5)
        self.assertEqual(self._inventory.size, 2)
        self.assertIsInstance(self._inventory.peek_item(0), items.FireBall)
        self.assertIsInstance(self._inventory.peek_item(1), items.MedicinalHerb)
        self.assertFalse(self._battle_context.enemy.is_dead())
        self.assertTrue(self._battle_context.is_finished())

    def test_ability_when_used_on_familiar_with_items_in_inventory_and_familiar_has_ImmuneToStealing_talent(self):
        self._familiar._talents = Talents.ImmuneToStealing
        self._inventory.add_item(items.FireBall())
        self._inventory.add_item(items.WindSeed())
        self._inventory.add_item(items.MedicinalHerb())
        self._rng.randrange.return_value = 1
        self._test_use_ability(performer=self._enemy, target=self._familiar)
        self.assertEqual(self._inventory.size, 3)

    def test_response_when_used_on_familiar_and_steal_fails(self):
        self._inventory.add_item(items.FireBall())
        self._inventory.add_item(items.WindSeed())
        self._inventory.add_item(items.MedicinalHerb())
        self._rng.randrange.return_value = 3
        self.assertEqual(
            self._test_use_ability(performer=self._enemy, target=self._familiar),
            'Enemy fails to steal anything.')

    def test_ability_when_used_on_familiar_with_items_in_inventory_and_steal_fails(self):
        self._inventory.add_item(items.FireBall())
        self._inventory.add_item(items.WindSeed())
        self._inventory.add_item(items.MedicinalHerb())
        self._rng.randrange.return_value = 3
        self._test_use_ability(performer=self._enemy, target=self._familiar)
        self._rng.randrange.assert_called_once_with(5)
        self.assertEqual(self._inventory.size, 3)
        self.assertIsInstance(self._inventory.peek_item(0), items.FireBall)
        self.assertIsInstance(self._inventory.peek_item(1), items.WindSeed)
        self.assertIsInstance(self._inventory.peek_item(2), items.MedicinalHerb)


class AbilitiesTest(unittest.TestCase):
    def test_all_abilities_can_be_found(self):
        def is_ability_class(cls):
            if not inspect.isclass(cls):
                return False
            if not issubclass(cls, Ability):
                return False
            return cls not in [Ability, AbilityWithSuccessChance, ApplyStatusAbility, ApplyTimedStatusAbility]
        
        import curry_quest.abilities

        all_abilities = {cls().name: cls for _, cls in inspect.getmembers(curry_quest.abilities, is_ability_class)}
        for ability_name, ability_class in all_abilities.items():
            found_ability = Abilities.find_ability(ability_name)
            self.assertIsNotNone(found_ability, f'No ability found for "{ability_name}"')
            self.assertIsInstance(found_ability, ability_class)

    def test_when_ability_cannot_be_found_ValueError_is_raised(self):
        with self.assertRaises(ValueError):
            Abilities.find_ability('Unknown ability')


if __name__ == '__main__':
    unittest.main()
