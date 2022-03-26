from abc import ABC, abstractmethod
from curry_quest.unit import Unit
from curry_quest.words import Words, FamiliarWords, UnitWords


class UnitActionContext:
    NO_TARGET = None

    def __init__(self):
        from curry_quest.state_machine_context import StateMachineContext

        self.performer: Unit = None
        self.target: Unit = None
        self.state_machine_context: StateMachineContext = None

    def has_target(self) -> bool:
        return self.target is not self.NO_TARGET

    @property
    def rng(self):
        return self.state_machine_context.rng

    def is_used_by_familiar(self) -> bool:
        return self.performer is self.state_machine_context.familiar

    def is_used_on_familiar(self) -> bool:
        return self.target is self.state_machine_context.familiar

    def is_used_on_yourself(self) -> bool:
        return self.performer is self.target

    @property
    def performer_words(self) -> Words:
        return FamiliarWords() if self.is_used_by_familiar() else UnitWords(self.performer)

    @property
    def target_words(self) -> Words:
        return FamiliarWords() if self.is_used_on_familiar() else UnitWords(self.target)


class UnitActionHandler(ABC):
    @abstractmethod
    def select_target(self, performer: Unit, other_unit: Unit) -> Unit: pass

    @abstractmethod
    def can_target_self(self) -> bool: pass

    @abstractmethod
    def can_target_other_unit(self) -> bool: pass

    @abstractmethod
    def can_have_no_target(self) -> bool: pass

    @abstractmethod
    def can_perform(self, unit_action_context: UnitActionContext) -> tuple[bool, str]: pass

    @abstractmethod
    def perform(self, unit_action_context: UnitActionContext) -> str: pass


class MpRequiringActionHandler(UnitActionHandler):
    def __init__(self, mp_cost: int):
        self._mp_cost = mp_cost

    def can_perform(self, unit_action_context: UnitActionContext) -> tuple[bool, str]:
        performer = unit_action_context.performer
        performer_words = unit_action_context.performer_words
        if not performer.has_enough_mp_for_action(self._mp_cost):
            return False, f'{performer_words.name.capitalize()} {performer_words.es_verb("do")} not have enough MP.'
        return True, ''

    def perform(self, unit_action_context: UnitActionContext) -> str:
        unit_action_context.performer.use_mp(self._mp_cost)
        return ''
