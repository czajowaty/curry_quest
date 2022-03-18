import asyncio
from curry_quest import commands
from curry_quest.config import Config
from curry_quest.hall_of_fame import HallsOfFameHandler, SmallestTurnsNumberRecord
from curry_quest.records import Records
from curry_quest.records_events_handler import RecordsEventsHandler
from curry_quest.services import Services
from curry_quest.state_machine import StateMachine, StateMachineContext
from curry_quest.state_machine_action import StateMachineAction
from curry_quest.states_files_handler import StateFilesHandler
import discord_helpers
import logging
from typing import Callable

logger = logging.getLogger(__name__)


class Controller:
    class PlayerDoesNotExist(Exception):
        def __init__(self, player_id: int):
            super().__init__()
            self.player_id = player_id

    class NoPlayerForEvent(Exception):
        pass

    class PlayerRecordsEventsHandler(RecordsEventsHandler):
        def __init__(self, player_state_machine: StateMachine, halls_of_fame_handler: HallsOfFameHandler):
            self._player_state_machine = player_state_machine
            self._halls_of_fame_handler = halls_of_fame_handler

        def handle_tower_clear(self, records: Records):
            self._add_to_halls_of_fame(
                HallsOfFameHandler.ANY_PERCENT,
                SmallestTurnsNumberRecord(records.turns_counter))
            if records.used_elevators_counter == 0:
                self._add_to_halls_of_fame(
                    HallsOfFameHandler.EQ_PERCENT,
                    SmallestTurnsNumberRecord(records.turns_counter))

        def _add_to_halls_of_fame(self, hall_of_fame_name, record):
            self._halls_of_fame_handler.add(
                self._player_state_machine.player_id,
                self._player_state_machine.player_name,
                hall_of_fame_name,
                record)

    def __init__(
            self,
            game_config: Config,
            halls_of_fame_handler: HallsOfFameHandler,
            states_files_handler: StateFilesHandler,
            services: Services=None):
        self._game_config = game_config
        self._halls_of_fame_handler = halls_of_fame_handler
        self._states_files_handler = states_files_handler
        self._services = services or Services()
        self._rng = self._services.rng()
        self._event_timer: asyncio.Task = None
        self.set_response_event_handler(lambda _: None)
        self._player_state_machines: dict[int, StateMachine] = self._states_files_handler.load(self._game_config)
        for player_state_machine in self._player_state_machines.values():
            self._set_records_events_handler(player_state_machine)

    def _set_records_events_handler(self, player_state_machine: StateMachine):
        player_state_machine.set_records_events_handler(
            self.PlayerRecordsEventsHandler(player_state_machine, self._halls_of_fame_handler))

    @property
    def _event_interval(self) -> Config.Timers:
        return self._game_config.timers.event_interval

    def set_response_event_handler(self, handler: Callable[[str], bool]):
        self._response_event_handler = handler

    def _send_response(self, player_id: int, responses: list[str]):
        for response_string in self._response_string_generator(responses):
            self._response_event_handler(f"{discord_helpers.user_mention(player_id)}: {response_string}")

    def _response_string_generator(self, responses: list[str]):
        def responses_group_to_string(responses_group: list[str]):
            return '\n'.join(responses_group)

        responses_group = []
        for response in responses:
            if response == StateMachineContext.RESPONSE_LINE_BREAK:
                if len(responses_group) > 0:
                    yield responses_group_to_string(responses_group)
                responses_group = []
            else:
                responses_group.append(response)
        if len(responses_group) > 0:
            yield responses_group_to_string(responses_group)

    def handle_user_action(self, player_id: int, player_name: str, command: str, args: tuple):
        self._handle_action(player_id, self._user_action(command, args), player_name)

    def _user_action(self, command: str, args: tuple=()) -> StateMachineAction:
        return StateMachineAction(command, args)

    def handle_admin_action(self, player_id: int, command: str, args: str):
        if not self._does_player_exist(player_id):
            return False
        self._handle_action(player_id, self._admin_action(command, args))
        return True

    def _admin_action(self, command: str, args: tuple=()) -> StateMachineAction:
        return StateMachineAction(command, args, is_given_by_admin=True)

    def _handle_action(self, player_id: int, action: StateMachineAction, player_name: str=None):
        if self._handle_generic_command(player_id, action):
            return
        if not self._does_player_exist(player_id):
            return
        player_state_machine = self._player_state_machine(player_id)
        if player_name is not None:
            player_state_machine.player_name = player_name
        responses = player_state_machine.on_action(action)
        if len(responses) > 0:
            self._send_response(player_id, responses)
        self._save_player_state(player_id)

    def _handle_generic_command(self, player_id: int, action: StateMachineAction):
        command = action.command
        if command == commands.HALL_OF_FAME:
            self._handle_hall_of_fame_command(player_id, action.args)
            return True
        return False

    def _handle_hall_of_fame_command(self, player_id, args):
        if len(args) == 0:
            self._send_invalid_hall_of_fame_command_response(player_id, f'Use "!hall_of_fame **NAME**".')
            return
        hall_of_fame_name = args[0]
        try:
            self._response_event_handler(self._halls_of_fame_handler.to_string(hall_of_fame_name))
        except ValueError:
            self._send_invalid_hall_of_fame_command_response(
                player_id,
                f'Hall of Fame with name "{hall_of_fame_name}" does not exist.')

    def _send_invalid_hall_of_fame_command_response(self, player_id, message):
        halls_of_fame_names = ', '.join(
            f'"{hall_of_fame_name}"'
            for hall_of_fame_name
            in self._halls_of_fame_handler.halls_of_fame_names)
        self._send_response(
            player_id,
            [f'{message}\nAvailable Halls of Fame: {halls_of_fame_names}.'])

    def _save_player_state(self, player_id: int):
        self._states_files_handler.save(self._player_state_machine(player_id))

    def _player_state_machine(self, player_id: int) -> StateMachine:
        if not self._does_player_exist(player_id):
            raise self.PlayerDoesNotExist(player_id)
        return self._player_state_machines[player_id]

    def _does_player_exist(self, player_id: int) -> bool:
        return player_id in self._player_state_machines

    def add_player(self, player_id: int, player_name: str):
        if self._does_player_exist(player_id):
            self._send_response(player_id, ["You already joined the Curry Quest."])
            return
        state_machine = StateMachine(self._game_config, player_id, player_name)
        self._set_records_events_handler(state_machine)
        self._player_state_machines[player_id] = state_machine
        self._handle_action(player_id, self._admin_action(commands.STARTED))

    def _is_game_started(self, player_id: int) -> bool:
        return self._does_player_exist(player_id) and self._player_state_machine(player_id).is_started()

    def remove_player(self, player_id: int):
        if not self._does_player_exist(player_id):
            self._send_response(player_id, ["You are not part of Curry Quest."])
            return
        del self._player_state_machines[player_id]
        self._states_files_handler.delete(player_id)
        self._send_response(player_id, ["You were removed from Curry Quest."])

    def start_timers(self):
        self._start_event_timer()

    def _stop_timers(self):
        self._cancel_timer(self._event_timer)

    def _start_event_timer(self):
        self._cancel_timer(self._event_timer)
        self._event_timer = self._services.timer('Event', self._event_interval, self._handle_event_timer_expiry)

    def _cancel_timer(self, timer: asyncio.Task):
        if timer is not None and not timer.done():
            timer.cancel()

    def _handle_event_timer_expiry(self):
        self._event_timer = None
        logger.info(f"Event timer expired")
        self._start_event_timer()
        try:
            player_id = self._select_player_for_event()
        except self.NoPlayerForEvent:
            logger.info(f"No eligible players for event.")
            return
        event_command = commands.GENERATE_EVENT if self._is_game_started(player_id) else commands.STARTED
        self._handle_action(player_id, self._admin_action(event_command))

    def _select_player_for_event(self) -> int:
        eligible_players = self._event_eligible_players()
        if len(eligible_players) == 0:
            raise self.NoPlayerForEvent()
        players_weights = [self._player_event_weight(player_name) for player_name in eligible_players]
        return self._rng.choices(eligible_players, players_weights)[0]

    def _event_eligible_players(self) -> list[str]:
        def is_event_eligible_player(player_id: int) -> bool:
            return self._is_player_waiting_for_event(player_id)

        return list(filter(is_event_eligible_player, self._player_state_machines.keys()))

    def _is_player_waiting_for_event(self, player_id) -> bool:
        return self._player_state_machine(player_id).is_waiting_for_event()

    def _player_event_weight(self, player_id: int) -> int:
        self._update_event_selection_penalty(player_id)
        state_machine = self._player_state_machine(player_id)
        player_selection_weights = self._game_config.player_selection_weights
        if state_machine.has_event_selection_penalty():
            return player_selection_weights.with_penalty
        else:
            return player_selection_weights.without_penalty

    def _update_event_selection_penalty(self, player_id):
        state_machine = self._player_state_machine(player_id)
        if not state_machine.has_event_selection_penalty():
            return
        if self._services.now() > state_machine.event_selection_penalty_end_dt:
            state_machine.clear_event_selection_penalty()
