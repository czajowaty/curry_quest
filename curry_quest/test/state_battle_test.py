import unittest
from unittest.mock import Mock, PropertyMock, call, create_autospec, patch
from curry_quest import commands
from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.spell import Spell
from curry_quest.state_battle import StateBattleEvent, StateStartBattle, StateBattlePreparePhase, StateBattleApproach, \
    StateBattlePhase, StateEnemyStats, StateBattleSkipTurn, StateBattleAttack, StateBattleUseSpell, \
    StateBattleUseItem, StateBattleTryToFlee, StateBattleEnemyTurn, DamageRoll, RelativeHeight
from curry_quest.state_machine_context import StateMachineContext, BattleContext
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.traits import SpellTraits, UnitTraits, CastSpellHandler, SpellCastContext
from curry_quest.unit import Unit


class StateBattleTestBase(unittest.TestCase):
    def setUp(self):
        self._game_config = Config()
        self._context = create_autospec(spec=StateMachineContext)
        self._rng = Mock()
        type(self._context).rng = PropertyMock(return_value=self._rng)
        self._context.random_selection_with_weights.side_effect = self._select_key_with_greatest_value
        self._responses = []
        self._context.add_response.side_effect = lambda response: self._responses.append(response)
        type(self._context).game_config = PropertyMock(return_value=self._game_config)
        self._battle_context = create_autospec(spec=BattleContext)
        type(self._context).battle_context = PropertyMock(return_value=self._battle_context)

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
        self._context.generate_floor_monster.return_value = 'MONSTER'
        type(self._context).floor = PropertyMock(return_value=7)
        self._test_on_enter()
        self._context.generate_floor_monster.assert_called_once_with(7)
        self._assert_action(commands.START_BATTLE, 'MONSTER')

    def test_when_created_with_monster_without_level_then_level_is_same_as_familiar(self):
        unit_traits = UnitTraits()
        self._game_config._monsters_traits['TestMonster'] = unit_traits
        type(self._context.familiar).level = 4
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
        self._enemy = create_autospec(spec=Unit)
        type(self._battle_context).enemy = PropertyMock(return_value=self._enemy)

    def _test_on_enter(self):
        return super()._test_on_enter(self._enemy)

    def test_on_enter_responds_with_enemy_stats(self):
        type(self._enemy).level = PropertyMock(return_value=10)
        type(self._enemy).name = PropertyMock(return_value='Monster')
        type(self._enemy).hp = PropertyMock(return_value=76)
        self._enemy.to_string.return_value = 'EnemyToString'
        self._test_on_enter()
        self._assert_responses('You encountered a LVL 10 Monster (76 HP).', 'EnemyToString.')

    def test_on_enter_starts_battle_prepare_phase(self):
        self._test_on_enter()
        self._context.start_battle.assert_called_once_with(self._enemy)
        self._battle_context.start_prepare_phase.assert_called_once_with(counter=3)

    def test_on_enter_proceeds_to_BattlePreparePhase_state(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_PREPARE_PHASE, (True,))


class StateBattlePreparePhaseTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattlePreparePhase

    def setUp(self):
        super().setUp()
        self._familiar = Unit(UnitTraits(), Config.Levels())
        type(self._context).familiar = PropertyMock(return_value=self._familiar)

        def set_prepare_phase_finished():
            self._battle_context.is_prepare_phase.return_value = False

        self._battle_context.finish_prepare_phase.side_effect = set_prepare_phase_finished

    def _test_on_enter(self, turn_used=True):
        return super()._test_on_enter(turn_used)

    def test_when_familiar_has_sleep_status_prepare_phase_is_finished_immediately(self):
        self._familiar.set_status(Statuses.Sleep)
        self._test_on_enter()
        self._battle_context.finish_prepare_phase.assert_called_once()
        self._assert_action(commands.BATTLE_PREPARE_PHASE_FINISHED)

    def test_when_prepare_phase_is_finished_then_battle_prepare_phase_finished_action_is_generated(self):
        self._battle_context.is_prepare_phase.return_value = False
        self._test_on_enter()
        self._assert_action(commands.BATTLE_PREPARE_PHASE_FINISHED)

    def test_when_prepare_phase_is_not_finished_then_battle_prepare_phase_finished_action_is_not_generated(self):
        self._battle_context.is_prepare_phase.return_value = True
        self._test_on_enter()
        self._context.generate_action.assert_not_called()

    def test_when_familiar_does_not_have_sleep_status_and_prepare_phase_turn_is_used_then_prepare_phase_counter_is_decreased(self):  # pylint: disable=E501
        self._test_on_enter(turn_used=True)
        self._battle_context.dec_prepare_phase_counter.assert_called_once()

    def test_when_familiar_does_not_have_sleep_status_and_prepare_phase_turn_is_not_used_then_prepare_phase_counter_is_not_decreased(self):
        self._test_on_enter(turn_used=False)
        self._battle_context.dec_prepare_phase_counter.assert_not_called()

    def test_when_familiar_does_not_have_sleep_status_and_it_is_prepare_phase_then_proper_response_is_given(self):
        self._battle_context.is_prepare_phase.return_value = True
        self._test_on_enter()
        self._assert_responses('The enemy is close, but you still have time to prepare.')

    def test_when_familiar_does_not_have_sleep_status_and_it_is_not_prepare_phase_then_proper_response_is_given(self):
        self._battle_context.is_prepare_phase.return_value = False
        self._test_on_enter()
        self._assert_responses('The enemy approaches you. Time to battle!')

    def test_when_familiar_has_sleep_status_then_proper_response_is_given(self):
        self._familiar.set_status(Statuses.Sleep)
        self._test_on_enter()
        self._assert_responses('You are very sleepy. As you\'re nodding off, an enemy approaches you. Time to battle!')


class StateBattleApproachTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleApproach

    def test_on_enter_generates_battle_prepare_phase_finished_action(self):
        self._test_on_enter()
        self._battle_context.finish_prepare_phase.assert_called_once()
        self._assert_action(commands.BATTLE_PREPARE_PHASE_FINISHED)


class StateBattlePhaseTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattlePhase

    def setUp(self):
        class TurnCounter:
            def __init__(self):
                self._turn_counter = 0

            def set(self, value):
                self._turn_counter = value

            def inc(self):
                self._turn_counter += 1

            def value(self):
                return self._value_counter

        super().setUp()
        self._familiar = Unit(UnitTraits(), Config.Levels())
        type(self._context).familiar = PropertyMock(return_value=self._familiar)
        self._enemy = Unit(UnitTraits(), Config.Levels())
        self._battle_context = BattleContext(self._enemy)
        type(self._context).battle_context = PropertyMock(return_value=self._battle_context)

    def _test_on_enter(self, battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=False):
        if battle_is_finished:
            self._battle_context.finish_battle()
        self._familiar.hp = 0 if is_familiar_dead else 1
        self._enemy.hp = 0 if is_enemy_dead else 1
        super()._test_on_enter()

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
        self._test_on_enter(battle_is_finished=True, is_familiar_dead=False, is_enemy_dead=False)
        self._context.finish_battle.assert_called_once()

    def test_when_familiar_dies_then_battle_is_finished(self):
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=True, is_enemy_dead=False)
        self._context.finish_battle.assert_called_once()

    def test_when_enemy_dies_then_battle_is_finished(self):
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=True)
        self._context.finish_battle.assert_called_once()

    def test_when_battle_is_not_finished_then_battle_is_not_finished(self):
        self._test_on_enter(battle_is_finished=False, is_familiar_dead=False, is_enemy_dead=False)
        self._context.finish_battle.assert_not_called()

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


class StateEnemyStatsTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateEnemyStats

    def test_on_enter_responds_with_enemy_stats(self):
        self._battle_context.enemy.to_string.return_value = 'MonsterStats'
        self._test_on_enter()
        self._assert_responses('Enemy stats: MonsterStats.')

    def test_on_enter_generates_player_turn_action(self):
        self._test_on_enter()
        self._assert_action(commands.PLAYER_TURN)


class StateBattleSkipTurnTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleSkipTurn

    def test_on_enter_response(self):
        self._test_on_enter()
        self._assert_responses('You skip turn.')

    def test_on_enter_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)


class StateBattleAttackTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleAttack

    def setUp(self):
        super().setUp()
        self._rng.choices.return_value = (DamageRoll.Normal,)
        self._enemy = Unit(UnitTraits(), Config.Levels())
        self._enemy.name = 'Monster'
        type(self._battle_context).enemy = PropertyMock(return_value=self._enemy)
        self._familiar = Unit(UnitTraits(), Config.Levels())
        self._familiar.name = 'Familiar'
        type(self._context).familiar = PropertyMock(return_value=self._familiar)

    def test_on_enter_generates_battle_action_performed_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_when_familiar_has_0_luck_attack_misses(self):
        self._familiar.luck = 0
        self._test_on_enter()
        self._assert_responses('You try to hit Monster, but it dodges swiftly.')

    def test_when_familiar_has_non_0_luck_then_hit_chance_is_checked_based_on_luck(self):
        self._familiar.luck = 10
        self._context.does_action_succeed.return_value = False
        self._test_on_enter()
        self._context.does_action_succeed.assert_called_once_with(success_chance=0.9)
        self._assert_responses('You try to hit Monster, but it dodges swiftly.')

    def test_when_familiar_has_blind_status_then_hit_chance_is_halved(self):
        self._familiar.luck = 10
        self._familiar.set_status(Statuses.Blind)
        self._context.does_action_succeed.return_value = False
        self._test_on_enter()
        self._context.does_action_succeed.assert_called_once_with(success_chance=0.45)
        self._assert_responses('You try to hit Monster, but it dodges swiftly.')

    def _test_damage_calculator_args(self, damage_roll=DamageRoll.Normal, critical_hit=False, damage=0):
        self._familiar.luck = 1
        self._context.does_action_succeed.side_effect = [True, critical_hit]
        with patch('curry_quest.state_battle.DamageCalculator') as DamageCalculatorMock:
            damage_calculator_mock = DamageCalculatorMock.return_value
            damage_calculator_mock.physical_damage.return_value = damage
            self._rng.choices.return_value = (damage_roll,)
            self._test_on_enter()
            damage_calculator_mock.physical_damage.assert_called_once()
            return DamageCalculatorMock.call_args.args, damage_calculator_mock.physical_damage.call_args.args

    def _test_damage_calculator_creation_args(self, *args, **kwargs):
        creation_args, _ = self._test_damage_calculator_args(*args, **kwargs)
        return creation_args

    def _test_damage_calculator_call_args(self, *args, **kwargs):
        _, call_args = self._test_damage_calculator_args(*args, **kwargs)
        return call_args

    def test_damage_calculator_is_created_with_familiar_and_enemy(self):
        familiar, enemy = self._test_damage_calculator_creation_args()
        self.assertIs(familiar, self._familiar)
        self.assertIs(enemy, self._enemy)

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
        damage_roll, _, _ = self._test_damage_calculator_call_args(damage_roll=DamageRoll.High)
        self.assertEqual(damage_roll, DamageRoll.High)
        damage_roll, _, _ = self._test_damage_calculator_call_args(damage_roll=DamageRoll.Low)
        self.assertEqual(damage_roll, DamageRoll.Low)

    def test_when_unit_has_crack_status_relative_height_is_Lower(self):
        self._familiar.set_status(Statuses.Crack)
        _, relative_height, _ = self._test_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Lower)

    def test_when_unit_has_upheaval_status_relative_height_is_Higher(self):
        self._familiar.set_status(Statuses.Upheavel)
        _, relative_height, _ = self._test_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Higher)

    def test_when_unit_has_crack_and_upheaval_status_relative_height_is_Same(self):
        self._familiar.set_status(Statuses.Upheavel | Statuses.Crack)
        _, relative_height, _ = self._test_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Same)

    def test_when_unit_has_no_status_relative_height_is_Same(self):
        _, relative_height, _ = self._test_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Same)

    def test_is_critical_is_passed_to_calculate_damage(self):
        _, _, is_critical = self._test_damage_calculator_call_args(critical_hit=False)
        self.assertFalse(is_critical)
        _, _, is_critical = self._test_damage_calculator_call_args(critical_hit=True)
        self.assertTrue(is_critical)

    def test_when_attack_hits_then_enemy_hp_is_decreased_by_damage(self):
        self._enemy.hp = 40
        self._test_damage_calculator_args(damage=15, critical_hit=False)
        self.assertEqual(self._enemy.hp, 25)

    def test_when_attack_hits_then_familiar_hp_is_not_touched(self):
        self._familiar.hp = 30
        self._enemy.hp = 40
        self._test_damage_calculator_args(damage=15, critical_hit=False)
        self.assertEqual(self._enemy.hp, 25)
        self.assertEqual(self._familiar.hp, 30)

    def test_when_enemy_has_electric_shock_talent_then_familiar_takes_quarter_of_reflected_damage(self):
        self._familiar.hp = 30
        self._enemy._talents |= Talents.ElectricShock
        self._test_damage_calculator_args(damage=15, critical_hit=False)
        self.assertEqual(self._familiar.hp, 27)

    def test_at_min_reflect_damage_is_1(self):
        self._familiar.hp = 30
        self._enemy._talents |= Talents.ElectricShock
        self._test_damage_calculator_args(damage=1, critical_hit=False)
        self.assertEqual(self._familiar.hp, 29)

    def test_response_on_normal_attack(self):
        self._enemy.hp = 40
        self._test_damage_calculator_args(damage=17)
        self._assert_responses('You hit dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_critical_attack(self):
        self._enemy.hp = 40
        self._test_damage_calculator_args(damage=17, critical_hit=True)
        self._assert_responses('You hit hard dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_from_below_attack(self):
        self._familiar.set_status(Statuses.Crack)
        self._enemy.hp = 40
        self._test_damage_calculator_args(damage=17)
        self._assert_responses('You hit from below dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_from_above_attack(self):
        self._familiar.set_status(Statuses.Upheavel)
        self._enemy.hp = 40
        self._test_damage_calculator_args(damage=17)
        self._assert_responses('You hit from above dealing 17 damage. Monster has 23 HP left.')

    def test_response_on_electric_shock_attack(self):
        self._familiar.hp = 30
        self._enemy.hp = 40
        self._enemy._talents |= Talents.ElectricShock
        self._test_damage_calculator_args(damage=17)
        self._assert_responses(
            'You hit dealing 17 damage. Monster has 23 HP left. '
            'An electrical shock runs through your body dealing 4 damage. You have 26 HP left.')


class StateBattleUseSpellTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleUseSpell

    def setUp(self):
        super().setUp()
        self._familiar = Mock(spec=Unit)
        type(self._context).familiar = PropertyMock(return_value=self._familiar)
        self._spell_cast_handler = Mock(spec=CastSpellHandler)
        self._spell_cast_handler.can_cast.return_value = True, ''
        self._spell_cast_handler.cast.return_value = ''
        self._spell_traits = SpellTraits()
        self._spell_traits.cast_handler = self._spell_cast_handler
        self._spell = Spell(self._spell_traits)
        type(self._familiar).spell = PropertyMock(return_value=self._spell)
        self._enemy = Unit(UnitTraits(), Config.Levels())
        self._enemy.name = 'Monster'
        type(self._battle_context).enemy = PropertyMock(return_value=self._enemy)

    def test_creating_fails_when_familiar_does_not_have_spell(self):
        self._familiar.has_spell.return_value = False
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'You do not have a spell.')

    def test_creating_fails_when_familiar_does_not_have_enough_mp(self):
        self._familiar.has_spell.return_value = True
        self._familiar.has_enough_mp_for_spell.return_value = False
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'You do not have enough MP.')

    def test_creating_fails_when_spell_cannot_be_casted(self):
        self._familiar.has_spell.return_value = True
        self._familiar.has_enough_mp_for_spell.return_value = True
        self._spell_cast_handler.can_cast.return_value = False, 'CANNOT CAST'
        error_message = self._test_create_state_failure()
        self.assertEqual(error_message, 'CANNOT CAST')

    def _test_spell_cast(self):
        def create_spell_cast_context(caster, other_unit):
            spell_cast_context = SpellCastContext()
            spell_cast_context.caster = caster
            spell_cast_context.target = other_unit
            spell_cast_context.other_than_target = caster
            spell_cast_context.state_machine_context = self._context
            return spell_cast_context

        self._context.create_spell_cast_context.side_effect = create_spell_cast_context
        self._familiar.has_spell.return_value = True
        self._familiar.has_enough_mp_for_spell.return_value = True
        self._spell_cast_handler.can_cast.return_value = True, ''
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
        self._assert_responses('You cast FamiliarSpell. spell casted.')

    def test_mp_usage(self):
        self._spell_traits.mp_cost = 6
        self._test_spell_cast()
        self._familiar.use_mp.assert_called_once_with(6)

    def test_spell_target(self):
        spell_cast_context = self._test_spell_cast()
        self.assertIs(spell_cast_context.target, self._enemy)


class StateBattleUseItemTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleUseItem

    def setUp(self):
        super().setUp()
        self._inventory = Mock()
        type(self._context).inventory = PropertyMock(return_value=self._inventory)
        self._item = Mock()
        self._item.can_use.return_value = (True, '')
        self._inventory.peek_item.return_value = self._item

    def _test_on_enter(self, item_index=0, is_prepare_phase=True, can_use_item=True, reason=''):
        self._inventory.find_item.return_value = (item_index, self._item)
        self._battle_context.is_prepare_phase.return_value = is_prepare_phase
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
        self._test_on_enter(can_use_item=True)
        self._assert_responses()

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


class StateBattleTryToFleeTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleTryToFlee

    def setUp(self):
        super().setUp()
        self._familiar = Unit(UnitTraits(), Config.Levels())
        type(self._context).familiar = PropertyMock(return_value=self._familiar)

    def _test_on_enter(self, flee_successful=False):
        self._context.does_action_succeed.return_value = flee_successful
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
        self._battle_context.finish_battle.assert_called_once()

    def test_response_when_flee_is_not_successful(self):
        self._test_on_enter(flee_successful=False)
        self._assert_responses('You attempt to flee from battle, but your path is blocked!')

    def test_when_flee_is_not_successful_battle_is_not_finished(self):
        self._test_on_enter(flee_successful=False)
        self._battle_context.finish_battle.assert_not_called()


class StateBattleEnemyTurnTest(StateBattleTestBase):
    @classmethod
    def _state_class(cls):
        return StateBattleEnemyTurn

    def setUp(self):
        super().setUp()
        self._rng.choices.return_value = (DamageRoll.Normal,)
        self._enemy = Unit(UnitTraits(), Config.Levels())
        self._enemy.name = 'Monster'
        self._enemy_action_weights = self._enemy.traits.action_weights
        type(self._battle_context).enemy = PropertyMock(return_value=self._enemy)
        self._familiar = Unit(UnitTraits(), Config.Levels())
        self._familiar.name = 'Familiar'
        type(self._context).familiar = PropertyMock(return_value=self._familiar)
        self._context.create_spell_cast_context.side_effect = self._create_spell_cast_context

    def _create_spell_cast_context(self, caster: Unit, other_unit: Unit):
        spell_cast_context = SpellCastContext()
        spell_cast_context.caster = caster
        spell_cast_context.target = other_unit
        spell_cast_context.state_machine_context = self._context
        return spell_cast_context

    def _test_on_enter(self, is_holy_scroll_active=False):
        self._battle_context.is_holy_scroll_active.return_value = is_holy_scroll_active
        return super()._test_on_enter()

    def test_on_enter_generates_battle_action_performed_action(self):
        self._test_on_enter()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_response_when_holy_scroll_is_active(self):
        self._test_on_enter(is_holy_scroll_active=True)
        self._assert_responses('The field is engulfed in the Holy Scroll\'s beams. Monster cannot act.')

    def _test_damage_calculator(self, configurator):
        with patch('curry_quest.state_battle.DamageCalculator') as DamageCalculatorMock:
            damage_calculator_mock = DamageCalculatorMock.return_value
            configurator(damage_calculator_mock)
            self._test_on_enter(is_holy_scroll_active=False)
            return damage_calculator_mock, DamageCalculatorMock

    def _test_physical_damage(self, damage_roll=DamageRoll.Normal, critical_hit=False, damage=0):
        def configurator(damage_calculator_mock):
            damage_calculator_mock.physical_damage.return_value = damage

        self._enemy_action_weights.physical_attack = 1
        self._enemy_action_weights.spell = 0
        self._enemy_action_weights.ability = 0
        self._enemy.luck = 1
        self._context.does_action_succeed.side_effect = [True, critical_hit]
        self._rng.choices.return_value = (damage_roll,)
        damage_calculator_mock, DamageCalculatorMock = self._test_damage_calculator(configurator)
        damage_calculator_mock.physical_damage.assert_called_once()
        return DamageCalculatorMock.call_args.args, damage_calculator_mock.physical_damage.call_args.args

    def _test_physical_attack_damage_calculator_creation_args(self, *args, **kwargs):
        creation_args, _ = self._test_physical_damage(*args, **kwargs)
        return creation_args

    def _test_physical_attack_damage_calculator_call_args(self, *args, **kwargs):
        _, call_args = self._test_physical_damage(*args, **kwargs)
        return call_args

    def test_damage_calculator_is_created_with_enemy_and_familiar(self):
        attacker, defender = self._test_physical_attack_damage_calculator_creation_args()
        self.assertIs(attacker, self._enemy)
        self.assertIs(defender, self._familiar)

    def test_damage_roll_distribution(self):
        self._test_physical_damage()
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
        damage_roll, _, _ = self._test_physical_attack_damage_calculator_call_args(damage_roll=DamageRoll.High)
        self.assertEqual(damage_roll, DamageRoll.High)
        damage_roll, _, _ = self._test_physical_attack_damage_calculator_call_args(damage_roll=DamageRoll.Low)
        self.assertEqual(damage_roll, DamageRoll.Low)

    def test_when_familiar_has_crack_status_relative_height_is_Higher(self):
        self._familiar.set_status(Statuses.Crack)
        _, relative_height, _ = self._test_physical_attack_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Higher)

    def test_when_familiar_has_upheaval_status_relative_height_is_Lower(self):
        self._familiar.set_status(Statuses.Upheavel)
        _, relative_height, _ = self._test_physical_attack_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Lower)

    def test_when_familiar_has_crack_and_upheaval_status_relative_height_is_Same(self):
        self._familiar.set_status(Statuses.Upheavel | Statuses.Crack)
        _, relative_height, _ = self._test_physical_attack_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Same)

    def test_when_familiar_has_no_status_relative_height_is_Same(self):
        _, relative_height, _ = self._test_physical_attack_damage_calculator_call_args()
        self.assertEqual(relative_height, RelativeHeight.Same)

    def test_is_critical_is_passed_to_calculate_damage(self):
        _, _, is_critical = self._test_physical_attack_damage_calculator_call_args(critical_hit=False)
        self.assertFalse(is_critical)
        _, _, is_critical = self._test_physical_attack_damage_calculator_call_args(critical_hit=True)
        self.assertTrue(is_critical)

    def test_when_attack_hits_then_familiars_hp_is_decreased_by_damage(self):
        self._familiar.hp = 40
        self._test_physical_damage(damage=15, critical_hit=False)
        self.assertEqual(self._familiar.hp, 25)

    def test_when_attack_hits_then_enemys_hp_is_not_touched(self):
        self._familiar.hp = 30
        self._enemy.hp = 40
        self._test_physical_damage(damage=15, critical_hit=False)
        self.assertEqual(self._familiar.hp, 15)
        self.assertEqual(self._enemy.hp, 40)

    def test_when_familiar_has_electric_shock_talent_then_enemy_takes_quarter_of_reflected_damage(self):
        self._enemy.hp = 30
        self._familiar._talents |= Talents.ElectricShock
        self._test_physical_damage(damage=15, critical_hit=False)
        self.assertEqual(self._enemy.hp, 27)

    def test_at_min_reflect_damage_is_1(self):
        self._enemy.hp = 30
        self._familiar._talents |= Talents.ElectricShock
        self._test_physical_damage(damage=1, critical_hit=False)
        self.assertEqual(self._enemy.hp, 29)

    def test_response_on_normal_attack(self):
        self._familiar.hp = 40
        self._test_physical_damage(damage=17)
        self._assert_responses('Monster hits dealing 17 damage. You have 23 HP left.')

    def test_response_on_critical_attack(self):
        self._familiar.hp = 40
        self._test_physical_damage(damage=17, critical_hit=True)
        self._assert_responses('Monster hits hard dealing 17 damage. You have 23 HP left.')

    def test_response_on_from_below_attack(self):
        self._familiar.set_status(Statuses.Upheavel)
        self._familiar.hp = 40
        self._test_physical_damage(damage=17)
        self._assert_responses('Monster hits from below dealing 17 damage. You have 23 HP left.')

    def test_response_on_from_above_attack(self):
        self._familiar.set_status(Statuses.Crack)
        self._familiar.hp = 40
        self._test_physical_damage(damage=17)
        self._assert_responses('Monster hits from above dealing 17 damage. You have 23 HP left.')

    def test_response_on_electric_shock_attack(self):
        self._familiar.hp = 30
        self._enemy.hp = 40
        self._familiar._talents |= Talents.ElectricShock
        self._test_physical_damage(damage=17)
        self._assert_responses(
            'Monster hits dealing 17 damage. You have 13 HP left. '
            'An electrical shock runs through Monster\'s body dealing 4 damage. Monster has 36 HP left.')

    def _test_spell_cast(self, spell_name='', mp_cost=0, can_cast=True, cast_response=''):
        self._enemy_action_weights.physical_attack = 0
        self._enemy_action_weights.spell = 1
        self._enemy_action_weights.ability = 0
        cast_handler = create_autospec(spec=CastSpellHandler)
        cast_handler.can_cast.return_value = can_cast, ''
        cast_handler.cast.return_value = cast_response
        self._prepare_enemys_spell(spell_name, mp_cost, cast_handler)
        self._test_on_enter()
        return cast_handler

    def _prepare_enemys_spell(self, spell_name='', mp_cost=0, cast_handler=None):
        spell_traits = SpellTraits()
        spell_traits.name = spell_name
        spell_traits.mp_cost = mp_cost
        spell_traits.cast_handler = cast_handler
        self._enemy.set_spell(spell_traits, level=1)

    def test_action_on_spell(self):
        self._test_spell_cast()
        self._assert_action(commands.BATTLE_ACTION_PERFORMED)

    def test_response_on_spell(self):
        self._enemy.name = 'monster'
        self._familiar.hp = 30
        self._test_spell_cast(spell_name='MonsterSpell', cast_response='Casted a spell.')
        self._assert_responses('Monster casts MonsterSpell. Casted a spell.')

    def test_mp_usage(self):
        self._enemy.mp = 60
        self._test_spell_cast(mp_cost=14)
        self.assertEqual(self._enemy.mp, 46)

    def test_spell_cast_context_for_cast(self):
        spell_cast_context = SpellCastContext()
        spell_cast_context.caster = self._enemy
        spell_cast_context.target = self._familiar
        spell_cast_context.state_machine_context = self._context
        self._context.create_spell_cast_context.side_effect = lambda _, __: spell_cast_context
        cast_handler = self._test_spell_cast()
        spell_cast_context = cast_handler.cast.call_args.args[0]
        self.assertIs(spell_cast_context.caster, self._enemy)
        self.assertIs(spell_cast_context.target, self._familiar)
        self.assertIs(spell_cast_context.state_machine_context, self._context)

    def test_spell_cast_context_for_can_cast(self):
        spell_cast_context = SpellCastContext()
        spell_cast_context.caster = self._enemy
        spell_cast_context.target = self._familiar
        spell_cast_context.state_machine_context = self._context
        self._context.create_spell_cast_context.side_effect = lambda _, __: spell_cast_context
        cast_handler = self._test_spell_cast()
        spell_cast_context = cast_handler.can_cast.call_args.args[0]
        self.assertIs(spell_cast_context.caster, self._enemy)
        self.assertIs(spell_cast_context.target, self._familiar)
        self.assertIs(spell_cast_context.state_machine_context, self._context)

    def _test_enemy_action_selection(self, can_cast=True, mp_cost=0):
        action_weights = []

        def select_enemy_action(actions_with_weights):
            _, greatest_weight = next(iter(actions_with_weights.items()))
            for index, (_, weight) in enumerate(actions_with_weights.items()):
                action_weights.append(weight)
                if weight > greatest_weight:
                    greatest_weight = weight
            return lambda: f'Action {index}'

        self._context.random_selection_with_weights.side_effect = select_enemy_action
        cast_handler = create_autospec(spec=CastSpellHandler)
        cast_handler.can_cast.return_value = can_cast, ''
        cast_handler.cast.return_value = ''
        self._prepare_enemys_spell('', mp_cost, cast_handler)
        self._test_on_enter()
        return action_weights

    def _create_action_weights_list(self, physical_attack, spell, ability):
        return [physical_attack, spell]

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
        action_weights = self._test_enemy_action_selection(mp_cost=5)
        self.assertEqual(action_weights, self._create_action_weights_list(physical_attack=5, spell=0, ability=15))

    def test_when_enemy_can_cast_and_has_enough_mp_for_a_spell_then_cast_spell_weight_will_be_taken_from_traits(self):
        self._enemy.mp = 5
        self._enemy_action_weights.physical_attack = 5
        self._enemy_action_weights.spell = 10
        self._enemy_action_weights.ability = 15
        action_weights = self._test_enemy_action_selection(can_cast=True, mp_cost=5)
        self.assertEqual(action_weights, self._create_action_weights_list(physical_attack=5, spell=10, ability=15))


if __name__ == '__main__':
    unittest.main()
