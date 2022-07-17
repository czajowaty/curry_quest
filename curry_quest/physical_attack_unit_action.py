from curry_quest.physical_attack_executor import PhysicalAttackExecutor
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext, MpRequiringActionHandler


class PhysicalAttackUnitActionHandler(MpRequiringActionHandler):
    def select_target(self, performer: Unit, other_unit: Unit) -> Unit:
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_perform(self, unit_action_context: UnitActionContext) -> tuple[bool, str]:
        return super().can_perform(unit_action_context)

    def perform(self, unit_action_context: UnitActionContext) -> str:
        super().perform(unit_action_context)
        return PhysicalAttackExecutor(unit_action_context).execute()
