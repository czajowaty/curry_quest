from abc import ABC, abstractmethod


class Ability(ABC):
    @property
    @abstractmethod
    def name(self): pass

    @property
    @abstractmethod
    def mp_cost(self): pass

    @abstractmethod
    def select_target(self, user, other_unit): pass

    @abstractmethod
    def can_target_self(self) -> bool: pass

    @abstractmethod
    def can_target_other_unit(self) -> bool: pass

    @abstractmethod
    def can_have_no_target(self) -> bool: pass

    @abstractmethod
    def can_use(self, action_context) -> tuple[bool, str]: pass

    @abstractmethod
    def use(self, action_context) -> str: pass
