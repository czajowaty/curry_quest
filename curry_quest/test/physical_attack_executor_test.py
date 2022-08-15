import unittest
from unittest.mock import patch, Mock
from curry_quest.config import Config
from curry_quest.physical_attack_executor import PhysicalAttackExecutor, DamageRoll, RelativeHeight
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.unit_traits import UnitTraits
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit import Unit


class PhysicalAttackExecutorTest(unittest.TestCase):
    def setUp(self):
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
        self._sut = PhysicalAttackExecutor(self._unit_action_context)

    def _call_execute(self):
        return self._sut.execute()

    def _test_execute(self, performer=None, target=None, other_than_target=None):
        self._unit_action_context.performer = performer or self._familiar
        self._unit_action_context.target = target or self._enemy
        return self._call_execute()

    def _test_attack_miss(self, performer, target):
        performer.luck = 0
        return self._test_execute(performer, target)

    def test_response_on_no_target_familiar_attack(self):
        self._unit_action_context.performer = self._familiar
        self._unit_action_context.target = None
        response = self._call_execute()
        self.assertEqual(response, 'You attack in opposite direction hitting nothing but air.')

    def test_response_on_no_target_enemy_attack(self):
        self._enemy.name = 'monster'
        self._unit_action_context.performer = self._enemy
        self._unit_action_context.target = None
        response = self._call_execute()
        self.assertEqual(response, 'Monster attacks in opposite direction hitting nothing but air.')

    def test_when_attacker_has_0_luck_attack_misses(self):
        self._enemy.hp = 25
        self._test_attack_miss(performer=self._familiar, target=self._enemy)
        self.assertEqual(self._enemy.hp, 25)

    def test_response_on_familiar_attack_miss(self):
        self._enemy.name = 'Monster'
        response = self._test_attack_miss(performer=self._familiar, target=self._enemy)
        self.assertEqual(response, 'You try to hit Monster, but it dodges swiftly.')

    def test_response_on_monsetr_attack_miss(self):
        self._enemy.name = 'Monster'
        response = self._test_attack_miss(performer=self._enemy, target=self._familiar)
        self.assertEqual(response, 'Monster tries to hit you, but you dodge swiftly.')

    def _test_hit_accurracy(self, attacker, hit_accuracy):
        self._does_action_succeed_mock.return_value = False
        self._test_execute(performer=attacker)
        self._does_action_succeed_mock.assert_called_once_with(success_chance=hit_accuracy)

    def test_when_attacker_has_non_0_luck_then_hit_chance_is_based_on_attackers_luck(self):
        self._familiar.luck = 40
        self._test_hit_accurracy(attacker=self._familiar, hit_accuracy=39/40)

    def test_when_attacker_has_blind_status_then_hit_chance_is_cut_in_half(self):
        self._familiar.luck = 40
        self._familiar.set_status(Statuses.Blind)
        self._test_hit_accurracy(attacker=self._familiar, hit_accuracy=39/80)

    def test_when_defender_has_invisible_status_then_hit_chance_is_cut_in_half(self):
        self._familiar.luck = 40
        self._enemy.set_status(Statuses.Invisible)
        self._test_hit_accurracy(attacker=self._familiar, hit_accuracy=39/80)

    def test_when_attacker_has_blind_status_and_defender_has_invisible_status_then_hit_chance_reduction_is_stacked(self):
        self._familiar.luck = 40
        self._familiar.set_status(Statuses.Blind)
        self._enemy.set_status(Statuses.Invisible)
        self._test_hit_accurracy(attacker=self._familiar, hit_accuracy=39/160)

    def _test_damage_calculator_args(
            self,
            attacker=None,
            defender=None,
            damage_roll=DamageRoll.Normal,
            critical_hit=False,
            damage=0,
            does_action_succeed_additional_return_values=[]):
        does_action_succeed_return_value = [True, critical_hit]
        does_action_succeed_return_value.extend(does_action_succeed_additional_return_values)
        self._does_action_succeed_mock.side_effect = does_action_succeed_return_value
        with patch('curry_quest.physical_attack_executor.DamageCalculator') as DamageCalculatorMock:
            damage_calculator_mock = DamageCalculatorMock.return_value
            damage_calculator_mock.physical_damage.return_value = damage
            self._rng.choices.return_value = (damage_roll,)
            response = self._test_execute(performer=attacker, target=defender)
            damage_calculator_mock.physical_damage.assert_called_once()
            return response, DamageCalculatorMock.call_args.args, damage_calculator_mock.physical_damage.call_args.args

    def _test_damage_calculator_creation_args(self, *args, **kwargs):
        _, creation_args, _ = self._test_damage_calculator_args(*args, **kwargs)
        return creation_args

    def _test_damage_calculator_call_args(self, *args, **kwargs):
        _, _, call_args = self._test_damage_calculator_args(*args, **kwargs)
        return call_args

    def test_damage_calculator_is_created_with_correct_args(self):
        attacker, defender = self._test_damage_calculator_creation_args(attacker=self._enemy, defender=self._familiar)
        self.assertIs(attacker, self._enemy)
        self.assertIs(defender, self._familiar)

    def test_damage_roll_distribution(self):
        self._test_damage_calculator_args()
        self._rng.choices.assert_called_once()
        call_args = self._rng.choices.call_args
        damage_rolls, = call_args.args
        weights = call_args.kwargs['weights']
        self.assertEqual(len(damage_rolls), 3)
        self.assertEqual(len(weights), 3)
        self.assertEqual(
            dict(zip(damage_rolls, weights)),
            {
                DamageRoll.Low: 1,
                DamageRoll.Normal: 2,
                DamageRoll.High: 1
            })

    def test_selected_damage_roll_is_passed_to_calculate_damage(self):
        damage_roll, _, _, _ = self._test_damage_calculator_call_args(damage_roll=DamageRoll.High)
        self.assertEqual(damage_roll, DamageRoll.High)
        damage_roll, _, _, _ = self._test_damage_calculator_call_args(damage_roll=DamageRoll.Low)
        self.assertEqual(damage_roll, DamageRoll.Low)

    def test_when_unit_has_crack_status_relative_height_is_Lower(self):
        self._enemy.set_status(Statuses.Crack)
        _, relative_height, _, _ = self._test_damage_calculator_call_args(attacker=self._enemy, defender=self._familiar)
        self.assertEqual(relative_height, RelativeHeight.Lower)

    def test_when_unit_has_upheaval_status_relative_height_is_Higher(self):
        self._familiar.set_status(Statuses.Upheaval)
        _, relative_height, _, _ = self._test_damage_calculator_call_args(attacker=self._familiar, defender=self._enemy)
        self.assertEqual(relative_height, RelativeHeight.Higher)

    def test_when_unit_has_crack_and_upheaval_status_relative_height_is_Same(self):
        self._familiar.set_status(Statuses.Upheaval | Statuses.Crack)
        _, relative_height, _, _ = self._test_damage_calculator_call_args(attacker=self._familiar, defender=self._enemy)
        self.assertEqual(relative_height, RelativeHeight.Same)

    def test_when_unit_has_no_status_relative_height_is_Same(self):
        _, relative_height, _, _ = self._test_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Same)

    def test_is_critical_is_passed_to_calculate_damage(self):
        _, _, is_critical, _ = self._test_damage_calculator_call_args(critical_hit=False)
        self.assertFalse(is_critical)
        _, _, is_critical, _ = self._test_damage_calculator_call_args(critical_hit=True)
        self.assertTrue(is_critical)

    def test_set_guaranteed_critical_ensures_that_attack_is_critical(self):
        self._sut.set_guaranteed_critical()
        _, _, is_critical, _ = self._test_damage_calculator_call_args(critical_hit=False)
        self.assertTrue(is_critical)

    def test_weapon_damage(self):
        self._sut.set_weapon_damage(15)
        _, _, _, weapon_damage = self._test_damage_calculator_call_args(attacker=self._familiar, defender=self._enemy)
        self.assertEqual(weapon_damage, 15)

    def test_when_attack_hits_then_enemy_hp_is_decreased_by_damage(self):
        self._enemy.hp = 40
        self._test_damage_calculator_args(attacker=self._familiar, defender=self._enemy, damage=15, critical_hit=False)
        self.assertEqual(self._enemy.hp, 25)

    def test_when_attack_hits_then_attackers_hp_is_not_touched(self):
        self._familiar.hp = 30
        self._enemy.hp = 40
        self._test_damage_calculator_args(attacker=self._familiar, defender=self._enemy, damage=15, critical_hit=False)
        self.assertEqual(self._familiar.hp, 30)

    def test_when_defender_has_electric_shock_talent_then_attacker_takes_quarter_of_reflected_damage(self):
        self._familiar.hp = 30
        self._enemy._talents |= Talents.ElectricShock
        self._test_damage_calculator_args(attacker=self._familiar, defender=self._enemy, damage=15, critical_hit=False)
        self.assertEqual(self._familiar.hp, 27)

    def test_at_min_reflected_damage_is_1(self):
        self._familiar.hp = 30
        self._enemy._talents |= Talents.ElectricShock
        self._test_damage_calculator_args(attacker=self._familiar, defender=self._enemy, damage=1, critical_hit=False)
        self.assertEqual(self._familiar.hp, 29)

    def test_when_defender_has_sleep_status_then_it_may_be_recovered(self):
        self._enemy.set_timed_status(Statuses.Sleep, duration=4)
        self._test_damage_calculator_args(
            attacker=self._familiar,
            defender=self._enemy,
            does_action_succeed_additional_return_values=[True])
        self.assertFalse(self._enemy.has_status(Statuses.Sleep))

    def test_when_defender_has_sleep_status_then_it_may_not_be_recovered(self):
        self._enemy.set_timed_status(Statuses.Sleep, duration=4)
        self._test_damage_calculator_args(
            attacker=self._familiar,
            defender=self._enemy,
            does_action_succeed_additional_return_values=[False])
        self.assertTrue(self._enemy.has_status(Statuses.Sleep))

    def test_when_defender_has_paralyze_status_then_it_may_be_recovered(self):
        self._enemy.set_timed_status(Statuses.Paralyze, duration=4)
        self._test_damage_calculator_args(
            attacker=self._familiar,
            defender=self._enemy,
            does_action_succeed_additional_return_values=[True])
        self.assertFalse(self._enemy.has_status(Statuses.Paralyze))

    def test_when_defender_has_paralyze_status_then_it_may_not_be_recovered(self):
        self._enemy.set_timed_status(Statuses.Paralyze, duration=4)
        self._test_damage_calculator_args(
            attacker=self._familiar,
            defender=self._enemy,
            does_action_succeed_additional_return_values=[False])
        self.assertTrue(self._enemy.has_status(Statuses.Paralyze))

    def test_when_defender_has_confuse_status_then_it_may_be_recovered(self):
        self._enemy.set_timed_status(Statuses.Confuse, duration=4)
        self._test_damage_calculator_args(
            attacker=self._familiar,
            defender=self._enemy,
            does_action_succeed_additional_return_values=[True])
        self.assertFalse(self._enemy.has_status(Statuses.Confuse))

    def test_when_defender_has_confuse_status_then_it_may_not_be_recovered(self):
        self._enemy.set_timed_status(Statuses.Confuse, duration=4)
        self._test_damage_calculator_args(
            attacker=self._familiar,
            defender=self._enemy,
            does_action_succeed_additional_return_values=[False])
        self.assertTrue(self._enemy.has_status(Statuses.Confuse))

    def _test_attack_response(
            self,
            attacker,
            defender,
            damage,
            expected_response,
            critical_hit=False,
            does_action_succeed_additional_return_values=[]):
        self._familiar.hp = 30
        self._enemy.name = 'Monster'
        self._enemy.hp = 40
        response, _, _ = self._test_damage_calculator_args(
            attacker=attacker,
            defender=defender,
            damage=damage,
            critical_hit=critical_hit,
            does_action_succeed_additional_return_values=does_action_succeed_additional_return_values)
        self.assertEqual(response, expected_response)
        return response

    def _test_familiar_attack_response(self, response, **kwargs):
        return self._test_attack_response(
            attacker=self._familiar,
            defender=self._enemy,
            expected_response=response,
            **kwargs)

    def _test_enemy_attack_response(self, response, defender=None, **kwargs):
        return self._test_attack_response(
            attacker=self._enemy,
            defender=self._familiar,
            expected_response=response,
            **kwargs)

    def test_response_on_normal_familiar_attack(self):
        self._test_familiar_attack_response(damage=17, response='You hit dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_normal_enemy_attack(self):
        self._test_enemy_attack_response(damage=14, response='Monster hits dealing 14 damage. You have 16 HP left.')

    def test_response_on_critical_familiar_attack(self):
        self._test_familiar_attack_response(
            damage=17,
            critical_hit=True,
            response='You hit hard dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_critical_enemy_attack(self):
        self._test_enemy_attack_response(
            damage=17,
            critical_hit=True,
            response='Monster hits hard dealing 17 damage. You have 13 HP left.')

    def test_response_on_from_below_familiar_attack(self):
        self._familiar.set_status(Statuses.Crack)
        self._test_familiar_attack_response(
            damage=17,
            response='You hit from below dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_from_below_enemy_attack(self):
        self._familiar.set_status(Statuses.Upheaval)
        self._test_enemy_attack_response(
            damage=11,
            response='Monster hits from below dealing 11 damage. You have 19 HP left.')

    def test_response_on_from_above_familiar_attack(self):
        self._familiar.set_status(Statuses.Upheaval)
        self._test_familiar_attack_response(
            damage=18,
            response='You hit from above dealing 18 damage. Monster has 22 HP left.')

    def test_response_on_from_above_monster_attack(self):
        self._familiar.set_status(Statuses.Crack)
        self._test_enemy_attack_response(
            damage=5,
            response='Monster hits from above dealing 5 damage. You have 25 HP left.')

    def test_response_on_electric_shock_for_familiar_attack(self):
        self._enemy._talents |= Talents.ElectricShock
        self._test_familiar_attack_response(
            damage=24,
            response='You hit dealing 24 damage. Monster has 16 HP left. An electrical shock runs through your body '
            'dealing 6 damage. You have 24 HP left.')

    def test_response_on_electric_shock_for_enemy_attack(self):
        self._familiar._talents |= Talents.ElectricShock
        self._test_enemy_attack_response(
            damage=13,
            response='Monster hits dealing 13 damage. You have 17 HP left. An electrical shock runs through Monster\'s '
            'body dealing 3 damage. Monster has 37 HP left.')

    def _test_debuff_recovery_response_for_familiar_attack(
            self,
            debuff: Statuses,
            debuff_recovery_response: str,
            debuffs_number=1):
        self._enemy.set_timed_status(debuff, duration=4)
        self._test_familiar_attack_response(
            damage=5,
            does_action_succeed_additional_return_values=[True] * debuffs_number,
            response='You hit dealing 5 damage. Monster has 35 HP left.\n' + debuff_recovery_response)

    def _test_debuff_recovery_response_for_enemy_attack(
            self,
            debuff: Statuses,
            debuff_recovery_response: str,
            debuffs_number=1):
        self._familiar.set_timed_status(debuff, duration=4)
        self._test_enemy_attack_response(
            damage=5,
            does_action_succeed_additional_return_values=[True] * debuffs_number,
            response='Monster hits dealing 5 damage. You have 25 HP left.\n' + debuff_recovery_response)

    def test_response_on_sleep_recovery_for_familiar_attack(self):
        self._test_debuff_recovery_response_for_familiar_attack(Statuses.Sleep, 'Monster wakes up.')

    def test_response_on_sleep_recovery_for_enemy_attack(self):
        self._test_debuff_recovery_response_for_enemy_attack(Statuses.Sleep, 'You wake up.')

    def test_response_on_paralyze_recovery_for_familiar_attack(self):
        self._test_debuff_recovery_response_for_familiar_attack(Statuses.Paralyze, 'Monster\'s paralysis wears off.')

    def test_response_on_paralyze_recovery_for_enemy_attack(self):
        self._test_debuff_recovery_response_for_enemy_attack(Statuses.Paralyze, 'Your paralysis wears off.')

    def test_response_on_confuse_recovery_for_familiar_attack(self):
        self._test_debuff_recovery_response_for_familiar_attack(Statuses.Confuse, 'Monster is no longer confused.')

    def test_response_on_confuse_recovery_for_enemy_attack(self):
        self._test_debuff_recovery_response_for_enemy_attack(Statuses.Confuse, 'You are no longer confused.')

    def test_response_on_combined_debuffs_recovery_for_familiar_attack(self):
        self._test_debuff_recovery_response_for_familiar_attack(
            Statuses.Sleep | Statuses.Paralyze | Statuses.Confuse,
            'Monster wakes up.\nMonster\'s paralysis wears off.\nMonster is no longer confused.',
            debuffs_number=3)

    def test_response_on_combined_debuffs_recovery_for_enemy_attack(self):
        self._test_debuff_recovery_response_for_enemy_attack(
            Statuses.Sleep | Statuses.Paralyze | Statuses.Confuse,
            'You wake up.\nYour paralysis wears off.\nYou are no longer confused.',
            debuffs_number=3)


if __name__ == '__main__':
    unittest.main()
