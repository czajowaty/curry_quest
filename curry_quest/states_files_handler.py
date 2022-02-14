from curry_quest.state_machine import StateMachine
import logging
import os.path

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
                state_machine.save(player_state_file)
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
        player_id_string, file_extension = os.path.splitext(state_file_name)
        if file_extension != STATE_FILE_SUFFIX:
            logger.debug(f"Non-json file trying to be loaded - {state_file_path}.")
            return
        try:
            player_id = int(player_id_string)
        except ValueError:
            logger.debug(f"State file name is not player id - {state_file_path}.")
            return
        try:
            with open(state_file_path, mode='r') as state_file:
                state_machine = StateMachine.load(state_file, self._game_config)
                logger.info(f"Loaded '{player_id}'s' state.")
                return state_machine
        except IOError as exc:
            logger.error(f"Error while loading '{player_id}'s' state. Reason - {exc}.")
