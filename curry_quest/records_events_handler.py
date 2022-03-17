from abc import ABC, abstractmethod
from curry_quest.records import Records


class RecordsEventsHandler(ABC):
    @abstractmethod
    def handle_tower_clear(self, records: Records): pass


class EmptyRecordsEventsHandler(RecordsEventsHandler):
    def handle_tower_clear(self, records: Records):
        pass
