from curry_quest import commands
from curry_quest.items import Item
from curry_quest.state_item import StateItemUse
from curry_quest.unit import Unit
from dummy_item import DummyItem
from state_test_base import StateTestBase
import unittest
from unittest.mock import PropertyMock, create_autospec


class StateItemUseTest(StateTestBase):
    @classmethod
    def _state_class(cls):
        return StateItemUse

    def setUp(self):
        super().setUp()

    def _test_on_enter(self, *args):
        if args == ():
            args = ('',)
        super()._test_on_enter(*args)

    def _create_matched_item(self, can_use, item_name='', item_use_response=''):
        return self._create_item_mock(
            can_use,
            does_name_match=True,
            item_name=item_name,
            item_use_response=item_use_response)

    def _create_non_matched_item(self, item_name=''):
        return self._create_item_mock(can_use=False, does_name_match=False, item_name=item_name)

    def _create_usable_item(self, item_name='', item_use_response=''):
        return self._create_item_mock(
            can_use=True,
            does_name_match=True,
            item_name=item_name,
            item_use_response=item_use_response)

    def _create_unusable_item(self, item_name='', cannot_use_reason='REASON'):
        item = self._create_item_mock(can_use=False, does_name_match=True, item_name=item_name)
        item.cannot_use_reason.return_value = cannot_use_reason
        return item

    def _create_item_mock(self, can_use, does_name_match, item_name='', item_use_response=''):
        item = create_autospec(spec=DummyItem)
        type(item).name = PropertyMock(return_value=item_name)
        item.matches_normalized_name.return_value = does_name_match
        item.matches_name.return_value = does_name_match
        item.cannot_use_reason.return_value = '' if can_use else 'REASON'
        item.use.return_value = item_use_response
        return item

    def _set_found_item(self, item):
        self._context.buffer_item(item)

    def _add_inventory_item(self, item):
        self._context.inventory.add_item(item)

    def _clear_inventory(self):
        self._context.inventory.clear()

    def _test_found_item_used(self, item_name='', item_use_response='') -> Item:
        item = self._create_usable_item(item_name=item_name, item_use_response=item_use_response)
        item.matches_normalized_name.return_value = True
        self._test_found_item_matched(item)
        self.assertIsNone(self._context.peek_buffered_item())

    def _test_found_item_matched(self, item):
        self._set_found_item(item)
        self._test_on_enter()

    def test_action_when_found_item_used(self):
        self._test_found_item_used()
        self._assert_action(commands.FOUND_ITEM_USED)

    def test_response_when_found_item_used(self):
        self._test_found_item_used(item_name='ITEM_NAME', item_use_response='FOUND ITEM USED.')
        self._assert_responses('You used the ITEM_NAME. FOUND ITEM USED.')

    def _assert_item_name_match(self, item: Item, expected_name):
        item.matches_normalized_name.assert_called_with(expected_name)

    def _test_inventory_item_used(self, item_name='', item_use_response=''):
        self._set_found_item(self._create_non_matched_item())
        inventory_item = self._create_matched_item(
            can_use=True,
            item_name=item_name,
            item_use_response=item_use_response)
        self._test_inventory_item_matched(inventory_item, item_name)
        self.assertTrue(self._context.inventory.is_empty())

    def _test_inventory_item_matched(self, item, item_name):
        self._clear_inventory()
        self._add_inventory_item(item)
        self._test_on_enter(item_name if item_name else 'ITEM')

    def test_action_when_inventory_item_used(self):
        self._test_inventory_item_used()
        self._assert_action(commands.INVENTORY_ITEM_USED)

    def test_response_when_inventory_item_used(self):
        self._test_inventory_item_used(item_name='INVENTORY_ITEM', item_use_response='INVENTORY ITEM USED.')
        self._assert_responses('You used the INVENTORY_ITEM. INVENTORY ITEM USED.')

    def _test_no_items_match(self):
        self._set_found_item(self._create_non_matched_item())
        self._add_inventory_item(self._create_non_matched_item())
        self._test_on_enter()

    def test_action_when_no_items_match(self):
        self._test_no_items_match()
        self._assert_action(commands.CANNOT_USE_ITEM)

    def test_response_when_no_items_match(self):
        self._test_no_items_match()
        self._assert_responses('You do not have such item in your inventory and it is not found item.')

    def test_items_are_searched_by_correct_name(self):
        found_item = self._create_non_matched_item()
        self._set_found_item(found_item)
        inventory_item_1 = self._create_non_matched_item()
        inventory_item_2 = self._create_non_matched_item()
        self._add_inventory_item(inventory_item_1)
        self._add_inventory_item(inventory_item_2)
        self._test_on_enter('SEARCHED ', ' ITEM')
        self._assert_item_name_match(found_item, expected_name='searcheditem')
        self._assert_item_name_match(inventory_item_1, expected_name='searcheditem')
        self._assert_item_name_match(inventory_item_2, expected_name='searcheditem')

    def _test_found_item_cannot_be_used(self, item_name='', cannot_use_reason='REASON'):
        item = self._create_unusable_item(item_name, cannot_use_reason)
        self._test_found_item_matched(item)
        self.assertIs(self._context.peek_buffered_item(), item)

    def test_action_when_found_item_cannot_be_used(self):
        self._test_found_item_cannot_be_used()
        self._assert_action(commands.CANNOT_USE_ITEM)

    def test_response_when_found_item_cannot_be_used(self):
        self._test_found_item_cannot_be_used(item_name='FOUND ITEM', cannot_use_reason='REASON.')
        self._assert_responses('Cannot use FOUND ITEM. REASON.')

    def _test_inventory_item_cannot_be_used(self, item_name='', cannot_use_reason='REASON'):
        self._set_found_item(self._create_non_matched_item())
        inventory_item = self._create_unusable_item(item_name, cannot_use_reason)
        self._test_inventory_item_matched(inventory_item, item_name)
        self.assertEqual(self._context.inventory.size, 1)
        self.assertEqual(self._context.inventory.peek_item(0), inventory_item)

    def test_action_when_inventory_item_cannot_be_used(self):
        self._test_inventory_item_cannot_be_used()
        self._assert_action(commands.CANNOT_USE_ITEM)

    def test_response_when_inventory_item_cannot_be_used(self):
        self._test_inventory_item_cannot_be_used(item_name='INVENTORY ITEM', cannot_use_reason='REASON.')
        self._assert_responses('Cannot use INVENTORY ITEM. REASON.')

    def _set_item_target(self, item: Item, target: Unit):
        item.select_target.return_value = target

    def test_item_select_target_args(self):
        item = self._create_usable_item()
        self._test_found_item_matched(item)
        item.select_target.assert_called_with(self._familiar, None)

    def test_item_use_context(self):
        item = self._create_usable_item()
        self._set_item_target(item, target=self._familiar)
        self._test_found_item_matched(item)
        item.use.assert_called_once()
        action_context = item.use.call_args.args[0]
        self.assertIs(action_context.performer, self._familiar)
        self.assertIs(action_context.target, self._familiar)
        self.assertIs(action_context.state_machine_context, self._context)

    def _test_item_has_no_target(self, item_name=''):
        item = self._create_usable_item(item_name=item_name)
        item.can_target_familiar.return_value = False
        self._test_found_item_matched(item)

    def test_action_when_item_has_no_target(self):
        self._test_item_has_no_target()
        self._assert_action(commands.CANNOT_USE_ITEM)

    def test_response_when_item_has_no_target(self):
        self._test_item_has_no_target(item_name='ITEM')
        self._assert_responses('Cannot use ITEM. No valid target.')


if __name__ == '__main__':
    unittest.main()
