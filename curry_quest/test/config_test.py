from curry_quest import Config
from curry_quest.spells import Spells


def print_units(units_traits):
    for index, (unit_name, unit_traits) in enumerate(units_traits.items()):
        print(f"  {index}: {unit_name}")
        print(f"    Base HP: {unit_traits.base_hp}")
        print(f"    HP growth: {unit_traits.hp_growth}")
        print(f"    Base MP: {unit_traits.base_mp}")
        print(f"    MP growth: {unit_traits.mp_growth}")
        print(f"    Base ATK: {unit_traits.base_attack}")
        print(f"    ATK growth: {unit_traits.attack_growth}")
        print(f"    Base DEF: {unit_traits.base_defense}")
        print(f"    DEF growth: {unit_traits.defense_growth}")
        print(f"    Base Luck: {unit_traits.base_luck}")
        print(f"    Luck growth: {unit_traits.luck_growth}")
        print(f"    Base given EXP: {unit_traits.base_exp_given}")
        print(f"    Given EXP growth: {unit_traits.exp_given_growth}")
        print(f"    Native genus: {unit_traits.native_genus}")
        print(f"    ATK MP cost: {unit_traits.physical_attack_mp_cost}")
        native_spell_base_name = unit_traits.native_spell_base_name
        dormant_spell_base_name = unit_traits.dormant_spell_base_name
        native_spell_traits = Spells.find_spell_traits(native_spell_base_name, unit_traits.native_genus)
        has_native_spell = native_spell_traits is not None
        print(f"    Native spell: {native_spell_traits.name if has_native_spell else '-'}")
        if has_native_spell:
            print(f"      Native genus: {native_spell_traits.native_genus}")
            print(f"      MP cost: {native_spell_traits.mp_cost}")
            print(f"      Cast handler: {native_spell_traits.handler}")
        dormant_spell_traits = Spells.find_spell_traits(dormant_spell_base_name, unit_traits.native_genus)
        has_dormant_spell = dormant_spell_traits is not None
        print(f"    Dormant spell: {dormant_spell_traits.name if has_dormant_spell else '-'}")
        if has_dormant_spell:
            print(f"      Native genus: {dormant_spell_traits.native_genus}")
            print(f"      MP cost: {dormant_spell_traits.mp_cost}")
            print(f"      Cast handler: {dormant_spell_traits.handler}")
        print(f"    Action weights:")
        print(f"      Attack: {unit_traits.action_weights.physical_attack}")
        print(f"      Spell: {unit_traits.action_weights.spell}")
        print(f"      Ability: {unit_traits.action_weights.ability}")
        print(f"    Talents: {unit_traits.talents}")
        print(f"    Is evolved: {unit_traits.is_evolved}")
        print(f"    Evolves into: {unit_traits.evolves_into if unit_traits.does_evolve() else '-'}")


if __name__ == '__main__':
    import sys

    with open(sys.argv[1], 'r') as config_file:
        config = Config.Parser(config_file).parse()
    print("All monster unit traits:")
    print_units(config.monsters_traits)
    print("Non-evolved monster unit traits:")
    print_units(config.non_evolved_monster_traits)
