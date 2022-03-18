from curry_quest.jsonable import Jsonable, JsonReaderHelper


class Records(Jsonable):
    def __init__(self):
        self.turns_counter = 0
        self.used_elevators_counter = 0

    def to_json_object(self):
        return {
            'turns_counter': self.turns_counter,
            'used_elevators_counter': self.used_elevators_counter
        }

    def from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        self.turns_counter = json_reader_helper.read_value_of_type_with_default(
            'turns_counter',
            int,
            default=self.turns_counter)
        self.used_elevators_counter = json_reader_helper.read_value_of_type_with_default(
            'used_elevators_counter',
            int,
            default=self.used_elevators_counter)
