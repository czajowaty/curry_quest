from curry_quest.items import normalize_item_name
from curry_quest.state_base import StateBase
from curry_quest.jsonable import JsonReaderHelper


class StateWithInventoryItem(StateBase):
    def __init__(self, context, item_index: int):
        super().__init__(context)
        self._item_index = item_index

    def _to_json_object(self):
        return {'item_index': self._item_index}

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        return cls(
            context,
            json_reader_helper.read_int_in_range('item_index', min_value=0, max_value=context.inventory.size))

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) < 1:
            raise cls.ArgsParseError('You need to specify item.')
        item_name = normalize_item_name(*args)
        try:
            index, _ = context.inventory.find_item(item_name)
        except ValueError:
            raise cls.ArgsParseError(f'You do not have "{item_name}" in your inventory.')
        return (index,)
