import unittest
from curry_quest.abilities import GetSeriousAbility
from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.floor_descriptor import FloorDescriptor
from curry_quest.genus import Genus
from curry_quest.items import Pita, HolyScroll, CureAllHerb, Oleem, MedicinalHerb, FireBall
from curry_quest.records import Records
from curry_quest.spells import Spells
from curry_quest.state_base import StateBase
from curry_quest.state_battle import StateBattleEvent, StateStartBattle, StateBattlePreparePhase, StateBattleApproach, \
    StateBattlePhase, StateBattlePlayerTurn, StateEnemyStats, StateBattleSkipTurn, StateBattleConfusedUnitTurn, \
    StateBattleAttack, StateBattleUseSpell, StateBattleUseAbility, StateBattleUseItem, StateBattleTryToFlee, \
    StateBattleEnemyTurn
from curry_quest.state_character import StateCharacterEvent, StateItemTrade, StateItemTradeAccepted, \
    StateItemTradeRejected, StateFamiliarTrade, StateFamiliarTradeAccepted, StateFamiliarTradeRejected, \
    StateEvolveFamiliar
from curry_quest.state_elevator import StateElevatorEvent, StateElevatorUsed, StateGoUp, StateElevatorOmitted, \
    StateNextFloor
from curry_quest.state_event import StateWaitForEvent, StateGenerateEvent
from curry_quest.state_familiar import StateFamiliarEvent, StateMetFamiliarIgnore, StateFamiliarFusion, \
    StateFamiliarReplacement
from curry_quest.state_initialize import StateInitialize, StateEnterTower
from curry_quest.state_item import StateItemEvent, StateItemPickUp, StateItemPickUpFullInventory, \
    StateItemPickUpAfterDrop, StateItemPickUpIgnored, StateItemEventFinished
from curry_quest.state_machine import StateMachine, StateStart, StateRestartByUser, StateGameOver
from curry_quest.state_machine_context import StateMachineContext, BattleContext
from curry_quest.state_trap import StateTrapEvent
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.unit import Unit
from curry_quest.unit_traits import UnitTraits
import json
from curry_quest.weight import StaticWeight, NoWeightPenaltyHandler


class SaveLoadStateTest(unittest.TestCase):
    def setUp(self):
        self._player_id = 5
        self._monster_traits = UnitTraits()
        self._monster_traits.name = 'Monster'
        self._ghosh_traits = UnitTraits()
        self._ghosh_traits.name = 'Ghosh'
        self._game_config = Config()
        self._game_config.events_weights['character'] = (StaticWeight(10), NoWeightPenaltyHandler())
        self._game_config.found_items_weights['Pita'] = (StaticWeight(10), NoWeightPenaltyHandler())
        self._game_config.character_events_weights['Cherrl'] = (StaticWeight(10), NoWeightPenaltyHandler())
        self._game_config.traps_weights['Sleep'] = (StaticWeight(10), NoWeightPenaltyHandler())
        for exp in range(10):
            self._game_config.levels.add_level(exp)
        for _ in range(40):
            self._game_config._floors.append(FloorDescriptor())
        self._game_config.monsters_traits[self._monster_traits.name] = self._monster_traits
        self._game_config.special_units_traits.ghosh = self._ghosh_traits
        self._sut = self._create_state_machine()

    def _create_state_machine(self):
        return StateMachine(self._game_config, self._player_id, 'PLAYER')

    @property
    def _context(self) -> StateMachineContext:
        return self._sut._context

    @property
    def _battle_context(self) -> BattleContext:
        return self._sut._context.battle_context

    def _test_save_load(self):
        json_object = self._sut.to_json_object()
        json_object = json.loads(json.dumps(json_object))
        loaded_state_machine = self._create_state_machine()
        loaded_state_machine.from_json_object(json_object)
        return loaded_state_machine

    def test_player_name_is_handled_correctly(self):
        self._sut.player_name = 'Player name'
        loaded_state_machine = self._test_save_load()
        self.assertEqual(loaded_state_machine.player_name, 'Player name')

    def test_responses_are_handled_correctly(self):
        self._sut._last_responses.append('Response 1')
        self._sut._last_responses.append('Response 3')
        loaded_state_machine = self._test_save_load()
        self.assertEqual(
            loaded_state_machine._last_responses,
            ['Response 1', 'Response 3'])

    def _test_save_load_state_machine_context(self) -> StateMachineContext:
        return self._test_save_load()._context

    def _test_save_load_current_climb_records(self) -> Records:
        return self._test_save_load_state_machine_context().records

    def test_current_climb_turns_counter_is_handled_correctly(self):
        self._sut._context.records.turns_counter = 3
        records = self._test_save_load_current_climb_records()
        self.assertEqual(records.turns_counter, 3)

    def test_current_climb_used_elevators_counter_is_handled_correctly(self):
        self._sut._context.records.used_elevators_counter = 2
        records = self._test_save_load_current_climb_records()
        self.assertEqual(records.used_elevators_counter, 2)

    def test_is_tutorial_done_is_handled_correctly(self):
        self._sut._context.set_tutorial_done()
        context = self._test_save_load_state_machine_context()
        self.assertTrue(context.is_tutorial_done)

    def test_floor_is_handled_correctly(self):
        self._sut._context.floor = 7
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context.floor, 7)

    def test_rng_state_is_handled_correctly(self):
        context = self._test_save_load_state_machine_context()
        random_list = [self._sut._context.rng.randint(1, 100) for _ in range(100)]
        loaded_random_list = [context.rng.randint(1, 100) for _ in range(100)]
        self.assertEqual(random_list, loaded_random_list, 'RNG object is not loaded correctly.')

    def test_responses_field_is_handled_correctly(self):
        self._sut._context.add_response('Response 1')
        self._sut._context.add_response('Response 3')
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context.take_responses(), ['Response 1', 'Response 3'])

    def test_generate_action_is_handled_correctly(self):
        self._sut._context.generate_action('COMMAND', 'ARG1', 3)
        context = self._test_save_load_state_machine_context()
        self.assertTrue(context.has_action())

    def test_generate_action_is_handled_correctly_when_there_is_no_action(self):
        context = self._test_save_load_state_machine_context()
        self.assertFalse(context.has_action())

    def test_when_generated_action_has_non_trivial_arguments_then_saving_throws_exception(self):
        self._sut._context.generate_action('COMMAND', {})
        with self.assertRaises(InvalidOperation):
            self._sut.to_json_object()

    def test_floor_turns_counter_is_handled_correctly(self):
        self._sut._context._floor_turns_counter = 4
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context.floor_turns_counter, 4)

    def test_go_up_on_next_event_finished_flag_is_handled_correctly(self):
        self._sut._context._go_up_on_next_event_finished_flag = True
        context = self._test_save_load_state_machine_context()
        self.assertTrue(context.should_go_up_on_next_event_finished)

    def test_inventory_is_handled_correctly(self):
        inventory = self._sut._context.inventory
        inventory.add_item(Pita())
        inventory.add_item(HolyScroll())
        inventory.add_item(CureAllHerb())
        context = self._test_save_load_state_machine_context()
        loaded_inventory = context.inventory
        self.assertEqual(loaded_inventory.items, ['Pita', 'Holy Scroll', 'Cure-All Herb'])

    def test_item_buffer_is_handled_correctly(self):
        self._sut._context.buffer_item(Oleem())
        context = self._test_save_load_state_machine_context()
        self.assertIsInstance(context.peek_buffered_item(), Oleem)

    def test_event_weight_handlers_are_handled_correctly(self):
        self._sut._context._event_weight_handlers['character_event'].penalty_timer = 3
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context._event_weight_handlers['character_event'].penalty_timer, 3)

    def test_item_weight_handlers_are_handled_correctly(self):
        self._sut._context._item_weight_handlers['Pita'].penalty_timer = 2
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context._item_weight_handlers['Pita'].penalty_timer, 2)

    def test_character_weight_handlers_are_handled_correctly(self):
        self._sut._context._character_weight_handlers['Cherrl'].penalty_timer = 6
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context._character_weight_handlers['Cherrl'].penalty_timer, 6)

    def test_trap_weight_handlers_are_handled_correctly(self):
        self._sut._context._trap_weight_handlers['Sleep'].penalty_timer = 5
        context = self._test_save_load_state_machine_context()
        self.assertEqual(context._trap_weight_handlers['Sleep'].penalty_timer, 5)

    def _test_save_load_familiar(self, familiar) -> Unit:
        self._sut._context.familiar = familiar
        return self._test_save_load_state_machine_context().familiar

    def _create_familiar(self):
        return Unit(self._monster_traits, self._game_config.levels)

    def test_familiar_traits_are_handled_correctly(self):
        loaded_familiar = self._test_save_load_familiar(self._create_familiar())
        self.assertIs(loaded_familiar.traits, self._monster_traits)

    def test_familiar_levels_are_handled_correctly(self):
        loaded_familiar = self._test_save_load_familiar(self._create_familiar())
        self.assertIs(loaded_familiar._levels, self._game_config.levels)

    def test_familiar_name_is_handled_correctly(self):
        loaded_familiar = self._test_save_load_familiar(self._create_familiar())
        self.assertEqual(loaded_familiar.name, 'Monster')

    def test_familiar_genus_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.genus = Genus.Water
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.genus, Genus.Water)

    def test_familiar_level_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.level = 4
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.level, 4)

    def test_familiar_talents_are_handled_correctly(self):
        familiar = self._create_familiar()
        familiar._talents = Talents.ElectricShock | Talents.ImmuneToStealing
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.talents, Talents.ElectricShock | Talents.ImmuneToStealing)

    def test_familiar_max_hp_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.max_hp = 8
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.max_hp, 8)

    def test_familiar_hp_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.hp = 7
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.hp, 7)

    def test_familiar_max_mp_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.max_mp = 10
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.max_mp, 10)

    def test_familiar_mp_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.mp = 20
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.mp, 20)

    def test_familiar_attack_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.attack = 15
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.attack, 15)

    def test_familiar_defense_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.defense = 13
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.defense, 13)

    def test_familiar_luck_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.luck = 7
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.luck, 7)

    def test_familiar_physical_attack_mp_cost_is_handled_correctly(self):
        self._monster_traits.physical_attack_mp_cost = 8
        familiar = self._create_familiar()
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.physical_attack_mp_cost, 8)

    def test_familiar_statuses_are_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.set_status(Statuses.Confuse)
        familiar.set_status(Statuses.Blind)
        familiar.set_status(Statuses.FireProtection)
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertTrue(loaded_familiar.has_status(Statuses.Confuse))
        self.assertTrue(loaded_familiar.has_status(Statuses.Blind))
        self.assertTrue(loaded_familiar.has_status(Statuses.FireProtection))

    def test_familiar_timed_statuses_are_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.set_timed_status(Statuses.Confuse, 4)
        familiar.set_timed_status(Statuses.Blind, 2)
        familiar.set_timed_status(Statuses.FireProtection, 7)
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.status_duration(Statuses.Confuse), {Statuses.Confuse: 4})
        self.assertEqual(loaded_familiar.status_duration(Statuses.Blind), {Statuses.Blind: 2})
        self.assertEqual(loaded_familiar.status_duration(Statuses.FireProtection), {Statuses.FireProtection: 7})

    def test_familiar_exp_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.exp = 156
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertEqual(loaded_familiar.exp, 156)

    def test_familiar_spell_traits_are_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.genus = Genus.Wind
        spell_traits = Spells.find_spell_traits('Heal', Genus.Wind)
        familiar.set_spell(spell_traits, level=1)
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertTrue(loaded_familiar.has_spell())
        self.assertIs(loaded_familiar.spell_traits, Spells.find_spell_traits('Heal', Genus.Wind))

    def test_familiar_spell_level_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.genus = Genus.Wind
        spell_traits = Spells.find_spell_traits('Heal', Genus.Wind)
        familiar.set_spell(spell_traits, level=7)
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertTrue(loaded_familiar.has_spell())
        self.assertEqual(loaded_familiar.spell_level, 7)

    def test_familiar_ability_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.ability = GetSeriousAbility()
        loaded_familiar = self._test_save_load_familiar(familiar)
        self.assertTrue(loaded_familiar.has_ability())
        self.assertIsInstance(loaded_familiar.ability, GetSeriousAbility)

    def test_unit_buffer_is_handled_correctly(self):
        unit = Unit(self._ghosh_traits, self._game_config.levels)
        self._sut._context.buffer_unit(unit)
        context = self._test_save_load_state_machine_context()
        loaded_buffered_unit = context.peek_buffered_unit()
        self.assertIs(loaded_buffered_unit.traits, self._ghosh_traits)

    def _test_save_load_battle_context(self) -> BattleContext:
        return self._test_save_load_state_machine_context().battle_context

    def _create_enemy(self, unit_traits=None):
        return Unit(unit_traits or self._ghosh_traits, self._game_config.levels)

    def _start_battle(self, enemy=None):
        enemy = enemy or Unit(self._ghosh_traits, self._game_config.levels)
        self._sut._context.start_battle(enemy)

    def test_enemy_is_handled_correctly(self):
        enemy = Unit(self._ghosh_traits, self._game_config.levels)
        self._start_battle(enemy)
        battle_context = self._test_save_load_battle_context()
        self.assertIs(battle_context.enemy.traits, self._ghosh_traits)

    def test_prepare_phase_counter_is_handled_correctly(self):
        self._start_battle()
        self._battle_context.start_prepare_phase(counter=3)
        battle_context = self._test_save_load_battle_context()
        self.assertEqual(battle_context._prepare_phase_counter, 3)

    def test_holy_scroll_counter_is_handled_correctly(self):
        self._start_battle()
        self._battle_context.set_holy_scroll_counter(counter=5)
        battle_context = self._test_save_load_battle_context()
        self.assertEqual(battle_context._holy_scroll_counter, 5)

    def test_is_first_turn_is_handled_correctly(self):
        self._start_battle()
        self._battle_context.is_first_turn = False
        battle_context = self._test_save_load_battle_context()
        self.assertFalse(battle_context.is_first_turn)

    def test_is_player_turn_is_handled_correctly(self):
        self._start_battle()
        self._battle_context.is_player_turn = False
        battle_context = self._test_save_load_battle_context()
        self.assertFalse(battle_context.is_player_turn)

    def test_turn_counter_is_handled_correctly(self):
        self._start_battle()
        self._battle_context._turn_counter = 4
        battle_context = self._test_save_load_battle_context()
        self.assertEqual(battle_context.turn_counter, 4)

    def test_is_battle_finished_is_handled_correctly(self):
        self._start_battle()
        self._battle_context.finish_battle()
        battle_context = self._test_save_load_battle_context()
        self.assertTrue(battle_context.is_finished())

    def _test_save_load_state(self, state: StateBase) -> StateBase:
        self._sut._state = state
        loaded_state = self._test_save_load()._state
        self.assertIsInstance(loaded_state, state.__class__)
        return loaded_state

    def _test_save_load_bare_state(self, state_class):
        loaded_state = self._test_save_load_state(state_class.create(self._context, ()))
        return loaded_state

    def test_state_start_is_handled_correctly(self):
        self._test_save_load_bare_state(StateStart)

    def test_state_restart_by_user_is_handled_correctly(self):
        self._test_save_load_bare_state(StateRestartByUser)

    def test_state_initialize_is_handled_correctly(self):
        state = StateInitialize.create(self._context, ('Monster', 4))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._monster_name, 'Monster')
        self.assertEqual(loaded_state._monster_level, 4)

    def test_state_initialize_without_parameters_is_handled_correctly(self):
        state = StateInitialize.create(self._context, ())
        loaded_state = self._test_save_load_state(state)
        self.assertIsNone(loaded_state._monster_name)
        self.assertIsNone(loaded_state._monster_level)

    def test_state_enter_tower_is_handled_correctly(self):
        self._test_save_load_bare_state(StateEnterTower)

    def test_state_wait_for_event_is_handled_correctly(self):
        state = StateWaitForEvent.create(self._context, ('COMMAND',))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._event_command, 'COMMAND')

    def test_state_wait_for_event_without_parameters_is_handled_correctly(self):
        state = StateWaitForEvent.create(self._context, ())
        loaded_state = self._test_save_load_state(state)
        self.assertIsNone(loaded_state._event_command)

    def test_state_generate_event_is_handled_correctly(self):
        self._test_save_load_bare_state(StateGenerateEvent)

    def test_state_battle_event_is_handled_correctly(self):
        state = StateBattleEvent.create(self._context, ('Monster', 7))
        loaded_state = self._test_save_load_state(state)
        self.assertIs(loaded_state._monster_traits, self._monster_traits)
        self.assertEqual(loaded_state._monster_level, 7)

    def test_state_battle_event_without_parametersis_handled_correctly(self):
        state = StateBattleEvent.create(self._context, ())
        loaded_state = self._test_save_load_state(state)
        self.assertIsNone(loaded_state._monster_traits)
        self.assertEqual(loaded_state._monster_level, 0)

    def test_state_start_battle_is_handled_correctly(self):
        enemy = self._create_enemy(self._ghosh_traits)
        state = StateStartBattle.create(self._context, (enemy,))
        loaded_state = self._test_save_load_state(state)
        self.assertIs(loaded_state._enemy.traits, self._ghosh_traits)

    def test_state_battle_prepare_phase_is_handled_correctly(self):
        state = StateBattlePreparePhase.create(self._context, (True,))
        loaded_state = self._test_save_load_state(state)
        self.assertIs(loaded_state._prepare_phase_turn_used, True)

    def test_state_battle_approach_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattleApproach)

    def test_state_battle_phase_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattlePhase)

    def test_state_battle_player_turn_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattlePlayerTurn)

    def test_state_enemy_stats_is_handled_correctly(self):
        self._test_save_load_bare_state(StateEnemyStats)

    def test_state_battle_skip_turn_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattleSkipTurn)

    def test_state_battle_attack_is_handled_correctly(self):
        self._context.familiar = self._create_familiar()
        self._context.start_battle(self._create_enemy(self._monster_traits))
        self._test_save_load_bare_state(StateBattleAttack)

    def test_state_battle_use_spell_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.genus = Genus.Fire
        familiar.set_spell(Spells.find_spell_traits('Brid', Genus.Fire), level=1)
        familiar.mp = 100
        self._context.familiar = familiar
        self._context.start_battle(self._create_enemy())
        self._test_save_load_bare_state(StateBattleUseSpell)

    def test_state_battle_use_ability_is_handled_correctly(self):
        familiar = self._create_familiar()
        familiar.ability = GetSeriousAbility()
        familiar.mp = 100
        self._context.familiar = familiar
        self._context.start_battle(self._create_enemy())
        self._test_save_load_bare_state(StateBattleUseAbility)
        
    def test_item_in_state_battle_use_item_is_handled_correctly(self):
        self._context.inventory.add_item(Pita())
        self._context.inventory.add_item(HolyScroll())
        self._context.inventory.add_item(MedicinalHerb())
        self._context.inventory.add_item(CureAllHerb())
        state = StateBattleUseItem.create(self._context, ('Medicinal ',))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._item_index, 2)

    def _test_state_battle_use_item_target(self, *args) -> StateBattleUseItem:
        self._context.inventory.add_item(Pita())
        state = StateBattleUseItem.create(self._context, ('Pita',) + args)
        return self._test_save_load_state(state)

    def test_familiar_target_in_state_battle_use_item_is_handled_correctly(self):
        self._context.familiar = self._create_familiar()
        loaded_state = self._test_state_battle_use_item_target('on', 'self')
        self.assertIs(loaded_state._target, loaded_state._context.familiar)

    def test_enemy_target_in_state_battle_use_item_is_handled_correctly(self):
        enemy_unit = self._create_enemy()
        self._start_battle(enemy=enemy_unit)
        loaded_state = self._test_state_battle_use_item_target('on', 'enemy')
        self.assertIs(loaded_state._target, loaded_state._context.battle_context.enemy)

    def test_no_target_in_state_battle_use_item_is_handled_correctly(self):
        loaded_state = self._test_state_battle_use_item_target()
        self.assertIs(loaded_state._target, None)

    def test_state_battle_try_to_flee_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattleTryToFlee)

    def test_state_battle_enemy_turn_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattleEnemyTurn)

    def test_state_battle_confused_unit_turn_is_handled_correctly(self):
        self._test_save_load_bare_state(StateBattleConfusedUnitTurn)

    def test_state_item_event_is_handled_correctly(self):
        state = StateItemEvent.create(self._context, ('Fire', 'Ball'))
        loaded_state = self._test_save_load_state(state)
        self.assertIsInstance(loaded_state._item, FireBall)

    def test_state_item_event_without_parameters_is_handled_correctly(self):
        state = StateItemEvent.create(self._context, ())
        loaded_state = self._test_save_load_state(state)
        self.assertIsNone(loaded_state._item)

    def test_state_item_pick_up_is_handled_correctly(self):
        self._test_save_load_bare_state(StateItemPickUp)

    def test_state_item_pick_full_inventory_is_handled_correctly(self):
        self._test_save_load_bare_state(StateItemPickUpFullInventory)

    def test_state_item_pick_up_after_drop_is_handled_correctly(self):
        self._context.inventory.add_item(Pita())
        self._context.inventory.add_item(HolyScroll())
        self._context.inventory.add_item(MedicinalHerb())
        self._context.inventory.add_item(CureAllHerb())
        state = StateItemPickUpAfterDrop.create(self._context, ('Holy ',))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._item_index, 1)

    def test_state_item_pick_up_ignored_is_handled_correctly(self):
        self._test_save_load_bare_state(StateItemPickUpIgnored)

    def test_state_item_event_finished_is_handled_correctly(self):
        self._test_save_load_bare_state(StateItemEventFinished)

    def test_state_trap_event_is_handled_correctly(self):
        self._test_save_load_bare_state(StateTrapEvent)

    def test_state_elevator_event_is_handled_correctly(self):
        self._test_save_load_bare_state(StateElevatorEvent)

    def test_state_elevator_used_is_handled_correctly(self):
        self._test_save_load_bare_state(StateElevatorUsed)

    def test_state_go_up_is_handled_correctly(self):
        self._test_save_load_bare_state(StateGoUp)

    def test_state_elevator_omitted_is_handled_correctly(self):
        self._test_save_load_bare_state(StateElevatorOmitted)

    def test_state_next_floor_is_handled_correctly(self):
        self._test_save_load_bare_state(StateNextFloor)

    def test_state_character_event_is_handled_correctly(self):
        state = StateCharacterEvent.create(self._context, ('Selfi',))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._character, 'Selfi')

    def test_state_character_event_without_parameters_is_handled_correctly(self):
        state = StateCharacterEvent.create(self._context, ())
        loaded_state = self._test_save_load_state(state)
        self.assertIsNone(loaded_state._character)

    def test_state_item_trade_is_handled_correctly(self):
        self._test_save_load_bare_state(StateItemTrade)

    def test_state_item_trade_accepted_is_handled_correctly(self):
        self._context.inventory.add_item(Pita())
        self._context.inventory.add_item(HolyScroll())
        self._context.inventory.add_item(MedicinalHerb())
        self._context.inventory.add_item(CureAllHerb())
        state = StateItemTradeAccepted.create(self._context, ('Cure-All ',))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._item_index, 3)

    def test_state_item_trade_rejected_is_handled_correctly(self):
        self._test_save_load_bare_state(StateItemTradeRejected)

    def test_state_familiar_trade_is_handled_correctly(self):
        self._test_save_load_bare_state(StateFamiliarTrade)

    def test_state_familiar_trade_accepted_is_handled_correctly(self):
        self._test_save_load_bare_state(StateFamiliarTradeAccepted)

    def test_state_familiar_trade_rejected_is_handled_correctly(self):
        self._test_save_load_bare_state(StateFamiliarTradeRejected)

    def test_state_evolve_familiar_is_handled_correctly(self):
        self._test_save_load_bare_state(StateEvolveFamiliar)

    def test_state_familiar_event_is_handled_correctly(self):
        state = StateFamiliarEvent.create(self._context, ('Monster', 7))
        loaded_state = self._test_save_load_state(state)
        self.assertEqual(loaded_state._monster_name, 'Monster')
        self.assertEqual(loaded_state._monster_level, 7)

    def test_state_familiar_event_without_parameters_is_handled_correctly(self):
        state = StateFamiliarEvent.create(self._context, ())
        loaded_state = self._test_save_load_state(state)
        self.assertIsNone(loaded_state._monster_name)
        self.assertIsNone(loaded_state._monster_level)

    def test_state_met_familiar_ignore_is_handled_correctly(self):
        self._test_save_load_bare_state(StateMetFamiliarIgnore)

    def test_state_familiar_fusion_is_handled_correctly(self):
        self._test_save_load_bare_state(StateFamiliarFusion)

    def test_state_familiar_replacement_is_handled_correctly(self):
        self._test_save_load_bare_state(StateFamiliarReplacement)

    def test_state_game_over_is_handled_correctly(self):
        self._test_save_load_bare_state(StateGameOver)


if __name__ == '__main__':
    unittest.main()
