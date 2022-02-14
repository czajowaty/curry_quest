from curry_quest.config import Config
from curry_quest.stats_calculator import StatsCalculator
from curry_quest.traits import UnitTraits
from curry_quest.unit import Unit


class UnitCreator:
    def __init__(self, unit_traits: UnitTraits):
        self._unit_traits = unit_traits

    def create(self, level, levels: Config.Levels=Config.Levels()) -> Unit:
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
        unit.set_spell_level(level)
        return unit
