from curry_quest import Config
from curry_quest.spell import Spells

if __name__ == '__main__':
    import sys

    with open(sys.argv[1], 'r') as config_file:
        config = Config.Parser(config_file).parse()
    for index, (unit_name, unit_traits) in enumerate(config.monsters_traits.items()):
        print(f"{index}: {unit_name}")
        print(f"  Native genus: {unit_traits.native_genus}")
        native_spell_base_name = unit_traits.native_spell_base_name
        dormant_spell_base_name = unit_traits.dormant_spell_base_name
        native_spell_traits = Spells.find_spell_traits(native_spell_base_name, unit_traits.native_genus)
        has_native_spell = native_spell_traits is not None
        print(f"  Native spell: {native_spell_traits.name if has_native_spell else '-'}")
        if has_native_spell:
            print(f"    Native genus: {native_spell_traits.native_genus}")
            print(f"    MP cost: {native_spell_traits.mp_cost}")
            print(f"    Cast handler: {native_spell_traits.cast_handler}")
        dormant_spell_traits = Spells.find_spell_traits(dormant_spell_base_name, unit_traits.native_genus)
        has_dormant_spell = dormant_spell_traits is not None
        print(f"  Dormant spell: {dormant_spell_traits.name if has_dormant_spell else '-'}")
        if has_dormant_spell:
            print(f"    Native genus: {dormant_spell_traits.native_genus}")
            print(f"    MP cost: {dormant_spell_traits.mp_cost}")
            print(f"    Cast handler: {dormant_spell_traits.cast_handler}")
