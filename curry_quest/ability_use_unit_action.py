from curry_quest.ability import Ability
from curry_quest.unit import Unit
from curry_quest.unit_action import MpRequiringActionHandler, UnitActionContext


class AbilityUseActionHandler(MpRequiringActionHandler):
    def __init__(self, ability: Ability):
        super().__init__(ability.mp_cost)
        self._ability = ability

    def select_target(self, performer: Unit, other_unit: Unit) -> Unit:
        return self._ability.select_target(performer, other_unit)

    def can_target_self(self) -> bool:
        return self._ability.can_target_self()

    def can_target_other_unit(self) -> bool:
        return self._ability.can_target_other_unit()

    def can_have_no_target(self) -> bool:
        return self._ability.can_have_no_target()

    def can_perform(self, action_context: UnitActionContext) -> tuple[bool, str]:
        can_perform, response = super().can_perform(action_context)
        if not can_perform:
            return can_perform, response
        performer = action_context.performer
        performer_words = action_context.performer_words
        if not performer.has_ability():
            return False, f'{performer_words.name.capitalize()} {performer_words.es_verb("do")} not have an ability.'
        return self._ability.can_use(action_context)

    def perform(self, action_context: UnitActionContext) -> str:
        super().perform(action_context)
        if not action_context.has_target():
            return self._prepare_no_target_response(action_context)
        response = self._prepare_use_response(action_context)
        response += self._ability.use(action_context)
        return response

    def _prepare_no_target_response(self, action_context: UnitActionContext):
        performer_words = action_context.performer_words
        return f'{performer_words.name.capitalize()} {performer_words.s_verb("use")} {self._ability.name} ' \
            'targeting nothing but air.'

    def _prepare_use_response(self, action_context: UnitActionContext):
        performer_words = action_context.performer_words
        target_words = action_context.target_words
        response = f'{performer_words.name.capitalize()} {performer_words.s_verb("use")} {self._ability.name} on '
        response += target_words.targeting_self_name if action_context.is_used_on_yourself() else target_words.name
        response += '. '
        return response
