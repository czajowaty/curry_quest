from curry_quest.levels_config import Levels
from curry_quest.spells import Spells
from curry_quest.stats_calculator import StatsCalculator
from curry_quest.unit_traits import UnitTraits
from curry_quest.unit import Unit


class UnitCreator:
    def __init__(self, unit_traits: UnitTraits):
        self._unit_traits = unit_traits

    def create(self, level, levels: Levels) -> Unit:
        stats_calculator = StatsCalculator(self._unit_traits)
        unit = Unit(self._unit_traits, levels)
        unit.level = level
        unit.max_hp = stats_calculator.hp(level)
        unit.hp = unit.max_hp
        unit.max_mp = stats_calculator.mp(level)
        unit.mp = unit.max_mp
        unit.attack = stats_calculator.attack(level)
        unit.defense = stats_calculator.defense(level)
        unit.luck = stats_calculator.luck(level)
        spell_name = self._unit_traits.native_spell_base_name
        if spell_name is not None:
            spell_traits = Spells.find_spell_traits(spell_name, unit.genus)
            unit.set_spell(spell_traits, level)
        if level > 0:
            unit.exp = levels.experience_for_next_level(level - 1)
        return unit
