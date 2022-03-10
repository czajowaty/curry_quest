from abc import abstractmethod
import json


class JsonConfigParser:
    class InvalidConfig(Exception):
        pass

    def __init__(self, config_file, config_class):
        self._config_file = config_file
        self._config_class = config_class
        self._config = self._config_class()

    def parse(self):
        try:
            config_json_string = self._config_file.read()
            self._config_json = json.loads(config_json_string)
            self._config = self._config_class()
            self._parse()
        except json.JSONDecodeError as exc:
            self._invalid_config(f'Invalid JSON: {exc}')
        except KeyError as exc:
            self._invalid_config(f'Missing key: {exc}')
            raise self.InvalidConfig()
        self._validate_config()
        return self._config

    def _parse_key_as_int(self, key: str):
        try:
            return int(self._config_json[key])
        except ValueError as exc:
            self._invalid_config(f'{key}: {exc}')

    def _invalid_config(self, msg):
        raise self.InvalidConfig(msg)

    @abstractmethod
    def _parse(self): pass

    @abstractmethod
    def _validate_config(self): pass
