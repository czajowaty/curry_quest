from curry_quest.genus import Genus
from curry_quest.spells_descriptor import create_spells_traits


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
