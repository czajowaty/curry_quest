import unittest
from unittest.mock import Mock
from curry_quest.hall_of_fame import HallsOfFameHandler, SmallestTurnsNumberRecord, LargestTurnsNumberRecord


class HallsOfFameHandlerTest(unittest.TestCase):
    def setUp(self):
        self._halls_fame_changed_handler = Mock()
        self._halls_of_fame_handler = self._create_halls_of_fame_handler()

    def _create_halls_of_fame_handler(self):
        return HallsOfFameHandler(self._halls_fame_changed_handler)

    def _call_to_string(self, hall_of_fame_name, limit=None):
        args = [hall_of_fame_name]
        if limit is not None:
            args.append(limit)
        return self._halls_of_fame_handler.to_string(*args).split('\n', maxsplit=1)

    def _test_to_string_header(self, hall_of_fame_name, expected_header):
        header, _ = self._call_to_string(hall_of_fame_name)
        self.assertEqual(header, expected_header)

    def _test_to_string_content(self, hall_of_fame_name, expected_content, limit=None):
        _, content = self._call_to_string(hall_of_fame_name, limit)
        self.assertEqual(content, expected_content)

    def _test_smallest_turns_number_hall_of_fame(self, hall_of_fame_name):
        self._halls_of_fame_handler.add(
            player_id=3,
            player_name='Player 1',
            hall_of_fame_name=hall_of_fame_name,
            record=SmallestTurnsNumberRecord(turns_number=4))
        self._halls_of_fame_handler.add(
            player_id=5,
            player_name='Player 9',
            hall_of_fame_name=hall_of_fame_name,
            record=SmallestTurnsNumberRecord(turns_number=7))
        json_object = self._halls_of_fame_handler.to_json_object()
        loaded_halls_of_fame_handler = self._create_halls_of_fame_handler()
        loaded_halls_of_fame_handler.from_json_object(json_object)
        self._test_to_string_content(hall_of_fame_name, '1. Player 1 - 4 turns\n2. Player 9 - 7 turns')

    def test_json_for_ANY_PERCENT(self):
        self._test_smallest_turns_number_hall_of_fame(HallsOfFameHandler.ANY_PERCENT)

    def test_json_for_EQ_PERCENT(self):
        self._test_smallest_turns_number_hall_of_fame(HallsOfFameHandler.EQ_PERCENT)

    def test_heade_for_ANY_PERCENT(self):
        self._test_to_string_header(HallsOfFameHandler.ANY_PERCENT, '"any%" Hall of Fame')

    def test_heade_for_EQ_PERCENT(self):
        self._test_to_string_header(HallsOfFameHandler.EQ_PERCENT, '"eq%" Hall of Fame')

    def _add_record(self, **kwargs):
        if 'hall_of_fame_name' not in kwargs:
            kwargs['hall_of_fame_name'] = HallsOfFameHandler.ANY_PERCENT
        self._halls_of_fame_handler.add(**kwargs)

    def _test_hall_of_fame(self, expected_content, hall_of_fame_name=HallsOfFameHandler.ANY_PERCENT, limit=None):
        self._test_to_string_content(hall_of_fame_name, expected_content, limit)

    def test_when_no_records_are_added_then_hall_of_fame_is_empty(self):
        self._test_hall_of_fame(expected_content='Empty')

    def test_order_is_based_on_record_order(self):
        self._add_record(player_id=6, player_name='Player 8', record=SmallestTurnsNumberRecord(7))
        self._add_record(player_id=2, player_name='Player 3', record=SmallestTurnsNumberRecord(5))
        self._test_hall_of_fame(expected_content='1. Player 3 - 5 turns\n2. Player 8 - 7 turns')

    def test_when_two_records_with_same_value_are_added_then_order_is_based_on_addition_order(self):
        self._add_record(player_id=6, player_name='Player 8', record=SmallestTurnsNumberRecord(5))
        self._add_record(player_id=2, player_name='Player 3', record=SmallestTurnsNumberRecord(5))
        self._test_hall_of_fame('1. Player 8 - 5 turns\n2. Player 3 - 5 turns')

    def test_by_default_only_5_top_records_are_shown(self):
        for i in range(10, 0, -1):
            self._add_record(player_id=i, player_name=f'Player {i}', record=SmallestTurnsNumberRecord(i))
        self._test_hall_of_fame(
            '1. Player 1 - 1 turn\n'
            '2. Player 2 - 2 turns\n'
            '3. Player 3 - 3 turns\n'
            '4. Player 4 - 4 turns\n'
            '5. Player 5 - 5 turns')

    def test_limit_decides_how_many_top_records_are_shown(self):
        for i in range(10, 0, -1):
            self._add_record(player_id=i, player_name=f'Player {i}', record=SmallestTurnsNumberRecord(i))
        self._test_hall_of_fame(
            '1. Player 1 - 1 turn\n'
            '2. Player 2 - 2 turns\n'
            '3. Player 3 - 3 turns\n'
            '4. Player 4 - 4 turns\n'
            '5. Player 5 - 5 turns\n'
            '6. Player 6 - 6 turns\n'
            '7. Player 7 - 7 turns\n'
            '8. Player 8 - 8 turns\n'
            '9. Player 9 - 9 turns\n'
            '10. Player 10 - 10 turns',
            limit=15)

    def test_when_invalid_record_type_is_added_then_exception_is_raised(self):
        with self.assertRaises(TypeError):
            self._add_record(player_id=1, player_name='Player 1', record=LargestTurnsNumberRecord(7))

    def test_after_every_entry_addition_changed_handler_is_called(self):
        self._add_record(player_id=6, player_name='Player 8', record=SmallestTurnsNumberRecord(5))
        self._halls_fame_changed_handler.assert_called_once()
        self._halls_fame_changed_handler.reset_mock()
        self._add_record(player_id=7, player_name='Player 6', record=SmallestTurnsNumberRecord(8))
        self._halls_fame_changed_handler.assert_called_once()

    def test_when_hall_of_fame_is_unknown_for_addition_then_exception_is_raised(self):
        with self.assertRaises(ValueError):
            self._halls_of_fame_handler.add(
                player_id=1,
                player_name='Player 1',
                hall_of_fame_name='some hall of fame',
                record=SmallestTurnsNumberRecord(7))

    def test_when_hall_of_fame_is_unknown_for_to_string_then_exception_is_raised(self):
        with self.assertRaises(ValueError):
            self._halls_of_fame_handler.to_string(hall_of_fame_name='some hall of fame')


if __name__ == '__main__':
    unittest.main()
