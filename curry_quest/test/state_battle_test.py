import unittest
from unittest.mock import Mock, PropertyMock, call, create_autospec, patch
from curry_quest import commands
from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.items import Item
from curry_quest.levels_config import Levels
from curry_quest.physical_attack_unit_action import PhysicalAttackUnitActionHandler
from curry_quest.spell_cast_unit_action import SpellCastContext
from curry_quest.spell_handler import SpellHandler
from curry_quest.spell_traits import SpellTraits
from curry_quest.state_battle import StateBattleEvent, StateStartBattle, StateBattlePreparePhase, StateBattleApproach, \
    StateBattlePhase, StateEnemyStats, StateBattleSkipTurn, StateBattleAttack, StateBattleUseSpell, \
    StateBattleUseItem, StateBattleTryToFlee, StateBattleEnemyTurn, StateBattleConfusedUnitTurn
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit_traits import UnitTraits
from random import Random


def create_action_handler_mock(action_handler_mock_class, original_select_target, action_response):
    action_handler_mock = action_handler_mock_class()
    action_handler_mock.select_target.side_effect = original_select_target
    action_handler_mock.can_perform.return_value = True, ''
    action_handler_mock.perform.return_value = action_response
    return action_handler_mock


def create_physical_attack_handler_mock(action_handler_mock_class, action_response=''):
    def original_select_target(performer, other_unit):
        return PhysicalAttackUnitActionHandler(mp_cost=0).select_target(performer, other_unit)

    return create_action_handler_mock(action_handler_mock_class, original_select_target, action_response)


class StateBattleTestBase(unittest.TestCase):
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
        self._familiar_unit_traits = UnitTraits()
        self._familiar = Unit(self._familiar_unit_traits, Levels())
        self._familiar.name = 'Familiar'
        self._familiar.hp = 1
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

    def _assert_action(self, action, *args, **kwargs):
        self._context.generate_action.assert_called_once_with(action, *args, **kwargs)

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


class StateBattleEventTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleEvent

    def test_creating_fails_for_unknown_monster(self):
        self._game_config._monsters_traits['TestMonster'] = UnitTraits()
        error_message = self._test_create_state_failure('TestMonster2')
        self.assertEqual(error_message, 'Unknown monster')

    def test_creating_fails_when_monster_level_is_not_a_number(self):
        self._game_config._monsters_traits['TestMonster2'] = UnitTraits()
        error_message = self._test_create_state_failure('TestMonster2', 'a1')
        self.assertEqual(error_message, 'Monster level is not a number')

    def test_when_created_without_monster_traits_then_monster_is_created_for_current_floor(self):
        self._context.generate_floor_monster = Mock(return_value='MONSTER')
        self._context.floor = 7
        self._test_on_enter()
        self._context.generate_floor_monster.assert_called_once_with(floor=7)
        self._assert_action(commands.START_BATTLE, 'MONSTER')

    def test_when_created_with_monster_without_level_then_level_is_same_as_familiar(self):
        unit_traits = UnitTraits()
        self._game_config._monsters_traits['TestMonster'] = unit_traits
        self._context.familiar.level = 4
        self._test_on_enter('TestMonster')
        self._context.generate_action.assert_called_once()
        command, enemy = self._context.generate_action.call_args.args
        self.assertEqual(command, commands.START_BATTLE)
        self.assertIs(enemy.traits, unit_traits)
        self.assertEqual(enemy.level, 4)

    def test_when_created_with_monster_and_level_then_level_is_same_as_request(self):
        unit_traits = UnitTraits()
        self._game_config._monsters_traits['TestMonster'] = unit_traits
        self._test_on_enter('TestMonster', ' 15')
        self._context.generate_action.assert_called_once()
        command, enemy = self._context.generate_action.call_args.args
        self.assertEqual(command, commands.START_BATTLE)
        self.assertIs(enemy.traits, unit_traits)
        self.assertEqual(enemy.level, 15)


class StateStartBattleTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateStartBattle

    def setUp(self):
        super().setUp()
        self._enemy = Unit(UnitTraits(), Levels())

    def _test_on_enter(self):
        return super()._test_on_enter(self._enemy)

    def test_on_enter_responds_with_enemy_stats(self):
        self._enemy.level = 10
        self._enemy.name = 'Monster'
        self._enemy.hp = 76
        self._enemy.to_string = Mock(return_value='EnemyToString')
        self._test_on_enter()
        self._assert_responses('You encountered a LVL 10 Monster (76 HP).', 'EnemyToString.')

    def test_on_enter_starts_battle_prepare_phase(self):
        self._context.start_battle(Unit(UnitTraits(), Levels()))
        battle_context = self._context.battle_context
        battle_context.start_prepare_phase = Mock()
        self._context.start_battle = Mock()
        self._test_on_enter()
        self._context.start_battle.assert_called_once_with(self._enemy)
        battle_context.start_prepare_phase.assert_called_once_with(counter=3)

    def test_on_enter_proceeds_to_BattlePreparePhase_state(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_PREPARE_PHASE, True)


class StateBattleStartedTestBase(StateBattleTestBase):
    def setUp(self):
        super().setUp()
        self._enemy_unit_traits = UnitTraits()
        self._enemy = Unit(self._enemy_unit_traits, Levels())
        self._enemy.hp = 1
        self._context.start_battle(self._enemy)
        self._battle_context = self._context.battle_context


class StateBattlePreparePhaseTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattlePreparePhase

    def _test_on_enter(self, turn_used=True):
        return super()._test_on_enter(turn_used)

    def _set_prepare_phase_not_finished_after_next_turn(self):
        self._battle_context.start_prepare_phase(counter=2)

    def _set_prepare_phase_finished_after_next_turn(self):
        self._battle_context.start_prepare_phase(counter=1)

    def test_when_familiar_has_sleep_status_prepare_phase_is_finished_immediately(self):
        self._set_prepare_phase_not_finished_after_next_turn()
        self._familiar.set_status(Statuses.Sleep)
        self._test_on_enter()
        self._assert_action(commands.BATTLE_PREPARE_PHASE_FINISHED)

    def test_when_prepare_phase_is_finished_then_battle_prepare_phase_finished_action_is_generated(self):
        self._set_prepare_phase_finished_after_next_turn()
        self._test_on_enter()
        self._assert_action(commands.BATTLE_PREPARE_PHASE_FINISHED)

    def test_when_prepare_phase_is_not_finished_then_battle_prepare_phase_finished_action_is_not_generated(self):
        self._set_prepare_phase_not_finished_after_next_turn()
        self._test_on_enter()
        self._context.generate_action.assert_not_called()

    def test_when_familiar_does_not_have_sleep_status_and_prepare_phase_turn_is_used_then_prepare_phase_counter_is_decreased(self):  # pylint: disable=E501
        self._battle_context.dec_prepare_phase_counter = Mock()
        self._test_on_enter(turn_used=True)
        self._battle_context.dec_prepare_phase_counter.assert_called_once()

    def test_when_familiar_does_not_have_sleep_status_and_prepare_phase_turn_is_not_used_then_prepare_phase_counter_is_not_decreased(self):
        self._battle_context.dec_prepare_phase_counter = Mock()
        self._test_on_enter(turn_used=False)
        self._battle_context.dec_prepare_phase_counter.assert_not_called()

    def test_when_familiar_does_not_have_sleep_status_and_it_is_prepare_phase_then_proper_response_is_given(self):
        self._set_prepare_phase_not_finished_after_next_turn()
        self._test_on_enter()
        self._assert_responses('The enemy is close, but you still have time to prepare.')

    def test_when_familiar_does_not_have_sleep_status_and_it_is_not_prepare_phase_then_proper_response_is_given(self):
        self._battle_context.finish_prepare_phase()
        self._test_on_enter()
        self._assert_responses('The enemy approaches you. Time to battle!')

    def test_when_familiar_has_sleep_status_then_proper_response_is_given(self):
        self._familiar.set_status(Statuses.Sleep)
        self._test_on_enter()
        self._assert_responses('You are very sleepy. As you\'re nodding off, an enemy approaches you. Time to battle!')


class StateBattleApproachTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleApproach

    def test_on_enter_generates_battle_prepare_phase_finished_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_PREPARE_PHASE_FINISHED)

    def test_on_enter_calls_finish_prepare_phase(self):
        self._battle_context.start_prepare_phase(counter=2)
        self._test_on_enter()
        self.assertFalse(self._battle_context.is_prepare_phase())


class StateBattlePhaseTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattlePhase

    def _test_on_enter(self, battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=False):
        if battle_is_finished:
            self._battle_context.finish_battle()
        self._familiar.hp = 0 if is_familiar_dead else 1
        self._enemy.hp = 0 if is_enemy_dead else 1
        super()._test_on_enter()

    def _assert_battle_is_finished(self):
        self.assertIsNone(self._context.battle_context)

    def _assert_battle_is_not_finished(self):
        self.assertIsNotNone(self._context.battle_context)

    def _test_battle_not_finished(self, is_first_turn=False, is_player_turn=False):
        self._battle_context.is_first_turn = is_first_turn
        self._battle_context.is_player_turn = is_player_turn
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=False)

    def test_action_on_player_turn_when_battle_is_not_finished(self):
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._assert_action(commands.ENEMY_TURN)
        self.assertEqual(self._battle_context.turn_counter, 0)

    def test_action_on_first_player_turn_with_quick_familiar_and_non_quick_enemy_when_battle_is_not_finished(self):
        self._familiar._talents = Talents.Quick
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._assert_action(commands.PLAYER_TURN)
        self.assertEqual(self._battle_context.turn_counter, 1)

    def test_action_on_second_player_turn_with_quick_familiar_and_non_quick_enemy_when_battle_is_not_finished(self):
        self._familiar._talents = Talents.Quick
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._assert_actions(call(commands.PLAYER_TURN), call(commands.ENEMY_TURN))
        self.assertEqual(self._battle_context.turn_counter, 0)

    def test_action_on_player_turn_with_quick_familiar_and_quick_enemy_when_battle_is_not_finished(self):
        self._familiar._talents = Talents.Quick
        self._enemy._talents = Talents.Quick
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._assert_action(commands.ENEMY_TURN)
        self.assertEqual(self._battle_context.turn_counter, 0)

    def test_action_on_enemy_turn_when_battle_is_not_finished(self):
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=False)
        self._assert_action(commands.PLAYER_TURN)

    def test_action_on_player_turn_when_battle_is_started(self):
        self._test_battle_not_finished(is_first_turn=True, is_player_turn=True)
        self._assert_action(commands.PLAYER_TURN)
        self.assertFalse(self._battle_context.is_first_turn)

    def test_action_after_player_turn_when_enemy_is_confused(self):
        self._enemy.set_status(Statuses.Confuse)
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._assert_action(commands.CONFUSED_UNIT_TURN)

    def test_action_after_player_turn_when_player_is_confused(self):
        self._familiar.set_status(Statuses.Confuse)
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=True)
        self._assert_action(commands.ENEMY_TURN)

    def test_action_after_enemy_turn_when_player_is_confused(self):
        self._familiar.set_status(Statuses.Confuse)
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=False)
        self._assert_action(commands.CONFUSED_UNIT_TURN)

    def test_action_after_enemy_turn_when_enemy_is_confused(self):
        self._enemy.set_status(Statuses.Confuse)
        self._test_battle_not_finished(is_first_turn=False, is_player_turn=False)
        self._assert_action(commands.PLAYER_TURN)

    def test_response_when_holy_scroll_finishes(self):
        self._battle_context.set_holy_scroll_counter(1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('The Holy Scroll\'s beams dissipate.')

    def test_response_when_holy_scroll_does_not_finish(self):
        self._battle_context.set_holy_scroll_counter(2)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses()

    def test_holy_scroll_is_finished_after_enemy_turn_when_counter_is_1(self):
        self._battle_context.set_holy_scroll_counter(1)
        self.assertTrue(self._battle_context.is_holy_scroll_active())
        self._test_battle_not_finished(is_player_turn=False)
        self.assertFalse(self._battle_context.is_holy_scroll_active())

    def test_holy_scroll_is_not_finished_after_enemy_turn_when_counter_is_2(self):
        self._battle_context.set_holy_scroll_counter(2)
        self.assertTrue(self._battle_context.is_holy_scroll_active())
        self._test_battle_not_finished(is_player_turn=False)
        self.assertTrue(self._battle_context.is_holy_scroll_active())

    def test_holy_scroll_is_finished_after_two_enemy_turns_when_counter_is_2(self):
        self._battle_context.set_holy_scroll_counter(2)
        self.assertTrue(self._battle_context.is_holy_scroll_active())
        self._test_battle_not_finished(is_player_turn=False)
        self._test_battle_not_finished(is_player_turn=False)
        self.assertFalse(self._battle_context.is_holy_scroll_active())

    def test_holy_scroll_is_not_finished_after_1st_enemy_turn_when_counter_is_1_and_enemy_has_quick_status(self):
        self._enemy._talents = Talents.Quick
        self._battle_context.set_holy_scroll_counter(1)
        self.assertTrue(self._battle_context.is_holy_scroll_active())
        self._test_battle_not_finished(is_player_turn=False)
        self.assertTrue(self._battle_context.is_holy_scroll_active())

    def test_holy_scroll_is_finished_after_2nd_enemy_turn_when_counter_is_1_and_enemy_has_quick_status(self):
        self._enemy._talents = Talents.Quick
        self._battle_context.set_holy_scroll_counter(1)
        self.assertTrue(self._battle_context.is_holy_scroll_active())
        self._test_battle_not_finished(is_player_turn=False)
        self._test_battle_not_finished(is_player_turn=False)
        self.assertFalse(self._battle_context.is_holy_scroll_active())

    def test_holy_scroll_is_not_finished_after_player_turn_when_counter_is_1(self):
        self._battle_context.set_holy_scroll_counter(1)
        self.assertTrue(self._battle_context.is_holy_scroll_active())
        self._test_battle_not_finished(is_player_turn=True)
        self.assertTrue(self._battle_context.is_holy_scroll_active())

    def test_response_on_blind_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.Blind, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You are no longer blind.')

    def test_response_on_blind_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.Blind, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit is no longer blind.')

    def test_response_on_poison_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.Poison, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You are no longer poisoned.')

    def test_response_on_poison_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.Poison, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit is no longer poisoned.')

    def test_response_on_confuse_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.Confuse, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You are no longer confused.')

    def test_response_on_confuse_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.Confuse, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit is no longer confused.')

    def test_response_on_fire_protection_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.FireProtection, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You no longer have protection of fire.')

    def test_response_on_fire_protection_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.FireProtection, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit no longer has protection of fire.')

    def test_response_on_water_protection_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.WaterProtection, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You no longer have protection of water.')

    def test_response_on_water_protection_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.WaterProtection, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit no longer has protection of water.')

    def test_response_on_wind_protection_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.WindProtection, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You no longer have protection of wind.')

    def test_response_on_wind_protection_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.WindProtection, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit no longer has protection of wind.')

    def test_response_on_fire_reflect_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.FireReflect, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You no longer reflect fire spells.')

    def test_response_on_fire_reflect_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.FireReflect, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit no longer reflects fire spells.')

    def test_response_on_reflect_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.Reflect, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You no longer reflect spells.')

    def test_response_on_reflect_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.Reflect, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit no longer reflects spells.')

    def test_response_on_wind_reflect_status_clearing_for_familiar(self):
        self._familiar.set_timed_status(Statuses.WindReflect, duration=1)
        self._test_battle_not_finished(is_player_turn=False)
        self._assert_responses('You no longer reflect wind spells.')

    def test_response_on_wind_reflect_status_clearing_for_monster(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.WindReflect, duration=1)
        self._test_battle_not_finished(is_player_turn=True)
        self._assert_responses('Enemy_unit no longer reflects wind spells.')

    def test_on_status_clear_unit_does_no_longer_have_a_status(self):
        self._familiar.set_timed_status(Statuses.Confuse, duration=1)
        self.assertTrue(self._familiar.has_status(Statuses.Confuse))
        self._test_battle_not_finished(is_player_turn=False)
        self.assertFalse(self._familiar.has_status(Statuses.Confuse))

    def test_on_status_is_not_cleared_for_duration_greater_than_1(self):
        self._familiar.set_timed_status(Statuses.Confuse, duration=2)
        self.assertTrue(self._familiar.has_status(Statuses.Confuse))
        self._test_battle_not_finished(is_player_turn=False)
        self.assertTrue(self._familiar.has_status(Statuses.Confuse))
        self.assertEqual(self._familiar.status_duration(Statuses.Confuse), {Statuses.Confuse: 1})

    def _test_status_effect(self, is_familiar_next_one_to_act, familiar_hp=1, enemy_hp=1):
        self._battle_context.is_first_turn = False
        self._battle_context.is_player_turn = not is_familiar_next_one_to_act
        self._familiar.hp = familiar_hp
        self._enemy.hp = enemy_hp
        super()._test_on_enter()

    def test_poison_effect_on_familiar_response(self):
        self._familiar.max_hp = 40
        self._familiar.set_timed_status(Statuses.Poison, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=True, familiar_hp=20)
        self._assert_responses('You lose 3 HP. You have 17 HP left.')

    def test_poison_effect_on_monster_response(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.max_hp = 40
        self._enemy.set_timed_status(Statuses.Poison, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=False, enemy_hp=20)
        self._assert_responses('Enemy_unit loses 3 HP. It has 17 HP left.')

    def test_poison_damage(self):
        self._familiar.max_hp = 40
        self._familiar.set_timed_status(Statuses.Poison, duration=1)
        self._test_status_effect(is_familiar_next_one_to_act=True, familiar_hp=20)
        self.assertEqual(self._familiar.hp, 17)

    def test_poison_damage_is_capped_to_leave_at_least_1_hp(self):
        self._familiar.max_hp = 40
        self._familiar.set_timed_status(Statuses.Poison, duration=1)
        self._test_status_effect(is_familiar_next_one_to_act=True, familiar_hp=3)
        self.assertEqual(self._familiar.hp, 1)

    def test_poison_damage_is_not_done_when_hp_is_1(self):
        self._familiar.max_hp = 40
        self._familiar.set_timed_status(Statuses.Poison, duration=1)
        self._test_status_effect(is_familiar_next_one_to_act=True, familiar_hp=1)
        self.assertEqual(self._familiar.hp, 1)

    def test_poison_effect_response_when_hp_is_1(self):
        self._familiar.max_hp = 40
        self._familiar.set_timed_status(Statuses.Poison, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=True, familiar_hp=1)
        self._assert_responses()

    def test_sleep_effect_on_familiar_response(self):
        self._familiar.set_timed_status(Statuses.Sleep, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=True)
        self._assert_responses('You sleep through your turn.')

    def test_sleep_effect_on_enemy_response(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.Sleep, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=False)
        self._assert_responses('Enemy_unit sleeps through its turn.')

    def test_action_on_familiar_with_sleep_status(self):
        self._familiar.set_timed_status(Statuses.Sleep, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=True)
        self._assert_action(commands.SKIP_TURN)

    def test_action_on_enemy_with_sleep_status(self):
        self._enemy.set_timed_status(Statuses.Sleep, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=False)
        self._assert_action(commands.SKIP_TURN)

    def test_paralyze_effect_on_familiar_response(self):
        self._familiar.set_timed_status(Statuses.Paralyze, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=True)
        self._assert_responses('You are paralyzed. You skip a turn.')

    def test_paralyze_effect_on_enemy_response(self):
        self._enemy.name = 'enemy_unit'
        self._enemy.set_timed_status(Statuses.Paralyze, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=False)
        self._assert_responses('Enemy_unit is paralyzed. It skips a turn.')

    def test_action_on_familiar_with_paralyze_status(self):
        self._familiar.set_timed_status(Statuses.Paralyze, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=True)
        self._assert_action(commands.SKIP_TURN)

    def test_action_on_enemy_with_paralyze_status(self):
        self._enemy.set_timed_status(Statuses.Paralyze, duration=2)
        self._test_status_effect(is_familiar_next_one_to_act=False)
        self._assert_action(commands.SKIP_TURN)

    def test_action_when_battle_is_finished(self):
        self._test_on_enter(battle_is_finished=True, is_familiar_dead=False, is_enemy_dead=False)
        self._assert_action(commands.EVENT_FINISHED)

    def test_action_when_enemy_is_defeated(self):
        self._test_on_enter(is_familiar_dead=False, is_enemy_dead=True)
        self._assert_action(commands.EVENT_FINISHED)

    def test_action_when_familiar_died(self):
        self._test_on_enter(is_familiar_dead=False, is_enemy_dead=True)
        self._assert_action(commands.EVENT_FINISHED)

    def test_when_battle_is_finished_then_battle_is_finished(self):
        self._assert_battle_is_not_finished()
        self._test_on_enter(battle_is_finished=True, is_familiar_dead=False, is_enemy_dead=False)
        self._assert_battle_is_finished()

    def test_when_familiar_dies_then_battle_is_finished(self):
        self._assert_battle_is_not_finished()
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=True, is_enemy_dead=False)
        self._assert_battle_is_finished()

    def test_when_enemy_dies_then_battle_is_finished(self):
        self._assert_battle_is_not_finished()
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=True)
        self._assert_battle_is_finished()

    def test_when_battle_is_not_finished_then_battle_is_not_finished(self):
        self._assert_battle_is_not_finished()
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=False)
        self._assert_battle_is_not_finished()

    def test_when_battle_is_finished_then_familiar_statuses_are_cleared(self):
        self._familiar.set_status(Statuses.Paralyze)
        self._test_on_enter(battle_is_finished=True, is_familiar_dead=True)
        self.assertFalse(self._familiar.has_any_status())

    def test_response_when_battle_is_finished_and_familiar_has_status(self):
        self._familiar.set_status(Statuses.Paralyze)
        self._test_on_enter(battle_is_finished=True, is_familiar_dead=True)
        self._assert_any_response('All statuses have been cleared.')

    def test_response_when_battle_is_finished_and_familiar_does_not_have_status(self):
        self._familiar.set_status(Statuses(0))
        self._test_on_enter(battle_is_finished=True, is_familiar_dead=True)
        self._assert_does_not_have_response('All statuses have been cleared.')

    def test_response_when_you_die(self):
        self._test_on_enter(is_familiar_dead=True)
        self._assert_responses('You died...')

    def _test_enemy_defeated(self, is_familiar_max_level=False, gained_exp=0, has_familiar_leveled_up=False):
        self._enemy.name = 'Monster'
        self._familiar.is_max_level = Mock(return_value=is_familiar_max_level)
        self._familiar.gain_exp = Mock(return_value=has_familiar_leveled_up)
        with patch('curry_quest.state_battle.StatsCalculator') as StatsCalculatorMock:
            stats_calculator_mock = StatsCalculatorMock()
            stats_calculator_mock.given_experience.return_value = gained_exp
            self._test_on_enter(battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=True)
            return stats_calculator_mock, StatsCalculatorMock

    def test_when_monster_is_defeated_and_familiar_is_at_max_level_then_familiar_does_not_gain_exp(self):
        self._test_enemy_defeated(is_familiar_max_level=True, gained_exp=20)
        self._familiar.gain_exp.assert_not_called()

    def test_when_monster_with_same_level_as_familiar_is_defeated_then_familiar_gains_exp(self):
        self._familiar.level = 5
        self._enemy.level = 5
        self._test_enemy_defeated(is_familiar_max_level=False, gained_exp=20)
        self._familiar.gain_exp.assert_called_once_with(20)

    def test_when_monster_with_higher_level_than_familiar_is_defeated_then_familiar_gains_exp(self):
        self._familiar.level = 4
        self._enemy.level = 5
        self._test_enemy_defeated(is_familiar_max_level=False, gained_exp=20)
        self._familiar.gain_exp.assert_called_once_with(40)

    def test_response_on_enemy_defeat_when_familiar_is_max_level(self):
        self._test_enemy_defeated(is_familiar_max_level=True)
        self._assert_responses('You defeated the Monster.')

    def test_response_on_enemy_defeat_when_familiar_is_not_max_level_and_familiar_did_not_level_up(self):
        self._test_enemy_defeated(is_familiar_max_level=False, gained_exp=25, has_familiar_leveled_up=False)
        self._assert_responses('You defeated the Monster and gained 25 EXP.')

    def test_response_on_enemy_defeat_when_familiar_lower_level_than_enemy(self):
        self._familiar.level = 4
        self._enemy.level = 5
        self._test_enemy_defeated(is_familiar_max_level=False, gained_exp=25, has_familiar_leveled_up=False)
        self._assert_responses('You defeated the Monster and gained 50 EXP.')

    def test_response_on_enemy_defeat_when_familiar_is_not_max_level_and_familiar_leveled_up(self):
        self._familiar.stats_to_string = Mock(return_value='FAMILIAR STATS')
        self._test_enemy_defeated(is_familiar_max_level=False, gained_exp=25, has_familiar_leveled_up=True)
        self._assert_responses(
            'You defeated the Monster and gained 25 EXP. You leveled up! Your new stats - FAMILIAR STATS.')


class StateEnemyStatsTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateEnemyStats

    def test_on_enter_responds_with_enemy_stats(self):
        self._enemy.to_string = Mock(return_value='MonsterStats')
        self._test_on_enter()
        self._assert_responses('Enemy stats: MonsterStats.')

    def test_on_enter_generates_player_turn_action(self):
        self._test_on_enter()
        self._assert_action(commands.PLAYER_TURN)


class StateBattleSkipTurnTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleSkipTurn

    def test_on_enter_response(self):
        self._test_on_enter()
        self._assert_responses('You skip turn.')

    def test_on_enter_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)


class StateBattleAttackTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleAttack

    def setUp(self):
        super().setUp()
        self._enemy.name = 'Monster'
        self._familiar.name = 'Familiar'

    def test_creating_fails_when_familiar_does_not_have_enough_mp(self):
        self._familiar.mp = 5
        self._familiar_unit_traits.physical_attack_mp_cost = 6
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'You do not have enough MP.')

    def test_on_enter_generates_battle_action_performed_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def _test_on_enter(self, action_handler_perform_response=''):
        with patch('curry_quest.state_machine_context.PhysicalAttackUnitActionHandler') as ActionHandlerMock:
            action_handler_mock = create_physical_attack_handler_mock(
                ActionHandlerMock,
                action_response=action_handler_perform_response)
            super()._test_on_enter()
        action_handler_mock.perform.assert_called_once()
        return action_handler_mock.perform.call_args.args[0]

    def test_response(self):
        self._test_on_enter(action_handler_perform_response='Physical attack response.')
        self._assert_responses('Physical attack response.')

    def test_action_handler_args(self):
        action_context = self._test_on_enter()
        self.assertIs(action_context.performer, self._familiar)
        self.assertIs(action_context.target, self._enemy)
        self.assertIs(action_context.state_machine_context, self._context)


class StateBattleUseSpellTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleUseSpell

    def setUp(self):
        super().setUp()
        self._spell_cast_handler = Mock(spec=SpellHandler)
        self._spell_cast_handler.select_target.return_value = self._enemy
        self._spell_cast_handler.can_cast.return_value = True, ''
        self._spell_cast_handler.cast.return_value = ''
        self._spell_traits = SpellTraits()
        self._spell_traits.handler = self._spell_cast_handler
        self._familiar.set_spell(self._spell_traits, level=5)
        self._enemy.name = 'Monster'

    def test_creating_fails_when_familiar_does_not_have_spell(self):
        self._familiar.clear_spell()
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'You do not have a spell.')

    def test_creating_fails_when_familiar_does_not_have_enough_mp(self):
        self._familiar.mp = 5
        self._spell_traits.mp_cost = 6
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'You do not have enough MP.')

    def test_creating_fails_when_spell_cannot_be_casted(self):
        self._familiar.mp = 10
        self._spell_traits.mp_cost = 6
        self._spell_cast_handler.can_cast.return_value = False, 'CANNOT CAST'
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'CANNOT CAST')

    def _test_spell_cast(self):
        self._test_on_enter()
        self._spell_cast_handler.cast.assert_called_once()
        return self._spell_cast_handler.cast.call_args.args[0]

    def test_action_on_spell_cast(self):
        self._test_spell_cast()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_response_on_spell(self):
        self._spell_traits.name = 'FamiliarSpell'
        self._spell_cast_handler.cast.return_value = 'spell casted.'
        self._test_spell_cast()
        self._assert_responses('You cast FamiliarSpell on Monster. spell casted.')

    def test_mp_usage(self):
        self._familiar.mp = 10
        self._spell_traits.mp_cost = 6
        self._test_spell_cast()
        self.assertEqual(self._familiar.mp, 4)

    def test_spell_target(self):
        self._spell_cast_handler.select_target.return_value = self._familiar
        spell_cast_context = self._test_spell_cast()
        self.assertIs(spell_cast_context.target, self._familiar)


class StateBattleUseItemTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleUseItem

    def setUp(self):
        super().setUp()
        self._inventory = Mock()
        self._context._inventory = self._inventory
        self._item = Mock()
        self._item.can_use.return_value = (True, '')
        self._item.use.return_value = ''
        self._inventory.peek_item.return_value = self._item

    def _test_on_enter(self, item_index=0, is_prepare_phase=True, can_use_item=True, reason=''):
        self._inventory.find_item.return_value = (item_index, self._item)
        if is_prepare_phase:
            self._battle_context.start_prepare_phase(counter=2)
        self._item.can_use.return_value = (can_use_item, reason)
        return super()._test_on_enter('')

    def test_item_is_fetched_from_correct_inventory_index(self):
        self._test_on_enter(item_index=2)
        self._inventory.peek_item.assert_called_once_with(2)

    def test_response_when_item_cannot_be_used(self):
        type(self._item).name = PropertyMock(return_value='ItemName')
        self._test_on_enter(can_use_item=False, reason='Reason for not using.')
        self._assert_responses('You cannot use ItemName. Reason for not using.')

    def test_action_when_item_cannot_be_used_in_prepare_phase(self):
        self._test_on_enter(is_prepare_phase=True, can_use_item=False)
        self._assert_action(commands.CANNOT_USE_ITEM_PREPARE_PHASE, False)

    def test_action_when_item_cannot_be_used_in_battle_phase(self):
        self._test_on_enter(is_prepare_phase=False, can_use_item=False)
        self._assert_action(commands.CANNOT_USE_ITEM_BATTLE_PHASE)

    def test_response_when_item_can_be_used(self):
        self._item.use.return_value = 'Item used.'
        self._test_on_enter(can_use_item=True)
        self._assert_responses('Item used.')

    def test_item_is_used(self):
        self._test_on_enter(can_use_item=True)
        self._item.use.assert_called_once_with(self._context)

    def test_item_is_taken_from_inventory_when_used(self):
        self._test_on_enter(item_index=5, can_use_item=True)
        self._context.inventory.take_item.assert_called_once_with(5)

    def test_action_when_item_can_be_used_in_prepare_phase(self):
        self._test_on_enter(is_prepare_phase=True, can_use_item=True)
        self._assert_action(commands.BATTLE_PREPARE_PHASE_ACTION_PERFORMED, True)

    def test_action_when_item_can_be_used_in_battle_phase(self):
        self._test_on_enter(is_prepare_phase=False, can_use_item=True)
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)


class StateBattleTryToFleeTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleTryToFlee

    def _test_on_enter(self, flee_successful=False):
        self._context.does_action_succeed = Mock(return_value=flee_successful)
        super()._test_on_enter()

    def test_generated_action_when_not_paralyzed(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_generated_action_when_paralyzed(self):
        self._familiar.set_status(Statuses.Paralyze)
        self._test_on_enter()
        self._assert_action(commands.CANNOT_FLEE)

    def test_response_when_paralyzed(self):
        self._familiar.set_status(Statuses.Paralyze)
        self._test_on_enter()
        self._assert_responses('You are paralyzed and cannot flee.')

    def test_response_when_flee_is_successful(self):
        self._test_on_enter(flee_successful=True)
        self._assert_responses('You successfully flee from the battle.')

    def test_when_flee_is_successful_battle_is_finished(self):
        self._test_on_enter(flee_successful=True)
        self.assertTrue(self._battle_context.is_finished())

    def test_response_when_flee_is_not_successful(self):
        self._test_on_enter(flee_successful=False)
        self._assert_responses('You attempt to flee from battle, but your path is blocked!')

    def test_when_flee_is_not_successful_battle_is_not_finished(self):
        self._test_on_enter(flee_successful=False)
        self.assertFalse(self._battle_context.is_finished())


class StateBattleEnemyTurnTest(StateBattleStartedTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleEnemyTurn

    def setUp(self):
        super().setUp()
        self._enemy.name = 'Monster'
        self._enemy_action_weights = self._enemy.traits.action_weights

    def _create_spell_cast_context(self, caster: Unit, other_unit: Unit):
        spell_cast_context = SpellCastContext()
        spell_cast_context.caster = caster
        spell_cast_context.target = other_unit
        spell_cast_context.state_machine_context = self._context
        return spell_cast_context

    def _test_on_enter(self, is_holy_scroll_active=False):
        if is_holy_scroll_active:
            self._battle_context.set_holy_scroll_counter(1)
        return super()._test_on_enter()

    def test_on_enter_generates_battle_action_performed_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_response_when_holy_scroll_is_active(self):
        self._test_on_enter(is_holy_scroll_active=True)
        self._assert_responses('The field is engulfed in the Holy Scroll\'s beams. Monster cannot act.')

    def _test_physical_attack(self, action_handler_perform_response=''):
        with patch('curry_quest.state_machine_context.PhysicalAttackUnitActionHandler') as ActionHandlerMock:
            action_handler_mock = create_physical_attack_handler_mock(
                ActionHandlerMock,
                action_response=action_handler_perform_response)
            self._test_on_enter()
        action_handler_mock.perform.assert_called_once()
        return action_handler_mock.perform.call_args.args[0]

    def test_response_on_physical_attack(self):
        self._test_physical_attack(action_handler_perform_response='Physical attack response.')
        self._assert_responses('Physical attack response.')

    def test_action_handler_args_for_physical_attack(self):
        action_context = self._test_physical_attack()
        self.assertIs(action_context.performer, self._enemy)
        self.assertIs(action_context.target, self._familiar)
        self.assertIs(action_context.state_machine_context, self._context)

    def _test_spell_cast(self, spell_name='', spell_level=1, mp_cost=0, target=None, can_cast=True, cast_response=''):
        self._enemy_action_weights.physical_attack = 0
        self._enemy_action_weights.spell = 1
        self._enemy_action_weights.ability = 0
        spell_handler = create_autospec(spec=SpellHandler)
        spell_handler.can_cast.return_value = can_cast, ''
        spell_handler.select_target.return_value = target or self._familiar
        spell_handler.cast.return_value = cast_response
        self._prepare_enemys_spell(spell_name, spell_level, mp_cost, spell_handler)
        self._test_on_enter()
        return spell_handler

    def _prepare_enemys_spell(self, spell_name='', spell_level=1, mp_cost=0, spell_handler=None):
        spell_traits = SpellTraits()
        spell_traits.name = spell_name
        spell_traits.mp_cost = mp_cost
        spell_traits.handler = spell_handler
        self._enemy.set_spell(spell_traits, level=spell_level)

    def test_action_on_spell(self):
        self._test_spell_cast()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_response_on_spell(self):
        self._enemy.name = 'monster'
        self._familiar.hp = 30
        self._test_spell_cast(spell_name='MonsterSpell', cast_response='Casted a spell.')
        self._assert_responses('Monster casts MonsterSpell on you. Casted a spell.')

    def test_mp_usage(self):
        self._enemy.mp = 60
        self._test_spell_cast(mp_cost=14)
        self.assertEqual(self._enemy.mp, 46)

    def test_spell_cast_context_for_cast(self):
        cast_handler = self._test_spell_cast(spell_level=8, target=self._familiar)
        spell_cast_context = cast_handler.cast.call_args.args[0]
        self.assertIs(spell_cast_context.performer, self._enemy)
        self.assertIs(spell_cast_context.target, self._familiar)
        self.assertIs(spell_cast_context.state_machine_context, self._context)
        self.assertEqual(spell_cast_context.spell_level, 8)
        self.assertIs(spell_cast_context.reflected_target, self._enemy)

    def test_spell_cast_context_for_can_cast(self):
        spell_handler = self._test_spell_cast(spell_level=5, target=self._enemy)
        spell_cast_context = spell_handler.can_cast.call_args.args[0]
        self.assertIs(spell_cast_context.performer, self._enemy)
        self.assertIs(spell_cast_context.target, self._enemy)
        self.assertIs(spell_cast_context.state_machine_context, self._context)
        self.assertEqual(spell_cast_context.spell_level, 5)
        self.assertIs(spell_cast_context.reflected_target, self._familiar)

    def _test_enemy_action_selection(self, can_cast=True, spell_mp_cost=0):
        action_weights = []

        def select_enemy_action(actions_with_weights):
            _, greatest_weight = next(iter(actions_with_weights.items()))
            for index, (_, weight) in enumerate(actions_with_weights.items()):
                action_weights.append(weight)
                if weight > greatest_weight:
                    greatest_weight = weight
            return lambda: f'Action {index}'

        self._context.random_selection_with_weights.side_effect = select_enemy_action
        spell_handler = create_autospec(spec=SpellHandler)
        spell_handler.select_target.return_value = self._familiar
        spell_handler.can_cast.return_value = can_cast, ''
        spell_handler.cast.return_value = ''
        self._prepare_enemys_spell(spell_name='', spell_level=1, mp_cost=spell_mp_cost, spell_handler=spell_handler)
        self._test_on_enter()
        return action_weights

    def _create_action_weights_list(self, physical_attack, spell, ability):
        return [physical_attack, spell]

    def test_when_enemy_does_not_have_enough_mp_for_a_physical_attack_then_physical_attack_weight_will_be_0(self):
        self._enemy_unit_traits.physical_attack_mp_cost = 5
        self._enemy.mp = 4
        self._enemy_action_weights.physical_attack = 5
        self._enemy_action_weights.spell = 10
        self._enemy_action_weights.ability = 15
        action_weights = self._test_enemy_action_selection()
        self.assertEqual(action_weights, self._create_action_weights_list(physical_attack=0, spell=10, ability=15))

    def test_when_enemy_cannot_cast_a_spell_then_cast_spell_weight_will_be_0(self):
        self._enemy_action_weights.physical_attack = 5
        self._enemy_action_weights.spell = 10
        self._enemy_action_weights.ability = 15
        action_weights = self._test_enemy_action_selection(can_cast=False)
        self.assertEqual(action_weights, self._create_action_weights_list(physical_attack=5, spell=0, ability=15))

    def test_when_enemy_does_not_have_enough_mp_for_a_spell_then_cast_spell_weight_will_be_0(self):
        self._enemy.mp = 4
        self._enemy_action_weights.physical_attack = 5
        self._enemy_action_weights.spell = 10
        self._enemy_action_weights.ability = 15
        action_weights = self._test_enemy_action_selection(spell_mp_cost=5)
        self.assertEqual(action_weights, self._create_action_weights_list(physical_attack=5, spell=0, ability=15))

    def test_when_enemy_can_cast_and_has_enough_mp_for_a_spell_then_cast_spell_weight_will_be_taken_from_traits(self):
        self._enemy.mp = 5
        self._enemy_action_weights.physical_attack = 5
        self._enemy_action_weights.spell = 10
        self._enemy_action_weights.ability = 15
        action_weights = self._test_enemy_action_selection(can_cast=True, spell_mp_cost=5)
        self.assertEqual(action_weights, self._create_action_weights_list(physical_attack=5, spell=10, ability=15))


class StateBattleConfusedUnitTurnTest(StateBattleStartedTestBase):
    class DummyItem(Item):
        @classmethod
        @property
        def name(cls) -> str: pass

        def can_use(self, context) -> tuple[bool, str]:
            pass

        def _use(self, context) -> str:
            pass

    @classmethod
    def _state_class(cls):
        return StateBattleConfusedUnitTurn

    def setUp(self):
        super().setUp()
        self._spell_traits = SpellTraits()
        self._familiar.set_spell(self._spell_traits, level=1)
        self._enemy.name = 'monster'
        self._enemy.set_spell(self._spell_traits, level=1)
        self._choice_call_number = 0
        self._selected_action_index = 0
        self._action_selector_choices = []
        self._selected_second_choice_index = 0
        self._second_selector_choices = []
        self._rng.choice.side_effect = self._rng_choice
        self._select_skip_turn()
        self._add_usable_item()

    def _rng_choice(self, choices):
        self._choice_call_number += 1
        if self._choice_call_number == 1:
            return self._action_selector(choices)
        elif self._choice_call_number == 2:
            return self._second_choices_selector(choices)
        else:
            self.fail('Unexpected call of rng.choice')

    def _action_selector(self, choices):
        self._action_selector_choices = choices[:]
        return choices[self._selected_action_index]

    def _second_choices_selector(self, choices):
        self._second_selector_choices = choices[:]
        return choices[self._selected_second_choice_index]

    def _assert_second_choices(self, sequence):
        self.assertEqual(len(self._second_selector_choices), len(sequence))
        self.assertEqual(set(self._second_selector_choices), set(sequence))

    def _test_familiar_turn_on_enter(self):
        self._battle_context.is_player_turn = True
        self._test_on_enter('You are confused.')

    def _test_enemy_turn_on_enter(self):
        self._battle_context.is_player_turn = False
        self._test_on_enter('Monster is confused.')

    def _test_on_enter(self, confused_response):
        super()._test_on_enter()
        self.assertTrue(len(self._responses) > 0)
        confused_response = self._responses.pop(0)
        self.assertEqual(confused_response, confused_response)

    def _select_skip_turn(self):
        self._selected_action_index = 0

    def _select_physical_attack(self):
        self._selected_action_index = 1

    def _select_spell_cast(self):
        self._selected_action_index = 2

    def _select_item_use(self):
        self._selected_action_index = 3

    def test_action_for_familiar_on_enter(self):
        self._test_familiar_turn_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_action_for_enemy_on_enter(self):
        self._test_enemy_turn_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_response_on_familiar_turn_skip(self):
        self._select_skip_turn()
        self._test_familiar_turn_on_enter()
        self._assert_responses('You decide to skip a turn.')

    def test_response_on_enemy_turn_skip(self):
        self._select_skip_turn()
        self._test_enemy_turn_on_enter()
        self._assert_responses('Monster decides to skip a turn.')

    def _test_familiar_physical_attack(self, action_response=''):
        return self._test_physical_attack(action_response, on_enter_call=self._test_familiar_turn_on_enter)

    def _test_enemy_physical_attack(self, action_response=''):
        return self._test_physical_attack(action_response, on_enter_call=self._test_enemy_turn_on_enter)

    def _test_physical_attack(self, action_response, on_enter_call) -> UnitActionContext:
        original_action_handler = PhysicalAttackUnitActionHandler(mp_cost=0)
        self._select_physical_attack()
        return self._test_mocked_unit_action_handler(
            class_path='curry_quest.state_machine_context.PhysicalAttackUnitActionHandler',
            action_response=action_response,
            on_enter_call=on_enter_call,
            can_target_self=original_action_handler.can_target_self(),
            can_target_other_unit=original_action_handler.can_target_other_unit(),
            can_have_no_target=original_action_handler.can_have_no_target())

    def test_response_on_familiar_physical_attack(self):
        self._test_familiar_physical_attack(action_response='Familiar physical attack.')
        self._assert_responses('Familiar physical attack.')

    def test_response_on_enemy_physical_attack(self):
        self._test_enemy_physical_attack(action_response='Enemy physical attack.')
        self._assert_responses('Enemy physical attack.')

    def test_familiar_physical_attack_target_choices(self):
        self._test_familiar_physical_attack()
        self._assert_second_choices([self._enemy, None])

    def test_enemy_physical_attack_target_choices(self):
        self._test_enemy_physical_attack()
        self._assert_second_choices([self._familiar, None])

    def test_familiar_physical_attack_action_context(self):
        action_context = self._test_familiar_physical_attack()
        self.assertIs(action_context.performer, self._familiar)
        self.assertIs(action_context.state_machine_context, self._context)

    def test_familiar_physical_attack_enemy_target_selection(self):
        self._selected_second_choice_index = 0
        action_context = self._test_familiar_physical_attack()
        self.assertTrue(action_context.has_target())
        self.assertIs(action_context.target, self._enemy)

    def test_familiar_physical_attack_empty_target_selection(self):
        self._selected_second_choice_index = 1
        action_context = self._test_familiar_physical_attack()
        self.assertFalse(action_context.has_target())

    def test_enemy_physical_attack_action_context(self):
        action_context = self._test_enemy_physical_attack()
        self.assertIs(action_context.performer, self._enemy)
        self.assertIs(action_context.state_machine_context, self._context)

    def test_enemy_physical_attack_enemy_target_selection(self):
        self._selected_second_choice_index = 0
        action_context = self._test_enemy_physical_attack()
        self.assertTrue(action_context.has_target())
        self.assertIs(action_context.target, self._familiar)

    def test_enemy_physical_attack_empty_target_selection(self):
        self._selected_second_choice_index = 1
        action_context = self._test_enemy_physical_attack()
        self.assertFalse(action_context.has_target())

    def _test_familiar_spell_cast(self, cast_response='', **kwargs):
        return self._test_spell_cast(cast_response, on_enter_call=self._test_familiar_turn_on_enter, **kwargs)

    def _test_enemy_spell_cast(self, cast_response='', **kwargs):
        return self._test_spell_cast(cast_response, on_enter_call=self._test_enemy_turn_on_enter, **kwargs)

    def _test_spell_cast(
            self,
            cast_response,
            on_enter_call,
            can_target_self=True,
            can_target_other_unit=True,
            can_have_no_target=True) -> SpellCastContext:
        self._select_spell_cast()
        return self._test_mocked_unit_action_handler(
            class_path='curry_quest.state_machine_context.SpellCastActionHandler',
            action_response=cast_response,
            on_enter_call=on_enter_call,
            can_target_self=can_target_self,
            can_target_other_unit=can_target_other_unit,
            can_have_no_target=can_have_no_target)

    def _test_mocked_unit_action_handler(
            self,
            class_path,
            action_response,
            on_enter_call,
            can_target_self,
            can_target_other_unit,
            can_have_no_target):
        with patch(class_path) as UnitActionHandlerMock:
            action_handler_mock = UnitActionHandlerMock()
            action_handler_mock.can_target_self.return_value = can_target_self
            action_handler_mock.can_target_other_unit.return_value = can_target_other_unit
            action_handler_mock.can_have_no_target.return_value = can_have_no_target
            action_handler_mock.perform.return_value = action_response
            on_enter_call()
            action_handler_mock.perform.assert_called_once()
            return action_handler_mock.perform.call_args.args[0]

    def test_response_on_familiar_spell_cast(self):
        self._test_familiar_spell_cast(cast_response='Familiar spell cast.')
        self._assert_responses('Familiar spell cast.')

    def test_response_on_enemy_spell_cast(self):
        self._test_enemy_spell_cast(cast_response='Enemy spell cast.')
        self._assert_responses('Enemy spell cast.')

    def test_familiar_spell_cast_target_choices_when_can_target_both(self):
        self._test_familiar_spell_cast(can_target_self=True, can_target_other_unit=True, can_have_no_target=True)
        self._assert_second_choices([self._familiar, self._enemy, None])

    def test_familiar_spell_cast_target_choices_when_cannot_target_any(self):
        self._test_familiar_spell_cast(can_target_self=False, can_target_other_unit=False, can_have_no_target=True)
        self.assertEqual(self._second_selector_choices, [None])

    def test_enemy_spell_cast_target_choices_when_can_target_both(self):
        self._test_enemy_spell_cast(can_target_self=True, can_target_other_unit=True, can_have_no_target=True)
        self._assert_second_choices([self._familiar, self._enemy, None])

    def test_enemy_spell_cast_target_choices_when_cannot_target_any(self):
        self._test_enemy_spell_cast(can_target_self=False, can_target_other_unit=False, can_have_no_target=True)
        self.assertEqual(self._second_selector_choices, [None])

    def test_familiar_spell_cast_action_context(self):
        self._familiar.set_spell_level(7)
        action_context = self._test_familiar_spell_cast()
        self.assertIs(action_context.performer, self._familiar)
        self.assertIs(action_context.state_machine_context, self._context)
        self.assertEqual(action_context.spell_level, 7)

    def test_enemy_spell_cast_action_context(self):
        self._enemy.set_spell_level(9)
        action_context = self._test_enemy_spell_cast()
        self.assertIs(action_context.performer, self._enemy)
        self.assertIs(action_context.state_machine_context, self._context)
        self.assertEqual(action_context.spell_level, 9)

    def test_familiar_spell_attack_familiar_target_selection(self):
        self._selected_second_choice_index = 0
        action_context = self._test_familiar_spell_cast()
        self.assertTrue(action_context.has_target())
        self.assertIs(action_context.target, self._familiar)
        self.assertIs(action_context.reflected_target, self._enemy)

    def test_familiar_spell_attack_enemy_target_selection(self):
        self._selected_second_choice_index = 1
        action_context = self._test_familiar_spell_cast()
        self.assertTrue(action_context.has_target())
        self.assertIs(action_context.target, self._enemy)
        self.assertIs(action_context.reflected_target, self._familiar)

    def test_familiar_spell_attack_empty_target_selection(self):
        self._selected_second_choice_index = 2
        action_context = self._test_familiar_spell_cast()
        self.assertFalse(action_context.has_target())
        self.assertIs(action_context.reflected_target, None)

    def test_enemy_spell_attack_enemy_target_selection(self):
        self._selected_second_choice_index = 0
        action_context = self._test_enemy_spell_cast()
        self.assertTrue(action_context.has_target())
        self.assertIs(action_context.target, self._enemy)
        self.assertIs(action_context.reflected_target, self._familiar)

    def test_enemy_spell_attack_familiar_target_selection(self):
        self._selected_second_choice_index = 1
        action_context = self._test_enemy_spell_cast()
        self.assertTrue(action_context.has_target())
        self.assertIs(action_context.target, self._familiar)
        self.assertIs(action_context.reflected_target, self._enemy)

    def test_enemy_spell_attack_empty_target_selection(self):
        self._selected_second_choice_index = 2
        action_context = self._test_enemy_spell_cast()
        self.assertFalse(action_context.has_target())
        self.assertIs(action_context.reflected_target, None)

    def _create_usable_item(self, item_use_response=''):
        return self._create_item_mock(can_use=True, item_use_response=item_use_response)

    def _create_unusable_item(self):
        return self._create_item_mock(can_use=False)

    def _create_item_mock(self, can_use, item_use_response=''):
        item = create_autospec(spec=self.DummyItem)
        item.can_use.return_value = can_use, ''
        item.use.return_value = item_use_response
        return item

    def _add_item(self, item):
        self._context.inventory.add_item(item)
        return item

    def _clear_inventory(self):
        self._context.inventory.clear()

    def _test_item_use(self):
        self._select_item_use()
        self._test_familiar_turn_on_enter()

    def test_response_on_item_use(self):
        self._clear_inventory()
        self._add_item(self._create_usable_item(item_use_response='Item use.'))
        self._test_item_use()
        self._assert_responses('Item use.')

    def test_only_usable_items_are_selected(self):
        self._clear_inventory()
        items = []
        items.append((0, self._add_item(self._create_usable_item())))
        items.append((1, self._add_item(self._create_usable_item())))
        self._add_item(self._create_unusable_item())
        items.append((3, self._add_item(self._create_usable_item())))
        self._test_item_use()
        self._assert_second_choices(items)

    def test_item_can_use_is_called_with_proper_context(self):
        item_1 = self._add_item(self._create_usable_item())
        item_2 = self._add_item(self._create_usable_item())
        item_3 = self._add_item(self._create_unusable_item())
        item_4 = self._add_item(self._create_usable_item())
        self._test_item_use()
        item_1.can_use.assert_called_once_with(self._context)
        item_2.can_use.assert_called_once_with(self._context)
        item_3.can_use.assert_called_once_with(self._context)
        item_4.can_use.assert_called_once_with(self._context)

    def test_selected_item_is_used(self):
        self._clear_inventory()
        for i in range(5):
            self._add_item(self._create_usable_item(item_use_response=f'Item {i}'))
        self._selected_second_choice_index = 2
        self._test_item_use()
        self._assert_responses('Item 2')

    def test_selected_item_use_context(self):
        self._clear_inventory()
        item = self._add_item(self._create_usable_item())
        self._test_item_use()
        self.assertIs(item.use.call_args.args[0], self._context)

    def _add_usable_item(self):
        self._add_item(self._create_usable_item())

    def _assert_possible_actions_number(self, possible_actions_number):
        self.assertEqual(len(self._action_selector_choices), possible_actions_number)

    def test_familiar_action_choices_when_everything_is_allowed(self):
        self._test_familiar_turn_on_enter()
        self._assert_possible_actions_number(4)

    def test_familiar_action_choices_when_familiar_does_not_have_enough_mp_for_physical_attack(self):
        self._familiar_unit_traits.physical_attack_mp_cost = 3
        self._familiar.mp = 2
        self._test_familiar_turn_on_enter()
        self._assert_possible_actions_number(3)

    def test_familiar_action_choices_when_familiar_has_no_spell(self):
        self._familiar.clear_spell()
        self._test_familiar_turn_on_enter()
        self._assert_possible_actions_number(3)

    def test_familiar_action_choices_when_familiar_does_not_have_enough_mp_for_spell_cast(self):
        self._spell_traits.mp_cost = 6
        self._familiar.mp = 5
        self._test_familiar_turn_on_enter()
        self._assert_possible_actions_number(3)

    def test_familiar_action_choices_when_inventory_is_empty(self):
        self._clear_inventory()
        self._test_familiar_turn_on_enter()
        self._assert_possible_actions_number(3)

    def test_familiar_action_choices_when_nothing_is_allowed(self):
        self._spell_traits.mp_cost = 4
        self._familiar_unit_traits.physical_attack_mp_cost = 4
        self._familiar.mp = 3
        self._clear_inventory()
        self._test_familiar_turn_on_enter()
        self._assert_possible_actions_number(1)

    def test_enemy_action_choices_when_everything_is_allowed(self):
        self._test_enemy_turn_on_enter()
        self._assert_possible_actions_number(3)

    def test_enemy_action_choices_when_familiar_does_not_have_enough_mp_for_physical_attack(self):
        self._enemy_unit_traits.physical_attack_mp_cost = 3
        self._enemy.mp = 2
        self._test_enemy_turn_on_enter()
        self._assert_possible_actions_number(2)

    def test_enemy_action_choices_when_familiar_has_no_spell(self):
        self._enemy.clear_spell()
        self._test_enemy_turn_on_enter()
        self._assert_possible_actions_number(2)

    def test_enemy_action_choices_when_familiar_does_not_have_enough_mp_for_spell_cast(self):
        self._spell_traits.mp_cost = 6
        self._enemy.mp = 5
        self._test_enemy_turn_on_enter()
        self._assert_possible_actions_number(2)

    def test_enemy_action_choices_when_nothing_is_allowed(self):
        self._spell_traits.mp_cost = 4
        self._enemy_unit_traits.physical_attack_mp_cost = 4
        self._enemy.mp = 3
        self._test_enemy_turn_on_enter()
        self._assert_possible_actions_number(1)


if __name__ == '__main__':
    unittest.main()
