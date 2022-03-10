from abc import ABC, abstractmethod
from curry_quest.damage_calculator import DamageCalculator
from curry_quest.genus import Genus
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.traits import CastSpellHandler, SpellCastContext, SpellTraits
from typing import Type


class DamageSpellHandler(CastSpellHandler):
    def __init__(self, raw_spell_damage):
        self._raw_spell_damage = raw_spell_damage

    def select_target(self, caster, other_unit):
        return other_unit

    def can_cast(self, spell_cast_context: SpellCastContext):
        return True, ''

    def cast(self, spell_cast_context):
        attacker = spell_cast_context.caster
        defender = spell_cast_context.target
        damage = DamageCalculator(attacker, defender).spell_damage(self._raw_spell_damage)
        defender.deal_damage(damage)
        return self._spell_attack_response(spell_cast_context, damage)

    def _spell_attack_response(self, spell_cast_context: SpellCastContext, damage: int):
        defender = spell_cast_context.target
        defender_name = spell_cast_context.target_name
        return f'It deals {damage} damage. ' \
            f'{defender_name.capitalize()} {spell_cast_context.target_have_verb} {defender.hp} HP left.'


class ApplyDebuffSpellHandler(CastSpellHandler):
    def __init__(self, debuff_status: Statuses, debuff_applied_label: str):
        self._debuff_status = debuff_status
        self._debuff_applied_label = debuff_applied_label

    def select_target(self, caster, other_unit):
        return other_unit

    def can_cast(self, spell_cast_context: SpellCastContext):
        return True, ''

    def cast(self, spell_cast_context: SpellCastContext):
        if self._does_cast_succeed(spell_cast_context):
            duration = self._calculate_debuff_duration(spell_cast_context)
            spell_cast_context.target.set_timed_status(self._debuff_status, duration)
            return self._prepare_response_on_success(spell_cast_context, duration)
        else:
            return 'It has no effect.'

    @abstractmethod
    def _does_cast_succeed(self, spell_cast_context: SpellCastContext): pass

    @abstractmethod
    def _calculate_debuff_duration(self, spell_cast_context: SpellCastContext): pass

    def _prepare_response_on_success(self, spell_cast_context: SpellCastContext, duration: int):
        response = f'{spell_cast_context.target_name.capitalize()} '
        response += 'is' if spell_cast_context.is_used_by_familiar() else 'are'
        response += f' {self._debuff_applied_label}.'
        return response


class ApplyDebuffWithStaticLikelihoodSpellHandler(ApplyDebuffSpellHandler):
    def __init__(self, debuff_status: Statuses, debuff_applied_label: str, cast_success_likelihood: int):
        super().__init__(debuff_status, debuff_applied_label)
        self._cast_success_likelihood = cast_success_likelihood

    def _does_cast_succeed(self, spell_cast_context: SpellCastContext):
        target = spell_cast_context.target
        success_chance = self._cast_success_likelihood / target.luck
        return spell_cast_context.state_machine_context.does_action_succeed(success_chance)


def calculate_standard_status_duration(
        spell_cast_context: SpellCastContext,
        static_status_duration,
        random_status_duration_upper_limit=3):
    rng = spell_cast_context.state_machine_context.rng
    spell_level_based_duration = spell_cast_context.caster.spell.level // 4
    random_duration = rng.randint(0, random_status_duration_upper_limit)
    return static_status_duration + spell_level_based_duration + random_duration


class PoisonSpellHandler(ApplyDebuffWithStaticLikelihoodSpellHandler):
    def __init__(self, cast_success_likelihood):
        ApplyDebuffWithStaticLikelihoodSpellHandler.__init__(
            self,
            debuff_status=Statuses.Poison,
            debuff_applied_label='poisoned',
            cast_success_likelihood=cast_success_likelihood)

    def _does_cast_succeed(self, spell_cast_context):
        if spell_cast_context.target.talents.has(Talents.PoisonProof):
            return False
        return super()._does_cast_succeed(spell_cast_context)

    def _calculate_debuff_duration(self, spell_cast_context: SpellCastContext):
        return calculate_standard_status_duration(spell_cast_context, static_status_duration=16)


class ApplyBuffSpellHandler(CastSpellHandler):
    def __init__(self, buff_status: Statuses, static_buff_duration: int, random_buff_duration_upper_limit: int):
        self._buff_status = buff_status
        self._static_buff_duration = static_buff_duration
        self._random_buff_duration_upper_limit = random_buff_duration_upper_limit

    def select_target(self, caster, other_unit):
        return caster

    def can_cast(self, spell_cast_context: SpellCastContext):
        return True, ''

    def cast(self, spell_cast_context: SpellCastContext):
        duration = calculate_standard_status_duration(
            spell_cast_context,
            static_status_duration=self._static_buff_duration,
            random_status_duration_upper_limit=self._random_buff_duration_upper_limit)
        spell_cast_context.target.set_timed_status(self._buff_status, duration)
        return self._create_response(spell_cast_context)

    @abstractmethod
    def _create_response(self, spell_cast_context: SpellCastContext): pass


class WallSpellHandler(ApplyBuffSpellHandler):
    def __init__(self, protection_status: Statuses, static_buff_duration: int, protection_label: str):
        super().__init__(
            buff_status=protection_status,
            static_buff_duration=static_buff_duration,
            random_buff_duration_upper_limit=3)
        self._protection_label = protection_label

    def _create_response(self, spell_cast_context: SpellCastContext):
        response = f'{spell_cast_context.target_name.capitalize()} gain'
        if not spell_cast_context.is_used_on_familiar():
            response += 's'
        response += f' protection of {self._protection_label}.'
        return response


class MirrorSpellHandler(ApplyBuffSpellHandler):
    def __init__(self, reflect_status: Statuses, static_buff_duration: int, reflect_label: str):
        super().__init__(
            buff_status=reflect_status,
            static_buff_duration=static_buff_duration,
            random_buff_duration_upper_limit=0)
        self._reflect_label = reflect_label

    def _create_response(self, spell_cast_context: SpellCastContext):
        response = f'{spell_cast_context.target_name.capitalize()} reflect'
        if not spell_cast_context.is_used_on_familiar():
            response += 's'
        response += f' {self._reflect_label} spells.'
        return response


class HpRecoverySpellHandler(CastSpellHandler):
    def select_target(self, caster, other_unit):
        return caster

    def can_cast(self, spell_cast_context: SpellCastContext):
        target = spell_cast_context.target
        if target.is_hp_at_max():
            return False, 'HP is already at max.'
        else:
            return True, ''

    def cast(self, spell_cast_context: SpellCastContext):
        recovery_amount = self._calculate_recovery_amount(spell_cast_context)
        target = spell_cast_context.target
        max_recovery_amount = target.max_hp - target.hp
        recovery_amount = min(recovery_amount, max_recovery_amount)
        target.restore_hp(recovery_amount)
        return self._spell_attack_response(spell_cast_context, recovery_amount)

    def _spell_attack_response(self, spell_cast_context: SpellCastContext, recovery_amount):
        target = spell_cast_context.target
        target_name = spell_cast_context.target_name
        return f'It heals {recovery_amount} HP. ' \
            f'{target_name.capitalize()} {spell_cast_context.target_have_verb} {target.hp} HP.'

    @abstractmethod
    def _calculate_recovery_amount(self, spell_cast_context: SpellCastContext): pass


class LevelBasedHpRecoverySpellHandler(HpRecoverySpellHandler):
    def __init__(self, base_heal, hp_mask_for_bonus, bonus_heal_multiplier):
        self._base_heal = base_heal
        self._hp_mask_for_bonus = hp_mask_for_bonus
        self._bonus_heal_multiplier = bonus_heal_multiplier

    def _calculate_recovery_amount(self, spell_cast_context: SpellCastContext):
        random_heal = spell_cast_context.rng.randint(0, 3)
        by_level_heal = (spell_cast_context.spell_level // 4)
        recovery_amount = self._base_heal + by_level_heal + random_heal
        target = spell_cast_context.target
        if self._has_bonus_heal(target):
            recovery_amount = int(recovery_amount * self._bonus_heal_multiplier)
        return recovery_amount

    def _has_bonus_heal(self, target):
        return (target.hp & self._hp_mask_for_bonus) != 0


class DeForthSpellHandler(HpRecoverySpellHandler):
    def _calculate_recovery_amount(self, spell_cast_context: SpellCastContext):
        return 0x200


class BlindSpellHandler(ApplyDebuffWithStaticLikelihoodSpellHandler):
    def __init__(
            self,
            debuff_status: Statuses,
            debuff_applied_label,
            protective_talent: Talents,
            static_debuff_duration: int):
        super().__init__(debuff_status, debuff_applied_label, cast_success_likelihood=16)
        self._protective_talent = protective_talent
        self._static_debuff_duration = static_debuff_duration

    def _does_cast_succeed(self, spell_cast_context):
        if spell_cast_context.target.talents.has(self._protective_talent):
            return False
        return super()._does_cast_succeed(spell_cast_context)

    def _calculate_debuff_duration(self, spell_cast_context: SpellCastContext):
        return calculate_standard_status_duration(
            spell_cast_context,
            static_status_duration=self._static_debuff_duration)


class BindSpellHandler(ApplyDebuffWithStaticLikelihoodSpellHandler):
    def __init__(self):
        super().__init__(debuff_status=Statuses.Paralyze, debuff_applied_label='paralyzed', cast_success_likelihood=16)

    def _does_cast_succeed(self, spell_cast_context: SpellCastContext):
        if spell_cast_context.target.talents.has(Talents.ParalysisProof):
            return False
        return super()._does_cast_succeed(spell_cast_context)


class LaLeBindSpellHandler(BindSpellHandler):
    def _does_cast_succeed(self, spell_cast_context: SpellCastContext):
        if not spell_cast_context.caster.genus.is_strong_against(spell_cast_context.target.genus):
            return False
        return super()._does_cast_succeed(spell_cast_context)

    def _calculate_debuff_duration(self, spell_cast_context: SpellCastContext):
        return 2


class LoBindSpellHandler(BindSpellHandler):
    def _calculate_debuff_duration(self, spell_cast_context: SpellCastContext):
        return 4


class SleepSpellHandler(ApplyDebuffWithStaticLikelihoodSpellHandler):
    def __init__(self, static_debuff_duration: int):
        super().__init__(debuff_status=Statuses.Sleep, debuff_applied_label='put to sleep', cast_success_likelihood=8)
        self._static_debuff_duration = static_debuff_duration

    def _does_cast_succeed(self, spell_cast_context: SpellCastContext):
        if spell_cast_context.target.talents.has(Talents.SleepProof):
            return False
        return super()._does_cast_succeed(spell_cast_context)

    def _calculate_debuff_duration(self, spell_cast_context: SpellCastContext):
        return calculate_standard_status_duration(
            spell_cast_context,
            static_status_duration=self._static_debuff_duration)


class MissableSpellHandler(CastSpellHandler):
    def cast(self, spell_cast_context: SpellCastContext):
        if self._does_cast_succeed(spell_cast_context):
            return self._handle_cast_success(spell_cast_context)
        else:
            return 'Spell misses.'

    @abstractmethod
    def _does_cast_succeed(self, spell_cast_context: SpellCastContext): pass

    @abstractmethod
    def _handle_cast_success(self, spell_cast_context: SpellCastContext): pass


class NonWindDownSpellHandler(MissableSpellHandler):
    def select_target(self, caster, other_unit):
        return other_unit

    def can_cast(self, spell_cast_context: SpellCastContext):
        return True, ''

    def _handle_cast_success(self, spell_cast_context: SpellCastContext):
        self._decrease_stat(spell_cast_context.target)
        stat_label = self._STAT_LABEL
        target = spell_cast_context.target
        response = f'Spell decreases '
        response += f'{target.name.capitalize()}\'s' if spell_cast_context.is_used_by_familiar() else 'your'
        stat_value = self._affected_stat_value(target)
        response += f' {stat_label}. New {stat_label}: {stat_value}.'
        return response

    def _does_cast_succeed(self, spell_cast_context: SpellCastContext):
        target = spell_cast_context.target
        if target.luck == 0:
            return True
        success_chance = (spell_cast_context.spell_level * 32) / target.luck
        return spell_cast_context.state_machine_context.does_action_succeed(success_chance)

    @abstractmethod
    def _decrease_stat(self, target): pass

    @abstractmethod
    def _affected_stat_value(self, target): pass


class LaDownSpellHandler(NonWindDownSpellHandler):
    _STAT_LABEL = 'ATK'

    def _decrease_stat(self, target):
        attack_decrease = (target.attack + 1) // 2
        target.attack -= attack_decrease

    def _affected_stat_value(self, target):
        return target.attack


class LeDownSpellHandler(NonWindDownSpellHandler):
    _STAT_LABEL = 'DEF'

    def _decrease_stat(self, target):
        defense_decrease = (target.defense + 1) // 2
        target.defense -= defense_decrease

    def _affected_stat_value(self, target):
        return target.defense


class LoDownSpellHandler(CastSpellHandler):
    def select_target(self, caster, other_unit):
        return other_unit

    def can_cast(self, spell_cast_context: SpellCastContext):
        is_min_level = spell_cast_context.target.is_min_level()
        if is_min_level:
            return False, 'Target is already at minimum level.'
        else:
            return True, ''

    def cast(self, spell_cast_context: SpellCastContext):
        if self._does_cast_succeed(spell_cast_context):
            return self._decrease_level(spell_cast_context)
        else:
            return 'Spell misses.'

    def _does_cast_succeed(self, spell_cast_context):
        target = spell_cast_context.target
        reduced_target_luck = target.luck - 16
        if reduced_target_luck <= 0:
            return True
        success_chance = (spell_cast_context.spell_level - 1) / reduced_target_luck
        return spell_cast_context.state_machine_context.does_action_succeed(success_chance)

    def _decrease_level(self, spell_cast_context):
        target = spell_cast_context.target
        target.decrease_level()
        response = f'{spell_cast_context.target_name.capitalize()} feel'
        if spell_cast_context.is_used_by_familiar():
            response += 's'
        response += f' weaker. New stats - {target.stats_to_string()}.'
        return response


class SpellNameCreator(ABC):
    @abstractmethod
    def fire(self): pass

    @abstractmethod
    def water(self): pass

    @abstractmethod
    def wind(self): pass


class FireSpellNameCreator(SpellNameCreator):
    def __init__(self, base_name):
        self._base_name = base_name

    def fire(self):
        return self._base_name

    def water(self):
        return f'Nea{self._base_name}'

    def wind(self):
        return f'Noa{self._base_name}'


class WaterSpellNameCreator(SpellNameCreator):
    def __init__(self, base_name):
        self._base_name = base_name

    def fire(self):
        return f'Dea{self._base_name}'

    def water(self):
        return f'De{self._base_name}'

    def wind(self):
        return f'Deo{self._base_name}'


class WindSpellNameCreator(SpellNameCreator):
    def __init__(self, base_name):
        self._base_name = base_name

    def fire(self):
        return f'La{self._base_name}'

    def water(self):
        return f'Le{self._base_name}'

    def wind(self):
        return f'Lo{self._base_name}'


SPELLS_DESCRIPTOR = {
    Genus.Fire: {
        'Breath': {
            'mp_cost': 12,
            'cast_handler': {'generic': DamageSpellHandler(raw_spell_damage=16)}
        },
        'Sled': {
            'mp_cost': 8,
            'cast_handler': {
                'generic': DamageSpellHandler(raw_spell_damage=8),
                'water': DamageSpellHandler(raw_spell_damage=10)
            }
        },
        'Brid': {
            'mp_cost': 10,
            'cast_handler': {'generic': DamageSpellHandler(raw_spell_damage=10)}
        },
        'Rise': {
            'mp_cost': 16,
            'cast_handler': {'generic': DamageSpellHandler(raw_spell_damage=19)}
        },
        'Poison': {
            'mp_cost': 8,
            'cast_handler': {
                'fire': PoisonSpellHandler(cast_success_likelihood=32),
                'water': PoisonSpellHandler(cast_success_likelihood=16),
                'wind': PoisonSpellHandler(cast_success_likelihood=16)
            }
        },
    },
    Genus.Water: {
        'Wall': {
            'mp_cost': 8,
            'cast_handler': {
                'fire': WallSpellHandler(
                    protection_status=Statuses.FireProtection,
                    static_buff_duration=2,
                    protection_label='fire'),
                'water': WallSpellHandler(
                    protection_status=Statuses.WaterProtection,
                    static_buff_duration=4,
                    protection_label='water'),
                'wind': WallSpellHandler(
                    protection_status=Statuses.WindProtection,
                    static_buff_duration=2,
                    protection_label='wind'),
            }
        },
        'Mirror': {
            'mp_cost': 8,
            'cast_handler': {
                'fire': MirrorSpellHandler(
                    reflect_status=Statuses.FireReflect,
                    static_buff_duration=2,
                    reflect_label='fire'),
                'water': MirrorSpellHandler(
                    reflect_status=Statuses.Reflect,
                    static_buff_duration=4,
                    reflect_label='all'),
                'wind': MirrorSpellHandler(
                    reflect_status=Statuses.WindReflect,
                    static_buff_duration=2,
                    reflect_label='wind')
            }
        },
        'Heal': {
            'mp_cost': 10,
            'cast_handler': {
                'fire': LevelBasedHpRecoverySpellHandler(
                    base_heal=4,
                    hp_mask_for_bonus=0x1,
                    bonus_heal_multiplier=1.5),
                'water': LevelBasedHpRecoverySpellHandler(
                    base_heal=16,
                    hp_mask_for_bonus=0x4,
                    bonus_heal_multiplier=1.125),
                'wind': LevelBasedHpRecoverySpellHandler(
                    base_heal=8,
                    hp_mask_for_bonus=0x2,
                    bonus_heal_multiplier=1.25)
            }
        },
        'Forth': {
            'mp_cost': 16,
            'cast_handler': {
                'fire': LevelBasedHpRecoverySpellHandler(
                    base_heal=8,
                    hp_mask_for_bonus=0x1,
                    bonus_heal_multiplier=2.0),
                'water': DeForthSpellHandler(),
                'wind': LevelBasedHpRecoverySpellHandler(
                    base_heal=16,
                    hp_mask_for_bonus=0x1,
                    bonus_heal_multiplier=1.5)
            }
        }
    },
    Genus.Wind: {
        'Blind': {
            'mp_cost': 8,
            'cast_handler': {
                'generic': BlindSpellHandler(
                    debuff_status=Statuses.Confuse,
                    debuff_applied_label='confused',
                    protective_talent=Talents.ConfusionProof,
                    static_debuff_duration=2),
                'wind': BlindSpellHandler(
                    debuff_status=Statuses.Blind,
                    debuff_applied_label='blinded',
                    protective_talent=Talents.BlinderProof,
                    static_debuff_duration=4)
            }
        },
        'Bind': {
            'mp_cost': 12,
            'cast_handler': {
                'generic': LaLeBindSpellHandler(),
                'wind': LoBindSpellHandler()
            }
        },
        'Sleep': {
            'mp_cost': 10,
            'cast_handler': {
                'generic': SleepSpellHandler(static_debuff_duration=2),
                'wind': SleepSpellHandler(static_debuff_duration=4)
            }
        },
        'Down': {
            'mp_cost': 9,
            'cast_handler': {
                'fire': LaDownSpellHandler(),
                'water': LeDownSpellHandler(),
                'wind': LoDownSpellHandler()
            }
        },
        'Grave': {
            'name': {'water': 'LeoGrave'},
            'mp_cost': 12,
            'cast_handler': {'generic': DamageSpellHandler(raw_spell_damage=24)}
        }
    }
}


def create_spells_traits():
    spells_traits = {}

    def update_spells_traits(genus: Genus, spell_name_creator_class: Type[SpellNameCreator]):
        elemental_spells_descriptor = SPELLS_DESCRIPTOR[genus]
        for spell_base_name, spell_descriptor in elemental_spells_descriptor.items():
            spell_name_creator = spell_name_creator_class(spell_base_name)
            if 'name' in spell_descriptor:
                def one_or_other(one, other):
                    def wrapped():
                        return one or other

                    return wrapped

                name_dict = spell_descriptor['name']
                spell_name_creator.fire = one_or_other(name_dict.get('fire'), spell_name_creator.fire())
                spell_name_creator.water = one_or_other(name_dict.get('water'), spell_name_creator.water())
                spell_name_creator.wind = one_or_other(name_dict.get('wind'), spell_name_creator.wind())
            cast_handler_descriptor = spell_descriptor['cast_handler']
            generic_cast_handler = cast_handler_descriptor.get('generic')

            def create_spell_traits(spell_name, genus_specific_cast_handler):
                spell_traits = SpellTraits()
                spell_traits.base_name = spell_base_name
                spell_traits.name = spell_name
                spell_traits.native_genus = genus
                spell_traits.mp_cost = spell_descriptor['mp_cost']
                spell_traits.cast_handler = genus_specific_cast_handler or generic_cast_handler
                return spell_traits

            spells_traits[spell_base_name] = {
                Genus.Fire: create_spell_traits(spell_name_creator.fire(), cast_handler_descriptor.get('fire')),
                Genus.Water: create_spell_traits(spell_name_creator.water(), cast_handler_descriptor.get('water')),
                Genus.Wind: create_spell_traits(spell_name_creator.wind(), cast_handler_descriptor.get('wind'))
            }

    update_spells_traits(Genus.Fire, FireSpellNameCreator)
    update_spells_traits(Genus.Water, WaterSpellNameCreator)
    update_spells_traits(Genus.Wind, WindSpellNameCreator)
    return spells_traits
