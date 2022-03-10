from curry_quest.genus import Genus
from curry_quest.spells_descriptor import create_spells_traits
from curry_quest.statuses import Statuses
from curry_quest.traits import SpellTraits


class Spell:
    def __init__(self, traits: SpellTraits, level=1):
        self._traits = traits
        self.level = level

    @property
    def traits(self) -> SpellTraits:
        return self._traits

    @property
    def level(self):
        return self._level

    @level.setter
    def level(self, value):
        self._level = value

    def select_target(self, caster, other_unit):
        return self._traits.cast_handler.select_target(caster, other_unit)

    def can_cast(self, spell_cast_context):
        return self._traits.cast_handler.can_cast(spell_cast_context)

    def cast(self, spell_cast_context):
        response = self._prepare_cast_response(spell_cast_context)
        response += self._handle_reflect(spell_cast_context)
        response += self._traits.cast_handler.cast(spell_cast_context)
        spell_cast_context.caster.use_mp(self._traits.mp_cost)
        return response

    def _prepare_cast_response(self, spell_cast_context):
        caster_name = spell_cast_context.caster_name.capitalize()
        response = f'{caster_name.capitalize()} cast'
        if not spell_cast_context.is_used_by_familiar():
            response += 's'
        response += f' {self._traits.name} on '
        if spell_cast_context.is_used_by_familiar():
            response += 'yourself' if spell_cast_context.is_used_on_familiar() else f'{spell_cast_context.target.name}'
        else:
            response += 'you' if spell_cast_context.is_used_on_familiar() else 'itself'
        response += '. '
        return response

    def _handle_reflect(self, spell_cast_context):
        original_caster = spell_cast_context.caster
        original_target = spell_cast_context.target
        if self._can_target_reflect_spell(original_caster, original_target):
            reflected_target = spell_cast_context.other_than_target
            spell_cast_context.other_than_target = spell_cast_context.target
            spell_cast_context.target = reflected_target
            response = 'It is reflected '
            if original_caster is spell_cast_context.target:
                response += 'back '
            response += 'at '
            response += 'you' if spell_cast_context.is_used_on_familiar() else f'{reflected_target.name}'
            response += '. '
            return response
        else:
            return ''

    def _can_target_reflect_spell(self, caster, target):
        if target.has_status(Statuses.Reflect):
            return True
        elif caster.genus == Genus.Fire:
            return target.has_status(Statuses.FireReflect)
        elif caster.genus == Genus.Wind:
            return target.has_status(Statuses.WindReflect)
        else:
            return False


class Spells:
    _SPELLS_TRAITS = create_spells_traits()

    @classmethod
    def find_spell_category_traits(cls, spell_base_name: str):
        if spell_base_name is None:
            return None
        if spell_base_name not in cls._SPELLS_TRAITS:
            raise ValueError(f'Unknown spell base name "{spell_base_name}"')
        return cls._SPELLS_TRAITS[spell_base_name]

    @classmethod
    def find_spell_traits(cls, spell_base_name: str, genus: Genus):
        if spell_base_name is None:
            return None
        spell_category_traits = cls.find_spell_category_traits(spell_base_name)
        if genus not in spell_category_traits:
            raise ValueError(f'Spell "{spell_base_name}" does not exist for "{genus}".')
        return spell_category_traits[genus]
