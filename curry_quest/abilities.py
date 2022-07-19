from abc import abstractmethod
from curry_quest.ability import Ability
from curry_quest.unit_action import UnitActionContext
from curry_quest.physical_attack_unit_action import PhysicalAttackExecutor
from curry_quest.statuses import Statuses


class BreakObstaclesAbility(Ability):
    @property
    def name(self):
        return 'Break obstacles'

    @property
    def mp_cost(self):
        return 4

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        physical_attack_executer = PhysicalAttackExecutor(action_context)
        physical_attack_executer.set_weapon_damage(int(action_context.performer.attack * 1.5))
        return physical_attack_executer.execute()


class ApplyDebuffAbility(Ability):
    def __init__(self, debuff_status: Statuses):
        self._debuff_status = debuff_status

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        action_context.target.set_status(self._debuff_status)
        return self._create_use_response(action_context)

    @abstractmethod
    def _create_use_response(self, action_context: UnitActionContext): pass


class ApplyTimedDebuffAbility(ApplyDebuffAbility):
    def __init__(self, debuff_status: Statuses, duration: int):
        super().__init__(debuff_status)
        self._duration = duration

    def use(self, action_context: UnitActionContext) -> str:
        response = super().use(action_context)
        action_context.target.set_timed_status(self._debuff_status, self._duration)
        return response


class PlayTheFluteAbility(ApplyDebuffAbility):
    def __init__(self):
        super().__init__(Statuses.Seal)

    @property
    def name(self):
        return 'Play the flute'

    @property
    def mp_cost(self):
        return 4

    def _create_use_response(self, action_context: UnitActionContext):
        target_words = action_context.target_words
        return f'{target_words.possessive_name.capitalize()} magic is sealed.'


class HypnotismAbility(ApplyTimedDebuffAbility):
    def __init__(self):
        super().__init__(debuff_status=Statuses.Sleep, duration=16)

    @property
    def name(self):
        return 'Hypnotism'

    @property
    def mp_cost(self):
        return 12

    def _create_use_response(self, action_context: UnitActionContext):
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} put to sleep.'


class BrainwashAbility(ApplyTimedDebuffAbility):
    def __init__(self):
        super().__init__(debuff_status=Statuses.Confuse, duration=16)

    @property
    def name(self):
        return 'Brainwash'

    @property
    def mp_cost(self):
        return 16

    def _create_use_response(self, action_context: UnitActionContext):
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} confused.'
