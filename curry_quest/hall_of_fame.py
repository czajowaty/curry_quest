from abc import abstractmethod, ABC
from curry_quest.jsonable import Jsonable, JsonReaderHelper, InvalidJson
import json
import logging

logger = logging.getLogger(__name__)


class HallOfFameRecord(Jsonable, ABC):
    @abstractmethod
    def to_string(self): pass

    @abstractmethod
    def is_before(self, other): pass


class TurnsNumberRecord(HallOfFameRecord):
    def __init__(self, turns_number: int=0):
        self._turns_number = turns_number

    def to_json_object(self):
        return self._turns_number

    def from_json_object(self, json_object):
        if not isinstance(json_object, int):
            raise InvalidJson(f'"{json_object}" is not valid record value for {self.__class__.__name__}.')
        self._turns_number = json_object

    def to_string(self):
        s = f'{self._turns_number} turn'
        if self._turns_number > 1:
            s += 's'
        return s


class SmallestTurnsNumberRecord(TurnsNumberRecord):
    def is_before(self, other):
        return self._turns_number < other._turns_number


class LargestTurnsNumberRecord(TurnsNumberRecord):
    def is_before(self, other):
        return self._turns_number > other._turns_number


class HallOfFame:
    class Entry:
        def __init__(self, player_id: int, player_name: str, record: HallOfFameRecord):
            self.player_id = player_id
            self.player_name = player_name
            self.record = record

        def is_before(self, other):
            return self.record.is_before(other.record)

        def to_string(self):
            return f'{self.player_name} - {self.record.to_string()}'

    def __init__(self, name, record_type):
        self._name = name
        self._record_type = record_type
        self._entries = []

    def to_json_object(self):
        return [self._entry_to_json(entry) for entry in self._entries]

    def _entry_to_json(self, entry):
        return {
            'player_id': entry.player_id,
            'player_name': entry.player_name,
            'record': entry.record.to_json_object()
        }

    def from_json_object(self, json_object):
        self._entries.clear()
        for entry_json_object in json_object:
            self._entries.append(self._entry_from_json(entry_json_object))

    def _entry_from_json(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        record = self._record_type()
        record.from_json_object(json_reader_helper.read_value('record'))
        return self.Entry(
            json_reader_helper.read_int('player_id'),
            json_reader_helper.read_non_empty_string('player_name'),
            record)

    def clear(self):
        return self._entries

    def add(self, entry: Entry):
        if not isinstance(entry.record, self._record_type):
            raise TypeError(f'Record has {type(entry.record)} type, but expecting {self._record_type}.')
        index = self._find_add_entry_index(entry)
        self._entries.insert(index, entry)

    def _find_add_entry_index(self, entry: Entry):
        start_index = 0
        end_index = len(self._entries)
        index = start_index
        while start_index < end_index:
            index = start_index + (end_index - start_index) // 2
            if entry.is_before(self._entries[index]):
                end_index = index
            else:
                index = index + 1
                start_index = index
        return index

    def to_string(self, limit=5):
        return f'"{self._name}" Hall of Fame\n{self._entries_to_string(limit)}'

    def _entries_to_string(self, limit):
        if len(self._entries) == 0:
            return 'Empty'
        return '\n'.join(
            f'{position}. {entry.to_string()}'
            for position, entry
            in enumerate(self._entries[:limit], start=1))


class HallsOfFameHandler(Jsonable):
    ANY_PERCENT = 'any%'
    EQ_PERCENT = 'eq%'
    ALL_HALLS_OF_FAME = {
        SmallestTurnsNumberRecord: [ANY_PERCENT, EQ_PERCENT]
    }

    def __init__(self, halls_of_fame_changed_handler):
        self._halls_of_fame_changed_handler = halls_of_fame_changed_handler
        self._halls_of_fame: dict[str, HallOfFame] = {}
        for record_type, halls_of_fame_names in self.ALL_HALLS_OF_FAME.items():
            for hall_of_fame_name in halls_of_fame_names:
                self._halls_of_fame[hall_of_fame_name] = HallOfFame(hall_of_fame_name, record_type)

    @property
    def halls_of_fame_names(self):
        return list(self._halls_of_fame.keys())

    def to_json_object(self):
        return dict((name, hall_of_fame.to_json_object()) for name, hall_of_fame in self._halls_of_fame.items())

    def from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        for hall_of_fame_name, hall_of_fame in self._halls_of_fame.items():
            hall_of_fame.clear()
            hall_of_fame_json_object = json_reader_helper.read_value_of_type_with_default(
                hall_of_fame_name,
                list,
                default=[])
            hall_of_fame.from_json_object(hall_of_fame_json_object)

    def add(self, player_id: int, player_name: str, hall_of_fame_name: str, record: HallOfFameRecord):
        logger.info(
            f"Adding new record '{record.to_string()}' to '{hall_of_fame_name}' for '{player_name}' (ID: {player_id}).")
        hall_of_fame = self._halls_of_fame.get(hall_of_fame_name)
        if hall_of_fame is None:
            self._raise_unknown_hall_of_fame_exception(hall_of_fame_name)
        hall_of_fame.add(HallOfFame.Entry(player_id, player_name, record))
        self._halls_of_fame_changed_handler(self)

    def to_string(self, hall_of_fame_name: str, limit: int=5):
        hall_of_fame = self._halls_of_fame.get(hall_of_fame_name)
        if hall_of_fame is None:
            self._raise_unknown_hall_of_fame_exception(hall_of_fame_name)
        return hall_of_fame.to_string(limit)

    def _raise_unknown_hall_of_fame_exception(self, hall_of_fame_name: str):
        self._raise_exception(f'Hall of fame with name "{hall_of_fame_name}" does not exist.')

    def _raise_exception(self, error_message):
        raise ValueError(error_message)

    @classmethod
    def from_file(cls, halls_of_fame_file_path):
        def _save_halls_of_fame(halls_of_fame_handler):
            logger.info(f"Saving Halls of Fame to '{halls_of_fame_file_path}' file.")
            try:
                with open(halls_of_fame_file_path, 'w') as f:
                    f.write(json.dumps(halls_of_fame_handler.to_json_object(), indent=2))
                logger.info(f"Halls of Fame saved to '{halls_of_fame_file_path}' file.")
            except IOError as exc:
                logger.warning(f"Could not save Halls of Fame. {exc}.")

        halls_of_fame_handler = HallsOfFameHandler(_save_halls_of_fame)
        logger.info(f"Loading Halls of Fame from '{halls_of_fame_file_path}' file.")
        try:
            with open(halls_of_fame_file_path, 'r') as f:
                halls_of_fame_handler.from_json_object(json.load(f))
        except FileNotFoundError:
            logger.info(f"Halls of fame file does not exist. Creating empty one.")
            _save_halls_of_fame(halls_of_fame_handler)
        except (IOError, json.JSONDecodeError) as exc:
            logger.info(f"Could not load Halls of Fame. {exc.__class__.__name__}: {exc}.")
        except InvalidJson as exc:
            logger.warning(f"Could not load Halls of Fame. {exc}")
        return halls_of_fame_handler
