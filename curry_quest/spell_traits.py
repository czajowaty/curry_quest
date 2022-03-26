from curry_quest.genus import Genus
from curry_quest.spell_handler import SpellHandler


class SpellTraits:
    def __init__(self):
        self.base_name = ''
        self.name = ''
        self.native_genus = Genus.Empty
        self.mp_cost = 0
        self.handler: SpellHandler = None
