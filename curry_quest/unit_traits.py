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
        self.physical_attack_mp_cost = 0
        self.native_spell_base_name: str = None
        self.dormant_spell_base_name: str = None
        self.ability_name: str = None
        self.action_weights = self.ActionWeights()
        self.talents = Talents.Empty
        self.is_evolved = False
        self.evolves_into: str = None

    def does_evolve(self) -> bool:
        return self.evolves_into is not None

    def copy(self) -> '__class__':
        return copy.deepcopy(self)
