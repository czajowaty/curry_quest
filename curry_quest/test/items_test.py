import unittest
from unittest.mock import create_autospec, PropertyMock
from curry_quest.genus import Genus
from curry_quest.items import Item, BattlePhaseOnlyItem, Pita, Oleem, HolyScroll, MedicinalHerb, CureAllHerb, \
    FireBall, WaterCrystal, LightSeed, SeaSeed, WindSeed, all_items
from curry_quest.levels_config import Levels
from curry_quest.state_machine_context import StateMachineContext, BattleContext
from curry_quest.statuses import Statuses
from curry_quest.unit import Unit
from curry_quest.unit_traits import UnitTraits
import inspect


class ItemTestBase(unittest.TestCase):
    _ITEM_CLASS = None

    def setUp(self):
        self._sut = self._ITEM_CLASS()
        self._familiar = Unit(UnitTraits(), Levels())
        self._battle_context = create_autospec(spec=BattleContext)
        self._context = create_autospec(spec=StateMachineContext)
        type(self._context).battle_context = PropertyMock(return_value=self._battle_context)
        type(self._context).familiar = PropertyMock(return_value=self._familiar)

    def _call_can_use(self):
        return self._sut.can_use(self._context)

    def _test_can_use_response(self, expected_response):
        _, response = self._call_can_use()
        self.assertEqual(response, expected_response)

    def _test_can_use(self, expected_can_use):
        can_use, _ = self._call_can_use()
        self.assertEqual(can_use, expected_can_use)

    def _call_use(self):
        self._set_can_use()
        response = self._sut.use(self._context)
        expected_prefix = f'You used the {self._sut.name}. '
        suffix_index = len(expected_prefix)
        self.assertEqual(response[:suffix_index], expected_prefix)
        return response[suffix_index:]


class PitaTest(ItemTestBase):
    _ITEM_CLASS = Pita

    def setUp(self):
        super().setUp()
        self._familiar.max_mp = 20

    def _set_can_use(self):
        self._familiar.mp = self._familiar.max_mp - 1

    def _set_cannot_use(self):
        self._familiar.mp = self._familiar.max_mp

    def test_when_mp_is_at_max_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('Your MP is already at max.')

    def test_when_mp_is_at_not_max_then_can_use(self):
        self._set_can_use()
        self._test_can_use(expected_can_use=True)

    def test_when_used_then_mp_is_restored(self):
        self._call_use()
        self.assertTrue(self._context.familiar.is_mp_at_max())

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'Your MP has been restored to max.')


class BattlePhaseOnlyItemTester:
    def _set_not_in_battle(self):
        self._context.is_in_battle.return_value = False

    def test_when_not_in_battle_then_cannot_use(self):
        self._set_not_in_battle()
        self._test_can_use(expected_can_use=False)

    def test_response_when_not_in_battle(self):
        self._set_not_in_battle()
        self._test_can_use_response('You are not in combat.')

    def _set_in_battle_prepare_phase(self):
        self._context.is_in_battle.return_value = True
        self._battle_context.is_prepare_phase.return_value = True

    def test_when_in_battle_prepare_phase_then_cannot_use(self):
        self._set_in_battle_prepare_phase()
        self._test_can_use(expected_can_use=False)

    def test_response_when_in_battle_prepare_phase(self):
        self._set_in_battle_prepare_phase()
        self._test_can_use_response('Combat has not started yet.')

    def _set_can_use(self):
        self._context.is_in_battle.return_value = True
        self._battle_context.is_prepare_phase.return_value = False

    def test_when_after_battle_prepare_phase_then_can_use(self):
        self._set_can_use()
        self._test_can_use(expected_can_use=True)


class OleemTest(ItemTestBase, BattlePhaseOnlyItemTester):
    _ITEM_CLASS = Oleem

    def test_when_used_then_battle_is_finished(self):
        self._call_use()
        self._battle_context.finish_battle.assert_called_once()

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'The enemy vanished!')


class HolyScrollTest(ItemTestBase, BattlePhaseOnlyItemTester):
    _ITEM_CLASS = HolyScroll

    def test_when_used_then_holy_scroll_counter_is_set(self):
        self._call_use()
        self._battle_context.set_holy_scroll_counter.assert_called_once_with(3)

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'You are invulnerable for the next 3 turns.')


class MedicinalHerbTest(ItemTestBase):
    _ITEM_CLASS = MedicinalHerb

    def setUp(self):
        super().setUp()
        self._familiar.max_hp = 10

    def _set_can_use(self):
        self._familiar.hp = self._familiar.max_hp - 1

    def _set_cannot_use(self):
        self._familiar.hp = self._familiar.max_hp

    def test_when_hp_is_at_max_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('Your HP is already at max.')

    def test_when_hp_is_at_not_max_then_can_use(self):
        self._set_can_use()
        self._test_can_use(expected_can_use=True)

    def test_when_used_then_hp_is_restored(self):
        self._call_use()
        self.assertTrue(self._context.familiar.is_hp_at_max())

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'Your HP has been restored to max.')


class CureAllHerbTest(ItemTestBase):
    _ITEM_CLASS = CureAllHerb

    def _set_can_use(self):
        self._familiar.set_status(Statuses.Poison)

    def _set_cannot_use(self):
        self._familiar.clear_statuses()

    def test_when_familiar_has_no_statuses_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('You do not have any statuses.')

    def test_when_familiar_has_statuses_then_can_use(self):
        self._set_can_use()
        self._test_can_use(expected_can_use=True)

    def test_when_used_then_statuses_are_cleared(self):
        self._call_use()
        self.assertFalse(self._context.familiar.has_any_status())

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'All statuses have been restored.')


class FireBallTest(ItemTestBase, BattlePhaseOnlyItemTester):
    _ITEM_CLASS = FireBall

    def setUp(self):
        super().setUp()
        self._enemy = Unit(UnitTraits(), Levels())
        type(self._battle_context).enemy = PropertyMock(return_value=self._enemy)

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


class WaterCrystalTest(ItemTestBase):
    _ITEM_CLASS = WaterCrystal

    def setUp(self):
        super().setUp()
        self._familiar.max_hp = 10
        self._familiar.max_mp = 15

    def _set_can_use(self):
        self._set_not_max_hp()
        self._set_not_max_mp()

    def _set_not_max_hp(self):
        self._familiar.hp = self._familiar.max_hp - 1

    def _set_not_max_mp(self):
        self._familiar.mp = self._familiar.max_mp - 1

    def _set_cannot_use(self):
        self._set_max_hp()
        self._set_max_mp()

    def _set_max_hp(self):
        self._familiar.hp = self._familiar.max_hp

    def _set_max_mp(self):
        self._familiar.mp = self._familiar.max_mp

    def test_when_hp_and_mp_is_at_max_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_when_hp_is_at_max_but_mp_is_not_then_can_use(self):
        self._set_max_hp()
        self._set_not_max_mp()
        self._test_can_use(expected_can_use=True)

    def test_when_mp_is_at_max_but_hp_is_not_then_can_use(self):
        self._set_not_max_hp()
        self._set_max_mp()
        self._test_can_use(expected_can_use=True)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('Your HP and MP are already at max.')

    def test_when_hp_is_at_not_max_then_can_use(self):
        self._set_can_use()
        self._test_can_use(expected_can_use=True)

    def test_when_used_then_hp_is_restored(self):
        self._call_use()
        self.assertTrue(self._context.familiar.is_hp_at_max())
        self.assertTrue(self._context.familiar.is_mp_at_max())

    def test_response_when_used(self):
        self.assertEqual(self._call_use(), 'Your HP and MP have been restored to max.')


class LightSeedTest(ItemTestBase):
    _ITEM_CLASS = LightSeed

    def _set_can_use(self):
        self._familiar.genus = Genus.Water

    def _set_cannot_use(self):
        self._familiar.genus = Genus.Fire

    def test_when_familiar_is_fire_genus_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_when_familiar_is_water_genus_then_can_use(self):
        self._familiar.genus = Genus.Water
        self._test_can_use(expected_can_use=True)

    def test_when_familiar_is_wind_genus_then_can_use(self):
        self._familiar.genus = Genus.Wind
        self._test_can_use(expected_can_use=True)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('Your genus is already Fire.')

    def test_when_used_then_genus_is_changed_to_fire(self):
        self._set_can_use()
        self._call_use()
        self.assertEqual(self._familiar.genus, Genus.Fire)


class SeaSeedTest(ItemTestBase):
    _ITEM_CLASS = SeaSeed

    def _set_can_use(self):
        self._familiar.genus = Genus.Fire

    def _set_cannot_use(self):
        self._familiar.genus = Genus.Water

    def test_when_familiar_is_water_genus_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_when_familiar_is_fire_genus_then_can_use(self):
        self._familiar.genus = Genus.Fire
        self._test_can_use(expected_can_use=True)

    def test_when_familiar_is_wind_genus_then_can_use(self):
        self._familiar.genus = Genus.Wind
        self._test_can_use(expected_can_use=True)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('Your genus is already Water.')

    def test_when_used_then_genus_is_changed_to_water(self):
        self._set_can_use()
        self._call_use()
        self.assertEqual(self._familiar.genus, Genus.Water)


class WindSeedTest(ItemTestBase):
    _ITEM_CLASS = WindSeed

    def _set_can_use(self):
        self._familiar.genus = Genus.Fire

    def _set_cannot_use(self):
        self._familiar.genus = Genus.Wind

    def test_when_familiar_is_wind_genus_then_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use(expected_can_use=False)

    def test_when_familiar_is_fire_genus_then_can_use(self):
        self._familiar.genus = Genus.Fire
        self._test_can_use(expected_can_use=True)

    def test_when_familiar_is_water_genus_then_can_use(self):
        self._familiar.genus = Genus.Water
        self._test_can_use(expected_can_use=True)

    def test_response_when_cannot_use(self):
        self._set_cannot_use()
        self._test_can_use_response('Your genus is already Wind.')

    def test_when_used_then_genus_is_changed_to_water(self):
        self._set_can_use()
        self._call_use()
        self.assertEqual(self._familiar.genus, Genus.Wind)


class AllItemsTest(unittest.TestCase):
    def test_all_items_returns_item_instances(self):
        for item in all_items():
            self.assertIsInstance(item, Item)

    def test_all_items_returns_all_the_items(self):
        import curry_quest.items

        all_items_classes = set(item.__class__ for item in all_items())
        inspected_all_items = set(
            value
            for _, value
            in inspect.getmembers(curry_quest.items)
            if inspect.isclass(value) and issubclass(value, Item) and value not in [Item, BattlePhaseOnlyItem]
        )
        self.assertEqual(all_items_classes, inspected_all_items)


if __name__ == '__main__':
    unittest.main()
