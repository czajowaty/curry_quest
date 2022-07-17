from unittest.mock import Mock, create_autospec, patch
from curry_quest.config import Config
from curry_quest.genus import Genus
from curry_quest.levels_config import Levels
from curry_quest.spell_handler import SpellHandler
from curry_quest.spells_descriptor import create_spells_traits
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.stats_calculator import StatsCalculator
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.spell_traits import SpellTraits
from curry_quest.spell_cast_unit_action import SpellCastContext, SpellCastActionHandler
from curry_quest.unit_traits import UnitTraits
from curry_quest.unit import Unit
import functools
import random
import unittest

SPELLS_TRAITS = create_spells_traits()


def load_tests(loader, standard_tests, pattern):
    module = __import__(__name__)
    tests = []
    for name in dir(module):
        obj = getattr(module, name)
        if name != SpellTestBase.__name__:
            if isinstance(obj, type) and issubclass(obj, unittest.TestCase):
                tests.append(loader.loadTestsFromTestCase(obj))
    return unittest.TestSuite(tests)


class SpellTestBase(unittest.TestCase):
    @classmethod
    def _spell_selector(cls):
        raise NotImplementedError()

    def setUp(self):
        self._spell_base_name, genus = self._spell_selector()
        self._spell_traits: SpellTraits = SPELLS_TRAITS[self._spell_base_name][genus]
        self._spell_cast_context = SpellCastContext(spell_level=1)
        self._caster_traits = UnitTraits()
        self._caster_levels = Levels()
        self._caster = Unit(self._caster_traits, self._caster_levels)
        self._caster.genus = genus
        self._caster.set_spell(self._spell_traits, level=1)
        self._spell_cast_context.performer = self._caster
        self._target_traits = UnitTraits()
        self._target_levels = Levels()
        self._target = Unit(self._target_traits, self._target_levels)
        self._spell_cast_context.target = self._target
        self._game_config = Config()
        self._state_machine_context = StateMachineContext(self._game_config)
        self._does_action_succeed_mock = Mock()
        self._does_action_succeed_mock.return_value = True
        self._state_machine_context.does_action_succeed = self._does_action_succeed_mock
        self._rng_mock = Mock(spec=random.Random)
        self._rng_mock.randint.return_value = 0
        self._state_machine_context._rng = self._rng_mock
        self._spell_cast_context.state_machine_context = self._state_machine_context

    def _cast_handler(self):
        return self._spell_traits.handler

    def _call_select_target(self, caster, other_unit):
        return self._cast_handler().select_target(caster, other_unit)

    def _call_can_cast(self):
        return self._cast_handler().can_cast(self._spell_cast_context)

    def _call_cast(self):
        return self._cast_handler().cast(self._spell_cast_context)

    def test_spell_base_name(self):
        self.assertEqual(self._spell_traits.base_name, self._spell_base_name)

    def test_spell_name(self):
        self.assertEqual(self._spell_traits.name, self._SPELL_NAME)

    def test_native_genus(self):
        self.assertEqual(self._spell_traits.native_genus, self._NATIVE_GENUS)

    def test_mp_cost(self):
        self.assertEqual(self._spell_traits.mp_cost, self._MP_COST)

    def _set_spell_level(self, spell_level):
        self._spell_cast_context.spell_level = spell_level


class NativeFireSpellTester:
    _NATIVE_GENUS = Genus.Fire


class NativeWaterSpellTester:
    _NATIVE_GENUS = Genus.Water


class NativeWindSpellTester:
    _NATIVE_GENUS = Genus.Wind


class SelfCastTester:
    def test_select_target(self):
        self.assertEqual(self._call_select_target('CASTER', 'OTHER_UNIT'), 'CASTER')


class OtherUnitCastTester:
    def test_select_target(self):
        self.assertEqual(self._call_select_target('CASTER', 'OTHER_UNIT'), 'OTHER_UNIT')


class CanAlwaysCastTester:
    def test_can_cast(self):
        can_cast, _ = self._call_can_cast()
        self.assertTrue(can_cast)


class DamagingSpellTester(OtherUnitCastTester, CanAlwaysCastTester):
    def _test_cast(self, damage=0):
        with patch('curry_quest.spells_descriptor.DamageCalculator') as DamageCalculatorMock:
            damage_calculator_mock = DamageCalculatorMock.return_value
            damage_calculator_mock.spell_damage.return_value = damage
            response = self._call_cast()
            damage_calculator_mock.spell_damage.assert_called_once()
            return response, DamageCalculatorMock.call_args.args, damage_calculator_mock.spell_damage.call_args.args

    def test_cast_response_when_target_is_monster(self):
        self._state_machine_context.familiar = self._caster
        self._target.name = 'target_unit'
        self._target.hp = 30
        self._target.max_hp = 30
        response, _, _ = self._test_cast(damage=6)
        self.assertEqual(response, 'It deals 6 damage. Target_unit has 24 HP left.')

    def test_cast_response_when_target_is_familiar(self):
        self._state_machine_context.familiar = self._target
        self._target.name = 'target_unit'
        self._target.hp = 20
        self._target.max_hp = 20
        response, _, _ = self._test_cast(damage=13)
        self.assertEqual(response, 'It deals 13 damage. You have 7 HP left.')

    def test_cast_damage_calculator_args(self):
        _, damage_calculator_args, _ = self._test_cast()
        self.assertEqual(damage_calculator_args, (self._caster, self._target))


class NativeFireDamagingSpellTester(NativeFireSpellTester, DamagingSpellTester):
    pass


class BreathTester(NativeFireDamagingSpellTester):
    _MP_COST = 12

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (16,))


class BreathTest(SpellTestBase, BreathTester):
    _SPELL_NAME = 'Breath'

    @classmethod
    def _spell_selector(cls):
        return 'Breath', Genus.Fire


class NeaBreathTest(SpellTestBase, BreathTester):
    _SPELL_NAME = 'NeaBreath'

    @classmethod
    def _spell_selector(cls):
        return 'Breath', Genus.Water


class NoaBreathTest(SpellTestBase, BreathTester):
    _SPELL_NAME = 'NoaBreath'

    @classmethod
    def _spell_selector(cls):
        return 'Breath', Genus.Wind


class SledTester(NativeFireDamagingSpellTester):
    _MP_COST = 8


class SledTest(SpellTestBase, SledTester):
    _SPELL_NAME = 'Sled'

    @classmethod
    def _spell_selector(cls):
        return 'Sled', Genus.Fire

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (8,))


class NeaSledTest(SpellTestBase, SledTester):
    _SPELL_NAME = 'NeaSled'

    @classmethod
    def _spell_selector(cls):
        return 'Sled', Genus.Water

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (10,))


class NoaSledTest(SpellTestBase, SledTester):
    _SPELL_NAME = 'NoaSled'

    @classmethod
    def _spell_selector(cls):
        return 'Sled', Genus.Wind

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (8,))


class BridTester(NativeFireDamagingSpellTester):
    _MP_COST = 10

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (10,))


class BridTest(SpellTestBase, BridTester):
    _SPELL_NAME = 'Brid'

    @classmethod
    def _spell_selector(cls):
        return 'Brid', Genus.Fire


class NeaBridTest(SpellTestBase, BridTester):
    _SPELL_NAME = 'NeaBrid'

    @classmethod
    def _spell_selector(cls):
        return 'Brid', Genus.Water


class NoaBridTest(SpellTestBase, BridTester):
    _SPELL_NAME = 'NoaBrid'

    @classmethod
    def _spell_selector(cls):
        return 'Brid', Genus.Wind


class RiseTester(NativeFireDamagingSpellTester):
    _MP_COST = 16

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (19,))


class RiseTest(SpellTestBase, RiseTester):
    _SPELL_NAME = 'Rise'

    @classmethod
    def _spell_selector(cls):
        return 'Rise', Genus.Fire


class NeaRiseTest(SpellTestBase, RiseTester):
    _SPELL_NAME = 'NeaRise'

    @classmethod
    def _spell_selector(cls):
        return 'Rise', Genus.Water


class NoaRiseTest(SpellTestBase, RiseTester):
    _SPELL_NAME = 'NoaRise'

    @classmethod
    def _spell_selector(cls):
        return 'Rise', Genus.Wind


def createStandardStatusDurationTester(status: Statuses, static_duration: int, random_duration_upper_limit: int):
    class StandardStatusDurationTester:
        def test_status_duration_when_cast_is_successful(self):
            def test_status_duration(spell_level, rng_duration, status_duration):
                self._set_spell_level(spell_level)
                self._test_cast(is_cast_successful=True, rng_duration=rng_duration)
                self.assertEqual(
                    self._target.status_duration(status),
                    {status: status_duration},
                    f'For spell_level={spell_level}, rng_duration={rng_duration}')

            test_status_duration(spell_level=11, rng_duration=2, status_duration=4 + static_duration)
            test_status_duration(spell_level=11, rng_duration=4, status_duration=6 + static_duration)
            test_status_duration(spell_level=12, rng_duration=4, status_duration=7 + static_duration)
            test_status_duration(spell_level=13, rng_duration=4, status_duration=7 + static_duration)
            test_status_duration(spell_level=14, rng_duration=4, status_duration=7 + static_duration)
            test_status_duration(spell_level=15, rng_duration=4, status_duration=7 + static_duration)
            test_status_duration(spell_level=16, rng_duration=4, status_duration=8 + static_duration)

        def test_rng_duration_range(self):
            self._test_cast(is_cast_successful=True)
            self._rng_mock.randint.assert_called_once_with(0, random_duration_upper_limit)

    return StandardStatusDurationTester


def createApplyDebuffTester(status: Statuses, status_proof_talent: Talents, status_applied_label: str):
    class ApplyDebuffTester:
        def test_cast_response_when_target_is_status_proof(self):
            self._target._talents = status_proof_talent
            response = self._test_cast()
            self.assertEqual(response, 'It has no effect.')

        def test_status_when_target_is_status_proof(self):
            self._target._talents = status_proof_talent
            self._test_cast()
            self.assertFalse(self._target.has_status(status))

        def test_cast_response_when_cast_is_unsuccessful(self):
            response = self._test_cast(is_cast_successful=False)
            self.assertEqual(response, 'It has no effect.')

        def test_status_when_cast_is_unsuccessful(self):
            self._test_cast(is_cast_successful=False)
            self.assertFalse(self._target.has_status(status))

        def test_cast_response_when_cast_is_successful_on_familiar(self):
            self._state_machine_context.familiar = self._target
            response = self._test_cast(is_cast_successful=True)
            self.assertEqual(response, f'You are {status_applied_label}.')

        def test_cast_response_when_cast_is_successful_on_monster(self):
            self._target.name = 'target_unit'
            self._state_machine_context.familiar = self._caster
            response = self._test_cast(is_cast_successful=True)
            self.assertEqual(response, f'Target_unit is {status_applied_label}.')

        def test_status_when_cast_is_successful(self):
            self._test_cast(is_cast_successful=True)
            self.assertTrue(self._target.has_status(status))

    return ApplyDebuffTester


def createGenusSensitiveApplyDebuffTester(
        target_genus: Genus,
        status: Statuses,
        status_proof_talent: Talents,
        status_applied_label: str):
    class ApplyDebuffTester:
        def test_cast_response_when_target_is_status_proof(self):
            self._target._talents = status_proof_talent
            response = self._test_cast(target_genus=target_genus)
            self.assertEqual(response, 'It has no effect.')

        def test_status_when_target_is_status_proof(self):
            self._target._talents = status_proof_talent
            self._test_cast(target_genus=target_genus)
            self.assertFalse(self._target.has_status(status))

        def test_cast_response_when_cast_is_unsuccessful(self):
            response = self._test_cast(target_genus=target_genus, is_cast_successful=False)
            self.assertEqual(response, 'It has no effect.')

        def test_status_when_cast_is_unsuccessful(self):
            self._test_cast(target_genus=target_genus, is_cast_successful=False)
            self.assertFalse(self._target.has_status(status))

        def test_cast_response_when_cast_is_successful_on_familiar(self):
            self._state_machine_context.familiar = self._target
            response = self._test_cast(target_genus=target_genus, is_cast_successful=True)
            self.assertEqual(response, f'You are {status_applied_label}.')

        def test_cast_response_when_cast_is_successful_on_monster(self):
            self._target.name = 'target_unit'
            self._state_machine_context.familiar = self._caster
            response = self._test_cast(target_genus=target_genus, is_cast_successful=True)
            self.assertEqual(response, f'Target_unit is {status_applied_label}.')

        def test_status_when_cast_is_successful(self):
            self._test_cast(target_genus=target_genus, is_cast_successful=True)
            self.assertTrue(self._target.has_status(status))

    return ApplyDebuffTester


class PoisonTester(
        NativeFireSpellTester,
        OtherUnitCastTester,
        CanAlwaysCastTester,
        createStandardStatusDurationTester(status=Statuses.Poison, static_duration=16, random_duration_upper_limit=3),
        createApplyDebuffTester(Statuses.Poison, Talents.PoisonProof, status_applied_label='poisoned')):
    _MP_COST = 8

    def _test_cast(self, is_cast_successful=True, target_luck=1, rng_duration=0):
        self._target.luck = target_luck
        self._does_action_succeed_mock.return_value = is_cast_successful
        self._rng_mock.randint.return_value = rng_duration
        return self._call_cast()

    def _test_cast_success_chance(self, target_luck, expected_success_chance, delta=0.001):
        self._does_action_succeed_mock.reset_mock()
        self._test_cast(target_luck=target_luck)
        self._does_action_succeed_mock.assert_called_once()
        success_chance = self._does_action_succeed_mock.call_args.args[0]
        self.assertAlmostEqual(success_chance, expected_success_chance, delta=delta)


class PoisonTest(SpellTestBase, PoisonTester):
    _SPELL_NAME = 'Poison'

    @classmethod
    def _spell_selector(cls):
        return 'Poison', Genus.Fire

    def test_cast_success_chance(self):
        self._test_cast_success_chance(target_luck=80, expected_success_chance=0.4)
        self._test_cast_success_chance(target_luck=40, expected_success_chance=0.8)
        self._test_cast_success_chance(target_luck=32, expected_success_chance=1.0)


class NeaPoisonTest(SpellTestBase, PoisonTester):
    _SPELL_NAME = 'NeaPoison'

    @classmethod
    def _spell_selector(cls):
        return 'Poison', Genus.Water

    def test_cast_success_chance(self):
        self._test_cast_success_chance(target_luck=80, expected_success_chance=0.2)
        self._test_cast_success_chance(target_luck=40, expected_success_chance=0.4)
        self._test_cast_success_chance(target_luck=20, expected_success_chance=0.8)


class NoaPoisonTest(SpellTestBase, PoisonTester):
    _SPELL_NAME = 'NoaPoison'

    @classmethod
    def _spell_selector(cls):
        return 'Poison', Genus.Wind

    def test_cast_success_chance(self):
        self._test_cast_success_chance(target_luck=80, expected_success_chance=0.2)
        self._test_cast_success_chance(target_luck=40, expected_success_chance=0.4)
        self._test_cast_success_chance(target_luck=20, expected_success_chance=0.8)


def createWallTester(applied_status: Statuses, element_label: str, static_status_duration: int):
    class WallTester(
            NativeWaterSpellTester,
            SelfCastTester,
            CanAlwaysCastTester,
            createStandardStatusDurationTester(
                status=applied_status,
                static_duration=static_status_duration,
                random_duration_upper_limit=3)):
        _MP_COST = 8

        def _test_cast(self, is_cast_successful=True, target_luck=1, rng_duration=0):
            self._rng_mock.randint.return_value = rng_duration
            return self._call_cast()

        def test_cast_response_when_cast_is_on_familiar(self):
            self._state_machine_context.familiar = self._target
            response = self._test_cast()
            self.assertEqual(response, f'You gain protection of {element_label}.')

        def test_cast_response_when_cast_is_on_monster(self):
            self._target.name = 'target_unit'
            self._state_machine_context.familiar = self._caster
            response = self._test_cast()
            self.assertEqual(response, f'Target_unit gains protection of {element_label}.')

        def test_status_when_cast(self):
            self._test_cast()
            self.assertTrue(self._target.has_status(applied_status))

    return WallTester


class DeaWallTest(
        SpellTestBase,
        createWallTester(Statuses.FireProtection, element_label='fire', static_status_duration=2)):
    _SPELL_NAME = 'DeaWall'

    @classmethod
    def _spell_selector(cls):
        return 'Wall', Genus.Fire


class DeWallTest(
        SpellTestBase,
        createWallTester(Statuses.WaterProtection, element_label='water', static_status_duration=4)):
    _SPELL_NAME = 'DeWall'

    @classmethod
    def _spell_selector(cls):
        return 'Wall', Genus.Water


class DeoWallTest(
        SpellTestBase,
        createWallTester(Statuses.WindProtection, element_label='wind', static_status_duration=2)):
    _SPELL_NAME = 'DeoWall'

    @classmethod
    def _spell_selector(cls):
        return 'Wall', Genus.Wind


def createMirrorTester(applied_status: Statuses, reflect_label: str, static_status_duration: int):
    class WallTester(
            NativeWaterSpellTester,
            SelfCastTester,
            CanAlwaysCastTester,
            createStandardStatusDurationTester(
                status=applied_status,
                static_duration=static_status_duration,
                random_duration_upper_limit=0)):
        _MP_COST = 8

        def _test_cast(self, is_cast_successful=True, target_luck=1, rng_duration=0):
            self._rng_mock.randint.return_value = rng_duration
            return self._call_cast()

        def test_cast_response_when_cast_is_on_familiar(self):
            self._state_machine_context.familiar = self._target
            response = self._test_cast()
            self.assertEqual(response, f'You reflect {reflect_label} spells.')

        def test_cast_response_when_cast_is_on_monster(self):
            self._target.name = 'target_unit'
            self._state_machine_context.familiar = self._caster
            response = self._test_cast()
            self.assertEqual(response, f'Target_unit reflects {reflect_label} spells.')

        def test_status_when_cast(self):
            self._test_cast()
            self.assertTrue(self._target.has_status(applied_status))

    return WallTester


class DeaMirrorTest(
        SpellTestBase,
        createMirrorTester(Statuses.FireReflect, reflect_label='fire', static_status_duration=2)):

    _SPELL_NAME = 'DeaMirror'

    @classmethod
    def _spell_selector(cls):
        return 'Mirror', Genus.Fire


class DeMirrorTest(
        SpellTestBase,
        createMirrorTester(Statuses.Reflect, reflect_label='all', static_status_duration=4)):

    _SPELL_NAME = 'DeMirror'

    @classmethod
    def _spell_selector(cls):
        return 'Mirror', Genus.Water


class DeoMirrorTest(
        SpellTestBase,
        createMirrorTester(Statuses.WindReflect, reflect_label='wind', static_status_duration=2)):

    _SPELL_NAME = 'DeoMirror'

    @classmethod
    def _spell_selector(cls):
        return 'Mirror', Genus.Wind


class HpRecoverySpellTester:
    def test_can_cast_when_hp_is_not_max(self):
        self._target.hp = 19
        self._target.max_hp = 20
        can_cast, _ = self._call_can_cast()
        self.assertTrue(can_cast)

    def test_cannot_cast_when_hp_is_max(self):
        self._target.hp = 20
        self._target.max_hp = 20
        can_cast, _ = self._call_can_cast()
        self.assertFalse(can_cast)

    def test_cannot_cast_response(self):
        self._target.hp = 20
        self._target.max_hp = 20
        _, response = self._call_can_cast()
        self.assertEqual(response, 'HP is already at max.')

    def _test_cast(self, target_hp=1, target_max_hp=100):
        self._target.hp = target_hp
        self._target.max_hp = target_max_hp
        return self._call_cast()

    def _test_recovery_amount(self, target_hp, target_max_hp, hp_after_heal, spell_level=1, rng_heal=0):
        self._set_spell_level(spell_level)
        self._target.hp = target_hp
        self._target.max_hp = target_max_hp
        self._rng_mock.randint.return_value = rng_heal
        self._test_cast(target_hp=target_hp, target_max_hp=target_max_hp)
        self.assertEqual(self._target.hp, hp_after_heal)

    def test_response_when_familiar_is_target(self):
        self._state_machine_context.familiar = self._target
        response = self._test_cast(target_hp=2, target_max_hp=255)
        recovery_amount = self._target.hp - 2
        self.assertEqual(response, f'It heals {recovery_amount} HP. You have {self._target.hp} HP.')

    def test_response_when_monster_is_target(self):
        self._state_machine_context.familiar = self._caster
        self._target.name = 'target_unit'
        response = self._test_cast(target_hp=2, target_max_hp=255)
        recovery_amount = self._target.hp - 2
        self.assertEqual(response, f'It heals {recovery_amount} HP. Target_unit has {self._target.hp} HP.')


class RngHpRecoverySpellTester(HpRecoverySpellTester):
    def test_rng_heal_range(self):
        self._test_cast()
        self._rng_mock.randint.assert_called_once_with(0, 3)


class HealTester(NativeWaterSpellTester, SelfCastTester, RngHpRecoverySpellTester):
    _MP_COST = 10


class DeaHealTest(SpellTestBase, HealTester):
    _SPELL_NAME = 'DeaHeal'

    @classmethod
    def _spell_selector(cls):
        return 'Heal', Genus.Fire

    def test_recovery_amount_from_level(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=8, spell_level=8)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=8, spell_level=9)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=8, spell_level=10)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=8, spell_level=11)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=9, spell_level=12)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=9, spell_level=13)

    def test_recovery_amount_from_rng_heal(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=9, spell_level=8, rng_heal=1)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=10, spell_level=8, rng_heal=2)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=11, spell_level=8, rng_heal=3)

    def test_bonus_recovery_amount(self):
        self._test_recovery_amount(target_hp=3, target_max_hp=40, hp_after_heal=18, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=4, target_max_hp=40, hp_after_heal=14, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=5, target_max_hp=40, hp_after_heal=20, spell_level=8, rng_heal=4)

    def test_recovery_capped_by_max_hp(self):
        self._test_recovery_amount(target_hp=3, target_max_hp=17, hp_after_heal=17, spell_level=8, rng_heal=4)


class DeHealTest(SpellTestBase, HealTester):
    _SPELL_NAME = 'DeHeal'

    @classmethod
    def _spell_selector(cls):
        return 'Heal', Genus.Water

    def test_recovery_amount_from_level(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=8)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=9)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=10)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=11)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=21, spell_level=12)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=21, spell_level=13)

    def test_recovery_amount_from_rng_heal(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=21, spell_level=8, rng_heal=1)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=22, spell_level=8, rng_heal=2)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=23, spell_level=8, rng_heal=3)

    def test_bonus_recovery_amount(self):
        self._test_recovery_amount(target_hp=3, target_max_hp=40, hp_after_heal=25, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=4, target_max_hp=40, hp_after_heal=28, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=5, target_max_hp=40, hp_after_heal=29, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=6, target_max_hp=40, hp_after_heal=30, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=7, target_max_hp=40, hp_after_heal=31, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=8, target_max_hp=40, hp_after_heal=30, spell_level=8, rng_heal=4)

    def test_recovery_capped_by_max_hp(self):
        self._test_recovery_amount(target_hp=3, target_max_hp=24, hp_after_heal=24, spell_level=8, rng_heal=4)


class DeoHealTest(SpellTestBase, HealTester):
    _SPELL_NAME = 'DeoHeal'

    @classmethod
    def _spell_selector(cls):
        return 'Heal', Genus.Wind

    def test_recovery_amount_from_level(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=11, spell_level=8)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=11, spell_level=9)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=11, spell_level=10)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=11, spell_level=11)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=12, spell_level=12)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=12, spell_level=13)

    def test_recovery_amount_from_rng_heal(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=12, spell_level=8, rng_heal=1)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=13, spell_level=8, rng_heal=2)
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=14, spell_level=8, rng_heal=3)

    def test_bonus_recovery_amount(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=15, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=19, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=3, target_max_hp=40, hp_after_heal=20, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=4, target_max_hp=40, hp_after_heal=18, spell_level=8, rng_heal=4)

    def test_recovery_capped_by_max_hp(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=14, hp_after_heal=14, spell_level=8, rng_heal=4)


class ForthTester(NativeWaterSpellTester, SelfCastTester):
    _MP_COST = 16


class DeaForthTest(SpellTestBase, ForthTester, RngHpRecoverySpellTester):
    _SPELL_NAME = 'DeaForth'

    @classmethod
    def _spell_selector(cls):
        return 'Forth', Genus.Fire

    def test_recovery_amount_from_level(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=12, spell_level=8)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=12, spell_level=9)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=12, spell_level=10)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=12, spell_level=11)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=13, spell_level=12)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=13, spell_level=13)

    def test_recovery_amount_from_rng_heal(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=13, spell_level=8, rng_heal=1)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=14, spell_level=8, rng_heal=2)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=15, spell_level=8, rng_heal=3)

    def test_bonus_recovery_amount(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=29, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=16, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=3, target_max_hp=40, hp_after_heal=31, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=4, target_max_hp=40, hp_after_heal=18, spell_level=8, rng_heal=4)

    def test_recovery_capped_by_max_hp(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=15, hp_after_heal=15, spell_level=8, rng_heal=4)


class DeForthTest(SpellTestBase, ForthTester, HpRecoverySpellTester):
    _SPELL_NAME = 'DeForth'

    @classmethod
    def _spell_selector(cls):
        return 'Forth', Genus.Water

    def test_recovery_amount(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=255, hp_after_heal=255, spell_level=8)
        self._test_recovery_amount(target_hp=1, target_max_hp=255, hp_after_heal=255, spell_level=9)
        self._test_recovery_amount(target_hp=1, target_max_hp=255, hp_after_heal=255, spell_level=10)
        self._test_recovery_amount(target_hp=1, target_max_hp=255, hp_after_heal=255, spell_level=11)


class DeoForthTest(SpellTestBase, ForthTester, RngHpRecoverySpellTester):
    _SPELL_NAME = 'DeoForth'

    @classmethod
    def _spell_selector(cls):
        return 'Forth', Genus.Wind

    def test_recovery_amount_from_level(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=8)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=9)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=10)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=20, spell_level=11)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=21, spell_level=12)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=21, spell_level=13)

    def test_recovery_amount_from_rng_heal(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=21, spell_level=8, rng_heal=1)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=22, spell_level=8, rng_heal=2)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=23, spell_level=8, rng_heal=3)

    def test_bonus_recovery_amount(self):
        self._test_recovery_amount(target_hp=1, target_max_hp=40, hp_after_heal=34, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=2, target_max_hp=40, hp_after_heal=24, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=3, target_max_hp=40, hp_after_heal=36, spell_level=8, rng_heal=4)
        self._test_recovery_amount(target_hp=4, target_max_hp=40, hp_after_heal=26, spell_level=8, rng_heal=4)

    def test_recovery_capped_by_max_hp(self):
        self._test_recovery_amount(target_hp=2, target_max_hp=23, hp_after_heal=23, spell_level=8, rng_heal=4)


class BlindTester(NativeWindSpellTester, OtherUnitCastTester, CanAlwaysCastTester):
    _MP_COST = 8

    def test_cast_success_chance(self):
        self._test_cast_success_chance(target_luck=80, expected_success_chance=0.2)
        self._test_cast_success_chance(target_luck=40, expected_success_chance=0.4)
        self._test_cast_success_chance(target_luck=20, expected_success_chance=0.8)

    def _test_cast_success_chance(self, target_luck, expected_success_chance, delta=0.001):
        self._does_action_succeed_mock.reset_mock()
        self._test_cast(target_luck=target_luck)
        self._does_action_succeed_mock.assert_called_once()
        success_chance = self._does_action_succeed_mock.call_args.args[0]
        self.assertAlmostEqual(success_chance, expected_success_chance, delta=delta)

    def _test_cast(self, is_cast_successful=True, target_luck=1, rng_duration=0):
        self._target.luck = target_luck
        self._does_action_succeed_mock.return_value = is_cast_successful
        self._rng_mock.randint.return_value = rng_duration
        return self._call_cast()


class LaLeBlindTester(
        BlindTester,
        createStandardStatusDurationTester(status=Statuses.Confuse, static_duration=2, random_duration_upper_limit=3),
        createApplyDebuffTester(Statuses.Confuse, Talents.ConfusionProof, status_applied_label='confused')):
    pass


class LaBlindTest(SpellTestBase, LaLeBlindTester):
    _SPELL_NAME = 'LaBlind'

    @classmethod
    def _spell_selector(cls):
        return 'Blind', Genus.Fire


class LeBlindTest(SpellTestBase, LaLeBlindTester):
    _SPELL_NAME = 'LeBlind'

    @classmethod
    def _spell_selector(cls):
        return 'Blind', Genus.Water


class LoBlindTest(
        SpellTestBase,
        BlindTester,
        createStandardStatusDurationTester(status=Statuses.Blind, static_duration=4, random_duration_upper_limit=3),
        createApplyDebuffTester(Statuses.Blind, Talents.BlinderProof, status_applied_label='blinded')):
    _SPELL_NAME = 'LoBlind'

    @classmethod
    def _spell_selector(cls):
        return 'Blind', Genus.Wind


def createBindTester(target_genus: Genus=Genus.Empty):
    class BindTester(NativeWindSpellTester, OtherUnitCastTester, CanAlwaysCastTester):
        _MP_COST = 12

        def test_cast_success_chance(self):
            self._test_cast_success_chance(target_luck=80, expected_success_chance=0.2)
            self._test_cast_success_chance(target_luck=40, expected_success_chance=0.4)
            self._test_cast_success_chance(target_luck=20, expected_success_chance=0.8)

        def _test_cast_success_chance(self, target_luck, expected_success_chance, delta=0.001):
            self._does_action_succeed_mock.reset_mock()
            self._test_cast(target_genus=target_genus, target_luck=target_luck)
            self._does_action_succeed_mock.assert_called_once()
            success_chance = self._does_action_succeed_mock.call_args.args[0]
            self.assertAlmostEqual(success_chance, expected_success_chance, delta=delta)

        def _test_cast(self, target_genus=None, is_cast_successful=True, target_luck=1):
            if target_genus is not None:
                self._target.genus = target_genus
            self._target.luck = target_luck
            self._does_action_succeed_mock.return_value = is_cast_successful
            return self._call_cast()

    return BindTester


class LaBindTester(
        SpellTestBase,
        createBindTester(target_genus=Genus.Wind),
        createGenusSensitiveApplyDebuffTester(
            target_genus=Genus.Wind,
            status=Statuses.Paralyze,
            status_proof_talent=Talents.ParalysisProof,
            status_applied_label='paralyzed')):
    _SPELL_NAME = 'LaBind'

    @classmethod
    def _spell_selector(cls):
        return 'Bind', Genus.Fire

    def test_debuff_duration(self):
        self._test_cast(target_genus=Genus.Wind, is_cast_successful=True)
        self.assertEqual(self._target.status_duration(Statuses.Paralyze), {Statuses.Paralyze: 2})

    def test_when_unit_has_no_genus_then_cast_is_unsuccessful(self):
        self._test_cast(target_genus=Genus.Empty, is_cast_successful=True)
        self.assertFalse(self._target.has_status(Statuses.Paralyze))

    def test_when_unit_has_genus_fire_then_cast_is_unsuccessful(self):
        self._test_cast(target_genus=Genus.Fire, is_cast_successful=True)
        self.assertFalse(self._target.has_status(Statuses.Paralyze))

    def test_when_unit_has_genus_water_then_cast_is_unsuccessful(self):
        self._test_cast(target_genus=Genus.Water, is_cast_successful=True)
        self.assertFalse(self._target.has_status(Statuses.Paralyze))


class LeBindTester(
        SpellTestBase,
        createBindTester(target_genus=Genus.Fire),
        createGenusSensitiveApplyDebuffTester(
            target_genus=Genus.Fire,
            status=Statuses.Paralyze,
            status_proof_talent=Talents.ParalysisProof,
            status_applied_label='paralyzed')):
    _SPELL_NAME = 'LeBind'

    @classmethod
    def _spell_selector(cls):
        return 'Bind', Genus.Water

    def test_debuff_duration(self):
        self._test_cast(target_genus=Genus.Fire, is_cast_successful=True)
        self.assertEqual(self._target.status_duration(Statuses.Paralyze), {Statuses.Paralyze: 2})

    def test_when_unit_has_no_genus_then_cast_is_unsuccessful(self):
        self._test_cast(target_genus=Genus.Empty, is_cast_successful=True)
        self.assertFalse(self._target.has_status(Statuses.Paralyze))

    def test_when_unit_has_genus_water_then_cast_is_unsuccessful(self):
        self._test_cast(target_genus=Genus.Water, is_cast_successful=True)
        self.assertFalse(self._target.has_status(Statuses.Paralyze))

    def test_when_unit_has_genus_wind_then_cast_is_unsuccessful(self):
        self._test_cast(target_genus=Genus.Water, is_cast_successful=True)
        self.assertFalse(self._target.has_status(Statuses.Paralyze))


class LoBindTester(
        SpellTestBase,
        createBindTester(),
        createApplyDebuffTester(Statuses.Paralyze, Talents.ParalysisProof, status_applied_label='paralyzed')):
    _SPELL_NAME = 'LoBind'

    @classmethod
    def _spell_selector(cls):
        return 'Bind', Genus.Wind

    def test_debuff_duration(self):
        self._test_cast(is_cast_successful=True)
        self.assertEqual(self._target.status_duration(Statuses.Paralyze), {Statuses.Paralyze: 4})


class SleepTester(NativeWindSpellTester, OtherUnitCastTester, CanAlwaysCastTester):
    _MP_COST = 10

    def test_cast_success_chance(self):
        self._test_cast_success_chance(target_luck=80, expected_success_chance=0.1)
        self._test_cast_success_chance(target_luck=40, expected_success_chance=0.2)
        self._test_cast_success_chance(target_luck=20, expected_success_chance=0.4)

    def _test_cast_success_chance(self, target_luck, expected_success_chance, delta=0.001):
        self._does_action_succeed_mock.reset_mock()
        self._test_cast(target_luck=target_luck)
        self._does_action_succeed_mock.assert_called_once()
        success_chance = self._does_action_succeed_mock.call_args.args[0]
        self.assertAlmostEqual(success_chance, expected_success_chance, delta=delta)

    def _test_cast(self, is_cast_successful=True, target_luck=1, rng_duration=0):
        self._target.luck = target_luck
        self._does_action_succeed_mock.return_value = is_cast_successful
        self._rng_mock.randint.return_value = rng_duration
        return self._call_cast()


class LoSleepTest(
        SpellTestBase,
        SleepTester,
        createStandardStatusDurationTester(status=Statuses.Sleep, static_duration=4, random_duration_upper_limit=3),
        createApplyDebuffTester(Statuses.Sleep, Talents.SleepProof, status_applied_label='put to sleep')):
    _SPELL_NAME = 'LoSleep'

    @classmethod
    def _spell_selector(cls):
        return 'Sleep', Genus.Wind


class DownTester(NativeWindSpellTester, ):
    _MP_COST = 9


class NonWindDownTester(DownTester, CanAlwaysCastTester):
    def _test_cast(self, target_luck=1, does_action_succeed=True):
        self._target.luck = target_luck
        self._does_action_succeed_mock.return_value = does_action_succeed
        return self._call_cast()

    def test_response_on_unsuccesful_cast(self):
        response = self._test_cast(target_luck=1, does_action_succeed=False)
        self.assertEqual(response, 'Spell misses.')

    def _test_cast_success_chance(self, target_luck=1, spell_level=1, success_chance=0.0, delta=0.001):
        self._does_action_succeed_mock.reset_mock()
        self._set_spell_level(spell_level)
        self._test_cast(target_luck=target_luck)
        self._does_action_succeed_mock.assert_called_once()
        used_success_chance = self._does_action_succeed_mock.call_args.args[0]
        self.assertAlmostEqual(used_success_chance, success_chance, delta=delta)

    def test_does_action_succeed_success_chance_by_spell_level(self):
        test_action_success_chance = functools.partial(self._test_cast_success_chance, target_luck=1)
        test_action_success_chance(spell_level=1, success_chance=32)
        test_action_success_chance(spell_level=2, success_chance=64)
        test_action_success_chance(spell_level=3, success_chance=96)
        test_action_success_chance(spell_level=4, success_chance=128)

    def test_does_action_succeed_success_chance_by_target_luck(self):
        test_action_success_chance = functools.partial(self._test_cast_success_chance, spell_level=1)
        test_action_success_chance(target_luck=1, success_chance=32)
        test_action_success_chance(target_luck=2, success_chance=16)
        test_action_success_chance(target_luck=3, success_chance=32/3)
        test_action_success_chance(target_luck=4, success_chance=8)


class LaDownTest(SpellTestBase, NonWindDownTester):
    _SPELL_NAME = 'LaDown'

    @classmethod
    def _spell_selector(cls):
        return 'Down', Genus.Fire

    def _test_cast_result(self, target_attack=8, expected_target_attack=4, target_luck=1, does_action_succeed=True):
        self._target.attack = target_attack
        self._test_cast(target_luck, does_action_succeed)
        self.assertEqual(self._target.attack, expected_target_attack)

    def test_when_cast_succeeds_attack_is_cut_in_half(self):
        self._test_cast_result(target_attack=4, expected_target_attack=2)
        self._test_cast_result(target_attack=5, expected_target_attack=2)
        self._test_cast_result(target_attack=6, expected_target_attack=3)
        self._test_cast_result(target_attack=7, expected_target_attack=3)
        self._test_cast_result(target_attack=8, expected_target_attack=4)

    def test_when_cast_does_not_succeed_attack_is_not_changed(self):
        self._test_cast_result(target_attack=4, expected_target_attack=4, does_action_succeed=False)

    def test_attack_does_not_underflow(self):
        self._test_cast_result(target_attack=1, expected_target_attack=1)

    def test_when_target_luck_is_0_then_cast_always_succeeds(self):
        self._test_cast_result(target_attack=6, expected_target_attack=3, target_luck=0, does_action_succeed=False)

    def test_response_on_successful_cast_on_familiar(self):
        self._state_machine_context.familiar = self._target
        self._target.attack = 6
        self.assertEqual(self._test_cast(), f'Spell decreases your ATK. New ATK: 3.')

    def test_response_on_successful_cast_on_enemy(self):
        self._state_machine_context.familiar = self._caster
        self._target.name = 'target_unit'
        self._target.attack = 6
        self.assertEqual(self._test_cast(), f'Spell decreases Target_unit\'s ATK. New ATK: 3.')


class LeDownTest(SpellTestBase, NonWindDownTester):
    _SPELL_NAME = 'LeDown'

    @classmethod
    def _spell_selector(cls):
        return 'Down', Genus.Water

    def _test_cast_result(self, target_defense=8, expected_target_defense=4, target_luck=1, does_action_succeed=True):
        self._target.defense = target_defense
        self._test_cast(target_luck, does_action_succeed)
        self.assertEqual(self._target.defense, expected_target_defense)

    def test_when_cast_succeeds_defense_is_cut_in_half(self):
        self._test_cast_result(target_defense=4, expected_target_defense=2)
        self._test_cast_result(target_defense=5, expected_target_defense=2)
        self._test_cast_result(target_defense=6, expected_target_defense=3)
        self._test_cast_result(target_defense=7, expected_target_defense=3)
        self._test_cast_result(target_defense=8, expected_target_defense=4)

    def test_when_cast_does_not_succeed_defense_is_not_changed(self):
        self._test_cast_result(target_defense=4, expected_target_defense=4, does_action_succeed=False)

    def test_defense_does_not_underflow(self):
        self._test_cast_result(target_defense=1, expected_target_defense=1)

    def test_when_target_luck_is_0_then_cast_always_succeeds(self):
        self._test_cast_result(target_defense=6, expected_target_defense=3, target_luck=0, does_action_succeed=False)

    def test_response_on_successful_cast_on_familiar(self):
        self._state_machine_context.familiar = self._target
        self._target.defense = 6
        self.assertEqual(self._test_cast(), f'Spell decreases your DEF. New DEF: 3.')

    def test_response_on_successful_cast_on_enemy(self):
        self._state_machine_context.familiar = self._caster
        self._target.name = 'target_unit'
        self._target.defense = 6
        self.assertEqual(self._test_cast(), f'Spell decreases Target_unit\'s DEF. New DEF: 3.')


class LoDownTest(SpellTestBase, DownTester):
    _SPELL_NAME = 'LoDown'

    @classmethod
    def _spell_selector(cls):
        return 'Down', Genus.Wind

    def _test_can_cast_result(self, target_level):
        self._target.level = target_level
        can_cast, _ = self._call_can_cast()
        return can_cast

    def test_can_cast_returns_false_when_target_is_level_1(self):
        self.assertFalse(self._test_can_cast_result(target_level=1))

    def test_can_cast_response_when_cannot_cast(self):
        self._target.level = 1
        _, response = self._call_can_cast()
        self.assertEqual(response, 'Target is already at minimum level.')

    def test_can_cast_returns_true_when_target_level_is_greater_than_1(self):
        self.assertTrue(self._test_can_cast_result(target_level=2))
        self.assertTrue(self._test_can_cast_result(target_level=3))
        self.assertTrue(self._test_can_cast_result(target_level=4))

    def test_cast_response_when_cast_does_not_succeed(self):
        self._does_action_succeed_mock.return_value = False
        self._target.luck = 20
        response = self._call_cast()
        self.assertEqual(response, 'Spell misses.')

    def test_cast_response_when_cast_succeeds_on_familiar(self):
        self._target.luck = 0
        self._state_machine_context.familiar = self._target
        response = self._call_cast()
        self.assertEqual(response, f'You feel weaker. New stats - {self._target.stats_to_string()}.')

    def test_cast_response_when_cast_succeeds_on_enemy(self):
        self._target.name = 'target_unit'
        self._target.luck = 0
        self._state_machine_context.familiar = self._caster
        response = self._call_cast()
        self.assertEqual(response, f'Target_unit feels weaker. New stats - {self._target.stats_to_string()}.')

    def _test_cast_success_by_luck_stat(self, target_luck, cast_successful):
        self._does_action_succeed_mock.reset_mock()
        self._does_action_succeed_mock.return_value = False
        self._target.level = 2
        self._target.luck = target_luck
        self._call_cast()
        did_cast_succeed = (self._target.level == 1)
        self.assertEqual(did_cast_succeed, cast_successful)

    def test_cast_always_succeeds_when_target_luck_is_16_or_less(self):
        self._test_cast_success_by_luck_stat(target_luck=16, cast_successful=True)
        self._test_cast_success_by_luck_stat(target_luck=15, cast_successful=True)
        self._test_cast_success_by_luck_stat(target_luck=14, cast_successful=True)
        self._test_cast_success_by_luck_stat(target_luck=13, cast_successful=True)

    def test_cast_does_not_succeed_when_target_luck_is_17_or_greater_and_action_does_not_succeed(self):
        self._test_cast_success_by_luck_stat(target_luck=17, cast_successful=False)
        self._test_cast_success_by_luck_stat(target_luck=18, cast_successful=False)

    def _test_cast_success_by_does_action_succeed_call(self, does_action_succeed, cast_successful):
        self._does_action_succeed_mock.return_value = does_action_succeed
        self._target.level = 2
        self._target.luck = 17
        self._call_cast()
        did_cast_succeed = (self._target.level == 1)
        self.assertEqual(did_cast_succeed, cast_successful)

    def test_cast_succeed_when_action_succeed(self):
        self._test_cast_success_by_does_action_succeed_call(does_action_succeed=True, cast_successful=True)

    def test_cast_does_not_succeed_when_action_does_not_succeed(self):
        self._test_cast_success_by_does_action_succeed_call(does_action_succeed=False, cast_successful=False)

    def _test_action_success_chance(self, spell_level, target_luck, expected_success_chance, delta=0.001):
        self._does_action_succeed_mock.reset_mock()
        self._set_spell_level(spell_level)
        self._target.luck = target_luck
        self._call_cast()
        self._does_action_succeed_mock.assert_called_once()
        success_chance = self._does_action_succeed_mock.call_args.args[0]
        self.assertAlmostEqual(success_chance, expected_success_chance, delta=delta)

    def test_does_action_succeed_success_chance_by_spell_level(self):
        test_action_success_chance = functools.partial(self._test_action_success_chance, target_luck=17)
        test_action_success_chance(spell_level=1, expected_success_chance=0)
        test_action_success_chance(spell_level=2, expected_success_chance=1)
        test_action_success_chance(spell_level=3, expected_success_chance=2)
        test_action_success_chance(spell_level=4, expected_success_chance=3)

    def test_does_action_succeed_success_chance_by_target_luck(self):
        test_action_success_chance = functools.partial(self._test_action_success_chance, spell_level=2)
        test_action_success_chance(target_luck=17, expected_success_chance=1)
        test_action_success_chance(target_luck=18, expected_success_chance=0.5)
        test_action_success_chance(target_luck=19, expected_success_chance=0.333)
        test_action_success_chance(target_luck=20, expected_success_chance=0.25)
        test_action_success_chance(target_luck=21, expected_success_chance=0.2)

    def _test_level_decrease(self, target_level, expected_target_level):
        self._does_action_succeed_mock.return_value = True
        self._target.level = target_level
        self._target.luck = 17
        self._call_cast()
        self.assertEqual(self._target.level, expected_target_level)

    def test_level_decrease_on_successful_cast(self):
        self._test_level_decrease(target_level=5, expected_target_level=4)

    def test_level_is_not_decreased_when_it_is_already_min(self):
        self._test_level_decrease(target_level=1, expected_target_level=1)

    def _test_stat_decrease(self, stats_calculator_method_selector, stat_modifier, target_level=2, target_luck=17):
        self._target.level = target_level
        self._target.luck = target_luck
        self._does_action_succeed_mock.return_value = True
        with patch('curry_quest.unit.StatsCalculator', spec=StatsCalculator) as StatsCalculatorMock:
            stats_calculator_mock = StatsCalculatorMock.return_value
            stats_calculator_mock.hp_increase.return_value = 0
            stats_calculator_mock.mp_increase.return_value = 0
            stats_calculator_mock.attack_increase.return_value = 0
            stats_calculator_mock.defense_increase.return_value = 0
            stats_calculator_mock.luck_increase.return_value = 0
            method_mock = stats_calculator_method_selector(stats_calculator_mock)
            method_mock.return_value = stat_modifier
            self._call_cast()
            method_mock.assert_called_once_with(target_level)
        return stats_calculator_mock

    def test_hp_decrease_on_successful_cast(self):
        self._target.hp = 10
        self._test_stat_decrease(lambda mock: mock.hp_increase, stat_modifier=4)
        self.assertEqual(self._target.hp, 6)

    def test_hp_does_not_underflow_on_successful_cast(self):
        self._target.hp = 4
        self._test_stat_decrease(lambda mock: mock.hp_increase, stat_modifier=4)
        self.assertEqual(self._target.hp, 1)

    def test_max_hp_decrease_on_successful_cast(self):
        self._target.max_hp = 20
        self._test_stat_decrease(lambda mock: mock.hp_increase, stat_modifier=7)
        self.assertEqual(self._target.max_hp, 13)

    def test_max_hp_does_not_underflow_on_successful_cast(self):
        self._target.max_hp = 4
        self._test_stat_decrease(lambda mock: mock.hp_increase, stat_modifier=4)
        self.assertEqual(self._target.max_hp, 1)

    def test_mp_decrease_on_successful_cast(self):
        self._target.mp = 50
        self._test_stat_decrease(lambda mock: mock.mp_increase, stat_modifier=5)
        self.assertEqual(self._target.mp, 45)

    def test_mp_does_not_underflow_on_successful_cast(self):
        self._target.mp = 4
        self._test_stat_decrease(lambda mock: mock.mp_increase, stat_modifier=5)
        self.assertEqual(self._target.mp, 0)

    def test_max_mp_decrease_on_successful_cast(self):
        self._target.max_mp = 80
        self._test_stat_decrease(lambda mock: mock.mp_increase, stat_modifier=2)
        self.assertEqual(self._target.max_mp, 78)

    def test_max_mp_does_not_underflow_on_successful_cast(self):
        self._target.max_mp = 4
        self._test_stat_decrease(lambda mock: mock.mp_increase, stat_modifier=5)
        self.assertEqual(self._target.max_mp, 0)

    def test_attack_decrease_on_successful_cast(self):
        self._target.attack = 14
        self._test_stat_decrease(lambda mock: mock.attack_increase, stat_modifier=1)
        self.assertEqual(self._target.attack, 13)

    def test_attack_does_not_underflow_on_successful_cast(self):
        self._target.attack = 4
        self._test_stat_decrease(lambda mock: mock.attack_increase, stat_modifier=4)
        self.assertEqual(self._target.attack, 1)

    def test_defense_decrease_on_successful_cast(self):
        self._target.defense = 6
        self._test_stat_decrease(lambda mock: mock.defense_increase, stat_modifier=5)
        self.assertEqual(self._target.defense, 1)

    def test_defense_does_not_underflow_on_successful_cast(self):
        self._target.defense = 4
        self._test_stat_decrease(lambda mock: mock.defense_increase, stat_modifier=4)
        self.assertEqual(self._target.defense, 1)

    def test_luck_decrease_on_successful_cast(self):
        self._test_stat_decrease(lambda mock: mock.luck_increase, stat_modifier=13, target_luck=40)
        self.assertEqual(self._target.luck, 27)

    def test_luck_does_not_underflow_on_successful_cast(self):
        self._test_stat_decrease(lambda mock: mock.luck_increase, stat_modifier=18, target_luck=17)
        self.assertEqual(self._target.luck, 0)

    def _test_stat_decrease_on_level_1(self, target_luck=17):
        self._target.level = 1
        self._target.luck = target_luck
        self._does_action_succeed_mock.return_value = True
        with patch('curry_quest.unit.StatsCalculator', spec=StatsCalculator) as StatsCalculatorMock:
            stats_calculator_mock = StatsCalculatorMock.return_value
            stats_calculator_mock.hp_increase.return_value = 1
            stats_calculator_mock.mp_increase.return_value = 1
            stats_calculator_mock.attack_increase.return_value = 1
            stats_calculator_mock.defense_increase.return_value = 1
            stats_calculator_mock.luck_increase.return_value = 1
            self._call_cast()

    def test_hp_is_not_decreased_when_level_is_min(self):
        self._target.hp = 20
        self._test_stat_decrease_on_level_1()
        self.assertEqual(self._target.hp, 20)

    def test_max_hp_is_not_decreased_when_level_is_min(self):
        self._target.max_hp = 20
        self._test_stat_decrease_on_level_1()
        self.assertEqual(self._target.max_hp, 20)

    def test_mp_is_not_decreased_when_level_is_min(self):
        self._target.mp = 20
        self._test_stat_decrease_on_level_1()
        self.assertEqual(self._target.mp, 20)

    def test_max_mp_is_not_decreased_when_level_is_min(self):
        self._target.max_mp = 20
        self._test_stat_decrease_on_level_1()
        self.assertEqual(self._target.max_mp, 20)

    def test_attack_is_not_decreased_when_level_is_min(self):
        self._target.attack = 20
        self._test_stat_decrease_on_level_1()
        self.assertEqual(self._target.attack, 20)

    def test_defense_is_not_decreased_when_level_is_min(self):
        self._target.defense = 20
        self._test_stat_decrease_on_level_1()
        self.assertEqual(self._target.defense, 20)

    def test_luck_is_not_decreased_when_level_is_min(self):
        self._test_stat_decrease_on_level_1(target_luck=20)
        self.assertEqual(self._target.luck, 20)


class GraveTester(NativeWindSpellTester, DamagingSpellTester):
    _MP_COST = 12

    def test_cast_spell_damage_args(self):
        _, _, spell_damage_args = self._test_cast()
        self.assertEqual(spell_damage_args, (24,))


class LaGraveTest(SpellTestBase, GraveTester):
    _SPELL_NAME = 'LaGrave'

    @classmethod
    def _spell_selector(cls):
        return 'Grave', Genus.Fire


class LeoGraveTest(SpellTestBase, GraveTester):
    _SPELL_NAME = 'LeoGrave'

    @classmethod
    def _spell_selector(cls):
        return 'Grave', Genus.Water


class LoGraveTest(SpellTestBase, GraveTester):
    _SPELL_NAME = 'LoGrave'

    @classmethod
    def _spell_selector(cls):
        return 'Grave', Genus.Wind


class ReflectTest(unittest.TestCase):
    def setUp(self):
        self._familiar = Unit(UnitTraits(), Levels())
        self._familiar.name = 'familiar'
        self._enemy = Unit(UnitTraits(), Levels())
        self._enemy.name = 'enemy'
        self._spell_handler = create_autospec(spec=SpellHandler)
        self._state_machine_context = StateMachineContext(Config())
        self._state_machine_context.familiar = self._familiar
        self._spell_traits = SpellTraits()
        self._spell_traits.name = 'test_spell'
        self._spell_traits.handler = self._spell_handler
        self._spell_cast_context = SpellCastContext(spell_level=1)
        self._spell_cast_context.performer = self._familiar
        self._spell_cast_context.target = self._enemy
        self._spell_cast_context.reflected_target = self._familiar
        self._spell_cast_context.state_machine_context = self._state_machine_context
        self._spell_cast_action_handler = SpellCastActionHandler(self._spell_traits)

    def _test_spell_cast(self, caster=None, target=None, reflected_target=None, spell_cast_response: str=''):
        recorded_caster = None
        recorded_target = None

        def record_caster_and_target(spell_cast_context: SpellCastContext):
            nonlocal recorded_caster
            nonlocal recorded_target
            recorded_caster = spell_cast_context.performer  # @UnusedVariable
            recorded_target = spell_cast_context.target  # @UnusedVariable
            return spell_cast_response

        self._spell_cast_context.performer = caster or self._familiar
        self._spell_cast_context.target = target or self._enemy
        self._spell_cast_context.reflected_target = reflected_target or self._familiar
        self._spell_handler.select_target.return_value = target
        self._spell_handler.cast.side_effect = record_caster_and_target
        response = self._spell_cast_action_handler.perform(self._spell_cast_context)
        return response, recorded_caster, recorded_target

    def _test_spell_reflect(self, caster_genus: Genus, target_status: Statuses, is_reflected: bool):
        self._familiar.genus = caster_genus
        self._enemy.set_status(target_status)
        response, caster, target = self._test_spell_cast(target=self._enemy, reflected_target=self._familiar)
        self.assertIs(caster, self._familiar)
        self.assertIs(target, self._familiar if is_reflected else self._enemy)
        return response

    def test_when_target_has_fire_reflect_status_then_fire_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Fire, target_status=Statuses.FireReflect, is_reflected=True)

    def test_when_target_has_reflect_status_then_fire_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Fire, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_fire_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Fire, target_status=Statuses.WindReflect, is_reflected=False)

    def test_when_target_has_fire_reflect_status_then_water_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Water, target_status=Statuses.FireReflect, is_reflected=False)

    def test_when_target_has_reflect_status_then_water_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Water, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_water_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Water, target_status=Statuses.WindReflect, is_reflected=False)

    def test_when_target_has_fire_reflect_status_then_wind_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Wind, target_status=Statuses.FireReflect, is_reflected=False)

    def test_when_target_has_reflect_status_then_wind_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Wind, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_wind_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Wind, target_status=Statuses.WindReflect, is_reflected=True)

    def test_when_target_has_fire_reflect_status_then_non_elemental_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Empty, target_status=Statuses.FireReflect, is_reflected=False)

    def test_when_target_has_reflect_status_then_non_elemental_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Empty, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_non_elemental_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Empty, target_status=Statuses.WindReflect, is_reflected=False)

    def _test_spell_reflect_response(self, caster, target, spell_cast_response):
        target.set_status(Statuses.Reflect)
        response, _, _ = self._test_spell_cast(
            caster=caster,
            target=target,
            reflected_target=self._enemy if self._familiar is target else self._familiar,
            spell_cast_response=spell_cast_response)
        return response

    def test_reflected_spell_response_when_spell_is_casted_by_familiar_on_itself(self):
        response = self._test_spell_reflect_response(
            caster=self._familiar,
            target=self._familiar,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'You cast test_spell on yourself. It is reflected at enemy. CASTED')

    def test_reflected_spell_response_when_spell_is_casted_by_familiar_on_enemy(self):
        response = self._test_spell_reflect_response(
            caster=self._familiar,
            target=self._enemy,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'You cast test_spell on enemy. It is reflected back at you. CASTED')

    def test_reflected_spell_response_when_spell_is_casted_by_enemy_on_familiar(self):
        response = self._test_spell_reflect_response(
            caster=self._enemy,
            target=self._familiar,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'Enemy casts test_spell on you. It is reflected back at enemy. CASTED')

    def test_reflected_spell_response_when_spell_is_casted_by_enemy_on_itself(self):
        response = self._test_spell_reflect_response(
            caster=self._enemy,
            target=self._enemy,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'Enemy casts test_spell on itself. It is reflected at you. CASTED')


if __name__ == '__main__':
    unittest.main()
