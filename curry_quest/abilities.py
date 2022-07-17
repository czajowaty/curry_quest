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


class PlayTheFluteAbility(Ability):
    @property
    def name(self):
        return 'Play the flute'

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
        action_context.target.set_status(Statuses.Seal)
        target_words = action_context.target_words
        return f'{target_words.possessive_name.capitalize()} magic is sealed.'
