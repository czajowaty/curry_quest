import unittest
from unittest.mock import create_autospec, PropertyMock
from curry_quest.config import Config
from curry_quest.item_use_unit_action import ItemUseActionHandler
from curry_quest.items import Item
from curry_quest.levels_config import Levels
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit_traits import UnitTraits
from curry_quest.state_machine_context import StateMachineContext


class ItemUseActionHandlerTest(unittest.TestCase):
    class DummyItem(Item):
        @classmethod
        @property
        def name(cls) -> str:
            return ''

        @classmethod
        def select_target(cls, familiar, enemy): pass

        @classmethod
        def can_target_familiar(cls) -> bool: pass

        @classmethod
        def can_target_enemy(cls) -> bool: pass

    def setUp(self):
        self._item_mock = create_autospec(spec=self.DummyItem)
        self._sut = ItemUseActionHandler(self._item_mock)
        self._familiar = Unit(UnitTraits(), Levels())
        self._enemy = Unit(UnitTraits(), Levels())
        self._unit_action_context = UnitActionContext()
        self._unit_action_context.performer = self._familiar
        self._state_machine_context = StateMachineContext(Config())
        self._unit_action_context.state_machine_context = self._state_machine_context

    def _call_select_target(self):
        return self._sut.select_target(self._familiar, self._enemy)

    def _set_select_target_return_value(self, unit):
        self._item_mock.select_target.return_value = unit

    def test_when_item_select_target_returns_familiar_then_select_target_returns_familiar(self):
        self._set_select_target_return_value(self._familiar)
        self.assertIs(self._call_select_target(), self._familiar)

    def test_when_item_select_target_returns_enemy_then_select_target_returns_enemy(self):
        self._set_select_target_return_value(self._familiar)
        self.assertIs(self._call_select_target(), self._familiar)

    def test_when_item_select_target_returns_no_target_then_select_target_returns_no_target(self):
        self._set_select_target_return_value(None)
        self.assertIsNone(self._call_select_target())

    def test_item_select_target_call_args(self):
        self._call_select_target()
        self._item_mock.select_target.assert_called_with(self._familiar, self._enemy)

    def _call_can_target_self(self):
        return self._sut.can_target_self()

    def _set_can_target_familiar_return_value(self, return_value):
        self._item_mock.can_target_familiar.return_value = return_value

    def test_when_item_can_target_familiar_then_can_target_self_returns_true(self):
        self._set_can_target_familiar_return_value(return_value=True)
        self.assertTrue(self._call_can_target_self())

    def test_when_item_cannot_target_familiar_then_can_target_self_returns_false(self):
        self._set_can_target_familiar_return_value(return_value=False)
        self.assertFalse(self._call_can_target_self())

    def _call_can_target_other_unit(self):
        return self._sut.can_target_other_unit()

    def _set_can_target_enemy_return_value(self, return_value):
        self._item_mock.can_target_enemy.return_value = return_value

    def test_when_item_can_target_enemy_then_can_target_other_unit_returns_true(self):
        self._set_can_target_enemy_return_value(return_value=True)
        self.assertTrue(self._call_can_target_other_unit())

    def test_when_item_cannot_target_enemy_then_can_target_other_unit_returns_false(self):
        self._set_can_target_enemy_return_value(return_value=False)
        self.assertFalse(self._call_can_target_other_unit())

    def test_can_have_no_target_returns_false(self):
        self.assertFalse(self._sut.can_have_no_target())

    def _call_can_perform(self):
        return self._sut.can_perform(self._unit_action_context)

    def _set_can_use_item(self):
        self._item_mock.cannot_use_reason.return_value = ''

    def test_when_item_cannot_use_reason_is_empty_then_can_perform_returns_false(self):
        self._set_can_use_item()
        self.assertEqual(self._call_can_perform(), (True, ''))

    def _set_cannot_use_item(self, reason='Reason'):
        self._item_mock.cannot_use_reason.return_value = reason

    def test_when_item_cannot_use_reason_is_not_empty_then_can_perform_returns_true_with_reason(self):
        self._set_cannot_use_item('Cannot use reason')
        self.assertEqual(self._call_can_perform(), (False, 'Cannot use reason'))

    def test_item_cannot_use_reason_is_called_with_proper_context(self):
        self._call_can_perform()
        self._item_mock.cannot_use_reason.assert_called_with(self._unit_action_context)

    def _call_perform(self):
        return self._sut.perform(self._unit_action_context)

    def test_when_item_can_be_used_then_perform_uses_item_with_proper_context(self):
        self._set_can_use_item()
        self._call_perform()
        self._item_mock.use.assert_called_once_with(self._unit_action_context)

    def test_when_item_cannot_be_used_then_perform_does_not_use_item(self):
        self._set_cannot_use_item()
        self._call_perform()
        self._item_mock.use.assert_not_called()

    def test_item_use_response(self):
        self._set_can_use_item()
        type(self._item_mock).name = PropertyMock(return_value='ITEM')
        self._item_mock.use.return_value = 'Item use response.'
        self.assertEqual(self._call_perform(), 'You used the ITEM. Item use response.')

    def test_response_when_cannot_use_item(self):
        self._set_cannot_use_item()
        type(self._item_mock).name = PropertyMock(return_value='ITEM')
        self.assertEqual(self._call_perform(), 'You used the ITEM. It has no effect.')


if __name__ == '__main__':
    unittest.main()
