from curry_quest.genus import Genus
from curry_quest.spell_cast_context import SpellCastContext
from curry_quest.spell_traits import SpellTraits
from curry_quest.statuses import Statuses
from curry_quest.unit import Unit
from curry_quest.unit_action import MpRequiringActionHandler


class SpellCastActionHandler(MpRequiringActionHandler):
    def __init__(self, spell_traits: SpellTraits):
        super().__init__(spell_traits.mp_cost)
        self._spell_traits = spell_traits
        self._spell_handler = spell_traits.handler

    def select_target(self, performer: Unit, other_unit: Unit) -> Unit:
        return self._spell_handler.select_target(performer, other_unit)

    def can_target_self(self) -> bool:
        return self._spell_handler.can_target_self()

    def can_target_other_unit(self) -> bool:
        return self._spell_handler.can_target_other_unit()

    def can_have_no_target(self) -> bool:
        return True

    def can_perform(self, spell_cast_context: SpellCastContext) -> tuple[bool, str]:
        can_perform, response = super().can_perform(spell_cast_context)
        if not can_perform:
            return can_perform, response
        caster = spell_cast_context.performer
        caster_words = spell_cast_context.performer_words
        if not caster.has_spell():
            return False, f'{caster_words.name.capitalize()} {caster_words.es_verb("do")} not have a spell.'
        return self._spell_handler.can_cast(spell_cast_context)

    def perform(self, spell_cast_context: SpellCastContext) -> str:
        super().perform(spell_cast_context)
        if not spell_cast_context.has_target():
            return self._prepare_no_target_response(spell_cast_context)
        response = self._prepare_cast_response(spell_cast_context)
        response += self._handle_reflect(spell_cast_context)
        response += self._spell_handler.cast(spell_cast_context)
        return response

    def _prepare_no_target_response(self, spell_cast_context: SpellCastContext):
        caster_words = spell_cast_context.performer_words
        return f'{caster_words.name.capitalize()} {caster_words.s_verb("cast")} {self._spell_traits.name} targeting ' \
            'nothing but air.'

    def _prepare_cast_response(self, spell_cast_context: SpellCastContext):
        caster_words = spell_cast_context.performer_words
        target_words = spell_cast_context.target_words
        response = f'{caster_words.name.capitalize()} {caster_words.s_verb("cast")} {self._spell_traits.name} on '
        response += target_words.targeting_self_name if spell_cast_context.is_used_on_yourself() else target_words.name
        response += '. '
        return response

    def _handle_reflect(self, spell_cast_context: SpellCastContext):
        original_caster = spell_cast_context.performer
        original_target = spell_cast_context.target
        if self._can_target_reflect_spell(original_caster, original_target):
            spell_cast_context.target = spell_cast_context.reflected_target
            target_words = spell_cast_context.target_words
            response = 'It is reflected '
            if original_caster is spell_cast_context.target:
                response += 'back '
            response += f'at {target_words.name}. '
            return response
        else:
            return ''

    def _can_target_reflect_spell(self, caster, target):
        if target is None:
            return False
        if target.has_status(Statuses.Reflect):
            return True
        elif caster.genus == Genus.Fire:
            return target.has_status(Statuses.FireReflect)
        elif caster.genus == Genus.Wind:
            return target.has_status(Statuses.WindReflect)
        else:
            return False
