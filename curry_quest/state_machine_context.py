import jsonpickle
from curry_quest.errors import InvalidOperation
from curry_quest.inventory import Inventory
from curry_quest.item_use_unit_action import ItemUseActionHandler
from curry_quest.items import Item, ItemJsonLoader
from curry_quest.jsonable import Jsonable, InvalidJson, JsonReaderHelper
from curry_quest.physical_attack_unit_action import PhysicalAttackUnitActionHandler
from curry_quest.records import Records
from curry_quest.records_events_handler import RecordsEventsHandler, EmptyRecordsEventsHandler
from curry_quest.spell_cast_unit_action import SpellCastContext, SpellCastActionHandler
from curry_quest.state_machine_action import StateMachineAction
from curry_quest.talents import Talents
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit_creator import UnitCreator
from curry_quest.unit_traits import UnitTraits
from curry_quest.services import Services
from curry_quest.weight import WeightHandler
import logging

logger = logging.getLogger(__name__)


class BattleContext(Jsonable):
    MIN_COUNTER = 0

    def __init__(self, enemy: Unit):
        self._enemy = enemy
        self._prepare_phase_counter = self.MIN_COUNTER
        self._holy_scroll_counter = self.MIN_COUNTER
        self.is_first_turn = True
        self.is_player_turn = True
        self.clear_turn_counter()
        self._finished = False

    def to_json_object(self):
        return {
            'enemy': self._enemy.to_json_object(),
            'prepare_phase_counter': self._prepare_phase_counter,
            'holy_scroll_counter': self._holy_scroll_counter,
            'is_first_turn': self.is_first_turn,
            'is_player_turn': self.is_player_turn,
            'turn_counter': self._turn_counter,
            'finished': self._finished
        }

    def from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        self._prepare_phase_counter = json_reader_helper.read_int_with_min(
            'prepare_phase_counter',
            min_value=self.MIN_COUNTER)
        self._holy_scroll_counter = json_reader_helper.read_int_with_min(
            'holy_scroll_counter',
            min_value=self.MIN_COUNTER)
        self.is_first_turn = json_reader_helper.read_bool('is_first_turn')
        self.is_player_turn = json_reader_helper.read_bool('is_player_turn')
        self._turn_counter = json_reader_helper.read_int_with_min('turn_counter', min_value=self.MIN_COUNTER)
        self._finished = json_reader_helper.read_bool('finished')

    @classmethod
    def enemy_json_object(cls, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        return json_reader_helper.read_dict('enemy')

    @property
    def enemy(self) -> Unit:
        return self._enemy

    def start_prepare_phase(self, counter: int):
        self._prepare_phase_counter = counter

    def is_prepare_phase(self) -> bool:
        return self._prepare_phase_counter > self.MIN_COUNTER

    def dec_prepare_phase_counter(self):
        self._prepare_phase_counter -= 1

    def finish_prepare_phase(self):
        self._prepare_phase_counter = self.MIN_COUNTER

    def is_holy_scroll_active(self) -> bool:
        return self._holy_scroll_counter > self.MIN_COUNTER

    def dec_holy_scroll_counter(self):
        self._holy_scroll_counter -= 1

    def set_holy_scroll_counter(self, counter):
        self._holy_scroll_counter = counter

    @property
    def turn_counter(self):
        return self._turn_counter

    def inc_turn_counter(self):
        self._turn_counter += 1

    def clear_turn_counter(self):
        self._turn_counter = self.MIN_COUNTER

    def is_finished(self):
        return self._finished

    def finish_battle(self):
        self._finished = True


class StateMachineContext(Jsonable):
    RESPONSE_LINE_BREAK = '\n'
    MIN_FLOOR = 0

    def __init__(self, game_config, services: Services=None):
        from curry_quest.config import Config

        self._game_config: Config = game_config
        self._services = services or Services()
        self._records_events_handler: RecordsEventsHandler = EmptyRecordsEventsHandler()
        self._current_climb_records = Records()
        self._is_tutorial_done = False
        self._floor = self.MIN_FLOOR
        self._familiar = None
        self._inventory = Inventory()
        self._battle_context: BattleContext = None
        self._item_buffer = None
        self._unit_buffer = None
        self._rng = self._services.rng()
        self._responses = []
        self._generated_action = None
        self._floor_turns_counter = 0
        self._go_up_on_next_event_finished_flag = False
        self._event_weight_handlers = {}
        self._item_weight_handlers = {}
        self._character_weight_handlers = {}
        self._trap_weight_handlers = {}
        self._fill_weight_handlers(self.game_config.events_weights, self._event_weight_handlers, key_suffix='_event')
        self._fill_weight_handlers(self.game_config.found_items_weights, self._item_weight_handlers)
        self._fill_weight_handlers(self.game_config.character_events_weights, self._character_weight_handlers)
        self._fill_weight_handlers(self.game_config.traps_weights, self._trap_weight_handlers)

    def _fill_weight_handlers(self, weight_descriptors, weight_handlers, key_suffix=''):
        for key, weight_descriptor in weight_descriptors.items():
            weight_handlers[key + key_suffix] = WeightHandler.from_descriptor(weight_descriptor)

    def to_json_object(self):
        json_object = {
            'records': self.records.to_json_object(),
            'is_tutorial_done': self.is_tutorial_done,
            'floor': self.floor,
            'inventory': self.inventory.to_json_object(),
            'rng_state': jsonpickle.encode(self.rng.getstate()),
            'responses': self._responses,
            'floor_turns_counter': self._floor_turns_counter,
            'go_up_on_next_event_finished_flag': self._go_up_on_next_event_finished_flag
        }
        if self._familiar is not None:
            json_object['familiar'] = self._familiar.to_json_object()
        if self.is_in_battle():
            json_object['battle_context'] = self.battle_context.to_json_object()
        if self._item_buffer is not None:
            json_object['item_buffer'] = self._item_buffer.to_json_object()
        if self._unit_buffer is not None:
            json_object['unit_buffer'] = self._unit_buffer.to_json_object()
        if self.has_action():
            json_object['generated_action'] = self._generated_action_to_json_object()
        json_object['events_penalties'] = self._weight_handlers_to_json_object(self._event_weight_handlers)
        json_object['items_penalties'] = self._weight_handlers_to_json_object(self._item_weight_handlers)
        json_object['characters_penalties'] = self._weight_handlers_to_json_object(self._character_weight_handlers)
        json_object['traps_penalties'] = self._weight_handlers_to_json_object(self._trap_weight_handlers)
        return json_object

    def _generated_action_to_json_object(self):
        delay, action = self._generated_action
        if not self._does_action_have_trivial_args(action):
            raise InvalidOperation(f'Action with non-trivial arguments cannot be converted to JSON - "{action}"')
        return {
            'delay': delay,
            'command': action.command,
            'args': action.args
        }

    def _does_action_have_trivial_args(self, action: StateMachineAction) -> bool:
        for arg in action.args:
            if not isinstance(arg, (int, str)):
                return False
        return True

    def _weight_handlers_to_json_object(self, weight_handlers):
        return {
            key: weight_handler.penalty_timer
            for key, weight_handler
            in weight_handlers.items()
            if weight_handler.has_penalty()
        }

    def from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        self._is_tutorial_done = json_reader_helper.read_bool('is_tutorial_done')
        self._current_climb_records.from_json_object(json_reader_helper.read_dict('records'))
        self._floor = json_reader_helper.read_int_in_range(
            'floor',
            min_value=self.MIN_FLOOR,
            max_value=self.game_config.highest_floor + 1)
        self._inventory.from_json_object(json_reader_helper.read_list('inventory'))
        if 'familiar' in json_object:
            self._familiar = self.create_familiar_from_json_object(json_object['familiar'])
        if 'battle_context' in json_object:
            self._read_battle_context_from_json_object(json_reader_helper.read_dict('battle_context'))
        if 'item_buffer' in json_object:
            self.buffer_item(ItemJsonLoader.from_json_object(json_object['item_buffer']))
        if 'unit_buffer' in json_object:
            self.buffer_unit(self.create_monster_from_json_object(json_object['unit_buffer']))
        self._rng.setstate(jsonpickle.decode(json_reader_helper.read_string('rng_state')))
        self._responses = json_reader_helper.read_list('responses')
        generated_action_json_object = json_reader_helper.read_optional_value_of_type('generated_action', dict)
        if generated_action_json_object is not None:
            self._read_generated_action_from_json_object(generated_action_json_object)
        self._floor_turns_counter = json_reader_helper.read_int_with_min('floor_turns_counter', min_value=0)
        self._go_up_on_next_event_finished_flag = json_reader_helper.read_bool('go_up_on_next_event_finished_flag')
        self._read_weight_handlers_from_json_object(
            json_reader_helper,
            penalties_key='events_penalties',
            weight_handlers=self._event_weight_handlers)
        self._read_weight_handlers_from_json_object(
            json_reader_helper,
            penalties_key='items_penalties',
            weight_handlers=self._item_weight_handlers)
        self._read_weight_handlers_from_json_object(
            json_reader_helper,
            penalties_key='characters_penalties',
            weight_handlers=self._character_weight_handlers)
        self._read_weight_handlers_from_json_object(
            json_reader_helper,
            penalties_key='traps_penalties',
            weight_handlers=self._trap_weight_handlers)

    def _read_generated_action_from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        delay = json_reader_helper.read_int_with_min('delay', min_value=0)
        command = json_reader_helper.read_non_empty_string('command')
        args = json_reader_helper.read_list('args')
        self.generate_delayed_action(delay, command, *args)

    def _read_weight_handlers_from_json_object(
            self,
            json_reader_helper: JsonReaderHelper,
            penalties_key: str,
            weight_handlers: dict):
        penalties_json_object = json_reader_helper.read_optional_value_of_type(penalties_key, dict)
        if penalties_json_object is None:
            return
        penalties_json_reader_helper = JsonReaderHelper(penalties_json_object)
        for key, weight_handler in weight_handlers.items():
            if key in penalties_json_reader_helper:
                penalty_timer = penalties_json_reader_helper.read_non_negative(key)
                weight_handler.penalty_timer = penalty_timer

    @property
    def services(self) -> Services:
        return self._services

    @property
    def records_events_handler(self):
        return self._records_events_handler

    @records_events_handler.setter
    def records_events_handler(self, new_records_events_handler):
        self._records_events_handler = new_records_events_handler

    @property
    def records(self):
        return self._current_climb_records

    def reset_current_climb_records(self):
        self._current_climb_records = Records()

    def create_familiar_from_json_object(self, unit_json_object):
        return self._create_unit_from_json_object(unit_json_object, self.game_config.monsters_traits)

    def create_monster_from_json_object(self, unit_json_object):
        return self._create_unit_from_json_object(unit_json_object, self.game_config.all_units_traits)

    def _create_unit_from_json_object(self, unit_json_object, units_traits):
        traits_name = Unit.traits_name_from_json_object(unit_json_object)
        if traits_name not in units_traits:
            raise InvalidJson(f'Unknown unit name "{traits_name}". JSON object: {unit_json_object}.')
        traits = units_traits[traits_name]
        unit = Unit(traits, self.game_config.levels)
        unit.from_json_object(unit_json_object)
        return unit

    def _read_battle_context_from_json_object(self, json_object):
        enemy = self.create_monster_from_json_object(BattleContext.enemy_json_object(json_object))
        self.start_battle(enemy)
        self._battle_context.from_json_object(json_object)

    @property
    def game_config(self):
        return self._game_config

    @property
    def is_tutorial_done(self) -> bool:
        return self._is_tutorial_done

    def set_tutorial_done(self):
        self._is_tutorial_done = True

    @property
    def floor(self):
        return self._floor

    @floor.setter
    def floor(self, value):
        self._floor = value
        self._floor_turns_counter = 0

    def is_at_the_top_of_tower(self) -> bool:
        return self._floor > self.game_config.highest_floor

    @property
    def familiar(self) -> Unit:
        return self._familiar

    @familiar.setter
    def familiar(self, value):
        self._familiar = value

    @property
    def inventory(self) -> Inventory:
        return self._inventory

    @property
    def battle_context(self) -> BattleContext:
        return self._battle_context

    def clear_item_buffer(self):
        self._item_buffer = None

    def buffer_item(self, item: Item):
        if self._item_buffer is not None:
            raise InvalidOperation(f'Item already buffered - {self._item_buffer.name}')
        self._item_buffer = item

    def peek_buffered_item(self) -> Item:
        return self._item_buffer

    def take_buffered_item(self) -> Item:
        item = self.peek_buffered_item()
        self.clear_item_buffer()
        return item

    def clear_unit_buffer(self):
        self._unit_buffer = None

    def buffer_unit(self, unit: Unit):
        self._unit_buffer = unit

    def peek_buffered_unit(self) -> Unit:
        return self._unit_buffer

    def take_buffered_unit(self) -> Unit:
        unit = self.peek_buffered_unit()
        self.clear_unit_buffer()
        return unit

    @property
    def rng(self):
        return self._rng

    def does_action_succeed(self, success_chance: float):
        return self.rng.random() < success_chance

    def is_in_battle(self) -> bool:
        return self._battle_context is not None

    def clear_battle_context(self):
        self._battle_context = None

    def start_battle(self, enemy: Unit):
        if self.is_in_battle():
            raise InvalidOperation(f'Battle already started - {enemy.name}')
        self._battle_context = BattleContext(enemy)

    def finish_battle(self):
        if not self.is_in_battle():
            raise InvalidOperation(f'Battle not started')
        self.clear_battle_context()

    def generate_floor_monster(self, floor: int, level_increase: int=0) -> Unit:
        highest_floor = self.game_config.highest_floor
        if floor > highest_floor:
            raise InvalidOperation(f'Highest floor is {highest_floor}')
        floor_descriptor = self.game_config.floors[floor]
        monster_descriptor = self.random_selection_with_weights(
            dict(zip(floor_descriptor.monsters, floor_descriptor.weights)))
        monster_traits = self.game_config.monsters_traits[monster_descriptor.name].copy()
        self._remove_enemy_forbidden_talents(monster_traits)
        monster_level = min(monster_descriptor.level + level_increase, self.game_config.levels.max_level)
        return UnitCreator(monster_traits).create(monster_level, levels=self.game_config.levels)

    def generate_non_evolved_monster(self, level: int) -> Unit:
        monsters_traits = self.game_config.non_evolved_monster_traits
        monster_name = self.rng.choice(list(monsters_traits.keys()))
        return UnitCreator(monsters_traits[monster_name]) \
            .create(level=level, levels=self.game_config.levels)

    def random_selection_with_weights(self, element_weight_dictionary: dict):
        logger.info(f"Selecting with weights '{element_weight_dictionary}'.")
        return self.rng.choices(list(element_weight_dictionary.keys()), list(element_weight_dictionary.values()))[0]

    def _remove_enemy_forbidden_talents(self, enemy_traits: UnitTraits):
        enemy_traits.talents &= ~(Talents.StrengthIncreased | Talents.Hard)

    def generate_action(self, command, *args):
        self._generate_action(0, command, *args)

    def generate_delayed_action(self, delay, command, *args):
        self._generate_action(delay, command, *args)
        _, action = self._generated_action
        if not self._does_action_have_trivial_args(action):
            raise InvalidOperation(f'Cannot generate delayed action with non-trivial arguments - "{action}"')

    def _generate_action(self, delay, command, *args):
        if self._generated_action is not None:
            raise InvalidOperation(f'Already generated - {self._generated_action}')
        self._generated_action = (delay, StateMachineAction.by_admin(command, *args))

    def has_action(self) -> bool:
        return self._generated_action is not None

    def take_action(self) -> tuple[int, StateMachineAction]:
        action = self._generated_action
        self._generated_action = None
        return action

    def add_response(self, response: str):
        self._responses.append(response)

    def add_response_line_break(self):
        self._responses.append(self.RESPONSE_LINE_BREAK)

    def peek_responses(self) -> list:
        return self._responses[:]

    def take_responses(self) -> list:
        responses = self.peek_responses()
        self._responses.clear()
        return responses

    @property
    def floor_turns_counter(self):
        return self._floor_turns_counter

    def increase_turns_counter(self):
        self._current_climb_records.turns_counter += 1
        self._floor_turns_counter += 1

    def is_earthquake_turn(self):
        return self._floor_turns_counter == self.game_config.eq_settings.earthquake_turn

    def turns_until_earthquake(self):
        return self._turns_until_turn(self.game_config.eq_settings.earthquake_turn)

    def is_earthquake_done(self):
        return self.turns_until_earthquake() == 0

    def is_floor_collapse_turn(self):
        return self._floor_turns_counter >= self.game_config.eq_settings.floor_collapse_turn

    def turns_until_floor_collapse(self):
        return self._turns_until_turn(self.game_config.eq_settings.floor_collapse_turn)

    def _turns_until_turn(self, turn):
        result = turn - self._floor_turns_counter
        return result if result > 0 else 0

    def should_go_up_on_next_event_finished(self) -> bool:
        return self._go_up_on_next_event_finished_flag

    def set_go_up_on_next_event_finished_flag(self):
        self._go_up_on_next_event_finished_flag = True

    def clear_go_up_on_next_event_finished_flag(self):
        self._go_up_on_next_event_finished_flag = False

    def create_physical_attack_without_target(self, attacker: Unit):
        action_handler = PhysicalAttackUnitActionHandler(attacker.physical_attack_mp_cost)
        action_context = UnitActionContext()
        action_context.performer = attacker
        action_context.state_machine_context = self
        return action_handler, action_context

    def create_physical_attack_with_target(self, attacker: Unit, other_unit: Unit):
        return self._create_action_with_target(
            self.create_physical_attack_without_target,
            attacker,
            other_unit)

    def create_spell_without_target(self, caster: Unit):
        if not caster.has_spell():
            raise InvalidOperation(f'{self.name} does not have a spell')
        action_handler = SpellCastActionHandler(caster.spell_traits)
        action_context = SpellCastContext(caster.spell_level)
        action_context.performer = caster
        action_context.state_machine_context = self
        return action_handler, action_context

    def create_spell_with_target(self, caster: Unit, other_unit: Unit):
        action_handler, action_context = self._create_action_with_target(
            self.create_spell_without_target,
            caster,
            other_unit)
        target = action_context.target
        if target is not None:
            action_context.reflected_target = other_unit if target is caster else caster
        return action_handler, action_context

    def _create_action_with_target(self, create_action_without_target, performer, other_unit):
        action_handler, action_context = create_action_without_target(performer)
        action_context.target = action_handler.select_target(performer, other_unit)
        return action_handler, action_context

    def create_item_use_without_target(self, item: Item) -> tuple[ItemUseActionHandler, UnitActionContext]:
        action_handler = ItemUseActionHandler(item)
        action_context = UnitActionContext()
        action_context.performer = self._familiar
        action_context.state_machine_context = self
        return action_handler, action_context

    def create_item_use_with_target(self, item: Item, target: Unit):
        action_handler, action_context = self.create_item_use_without_target(item)
        if target is None:
            action_context.target = action_handler.select_target(
                self._familiar,
                self.battle_context.enemy if self.is_in_battle() else None)
        else:
            action_context.target = target
        return action_handler, action_context

    @property
    def events_weights(self):
        return self._create_weights(self._event_weight_handlers)

    @property
    def items_weights(self):
        return self._create_weights(self._item_weight_handlers)

    @property
    def characters_weights(self):
        return self._create_weights(self._character_weight_handlers)

    @property
    def trap_weights(self):
        return self._create_weights(self._trap_weight_handlers)

    def _create_weights(self, weight_handlers):
        weights = {}
        for key, weight_handler in weight_handlers.items():
            weight_value = weight_handler.value(self)
            if weight_value > 0:
                weights[key] = weight_value
        return weights

    def set_event_weight_penalty(self, event):
        self._set_weight_penalty(self._event_weight_handlers, event)

    def set_character_weight_penalty(self, character):
        self._set_weight_penalty(self._character_weight_handlers, character)

    def set_item_weight_penalty(self, item_name):
        self._set_weight_penalty(self._item_weight_handlers, item_name)

    def set_trap_weight_penalty(self, trap):
        self._set_weight_penalty(self._trap_weight_handlers, trap)

    def _set_weight_penalty(self, weight_handlers, key):
        weight_handlers[key].set_penalty()

    def decrease_weight_penalty_timers(self):
        self._decrease_weight_penalty_timers(self._event_weight_handlers)
        self._decrease_weight_penalty_timers(self._item_weight_handlers)
        self._decrease_weight_penalty_timers(self._character_weight_handlers)
        self._decrease_weight_penalty_timers(self._trap_weight_handlers)

    def _decrease_weight_penalty_timers(self, weight_handlers):
        for weight_handler in weight_handlers.values():
            weight_handler.decrease_penalty_timer()
