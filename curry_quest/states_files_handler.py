from curry_quest.state_machine import StateMachine
import json
import logging
import os.path
from curry_quest.jsonable import InvalidJson

logger = logging.getLogger(__name__)
STATE_FILE_SUFFIX = '.json'


class StateFilesHandler:
    def __init__(self, state_files_directory: str):
        self._state_files_directory = state_files_directory

    def load(self, game_config):
        return StateFilesLoader(self._state_files_directory, game_config).load()

    def save(self, state_machine: StateMachine):
        player_id = state_machine.player_id
        logger.debug(f"Saving state for '{player_id}'.")
        try:
            with open(self._player_state_file_path(player_id), mode='w') as player_state_file:
                player_state_file.write(json.dumps(state_machine.to_json_object(), indent=2))
        except IOError as exc:
            logger.error(f"Could not save state file for '{player_id}'. Reason - {exc}.")

    def delete(self, player_id: int):
        logger.debug(f"Removing state for '{player_id}'.")
        try:
            os.remove(self._player_state_file_path(player_id))
        except (IOError, FileNotFoundError) as exc:
            logger.error(f"Could not delete state file for '{player_id}'. Reason - {exc}.")

    def _player_state_file_path(self, player_id: int) -> str:
        return os.path.join(self._state_files_directory, self._player_state_file_name(player_id))

    def _player_state_file_name(self, player_id: int) -> str:
        return str(player_id) + STATE_FILE_SUFFIX


class StateFilesLoader:
    def __init__(self, state_files_directory: str, game_config):
        self._game_config = game_config
        self._state_files_directory = state_files_directory
        self._state_machines = {}

    def load(self) -> dict[str, StateMachine]:
        for file_name in os.listdir(self._state_files_directory):
            file_path = os.path.join(self._state_files_directory, file_name)
            if os.path.isfile(file_path):
                self._load_state_file(file_path)
        return self._state_machines

    def _load_state_file(self, state_file_path: str):
        _, state_file_name = os.path.split(state_file_path)
        _, file_extension = os.path.splitext(state_file_name)
        if file_extension != STATE_FILE_SUFFIX:
            logger.debug(f"Non-json file trying to be loaded - {state_file_path}.")
            return
        try:
            with open(state_file_path, mode='r') as state_file:
                state_json_object = json.load(state_file)
                player_id = StateMachine.player_id_from_json_object(state_json_object)
                state_machine = StateMachine(self._game_config, player_id, player_name='')
                state_machine.from_json_object(state_json_object)
                self._state_machines[player_id] = state_machine
                logger.info(f"Loaded '{player_id}'s' state.")
        except (IOError, json.JSONDecodeError, InvalidJson) as exc:
            logger.error(f"Error while loading '{state_file_name}' state file. Reason - {exc}.")
