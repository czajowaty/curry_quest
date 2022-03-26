from abc import ABC, abstractmethod
from curry_quest.unit import Unit


class Words(ABC):
    @property
    @abstractmethod
    def name(self): pass

    @property
    @abstractmethod
    def pronoun(self): pass

    @property
    @abstractmethod
    def possessive_name(self): pass

    @property
    @abstractmethod
    def possessive_pronoun(self): pass

    @property
    @abstractmethod
    def targeting_self_name(self): pass

    @property
    @abstractmethod
    def be_verb(self): pass

    @property
    @abstractmethod
    def have_verb(self): pass

    @abstractmethod
    def s_verb(self, verb_root_form): pass

    @abstractmethod
    def es_verb(self, verb_root_form): pass

    @abstractmethod
    def ies_verb(self, verb_root_form): pass


class FamiliarWords(Words):
    @property
    def name(self):
        return 'you'

    @property
    def pronoun(self):
        return 'you'

    @property
    def possessive_name(self):
        return 'your'

    @property
    def possessive_pronoun(self):
        return self.possessive_name

    @property
    def be_verb(self):
        return 'are'

    @property
    def targeting_self_name(self):
        return 'yourself'

    @property
    def have_verb(self):
        return 'have'

    def s_verb(self, verb_root_form):
        return verb_root_form

    def es_verb(self, verb_root_form):
        return verb_root_form

    def ies_verb(self, verb_root_form):
        return verb_root_form


class UnitWords(Words):
    def __init__(self, unit: Unit):
        self._unit = unit

    @property
    def name(self):
        return self._unit.name

    @property
    def pronoun(self):
        return 'it'

    @property
    def possessive_name(self):
        return f'{self.name}\'s'

    @property
    def possessive_pronoun(self):
        return 'its'

    @property
    def targeting_self_name(self):
        return 'itself'

    @property
    def be_verb(self):
        return 'is'

    @property
    def have_verb(self):
        return 'has'

    def s_verb(self, verb_root_form):
        return f'{verb_root_form}s'

    def es_verb(self, verb_root_form):
        return f'{verb_root_form}es'

    def ies_verb(self, verb_root_form):
        return f'{verb_root_form[:-1]}ies'
