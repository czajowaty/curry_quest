from json_config_parser import JsonConfigParser
from collections.abc import Mapping, Sequence
from curry_quest.floor_descriptor import FloorDescriptor, Monster
from curry_quest.genus import Genus
from curry_quest.items import all_items
from curry_quest.levels_config import Levels
from curry_quest.spells import Spells
from curry_quest.talents import Talents
from curry_quest.unit_traits import UnitTraits


class Config:
    class InvalidConfig(Exception):
        pass

    class Timers:
        def __init__(self):
            self.event_interval = 0
            self.event_penalty_duration = 0

    class EarthquakeSettings:
        def __init__(self):
            self.earthquake_turn = 0
            self.floor_collapse_turn = 0

    class Probabilities:
        def __init__(self):
            self.flee = 0.0

    class PlayerSelectionWeights:
        def __init__(self):
            self.without_penalty = 0
            self.with_penalty = 0

    class SpecialUnitsTraits:
        def __init__(self):
            self.ghosh = UnitTraits()

    class WeightRange:
        def __init__(self, start, end):
            self.start = start
            self.end = end

        def int_value_at(self, fraction) -> int:
            return round(self.value_at(fraction))

        def value_at(self, fraction) -> float:
            return (1.0 - fraction) * self.start + fraction * self.end

    def __init__(self):
        self._timers = self.Timers()
        self._eq_settings = self.EarthquakeSettings()
        self._probabilities = self.Probabilities()
        self._player_selection_weights = self.PlayerSelectionWeights()
        self.events_weights = {}
        self.character_events_weights = {}
        self.traps_weights = {}
        self.found_items_weights = {}
        self._levels = Levels()
        self._default_physical_attack_mp_cost = 0
        self._monsters_traits = {}
        self._special_units_traits = self.SpecialUnitsTraits()
        self._floors = []

    @property
    def timers(self):
        return self._timers

    @property
    def eq_settings(self):
        return self._eq_settings

    @property
    def probabilities(self):
        return self._probabilities

    @property
    def player_selection_weights(self):
        return self._player_selection_weights

    @property
    def levels(self):
        return self._levels

    @property
    def monsters_traits(self) -> Mapping[str, UnitTraits]:
        return self._monsters_traits

    @property
    def non_evolved_monster_traits(self) -> Mapping[str, UnitTraits]:
        monsters_traits = self.monsters_traits
        return dict(
            (monster_traits.name, monster_traits)
            for monster_traits
            in monsters_traits.values()
            if not monster_traits.is_evolved)

    @property
    def special_units_traits(self):
        return self._special_units_traits

    @property
    def all_units_traits(self) -> Mapping[str, UnitTraits]:
        all_units_traits = {}
        all_units_traits.update(self.monsters_traits)
        ghosh_traits = self.special_units_traits.ghosh
        all_units_traits[ghosh_traits.name] = ghosh_traits
        return all_units_traits

    @property
    def floors(self) -> Sequence[FloorDescriptor]:
        return self._floors

    @property
    def highest_floor(self) -> int:
        return len(self._floors) - 1

    class Parser(JsonConfigParser):
        def __init__(self, config_file):
            super().__init__(config_file, Config)

        def _parse(self):
            self._read_timers()
            self._read_eq_settings()
            self._read_probabilities()
            self._read_player_selection_weights()
            self._read_events_weights()
            self._config.found_items_weights = self._config_json['found_items_weights']
            self._config.character_events_weights = self._config_json['characters_events_weights']
            self._config.traps_weights = self._config_json['traps_weights']
            self._read_levels()
            self._default_monster_action_weights = self._read_monster_action_weights(
                self._config_json['default_monster_action_weights'])
            self._default_physical_attack_mp_cost = self._config_json['default_physical_attack_mp_cost']
            self._read_monsters_traits()
            self._read_special_units_traits()
            self._read_floors()

        def _read_timers(self):
            timers = self._config._timers
            timers_json = self._config_json['timers']
            try:
                timers.event_interval = int(timers_json['event_interval'])
                timers.event_penalty_duration = int(timers_json['event_penalty_duration'])
            except ValueError as exc:
                raise self.InvalidConfig(f"{timers_json}: {exc}")

        def _read_eq_settings(self):
            eq_settings = self._config._eq_settings
            eq_settings_json = self._config_json['earthquake_settings']
            try:
                eq_settings.earthquake_turn = int(eq_settings_json['turns_to_earthquake'])
                eq_settings.floor_collapse_turn = eq_settings.earthquake_turn
                eq_settings.floor_collapse_turn += int(eq_settings_json['turns_from_earthquake_to_floor_collapse'])
            except ValueError as exc:
                raise self.InvalidConfig(f"{eq_settings_json}: {exc}")

        def _read_probabilities(self):
            probabilities = self._config._probabilities
            probabilities_json = self._config_json['probabilities']
            try:
                probabilities.flee = float(probabilities_json['flee'])
            except ValueError as exc:
                raise self.InvalidConfig(f"{probabilities_json}: {exc}")

        def _read_player_selection_weights(self):
            player_selection_weights = self._config._player_selection_weights
            player_selection_weights_json = self._config_json['player_selection_weights']
            try:
                player_selection_weights.without_penalty = player_selection_weights_json['without_penalty']
                player_selection_weights.with_penalty = player_selection_weights_json['with_penalty']
            except ValueError as exc:
                raise self.InvalidConfig(f"{player_selection_weights_json}: {exc}")

        def _read_events_weights(self):
            events_weights = self._config_json['events_weights']
            elevator_weight = events_weights['elevator']
            events_weights['elevator'] = Config.WeightRange(elevator_weight['start'], elevator_weight['end'])
            self._config.events_weights = events_weights

        def _read_levels(self):
            levels = self._config._levels
            levels_json = self._config_json['experience_per_level']
            experience_for_prev_level = -1
            for level, experience_for_next_level in enumerate(levels_json, start=1):
                if experience_for_next_level <= experience_for_prev_level:
                    raise self.InvalidConfig(
                        f'Experience required for LVL {level} is not greater than for LVL {level - 1}')
                levels.add_level(experience_for_next_level)
                experience_for_prev_level = experience_for_next_level

        def _read_monster_action_weights(self, monster_action_weights_json):
            action_weights = UnitTraits.ActionWeights()
            try:
                action_weights.physical_attack = int(monster_action_weights_json['physical_attack'])
                action_weights.spell = int(monster_action_weights_json['spell'])
            except ValueError as exc:
                self._invalid_config(f'{monster_action_weights_json}: {exc}')
            return action_weights

        def _read_monsters_traits(self):
            monsters_json = self._config_json['monsters']
            monsters_traits = {}
            for monster_json in monsters_json:
                monster_traits = self._create_unit_traits(monster_json)
                if monster_traits.name in monsters_traits:
                    raise self.InvalidConfig(f"Double entry for monster '{monster_traits.name}' traits")
                monsters_traits[monster_traits.name] = monster_traits
            self._config._monsters_traits = monsters_traits

        def _create_unit_traits(self, unit_json):
            unit_traits = UnitTraits()
            try:
                unit_traits.name = unit_json['name']
                unit_traits.base_hp = unit_json['base_hp']
                unit_traits.hp_growth = unit_json['hp_growth']
                unit_traits.base_mp = unit_json['base_mp']
                unit_traits.mp_growth = unit_json['mp_growth']
                unit_traits.base_attack = unit_json['base_attack']
                unit_traits.attack_growth = unit_json['attack_growth']
                unit_traits.base_defense = unit_json['base_defense']
                unit_traits.defense_growth = unit_json['defense_growth']
                unit_traits.base_luck = unit_json['base_luck']
                unit_traits.luck_growth = unit_json['luck_growth']
                unit_traits.base_exp_given = unit_json['base_exp']
                unit_traits.exp_given_growth = unit_json['exp_growth']
                unit_traits.native_genus = self._parse_genus(unit_json['element'])
                unit_traits.physical_attack_mp_cost = self._parse_physical_attack_mp_cost(unit_json)
                unit_traits.native_spell_base_name = unit_json.get('spell')
                unit_traits.dormant_spell_base_name = unit_json.get('dormant_spell')
                if 'action_weights' in unit_json:
                    unit_traits.action_weights = self._read_monster_action_weights(unit_json['action_weights'])
                else:
                    unit_traits.action_weights = self._default_monster_action_weights.copy()
                unit_traits.talents = self._parse_talents(unit_json.get('talents'))
                unit_traits.is_evolved = unit_json.get('is_evolved', False)
                unit_traits.evolves_into = unit_json.get('evolves_into')
            except KeyError as exc:
                self._invalid_config(f'{unit_json}: missing key {exc}')
            except ValueError as exc:
                self._invalid_config(f'{unit_json}: {exc}')
            return unit_traits

        def _parse_genus(self, genus_name):
            if genus_name == 'None':
                return Genus.Empty
            for genus in Genus:
                if genus.name == genus_name:
                    return genus
            raise ValueError(f'Unknown genus "{genus_name}"')

        def _parse_physical_attack_mp_cost(self, unit_json):
            return unit_json['physical_attack_mp_cost'] \
                if 'physical_attack_mp_cost' in \
                unit_json else self._default_physical_attack_mp_cost

        def _parse_talents(self, talents_string):
            if talents_string is None:
                return Talents.Empty
            talents = Talents.Empty
            for talent_name in talents_string.split(','):
                talents |= self._parse_talent(talent_name)
            return talents

        def _parse_talent(self, talent_name):
            for talent in Talents:
                if talent.name == talent_name:
                    return talent
            raise ValueError(f'Unknown talent "{talent_name}"')

        def _read_special_units_traits(self):
            special_units_traits = self._config._special_units_traits
            special_units_json = self._config_json['special_units']
            try:
                special_units_traits.ghosh = self._create_unit_traits(special_units_json['ghosh'])
            except KeyError as exc:
                raise self.InvalidConfig(f'Missing special units traits - {exc}')

        def _read_floors(self):
            floors_json = self._config_json['floors']
            floors = []
            for floor_json in floors_json:
                floors.append(self._create_floor(floor_json))
            self._config._floors = floors

        def _create_floor(self, floor_json):
            floor = FloorDescriptor()
            try:
                for monster_json in floor_json:
                    floor.add_monster(
                        Monster(monster_json['monster'], monster_json['level']),
                        monster_json['weight'])
            except KeyError as exc:
                raise self.InvalidConfig(f"{floor_json}: missing key {exc}")
            return floor

        def _validate_config(self):
            self._validate_earthquake_settings()
            self._validate_probabilities()
            self._validate_events_weights()
            self._validate_found_items_weights()
            self._validate_characters_events_weights()
            self._validate_traps_weights()
            self._validate_experience_per_level()
            self._validate_monsters_traits()
            self._validate_floors()

        def _validate_earthquake_settings(self):
            if self._config.eq_settings.earthquake_turn == 0:
                raise self.InvalidConfig(f'"turns_to_earthquake" value must be greater than 0.')
            if self._config.eq_settings.floor_collapse_turn == self._config.eq_settings.earthquake_turn:
                raise self.InvalidConfig(f'"turns_from_earthquake_to_floor_collapse" value must be greater than 0.')

        def _validate_probabilities(self):
            self._validate_probability('flee', self._config.probabilities.flee)

        def _validate_probability(self, name, probability):
            min_probability = 0.0
            max_probability = 1.0
            if probability < min_probability or probability > max_probability:
                raise self.InvalidConfig(
                    f'Probability "{name}"={probability} is outside range [{min_probability}-{max_probability}]')

        def _validate_events_weights(self):
            self._validate_weights_dictionary(
                'events_weights',
                self._config.events_weights,
                ['battle', 'character', 'elevator', 'item', 'trap', 'familiar'])

        def _validate_found_items_weights(self):
            self._validate_weights_dictionary(
                'found_items_weights',
                self._config.found_items_weights,
                [item.name for item in all_items()])

        def _validate_characters_events_weights(self):
            self._validate_weights_dictionary(
                'character_events_weights',
                self._config.character_events_weights,
                ['Cherrl', 'Nico', 'Patty', 'Fur', 'Selfi', 'Mia', 'Vivianne', 'Ghosh', 'Beldo'])

        def _validate_traps_weights(self):
            self._validate_weights_dictionary(
                'traps_weights',
                self._config.traps_weights,
                ['Slam', 'Sleep', 'Upheaval', 'Crack', 'Go up', 'Blinder'])

        def _validate_weights_dictionary(self, dictionary_name, weights_dictionary, expected_keys):
            missing_keys = set(expected_keys) - set(weights_dictionary.keys())
            if len(missing_keys) > 0:
                missing_keys_string = ', '.join(f'"{missing_key}"' for missing_key in missing_keys)
                raise self.InvalidConfig(f'"{dictionary_name}" - missing weights for: {missing_keys_string}')
            excessive_keys = set(weights_dictionary.keys()) - set(expected_keys)
            if len(excessive_keys) > 0:
                excessive_keys_string = ', '.join(f'"{excessive_key}"' for excessive_key in excessive_keys)
                raise self.InvalidConfig(f'"{dictionary_name}" - excessive_keys weights for: {excessive_keys_string}')
            summed_start_weight = 0
            summed_end_weight = 0
            for key, value in weights_dictionary.items():
                if isinstance(value, int):
                    summed_start_weight += value
                    summed_end_weight += value
                elif isinstance(value, Config.WeightRange):
                    summed_start_weight += value.start
                    summed_end_weight += value.end
                else:
                    raise self.InvalidConfig(f'"{dictionary_name}" - unexpected value ("{key}": "{value}")')
            if summed_start_weight == 0:
                raise self.InvalidConfig(f'"{dictionary_name}" - all start weights are 0s')
            if summed_end_weight == 0:
                raise self.InvalidConfig(f'"{dictionary_name}" - all end weights are 0s')

        def _validate_experience_per_level(self):
            if self._config.levels.max_level == 0:
                raise self.InvalidConfig(f'No levels defined')

        def _validate_monsters_traits(self):
            for monster_trait in self._config.monsters_traits.values():
                try:
                    spell_type = 'native'
                    Spells.find_spell_category_traits(monster_trait.native_spell_base_name)
                    spell_type = 'dormant'
                    Spells.find_spell_category_traits(monster_trait.dormant_spell_base_name)
                except ValueError as exc:
                    raise self.InvalidConfig(f'{monster_trait.name} - {spell_type} spell parsing error. {exc.args[0]}.')
                if monster_trait.does_evolve() and monster_trait.evolves_into not in self._config.monsters_traits:
                    raise self.InvalidConfig(
                        f'{monster_trait.name} - unknown monster to evolve to - {monster_trait.evolves_into}')

        def _validate_floors(self):
            if self._config.highest_floor == 0:
                raise self.InvalidConfig(f'No floors specified')
            for index, floor in enumerate(self._config.floors):
                if len(floor.monsters) == 0:
                    raise self.InvalidConfig(f'Floor at index {index} has no monsters')
                for monster in floor.monsters:
                    if monster.name not in self._config.monsters_traits:
                        raise self.InvalidConfig(f'Floor at index {index} has unknown monster "{monster.name}"')
