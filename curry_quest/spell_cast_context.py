from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext


class SpellCastContext(UnitActionContext):
    def __init__(self, spell_level: int):
        super().__init__()
        self.spell_level = spell_level
        self.reflected_target: Unit = None
