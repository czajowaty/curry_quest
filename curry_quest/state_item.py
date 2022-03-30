from curry_quest import commands
from curry_quest.item_use_unit_action import ItemUseActionHandler
from curry_quest.items import Item, normalize_item_name, all_items
from curry_quest.jsonable import JsonReaderHelper
from curry_quest.state_base import StateBase
from curry_quest.state_with_inventory_item import StateWithInventoryItem
from curry_quest.unit_action import UnitActionContext


class StateItemEvent(StateBase):
    def __init__(self, context, item: Item=None):
        super().__init__(context)
        self._item = item

    def _to_json_object(self):
        return {'item_name': None if self._item is None else self._item.name}

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        item_name = json_reader_helper.read_optional_value_of_type('item_name', str)
        return cls.create(context, () if item_name is None else (item_name,))

    def on_enter(self):
        item = self._select_item()
        self._context.buffer_item(item)
        self._context.add_response(f"You come across a {item.name}. Do you want to pick it up?")

    def _select_item(self):
        return self._item or self._context.random_selection_with_weights(self._found_items_weights())

    def _found_items_weights(self):
        return dict((item, self.game_config.found_items_weights[item.name]) for item in all_items())

    def is_waiting_for_user_action(self) -> bool:
        return True

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) == 0:
            return ()
        item_name = normalize_item_name(*args)
        for item in all_items():
            if normalize_item_name(item.name).startswith(item_name):
                return item,
        raise cls.ArgsParseError('Unknown item')


class StateItemPickUp(StateBase):
    def on_enter(self):
        if not self.inventory.is_full():
            item = self._context.take_buffered_item()
            self.inventory.add_item(item)
            self._context.add_response(f"You take the {item.name} with you.")
            self._context.generate_action(commands.ITEM_PICKED_UP)
        else:
            self._context.generate_action(commands.FULL_INVENTORY)


class StateItemPickUpFullInventory(StateBase):
    def on_enter(self):
            items = ', '.join(self.inventory.items)
            found_item_name = self._context.peek_buffered_item().name
            self._context.add_response(
                f"Your inventory is full. You need to drop/use one of your current items first. "
                f"You can also use found {found_item_name} or ignore it. You have: {items}.")

    def is_waiting_for_user_action(self) -> bool:
        return True


class StateItemUse(StateBase):
    class CannotUseItem(Exception):
        pass

    def __init__(self, context, *item_name_parts):
        super().__init__(context)
        self._item_name = normalize_item_name(*item_name_parts)

    def on_enter(self):
        try:
            item, remove_item, next_command = self._select_item_descriptor()
            action_handler, action_context = self._create_item_use_action(item)
        except self.CannotUseItem as exc:
            self._context.add_response(f"{exc}")
            self._context.generate_action(commands.CANNOT_USE_ITEM)
            return
        response = action_handler.perform(action_context)
        self._context.add_response(response)
        remove_item()
        self._context.generate_action(next_command)

    def _select_item_descriptor(self):
        item_descriptor = self._found_item_descriptor()
        if item_descriptor is None:
            item_descriptor = self._inventory_item_descriptor()
        if item_descriptor is None:
            raise self.CannotUseItem('You do not have such item in your inventory and it is not found item.')
        return item_descriptor

    def _create_item_use_action(self, item) -> tuple[ItemUseActionHandler, UnitActionContext]:
        def raise_cannot_use_item(reason):
            raise self.CannotUseItem(f'Cannot use {item.name}. {reason}')

        if not item.can_target_familiar():
            raise_cannot_use_item('No valid target.')
        action_handler, action_context = self._context.create_item_use_with_target(item, target=None)
        action_context.target = self._context.familiar
        can_use, reason = action_handler.can_perform(action_context)
        if not can_use:
            raise_cannot_use_item(reason)
        return action_handler, action_context

    def _found_item_descriptor(self):
        item = self._context.peek_buffered_item()
        if item.matches_normalized_name(self._item_name):
            return item, lambda: self._context.take_buffered_item(), commands.FOUND_ITEM_USED
        else:
            return None

    def _inventory_item_descriptor(self):
        try:
            index, item = self._context.inventory.find_item(self._item_name)
            return item, lambda: self._context.inventory.take_item(index), commands.INVENTORY_ITEM_USED
        except ValueError:
            return None

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) < 1:
            raise cls.ArgsParseError('You need to specify item.')
        return args


class StateItemPickUpAfterDrop(StateWithInventoryItem):
    def on_enter(self):
        dropped_item = self.inventory.take_item(self._item_index)
        picked_up_item = self._context.take_buffered_item()
        self.inventory.add_item(picked_up_item)
        self._context.add_response(f"You drop a {dropped_item.name} and take a {picked_up_item.name} instead.")
        self._context.generate_action(commands.ITEM_PICKED_UP)


class StateItemPickUpIgnored(StateBase):
    def on_enter(self):
        item = self._context.take_buffered_item()
        self._context.add_response(f"You leave the {item.name} on the ground and leave.")
        self._context.generate_action(commands.EVENT_FINISHED)


class StateItemEventFinished(StateBase):
    def on_enter(self):
        self._context.clear_item_buffer()
        self._context.generate_action(commands.EVENT_FINISHED)
