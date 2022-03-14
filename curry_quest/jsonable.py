from abc import ABC, abstractmethod


class InvalidJson(Exception):
    pass


class Jsonable(ABC):
    @abstractmethod
    def to_json_object(self): pass

    @abstractmethod
    def from_json_object(self, json_object): pass


class JsonReaderHelper:
    def __init__(self, json_object):
        self._json_object = json_object
        if not isinstance(self._json_object, dict):
            self._raise_exception('Not a valid JSON.')

    def read_value(self, key):
        if key not in self._json_object:
            self._raise_exception(f'Key "{key}" does not exist.')
        return self._json_object[key]

    def read_bool(self, key):
        return self.read_value_of_type(key, bool)

    def read_int(self, key):
        return self.read_value_of_type(key, int)

    def read_int_with_min(self, key, min_value):
        value = self.read_int(key)
        if value < min_value:
            self._raise_exception(f'"{key}={value}" expected to be greater than {min_value}.')
        return value

    def read_int_in_range(self, key, min_value, max_value):
        value = self.read_int(key)
        if value < min_value or value > max_value:
            self._raise_exception(f'"{key}={value}" expected to be in range [{min_value}, {max_value}].')
        return value

    def read_float(self, key):
        return self.read_value_of_type(key, float)

    def read_string(self, key):
        return self.read_value_of_type(key, str)

    def read_non_empty_string(self, key):
        value = self.read_string(key).strip()
        if len(value) == 0:
            self._raise_exception(f'"{key}={value}" expected to be non-empty.')
        return value

    def read_enum(self, key, enum_type):
        value = self.read_int(key)
        try:
            return enum_type(value)
        except ValueError as exc:
            self._raise_exception(f'{key}={value}. {"".join(exc.args)}.')

    def read_list(self, key):
        return self.read_value_of_type(key, list)

    def read_dict(self, key):
        return self.read_value_of_type(key, dict)

    def read_value_of_type(self, key, value_type):
        value = self.read_value(key)
        if not isinstance(value, value_type):
            self._raise_exception(f'"{key}={value}" expected to be {value_type} but is {type(value)}.')
        return value

    def read_value_of_type_with_default(self, key, value_type, default):
        value = self._json_object.get(key, default)
        if not isinstance(value, value_type):
            self._raise_exception(f'"{key}={value}" expected to be {value_type} but is {type(value)}.')
        return value

    def read_optional_value_of_type(self, key, value_type):
        if key not in self._json_object:
            return None
        value = self.read_value(key)
        if value is None:
            return None
        return self.read_value_of_type(key, value_type)

    def _raise_exception(self, error_msg):
        raise InvalidJson(f'{error_msg} JSON object: {self._json_object}".')
