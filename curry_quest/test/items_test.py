import unittest
from unittest.mock import create_autospec, PropertyMock
from curry_quest.genus import Genus
from curry_quest.items import Item, DefaultFamiliarTargetItem, DefaultEnemyTargetItem, NoDefaultTargetItem, \
    FamiliarOnlyItem, EnemyOnlyItem, FamiliarAndEnemyItem, BattlePhaseOnlyItem, Pita, Oleem, HolyScroll, \
    MedicinalHerb, CureAllHerb, FireBall, WaterCrystal, LightSeed, SeaSeed, WindSeed, all_items
from curry_quest.levels_config import Levels
from curry_quest.state_machine_context import StateMachineContext, BattleContext
from curry_quest.statuses import Statuses
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit_traits import UnitTraits
import inspect


class ItemTestBase(unittest.TestCase):
    _ITEM_CLASS = None

    def setUp(self):
        self._sut = self._ITEM_CLASS()
        self._familiar = Unit(UnitTraits(), Levels())
        self._battle_context = create_autospec(spec=BattleContext)
        self._context = create_autospec(spec=StateMachineContext)
        type(self._context).familiar = PropertyMock(return_value=self._familiar)
        type(self._context).battle_context = PropertyMock(return_value=self._battle_context)
        self._enemy = Unit(UnitTraits(), Levels())
        self._enemy.name = 'monster'
        type(self._battle_context).enemy = PropertyMock(return_value=self._enemy)
        self._action_context = UnitActionContext()
        self._action_context.performer = self._familiar
        self._action_context.state_machine_context = self._context

    def _call_select_target(self):
        return self._sut.select_target(self._familiar, self._enemy)

    def _call_can_target_familiar(self):
        return self._sut.can_target_familiar()

    def _call_can_target_enemy(self):
        return self._sut.can_target_enemy()

    def _call_cannot_use_reason(self):
        return self._sut.cannot_use_reason(self._action_context)

    def _test_cannot_use_reason(self, expected_reason):
        reason = self._call_cannot_use_reason()
        self.assertEqual(reason, expected_reason)

    def _test_can_use(self):
        reason = self._call_cannot_use_reason()
        self.assertFalse(bool(reason))

    def _call_use(self):
        return self._sut.use(self._action_context)

    def _use_on_unit(self, unit: Unit):
        self._action_context.target = unit
        return self._call_use()

    def _use_on_familiar(self):
        self._set_can_use_on_familiar()
        return self._use_on_unit(self._familiar)

    def _set_can_use_on_familiar(self):
        pass

    def _use_on_enemy(self):
        self._set_can_use_on_enemy()
        return self._use_on_unit(self._enemy)

    def _set_can_use_on_enemy(self):
        pass


class AlwaysUsableItemTester:
    def test_can_always_use(self):
        self._test_can_use()


class DefaultFamiliarTargetItemTester:
    def test_select_target_returns_familiar(self):
        self.assertIs(self._call_select_target(), self._familiar)


class FamiliarOnlyItemTester(DefaultFamiliarTargetItemTester):
    def test_can_target_familiar_returns_true(self):
        self.assertTrue(self._call_can_target_familiar())

    def test_can_target_enemy_returns_true(self):
        self.assertFalse(self._call_can_target_enemy())


class DefaultEnemyTargetItemTester:
    def test_select_target_returns_familiar(self):
        self.assertIs(self._call_select_target(), self._enemy)


class EnemyOnlyItemTester(DefaultEnemyTargetItemTester):
    def test_can_target_familiar_returns_true(self):
        self.assertFalse(self._call_can_target_familiar())

    def test_can_target_enemy_returns_true(self):
        self.assertTrue(self._call_can_target_enemy())


class NoDefaultTargetItemTester:
    def test_select_target_returns_familiar(self):
        self.assertIsNone(self._call_select_target())


class FamiliarAndEnemyItemTester:
    def test_can_target_familiar_returns_true(self):
        self.assertTrue(self._call_can_target_familiar())

    def test_can_target_enemy_returns_true(self):
        self.assertTrue(self._call_can_target_enemy())


class HiddenMpRestoreItemTester:
    def test_when_used_on_unit_then_3_mp_is_restored(self):
        self._enemy.mp = 5
        self._enemy.max_mp = 10
        self._use_on_unit(self._enemy)
        self.assertEqual(self._enemy.mp, 8)


class PitaTest(ItemTestBase, AlwaysUsableItemTester, FamiliarOnlyItemTester):
    _ITEM_CLASS = Pita

    def setUp(self):
        super().setUp()
        self._familiar.max_mp = 20
        self._enemy.max_mp = 20

    def _set_mp_to_not_max(self, unit: Unit):
        unit.mp = unit.max_mp - 1

    def _set_mp_to_max(self, unit: Unit):
        unit.mp = unit.max_mp

    def _assert_max_mp(self, unit: Unit, expected_max_mp: int):
        self.assertEqual(unit.max_mp, expected_max_mp)
        self.assertTrue(unit.is_mp_at_max())

    def test_when_used_on_unit_with_not_max_mp_then_mp_is_restored(self):
        max_mp = self._enemy.max_mp
        self._set_mp_to_not_max(self._enemy)
        self._use_on_unit(self._enemy)
        self._assert_max_mp(self._enemy, max_mp)

    def test_when_used_on_unit_with_max_mp_then_max_mp_is_increased(self):
        max_mp = self._enemy.max_mp
        self._set_mp_to_max(self._enemy)
        self._use_on_unit(self._enemy)
        self._assert_max_mp(self._enemy, max_mp + 1)

    def test_response_when_used_on_familiar_and_mp_is_not_at_max(self):
        self._set_mp_to_not_max(self._familiar)
        self.assertEqual(self._use_on_familiar(), 'Your MP has been restored to max.')

    def test_response_when_used_on_familiar_and_mp_is_at_max(self):
        self._set_mp_to_max(self._familiar)
        self.assertEqual(self._use_on_familiar(), 'Your max MP has increased.')

    def test_response_when_used_on_enemy_and_mp_is_not_at_max(self):
        self._set_mp_to_not_max(self._enemy)
        self.assertEqual(self._use_on_enemy(), 'Monster\'s MP has been restored to max.')

    def test_response_when_used_on_enemy_and_mp_is_at_max(self):
        self._set_mp_to_max(self._enemy)
        self.assertEqual(self._use_on_enemy(), 'Monster\'s max MP has increased.')


class BattlePhaseOnlyItemTester:
    def _set_not_in_battle(self):
        self._context.is_in_battle.return_value = False

    def test_when_not_in_battle_then_cannot_use(self):
        self._set_not_in_battle()
        self._test_cannot_use_reason('You are not in combat.')

    def _set_in_battle_prepare_phase(self):
        self._context.is_in_battle.return_value = True
        self._battle_context.is_prepare_phase.return_value = True

    def test_when_in_battle_prepare_phase_then_cannot_use(self):
        self._set_in_battle_prepare_phase()
        self._test_cannot_use_reason('Combat has not started yet.')

    def _set_can_use(self):
        self._context.is_in_battle.return_value = True
        self._battle_context.is_prepare_phase.return_value = False

    def test_when_after_battle_prepare_phase_then_can_use(self):
        self._set_can_use()
        self._test_can_use()


class OleemTest(ItemTestBase, BattlePhaseOnlyItemTester, EnemyOnlyItemTester):
    _ITEM_CLASS = Oleem

    def test_when_used_then_battle_is_finished(self):
        self._call_use()
        self._battle_context.finish_battle.assert_called_once()

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'The enemy vanished!')


class HolyScrollTest(ItemTestBase, BattlePhaseOnlyItemTester, FamiliarOnlyItemTester):
    _ITEM_CLASS = HolyScroll

    def test_when_used_then_holy_scroll_counter_is_set(self):
        self._call_use()
        self._battle_context.set_holy_scroll_counter.assert_called_once_with(3)

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'You are invulnerable for the next 3 turns.')


class MedicinalHerbTest(
        ItemTestBase,
        AlwaysUsableItemTester,
        FamiliarAndEnemyItemTester,
        DefaultFamiliarTargetItemTester,
        HiddenMpRestoreItemTester):
    _ITEM_CLASS = MedicinalHerb

    def setUp(self):
        super().setUp()
        self._familiar.max_hp = 10
        self._enemy.max_hp = 10

    def _set_hp_to_not_max(self, unit: Unit):
        unit.hp = unit.max_hp - 1

    def _set_hp_to_max(self, unit: Unit):
        unit.hp = unit.max_hp

    def _assert_max_hp(self, unit: Unit, expected_max_hp: int):
        self.assertEqual(unit.max_hp, expected_max_hp)
        self.assertTrue(unit.is_hp_at_max())

    def test_when_used_on_unit_with_not_max_hp_then_hp_is_restored(self):
        max_hp = self._enemy.max_hp
        self._set_hp_to_not_max(self._enemy)
        self._use_on_unit(self._enemy)
        self._assert_max_hp(self._enemy, max_hp)

    def test_when_used_on_unit_with_max_hp_then_max_hp_is_increased(self):
        max_hp = self._enemy.max_hp
        self._set_hp_to_max(self._enemy)
        self._use_on_unit(self._enemy)
        self._assert_max_hp(self._enemy, max_hp + 1)

    def test_response_when_used_on_familiar_and_hp_is_not_at_max(self):
        self._set_hp_to_not_max(self._familiar)
        self.assertEqual(self._use_on_familiar(), 'Your HP has been restored to max.')

    def test_response_when_used_on_familiar_and_hp_is_at_max(self):
        self._set_hp_to_max(self._familiar)
        self.assertEqual(self._use_on_familiar(), 'Your max HP has increased.')

    def test_response_when_used_on_enemy_and_hp_is_not_at_max(self):
        self._set_hp_to_not_max(self._enemy)
        self.assertEqual(self._use_on_enemy(), 'Monster\'s HP has been restored to max.')

    def test_response_when_used_on_enemy_and_hp_is_at_max(self):
        self._set_hp_to_max(self._enemy)
        self.assertEqual(self._use_on_enemy(), 'Monster\'s max HP has increased.')


class CureAllHerbTest(
        ItemTestBase,
        AlwaysUsableItemTester,
        FamiliarAndEnemyItemTester,
        DefaultFamiliarTargetItemTester,
        HiddenMpRestoreItemTester):
    _ITEM_CLASS = CureAllHerb

    def _set_status_on_unit(self, unit: Unit):
        unit.set_status(Statuses.Poison)

    def test_when_used_then_statuses_are_cleared(self):
        self._set_status_on_unit(self._enemy)
        self._use_on_unit(self._enemy)
        self.assertFalse(self._enemy.has_any_status())

    def test_response_when_used_on_familiar(self):
        self.assertEqual(self._use_on_familiar(), 'Your statuses have been cleared.')

    def test_response_when_used_on_enemy(self):
        self.assertEqual(self._use_on_enemy(), 'Monster\'s statuses have been cleared.')


class FireBallTest(ItemTestBase, BattlePhaseOnlyItemTester, EnemyOnlyItemTester):
    _ITEM_CLASS = FireBall

    def test_when_used_then_deals_half_max_hp_damage(self):
        self._enemy.hp = 18
        self._enemy.max_hp = 30
        self._call_use()
        self.assertEqual(self._enemy.hp, 3)

    def test_response_when_used(self):
        self._enemy.hp = 25
        self._enemy.max_hp = 37
        self._enemy.name = 'enemy'
        self.assertEqual(
            self._call_use(),
            'Flames spew forth from the Fire Ball dealing 18 damage. Enemy has 7 HP left.')


class WaterCrystalTest(ItemTestBase, AlwaysUsableItemTester, FamiliarOnlyItemTester):
    _ITEM_CLASS = WaterCrystal

    def test_when_used_then_hp_and_mp_are_restored(self):
        self._familiar.hp = 7
        self._familiar.max_hp = 10
        self._familiar.mp = 0
        self._familiar.max_mp = 15
        self._call_use()
        self.assertEqual(self._familiar.hp, 10)
        self.assertEqual(self._familiar.mp, 15)

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'Your HP and MP have been restored to max.')


class LightSeedTest(
        ItemTestBase,
        AlwaysUsableItemTester,
        FamiliarAndEnemyItemTester,
        NoDefaultTargetItemTester,
        HiddenMpRestoreItemTester):
    _ITEM_CLASS = LightSeed

    def test_when_used_on_familiar_then_familiar_genus_is_changed_to_fire(self):
        self._familiar.genus = Genus.Water
        self._use_on_familiar()
        self.assertEqual(self._familiar.genus, Genus.Fire)

    def test_when_used_on_enemy_then_enemy_genus_is_changed_to_fire(self):
        self._enemy.genus = Genus.Wind
        self._use_on_enemy()
        self.assertEqual(self._enemy.genus, Genus.Fire)

    def test_response_when_used_on_familiar(self):
        self.assertEqual(self._use_on_familiar(), 'Your genus changed to Fire.')

    def test_response_when_used_on_enemy(self):
        self.assertEqual(self._use_on_enemy(), 'Monster\'s genus changed to Fire.')


class SeaSeedTest(
        ItemTestBase,
        AlwaysUsableItemTester,
        FamiliarAndEnemyItemTester,
        NoDefaultTargetItemTester,
        HiddenMpRestoreItemTester):
    _ITEM_CLASS = SeaSeed

    def test_when_used_on_familiar_then_familiar_genus_is_changed_to_water(self):
        self._familiar.genus = Genus.Fire
        self._use_on_familiar()
        self.assertEqual(self._familiar.genus, Genus.Water)

    def test_when_used_on_enemy_then_enemy_genus_is_changed_to_water(self):
        self._enemy.genus = Genus.Wind
        self._use_on_enemy()
        self.assertEqual(self._enemy.genus, Genus.Water)

    def test_response_when_used_on_familiar(self):
        self.assertEqual(self._use_on_familiar(), 'Your genus changed to Water.')

    def test_response_when_used_on_enemy(self):
        self.assertEqual(self._use_on_enemy(), 'Monster\'s genus changed to Water.')


class WindSeedTest(
        ItemTestBase,
        AlwaysUsableItemTester,
        FamiliarAndEnemyItemTester,
        NoDefaultTargetItemTester,
        HiddenMpRestoreItemTester):
    _ITEM_CLASS = WindSeed

    def test_when_used_on_familiar_then_familiar_genus_is_changed_to_wind(self):
        self._familiar.genus = Genus.Fire
        self._use_on_familiar()
        self.assertEqual(self._familiar.genus, Genus.Wind)

    def test_when_used_on_enemy_then_enemy_genus_is_changed_to_wind(self):
        self._enemy.genus = Genus.Wind
        self._use_on_enemy()
        self.assertEqual(self._enemy.genus, Genus.Wind)

    def test_response_when_used_on_familiar(self):
        self.assertEqual(self._use_on_familiar(), 'Your genus changed to Wind.')

    def test_response_when_used_on_enemy(self):
        self.assertEqual(self._use_on_enemy(), 'Monster\'s genus changed to Wind.')


class AllItemsTest(unittest.TestCase):
    def test_all_items_returns_item_instances(self):
        for item in all_items():
            self.assertIsInstance(item, Item)

    def test_all_items_returns_all_the_items(self):
        import curry_quest.items

        def is_item(cls):
            if not inspect.isclass(cls):
                return False
            if not issubclass(cls, Item):
                return False
            return cls not in [
                Item,
                DefaultFamiliarTargetItem,
                DefaultEnemyTargetItem,
                NoDefaultTargetItem,
                FamiliarOnlyItem,
                EnemyOnlyItem,
                FamiliarAndEnemyItem,
                BattlePhaseOnlyItem]

        all_items_classes = set(item.__class__ for item in all_items())
        inspected_all_items = set(value for _, value in inspect.getmembers(curry_quest.items) if is_item(value))
        self.assertEqual(all_items_classes, inspected_all_items)


if __name__ == '__main__':
    unittest.main()
