from curry_quest.errors import InvalidOperation
from curry_quest.items import normalize_item_name
from curry_quest.jsonable import JsonReaderHelper
from curry_quest.state_base import StateBase
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.unit import Unit


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


class StateWithInventoryItemAndTarget(StateWithInventoryItem):
    FAMILIAR_TARGET_STRING = 'familiar'
    ENEMY_TARGET_STRING = 'enemy'

    def __init__(self, context, item_index: int, target: Unit):
        super().__init__(context, item_index)
        self._target = target

    def _to_json_object(self):
        json_object = super()._to_json_object()
        if self._target is not None:
            json_object['target'] = self._target_string()
        return json_object

    def _target_string(self):
        if self._target is self._context.familiar:
            return self.FAMILIAR_TARGET_STRING
        if self._context.is_in_battle() and self._target is self._context.battle_context.enemy:
            return self.ENEMY_TARGET_STRING
        raise InvalidOperation('Target is neither familiar or enemy.')

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        target_string = json_reader_helper.read_optional_value_of_type('target', value_type=str)
        try:
            target = cls._target_string_to_target(context, target_string)
        except ValueError:
            json_reader_helper.raise_exception(f'Unexpected target "{target_string}".')
        return cls(
            context,
            json_reader_helper.read_int_in_range('item_index', min_value=0, max_value=context.inventory.size),
            target)

    @classmethod
    def _target_string_to_target(cls, context: StateMachineContext, target_string: str):
        if target_string is None:
            return None
        if target_string == cls.FAMILIAR_TARGET_STRING:
            return context.familiar
        if target_string == cls.ENEMY_TARGET_STRING:
            if not context.is_in_battle():
                raise ValueError()
            return context.battle_context.enemy
        raise ValueError()

    @classmethod
    def _parse_args(cls, context, args):
        target, args = cls._process_args_for_target(context, args)
        parsed_args = super()._parse_args(context, args)
        return parsed_args + (target,)

    @classmethod
    def _process_args_for_target(cls, context: StateMachineContext, args):
        if len(args) >= 2:
            target = cls._parse_target_indicator(context, args[0], args[1])
            if target is not None:
                return target, args[2:]
            target = cls._parse_target_indicator(context, args[-2], args[-1])
            if target is not None:
                return target, args[:-2]
        return None, args

    @classmethod
    def _parse_target_indicator(cls, context: StateMachineContext, arg_1, arg_2):
        if arg_1.lower() != 'on':
            return None
        if arg_2.lower() == 'self':
            return context._familiar
        if context.is_in_battle() and arg_2.lower() == 'enemy':
            return context._battle_context.enemy
        return None
