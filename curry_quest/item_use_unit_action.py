from curry_quest.items import Item
from curry_quest.unit_action import UnitActionHandler, UnitActionContext
from curry_quest.unit import Unit


class ItemUseActionHandler(UnitActionHandler):
    def __init__(self, item: Item):
        self._item = item

    def select_target(self, familiar: Unit, enemy: Unit) -> Unit:
        return self._item.select_target(familiar, enemy)

    def can_target_self(self) -> bool:
        return self._item.can_target_familiar()

    def can_target_other_unit(self) -> bool:
        return self._item.can_target_enemy()

    def can_have_no_target(self) -> bool:
        return False

    def can_perform(self, unit_action_context: UnitActionContext) -> tuple[bool, str]:
        reason = self._item.cannot_use_reason(unit_action_context)
        return (False, reason) if reason else (True, '')

    def perform(self, unit_action_context: UnitActionContext) -> str:
        can_use = not bool(self._item.cannot_use_reason(unit_action_context))
        response = f'You used the {self._item.name}. '
        response += self._item.use(unit_action_context) if can_use else 'It has no effect.'
        return response
