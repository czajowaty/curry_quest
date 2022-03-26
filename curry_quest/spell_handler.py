from abc import abstractmethod
from curry_quest.spell_cast_context import SpellCastContext


class SpellHandler:
    @abstractmethod
    def select_target(self, caster, other_unit): pass

    @abstractmethod
    def can_target_self(self) -> bool: pass

    @abstractmethod
    def can_target_other_unit(self) -> bool: pass

    @abstractmethod
    def can_cast(self, spell_cast_context: SpellCastContext) -> tuple[bool, str]: pass

    @abstractmethod
    def cast(self, spell_cast_context: SpellCastContext) -> str: pass
