import unittest
from unittest.mock import Mock
from curry_quest.hall_of_fame import HallsOfFameHandler, SmallestTurnsNumberRecord, LargestTurnsNumberRecord


class HallsOfFameHandlerTest(unittest.TestCase):
    def setUp(self):
        self._halls_fame_changed_handler = Mock()
        self._halls_of_fame_handler = self._create_halls_of_fame_handler()

    def _create_halls_of_fame_handler(self):
        return HallsOfFameHandler(self._halls_fame_changed_handler)

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
        self.assertEqual(
            loaded_halls_of_fame_handler.to_string(hall_of_fame_name),
            f'"{hall_of_fame_name}" Hall of Fame\n'
            '1. Player 1 - 4 turns\n'
            '2. Player 9 - 7 turns')

    def test_json_for_TOWER_1_CLEAR(self):
        self._test_smallest_turns_number_hall_of_fame(HallsOfFameHandler.TOWER_1_CLEAR)

    def test_json_for_TOWER_1_EQ_CLEAR(self):
        self._test_smallest_turns_number_hall_of_fame(HallsOfFameHandler.TOWER_1_EQ_CLEAR)

    def test_when_no_records_are_added_then_hall_of_fame_is_empty(self):
        self.assertEqual(
            self._halls_of_fame_handler.to_string(HallsOfFameHandler.TOWER_1_CLEAR),
            '"Tower clear" Hall of Fame\nEmpty')

    def test_order_is_based_on_record_order(self):
        self._halls_of_fame_handler.add(
            player_id=6,
            player_name='Player 8',
            hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
            record=SmallestTurnsNumberRecord(7))
        self._halls_of_fame_handler.add(
            player_id=2,
            player_name='Player 3',
            hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
            record=SmallestTurnsNumberRecord(5))
        self.assertEqual(
            self._halls_of_fame_handler.to_string(HallsOfFameHandler.TOWER_1_CLEAR),
            '"Tower clear" Hall of Fame\n'
            '1. Player 3 - 5 turns\n'
            '2. Player 8 - 7 turns')

    def test_when_two_records_with_same_value_are_added_then_order_is_based_on_addition_order(self):
        self._halls_of_fame_handler.add(
            player_id=6,
            player_name='Player 8',
            hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
            record=SmallestTurnsNumberRecord(5))
        self._halls_of_fame_handler.add(
            player_id=2,
            player_name='Player 3',
            hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
            record=SmallestTurnsNumberRecord(5))
        self.assertEqual(
            self._halls_of_fame_handler.to_string(HallsOfFameHandler.TOWER_1_CLEAR),
            '"Tower clear" Hall of Fame\n'
            '1. Player 8 - 5 turns\n'
            '2. Player 3 - 5 turns')

    def test_by_default_only_5_top_records_are_shown(self):
        for i in range(10, 0, -1):
            self._halls_of_fame_handler.add(
                player_id=i,
                player_name=f'Player {i}',
                hall_of_fame_name=HallsOfFameHandler.TOWER_1_EQ_CLEAR,
                record=SmallestTurnsNumberRecord(i))
        self.assertEqual(
            self._halls_of_fame_handler.to_string(HallsOfFameHandler.TOWER_1_EQ_CLEAR),
            '"Tower 1 EQ clear" Hall of Fame\n'
            '1. Player 1 - 1 turn\n'
            '2. Player 2 - 2 turns\n'
            '3. Player 3 - 3 turns\n'
            '4. Player 4 - 4 turns\n'
            '5. Player 5 - 5 turns')

    def test_limit_decides_how_many_top_records_are_shown(self):
        for i in range(10, 0, -1):
            self._halls_of_fame_handler.add(
                player_id=i,
                player_name=f'Player {i}',
                hall_of_fame_name=HallsOfFameHandler.TOWER_1_EQ_CLEAR,
                record=SmallestTurnsNumberRecord(i))
        self.assertEqual(
            self._halls_of_fame_handler.to_string(HallsOfFameHandler.TOWER_1_EQ_CLEAR, limit=15),
            '"Tower 1 EQ clear" Hall of Fame\n'
            '1. Player 1 - 1 turn\n'
            '2. Player 2 - 2 turns\n'
            '3. Player 3 - 3 turns\n'
            '4. Player 4 - 4 turns\n'
            '5. Player 5 - 5 turns\n'
            '6. Player 6 - 6 turns\n'
            '7. Player 7 - 7 turns\n'
            '8. Player 8 - 8 turns\n'
            '9. Player 9 - 9 turns\n'
            '10. Player 10 - 10 turns')

    def test_when_invalid_record_type_is_added_then_exception_is_raised(self):
        with self.assertRaises(TypeError):
            self._halls_of_fame_handler.add(
                player_id=1,
                player_name='Player 1',
                hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
                record=LargestTurnsNumberRecord(7))

    def test_after_every_entry_addition_changed_handler_is_called(self):
        self._halls_of_fame_handler.add(
            player_id=6,
            player_name='Player 8',
            hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
            record=SmallestTurnsNumberRecord(5))
        self._halls_fame_changed_handler.assert_called_once()
        self._halls_fame_changed_handler.reset_mock()
        self._halls_of_fame_handler.add(
            player_id=7,
            player_name='Player 6',
            hall_of_fame_name=HallsOfFameHandler.TOWER_1_CLEAR,
            record=SmallestTurnsNumberRecord(8))
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
