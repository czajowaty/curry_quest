from curry_quest import commands
from curry_quest.jsonable import JsonReaderHelper
from curry_quest.state_base import StateBase
import logging

logger = logging.getLogger(__name__)


class StateWaitForEvent(StateBase):
    def __init__(self, context, event_command=None):
        super().__init__(context)
        self._event_command = event_command

    def _to_json_object(self):
        return {'event_command': self._event_command}

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        return cls.create(
            context,
            (json_reader_helper.read_optional_value_of_type('event_command', str),))

    def on_enter(self):
        if self._event_command is not None:
            self._context.generate_action(self._event_command)

    def is_waiting_for_event(self) -> bool:
        return True

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) == 0:
            return ()
        return args[0],


class StateGenerateEvent(StateBase):
    def on_enter(self):
        event = self._select_event()
        self._context.set_event_weight_penalty(event)
        self._context.generate_action(commands.EVENT_GENERATED, event)

    def _select_event(self):
        events_weights = self._context.events_weights
        if len(events_weights) > 0:
            return self._context.random_selection_with_weights(events_weights)
        else:
            commands.BATTLE_EVENT


class StateEventFinished(StateBase):
    def on_enter(self):
        self._context.increase_turns_counter()
        self._context.decrease_weight_penalty_timers()
        floor_collapsed = self._handle_earthquake()
        self._context.generate_action(commands.GO_UP if floor_collapsed else commands.EVENT_FINISHED)

    def _handle_earthquake(self):
        if self._context.is_earthquake_turn():
            self._context.add_response('Earthquake!!! You should probably hurry upstairs...')
        elif self._context.is_floor_collapse_turn():
            self._context.add_response('Whole floor is collapsing and you are teleported to next floor.')
            return True
        return False
