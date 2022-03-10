from abc import ABC, abstractmethod
import copy
from curry_quest.genus import Genus
from curry_quest.talents import Talents


class UnitTraits:
    class ActionWeights:
        def __init__(self):
            self.physical_attack = 1
            self.spell = 0
            self.ability = 0

        def copy(self):
            action_weights_copy = self.__class__()
            action_weights_copy.physical_attack = self.physical_attack
            action_weights_copy.spell = self.spell
            return action_weights_copy

    def __init__(self):
        self.name = ''
        self.base_hp = 0
        self.hp_growth = 0
        self.base_mp = 0
        self.mp_growth = 0
        self.base_attack = 0
        self.attack_growth = 0
        self.base_defense = 0
        self.defense_growth = 0
        self.base_luck = 0
        self.luck_growth = 0
        self.base_exp_given = 0
        self.exp_given_growth = 0
        self.native_genus = Genus.Empty
        self.native_spell_base_name = None
        self.dormant_spell_base_name = None
        self.action_weights = self.ActionWeights()
        self.talents = Talents.Empty
        self.is_evolved = False
        self.evolves_into = None

    def does_evolve(self) -> bool:
        return self.evolves_into is not None

    def copy(self) -> '__class__':
        return copy.deepcopy(self)


class SpellCastContext:
    def __init__(self):
        self.caster = None
        self.target = None
        self.other_than_target = None
        self.state_machine_context = None

    @property
    def rng(self):
        return self.state_machine_context.rng

    @property
    def spell_level(self) -> int:
        return self.caster.spell.level

    def is_used_by_familiar(self) -> bool:
        return self.caster is self.state_machine_context.familiar

    def is_used_on_familiar(self) -> bool:
        return self.target is self.state_machine_context.familiar

    @property
    def caster_name(self) -> str:
        return 'you' if self.is_used_by_familiar() else self.caster.name

    @property
    def target_name(self) -> str:
        return self.target.name if self.is_used_by_familiar() else 'you'

    @property
    def target_have_verb(self) -> str:
        return 'has' if self.is_used_by_familiar() else 'have'


class CastSpellHandler(ABC):
    @abstractmethod
    def select_target(self, caster, other_unit): pass

    @abstractmethod
    def can_cast(self, spell_cast_context: SpellCastContext): pass

    @abstractmethod
    def cast(self, spell_cast_context: SpellCastContext): pass


class SpellTraits:
    def __init__(self):
        self.base_name = ''
        self.name = ''
        self.native_genus = Genus.Empty
        self.mp_cost = 0
        self.cast_handler: CastSpellHandler = None
