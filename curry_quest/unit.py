import logging
from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.genus import Genus
from curry_quest.jsonable import Jsonable, InvalidJson, JsonReaderHelper
from curry_quest.spell import Spell, Spells
from curry_quest.stats_calculator import StatsCalculator
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.traits import SpellTraits, UnitTraits

logger = logging.getLogger(__name__)


class Unit(Jsonable):
    MIN_LEVEL = 1
    MIN_ALIVE_HP = 1
    MIN_DEAD_HP = 0
    MIN_MP = 0
    MIN_ATTACK = 1
    MIN_DEFENSE = 1
    MIN_LUCK = 0

    def __init__(self, traits: UnitTraits, levels: Config.Levels):
        self._traits = traits
        self._levels = levels
        self.name = traits.name
        self.genus = traits.native_genus
        self.level = self.MIN_LEVEL
        self._talents = traits.talents
        self.max_hp = traits.base_hp
        self.hp = self.max_hp
        self.max_mp = traits.base_mp
        self.mp = self.max_mp
        self.attack = traits.base_attack
        self.defense = traits.base_defense
        self.luck = traits.base_luck
        self._timed_statuses: dict[Statuses, int] = {}
        self.clear_statuses()
        if traits.native_spell_base_name is not None:
            native_spell_traits = Spells.find_spell_traits(traits.native_spell_base_name, self.genus)
            self.set_spell(native_spell_traits, self.level)
        else:
            self.clear_spell()
        self.exp = 0

    def to_json_object(self):
        unit_json_object = {
            'traits_name': self.traits.name,
            'name': self.name,
            'genus': self.genus.value,
            'level': self.level,
            'talents': self._talents.value,
            'max_hp': self._max_hp,
            'hp': self._hp,
            'max_mp': self._max_mp,
            'mp': self._mp,
            'attack': self._attack,
            'defense': self._defense,
            'luck': self._luck,
            'statuses': self._statuses.value,
            'timed_statuses': dict((status.value, duration) for status, duration in self._timed_statuses.items()),
            'exp': self._exp
        }
        if self.has_spell():
            unit_json_object['spell'] = {
                'base_name': self._spell_traits.base_name,
                'level': self._spell_level
            }
        return unit_json_object

    def from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        self.genus = json_reader_helper.read_enum('genus', Genus)
        self.level = json_reader_helper.read_int_in_range('level', min_value=1, max_value=self._levels.max_level)
        self._talents = json_reader_helper.read_enum('talents', Talents)
        self.max_hp = json_reader_helper.read_int_with_min('max_hp', min_value=self.MIN_ALIVE_HP)
        self.hp = json_reader_helper.read_int_with_min('hp', min_value=self.MIN_DEAD_HP)
        self.max_mp = json_reader_helper.read_int_with_min('max_mp', min_value=self.MIN_MP)
        self.mp = json_reader_helper.read_int_with_min('mp', min_value=self.MIN_MP)
        self.attack = json_reader_helper.read_int_with_min('attack', min_value=self.MIN_ATTACK)
        self.defense = json_reader_helper.read_int_with_min('defense', min_value=self.MIN_DEFENSE)
        self.luck = json_reader_helper.read_int_with_min('luck', min_value=self.MIN_LUCK)
        self.clear_statuses()
        self.set_status(json_reader_helper.read_enum('statuses', Statuses))
        for status_id_string, duration in json_reader_helper.read_dict('timed_statuses').items():
            try:
                status_id = int(status_id_string)
            except ValueError:
                self._raise_invalid_json(
                    json_object,
                    f'"{status_id}"="{duration}". '
                    f'Status ID "{status_id}" is not valid integer.')
            if not isinstance(duration, int):
                self._raise_invalid_json(
                    json_object,
                    f'"{status_id}"="{duration}". '
                    f'Duration "{duration}" expected to be integer, but is {type(duration)}.')
            if duration > 0:
                try:
                    self.set_timed_status(Statuses(status_id), duration)
                except ValueError:
                    self._raise_invalid_json(json_object, f'"{status_id}" is not valid Status ID.')
        self.exp = json_reader_helper.read_int_with_min('exp', min_value=0)
        if 'spell' in json_object:
            spell_json_object = json_reader_helper.read_dict('spell')
            spell_json_reader_helper = JsonReaderHelper(spell_json_object)
            spell_base_name = spell_json_reader_helper.read_string('base_name')
            self.set_spell(
                Spells.find_spell_traits(spell_base_name, self.genus),
                level=spell_json_reader_helper.read_int_with_min('level', min_value=1))

    def _raise_invalid_json(self, json_object, error_msg):
        raise InvalidJson(f'{error_msg} JSON object: {self._json_object}".')

    @classmethod
    def traits_name_from_json_object(cls, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        return json_reader_helper.read_string('traits_name')

    @property
    def traits(self):
        return self._traits

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, value):
        self._name = value

    @property
    def genus(self) -> Genus:
        return self._genus

    @genus.setter
    def genus(self, value: Genus):
        self._genus = value

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        self._level = value

    def is_min_level(self) -> bool:
        return self.level <= 1

    def is_max_level(self) -> bool:
        return self.level >= self._levels.max_level

    @property
    def talents(self) -> Talents:
        return self._talents

    @property
    def max_hp(self):
        multiplier = 2 if self.talents.has(Talents.HpIncreased) else 1
        return self._max_hp * multiplier

    @max_hp.setter
    def max_hp(self, value):
        self._max_hp = max(value, self.MIN_ALIVE_HP)

    @property
    def hp(self):
        return self._hp

    @hp.setter
    def hp(self, value):
        self._hp = max(value, self.MIN_DEAD_HP)

    def is_hp_at_max(self) -> bool:
        return self.hp >= self.max_hp

    def is_dead(self) -> bool:
        return self.hp <= self.MIN_DEAD_HP

    def restore_hp(self, recovery_amount=None):
        recovery_amount = recovery_amount or self.max_hp
        self.hp = min(self.hp + recovery_amount, self.max_hp)

    def deal_damage(self, damage):
        self.hp -= damage

    @property
    def max_mp(self):
        multiplier = 2 if self.talents.has(Talents.MpIncreased) else 1
        return self._max_mp * multiplier

    @max_mp.setter
    def max_mp(self, value):
        self._max_mp = max(value, self.MIN_MP)

    @property
    def mp(self):
        return self._mp

    @mp.setter
    def mp(self, value):
        self._mp = max(value, self.MIN_MP)

    def is_mp_at_max(self) -> bool:
        return self.mp >= self.max_mp

    def restore_mp(self):
        self.mp = self.max_mp

    def use_mp(self, mp_usage):
        if self.talents.has(Talents.MpConsumptionDecreased):
            mp_usage //= 2
        self.mp -= mp_usage

    @property
    def attack(self):
        multiplier = 2 if self.talents.has(Talents.StrengthIncreased) else 1
        return int(self._attack * self._stat_factor() * multiplier)

    @attack.setter
    def attack(self, value):
        self._attack = max(value, self.MIN_ATTACK)

    @property
    def defense(self):
        multiplier = 2 if self.talents.has(Talents.Hard) else 1
        return int(self._defense * self._stat_factor() * multiplier)

    @defense.setter
    def defense(self, value):
        self._defense = max(value, self.MIN_DEFENSE)

    @property
    def luck(self):
        return int(self._luck * self._stat_factor())

    @luck.setter
    def luck(self, value):
        self._luck = max(value, self.MIN_LUCK)

    def _stat_factor(self) -> float:
        STAT_BOOST_FACTOR = 0.5
        stat_factor = 1.0
        if self.has_boosted_stats():
            stat_factor += STAT_BOOST_FACTOR
        return stat_factor

    def has_any_status(self) -> bool:
        return self._statuses.value != 0

    def has_status(self, status: Statuses) -> bool:
        return (self._statuses & status) == status

    def status_duration(self, statuses: Statuses) -> dict[Statuses, int]:
        return dict(
            (status, self._timed_statuses[status])
            for status
            in list(Statuses)
            if statuses & status)

    def has_boosted_stats(self) -> bool:
        return self.has_status(Statuses.StatsBoost)

    def set_status(self, status: Statuses):
        self._statuses |= status

    def set_timed_status(self, statuses: Statuses, duration: int):
        self.set_status(statuses)
        for status in list(Statuses):
            if statuses & status:
                self._timed_statuses[status] = duration

    def decrease_timed_status_counters(self):
        cleared_statuses_list = []
        cleared_statuses_mask = Statuses(0)
        for status, duration in self._timed_statuses.items():
            if duration > 1:
                self._timed_statuses[status] -= 1
            else:
                cleared_statuses_list.append(status)
                cleared_statuses_mask |= status
        self.clear_status(cleared_statuses_mask)
        return cleared_statuses_list

    def clear_statuses(self):
        self._statuses = Statuses(0)
        self._timed_statuses.clear()

    def clear_status(self, statuses: Statuses):
        self._statuses &= ~statuses
        for status in list(Statuses):
            if statuses & status:
                del self._timed_statuses[status]

    @property
    def spell(self) -> Spell:
        if not self.has_spell():
            return None
        spell_level = self._spell_level
        if self.talents.has(Talents.MagicAttackIncreased):
            spell_level *= 2
        return Spell(self._spell_traits, spell_level)

    def has_spell(self) -> bool:
        return self._spell_traits is not None

    def set_spell(self, traits: SpellTraits, level: int):
        self._spell_traits = traits
        self._spell_level = level

    def set_spell_level(self, level: int):
        if not self.has_spell():
            return
        self._spell_level = level

    def clear_spell(self):
        self._spell_traits = None
        self._spell_level = 0

    @property
    def spell_mp_cost(self) -> int:
        return self._spell_traits.mp_cost

    def has_enough_mp_for_spell(self) -> bool:
        return self.mp >= self.spell_mp_cost

    @property
    def exp(self):
        return self._exp

    @exp.setter
    def exp(self, value):
        self._exp = value

    def gain_exp(self, gained_exp) -> bool:
        has_leveled_up = False
        if self.is_max_level():
            return has_leveled_up
        self.exp += gained_exp
        while not self.is_max_level() and self.exp >= self.experience_for_next_level():
            has_leveled_up = True
            self._level_up()
        return has_leveled_up

    def experience_for_next_level(self) -> int:
        if self.is_max_level():
            return 0
        return self._levels.experience_for_next_level(self.level)

    def fuse(self, other: '__class__'):
        self._talents = self.traits.talents | other.traits.talents
        if self.genus.is_weak_against(other.genus):
            self._genus = other.genus
        self._handle_spell_on_fusion(other)

    def _handle_spell_on_fusion(self, other: '__class__'):
        if self.has_spell():
            return
        spell_traits = self._select_fusion_spell_traits(other)
        if spell_traits is None:
            return
        self.set_spell(spell_traits, level=self.level)

    def _select_fusion_spell_traits(self, other: '__class__'):
        if other.has_spell():
            return other._spell_traits
        else:
            return Spells.find_spell_traits(self.traits.dormant_spell_base_name, self.genus)

    def does_evolve(self) -> bool:
        return self.traits.does_evolve()

    def evolve(self, evolved_unit_traits: UnitTraits):
        if not self.does_evolve():
            raise InvalidOperation(f'{self.name} does not evolve.')
        self._traits = evolved_unit_traits
        self.name = evolved_unit_traits.name

    class StatsChange:
        def __init__(self):
            self.hp = 0
            self.mp = 0
            self.attack = 0
            self.defense = 0
            self.luck = 0

        def __mul__(self, multiplier):
            self.hp *= multiplier
            self.mp *= multiplier
            self.attack *= multiplier
            self.defense *= multiplier
            self.luck *= multiplier

        def apply(self, unit, multiplier):
            unit.hp = max(unit._hp + self.hp * multiplier, 1)
            unit.max_hp = unit._max_hp + self.hp * multiplier
            unit.mp = unit._mp + self.mp * multiplier
            unit.max_mp = unit._max_mp + self.mp * multiplier
            unit.attack = unit._attack + self.attack * multiplier
            unit.defense = unit._defense + self.defense * multiplier
            unit.luck = unit._luck + self.luck * multiplier

        @classmethod
        def for_level(cls, stats_calculator, level):
            stats_change = cls()
            stats_change.hp = stats_calculator.hp_increase(level)
            stats_change.mp = stats_calculator.mp_increase(level)
            stats_change.attack = stats_calculator.attack_increase(level)
            stats_change.defense = stats_calculator.defense_increase(level)
            stats_change.luck = stats_calculator.luck_increase(level)
            return stats_change

    def _stats_calculator(self) -> StatsCalculator:
        return StatsCalculator(self.traits)

    def _level_up(self):
        are_stats_boosted = self.has_boosted_stats()
        if are_stats_boosted:
            self.clear_status(Statuses.StatsBoost)
        self.level += 1
        self.StatsChange.for_level(self._stats_calculator(), self.level).apply(self, multiplier=1)
        self._increase_spell_level_on_level_up()
        if are_stats_boosted:
            self.set_status(Statuses.StatsBoost)

    def _increase_spell_level_on_level_up(self):
        if not self.has_spell():
            return
        if self.genus != self._spell_traits.native_genus:
            return
        self._spell_level += 1
        if self._spell_level < self.level:
            self._spell_level += 1

    def decrease_level(self):
        if self.is_min_level():
            return
        are_stats_boosted = self.has_boosted_stats()
        if are_stats_boosted:
            self.clear_status(Statuses.StatsBoost)
        self.StatsChange.for_level(self._stats_calculator(), self.level).apply(self, multiplier=-1)
        self._decrease_spell_level_on_level_down()
        self.level -= 1
        if are_stats_boosted:
            self.set_status(Statuses.StatsBoost)

    def _decrease_spell_level_on_level_down(self):
        if not self.has_spell():
            return
        if self._spell_level > 1:
            self._spell_level -= 1

    def to_string(self) -> str:
        return f'{self.name} - {self.stats_to_string()}'

    def stats_to_string(self) -> str:
        s = f'genus: {self._genus_to_string()}, talents: {self._talents_to_string()}, LVL: {self.level}, ' \
            f'HP: {self.hp}/{self.max_hp}, MP: {self.mp}/{self.max_mp}, ' \
            f'ATK: {self.attack}, DEF: {self.defense}, LUCK: {self.luck}'
        if self.has_any_status():
            s += f', statuses: {self._statuses_to_string()}'
        if self.has_spell():
            s += f', spell: LVL {self.spell.level} {self.spell.traits.name} (MP cost: {self.spell_mp_cost})'
        s += f', EXP: {self.exp}'
        if not self.is_max_level():
            s += f' ({self.experience_for_next_level() - self.exp} more EXP to next LVL)'
        return s

    def _genus_to_string(self) -> str:
        if self.genus is Genus.Empty:
            return '-'
        else:
            return self.genus.name

    def _talents_to_string(self) -> str:
        if self.talents is Talents.Empty:
            return '-'
        else:
            return ', '.join(talent.name for talent in Talents.all() if self.talents.has(talent))

    def _statuses_to_string(self) -> str:
        return ', '.join(self._status_to_string(status) for status in Statuses if self.has_status(status))

    def _status_to_string(self, status: Statuses):
        status_string = status.name
        if status in self._timed_statuses:
            status_string += f'({self._timed_statuses[status]})'
        return status_string
