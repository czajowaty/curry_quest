import logging
from curry_quest.errors import InvalidOperation
from curry_quest.jsonable import Jsonable, JsonReaderHelper
from curry_quest.state_machine_context import StateMachineContext
from abc import abstractmethod

logger = logging.getLogger(__name__)


class StateBase(Jsonable):
    class ArgsParseError(Exception):
        pass

    class PreConditionsNotMet(Exception):
        pass

    def __init__(self, context: StateMachineContext):
        self._context = context

    def to_json_object(self):
        json_object = self._to_json_object()
        json_object['state_name'] = self.state_name()
        return json_object

    def _to_json_object(self):
        return {}

    @classmethod
    def state_name(cls):
        return cls.__name__

    def from_json_object(self, json_object):
        raise NotImplementedError(f'{self.__class__.__name__}.{self.from_json_object}')

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        return cls(context)

    @property
    def name(self):
        return self.__class__.__name__

    @property
    def game_config(self):
        return self._context.game_config

    @property
    def inventory(self):
        return self._context.inventory

    def on_enter(self):
        logger.debug(f"{self}.on_enter()")

    def is_waiting_for_user_action(self) -> bool:
        return False

    def is_waiting_for_event(self) -> bool:
        return False

    @classmethod
    def create(cls, context, args):
        try:
            parsed_args = cls._parse_args(context, args)
            cls._verify_preconditions(context, parsed_args)
        except cls.ArgsParseError as exc:
            raise InvalidOperation(str(exc))
        except cls.PreConditionsNotMet as exc:
            raise InvalidOperation(str(exc))
        return cls(context, *parsed_args)

    @classmethod
    def _parse_args(cls, context, args):
        return ()

    @classmethod
    def _verify_preconditions(cls, context, parsed_args):
        pass

    def __str__(self):
        return self.name
