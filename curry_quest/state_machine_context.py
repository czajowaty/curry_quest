import jsonpickle
import random
from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.inventory import Inventory
from curry_quest.items import Item, ItemJsonLoader
from curry_quest.jsonable import Jsonable, InvalidJson, JsonReaderHelper
from curry_quest.state_machine_action import StateMachineAction
from curry_quest.talents import Talents
from curry_quest.traits import UnitTraits, SpellCastContext
from curry_quest.unit import Unit
from curry_quest.unit_creator import UnitCreator
from curry_quest.records import Records
from curry_quest.records_events_handler import RecordsEventsHandler, EmptyRecordsEventsHandler


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

    def __init__(self, game_config: Config):
        self._game_config = game_config
        self._records_events_handler: RecordsEventsHandler = EmptyRecordsEventsHandler()
        self._current_climb_records = Records()
        self._is_tutorial_done = False
        self._floor = self.MIN_FLOOR
        self._familiar = None
        self._inventory = Inventory()
        self._battle_context = None
        self._last_met_character = ''
        self._item_buffer = None
        self._unit_buffer = None
        self._rng = random.Random()
        self._responses = []
        self._generated_action = None
        self._floor_turns_counter = 0

    def to_json_object(self):
        json_object = {
            'records': self.records.to_json_object(),
            'is_tutorial_done': self.is_tutorial_done,
            'floor': self.floor,
            'inventory': self.inventory.to_json_object(),
            'last_met_character': self.last_met_character,
            'rng_state': jsonpickle.encode(self.rng.getstate()),
            'responses': self._responses,
            'floor_turns_counter': self._floor_turns_counter
        }
        if self._familiar is not None:
            json_object['familiar'] = self._familiar.to_json_object()
        if self.is_in_battle():
            json_object['battle_context'] = self.battle_context.to_json_object()
        if self._item_buffer is not None:
            json_object['item_buffer'] = self._item_buffer.to_json_object()
        if self._unit_buffer is not None:
            json_object['unit_buffer'] = self._unit_buffer.to_json_object()
        return json_object

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
        self.last_met_character = json_reader_helper.read_string('last_met_character')
        if 'item_buffer' in json_object:
            self.buffer_item(ItemJsonLoader.from_json_object(json_object['item_buffer']))
        if 'unit_buffer' in json_object:
            self.buffer_unit(self.create_monster_from_json_object(json_object['unit_buffer']))
        self._rng.setstate(jsonpickle.decode(json_reader_helper.read_string('rng_state')))
        self._responses = json_reader_helper.read_list('responses')
        self._floor_turns_counter = json_reader_helper.read_int_with_min('floor_turns_counter', min_value=0)

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
    def last_met_character(self) -> str:
        return self._last_met_character

    @last_met_character.setter
    def last_met_character(self, value):
        self._last_met_character = value

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

    def create_spell_cast_context(self, caster: Unit, other_unit: Unit) -> SpellCastContext:
        if not caster.has_spell():
            raise InvalidOperation(f'{caster.name} does not have a spell')
        spell_cast_context = SpellCastContext()
        spell_cast_context.caster = caster
        target = caster.spell.select_target(caster, other_unit)
        spell_cast_context.target = target
        spell_cast_context.other_than_target = other_unit if target is caster else caster
        spell_cast_context.state_machine_context = self
        return spell_cast_context

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
        return self.rng.choices(list(element_weight_dictionary.keys()), list(element_weight_dictionary.values()))[0]

    def _remove_enemy_forbidden_talents(self, enemy_traits: UnitTraits):
        enemy_traits.talents &= ~(Talents.StrengthIncreased | Talents.Hard)

    def generate_action(self, command, *args):
        if self._generated_action is not None:
            raise InvalidOperation(f'Already generated - {self._generated_action}')
        self._generated_action = StateMachineAction(command, args, is_given_by_admin=True)

    def has_action(self) -> bool:
        return self._generated_action is not None

    def take_action(self) -> StateMachineAction:
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
