from datetime import datetime, timedelta
import unittest
from unittest.mock import Mock, PropertyMock, patch
from curry_quest import commands
from curry_quest.config import Config
from curry_quest.controller import Controller
from curry_quest.state_machine import StateMachine


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self._states_files_handler = Mock()
        self._states_files_handler.load = Mock(return_value={})
        self._hall_of_fame_handler = Mock()
        self._services = Mock()
        self._rng = Mock()
        self._services.rng = Mock(return_value=self._rng)
        self._timer_mock = Mock()
        self._services.timer = Mock(return_value=self._timer_mock)
        self._now_mock = Mock(return_value=datetime(year=2022, month=2, day=9, hour=10, minute=30, second=45))
        self._services.now = self._now_mock
        self._send_message = Mock()

    def _create_controller(self, game_config: Config=None):
        controller = Controller(
            game_config or self._config(),
            self._hall_of_fame_handler,
            self._states_files_handler,
            self._services)
        controller.set_response_event_handler(self._send_message)
        return controller

    def _config(self, event_interval=0):
        config = Config()
        config._timers.event_interval = event_interval
        config._player_selection_weights.with_penalty = 5
        config._player_selection_weights.without_penalty = 10
        return config

    def _timer_call_args(self):
        self._services.timer.assert_called_once()
        return self._services.timer.call_args.args

    def test_when_player_does_not_exist_then_add_player_adds_player_and_starts_the_game(self):
        with patch('curry_quest.controller.StateMachine') as StateMachineMock:
            controller = self._create_controller()
            state_machine_mock = StateMachineMock.return_value
            state_machine_mock.is_finished = Mock(return_value=False)
            controller.add_player(4, 'player')
            state_machine_mock.on_action.assert_called_once()
            action = state_machine_mock.on_action.call_args.args[0]
            self.assertEqual(action.command, 'started')

    def test_when_player_exists_then_add_player_is_ignored(self):
        state_machine_mock = Mock()
        self._states_files_handler.load = Mock(return_value={4: state_machine_mock})
        with patch('curry_quest.controller.StateMachine') as StateMachineMock:
            created_state_machine_mock = StateMachineMock.return_value
            controller = self._create_controller()
            controller.add_player(4, 'player')
            created_state_machine_mock.on_action.assert_not_called()
            self._send_message.assert_called_with('<@!4>: You already joined the Curry Quest.')

    def test_when_player_does_not_exist_then_remove_player_is_ignored(self):
        controller = self._create_controller()
        controller.remove_player(4)
        self._send_message.assert_called_with('<@!4>: You are not part of Curry Quest.')

    def test_when_player_exists_then_remove_player_removes_player_from_the_game(self):
        state_machine_mock = Mock()
        self._states_files_handler.load = Mock(return_value={4: state_machine_mock})
        controller = self._create_controller()
        controller.remove_player(4)
        self._send_message.assert_called_with('<@!4>: You were removed from Curry Quest.')
        controller.remove_player(4)
        self._send_message.assert_called_with('<@!4>: You are not part of Curry Quest.')

    def test_when_player_exists_then_remove_player_deletes_player_state_file(self):
        state_machine_mock = Mock()
        self._states_files_handler.load = Mock(return_value={4: state_machine_mock})
        controller = self._create_controller()
        controller.remove_player(4)
        self._states_files_handler.delete.assert_called_once_with(4)

    def test_when_event_timer_expires_it_is_restarted(self):
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        self._services.timer.reset_mock()
        timer_expiry_handler()
        self._services.timer.assert_called_once()

    def test_when_event_timer_interval_is_taken_from_config(self):
        controller = self._create_controller(game_config=self._config(event_interval=30))
        controller.start_timers()
        _, interval, _ = self._timer_call_args()
        self.assertEqual(interval, 30)

    def _state_machine_mock(
            self,
            player_name_mock=None,
            has_event_selection_penalty=False,
            is_finished=False,
            is_started=True,
            is_waiting_for_event=True,
            event_selection_penalty_end_dt=None):
        state_machine_mock = Mock(spec=StateMachine)
        type(state_machine_mock).player_name = player_name_mock or PropertyMock(return_value='')
        state_machine_mock.has_event_selection_penalty = Mock(return_value=has_event_selection_penalty)
        state_machine_mock.on_action = Mock(return_value=[])
        state_machine_mock.is_finished = Mock(return_value=is_finished)
        state_machine_mock.is_started = Mock(return_value=is_started)
        state_machine_mock.is_waiting_for_event = Mock(return_value=is_waiting_for_event)
        state_machine_mock.event_selection_penalty_end_dt = \
            event_selection_penalty_end_dt or self._now_mock.return_value

        def clear_event_selection_penalty():
            state_machine_mock.has_event_selection_penalty.return_value = False

        state_machine_mock.clear_event_selection_penalty = Mock(side_effect=clear_event_selection_penalty)
        return state_machine_mock

    def _assert_admin_on_action_call(self, state_machine_mock, command, *args):
        self._assert_on_action_call(state_machine_mock, command, args, is_given_by_admin=True)

    def _assert_user_on_action_call(self, state_machine_mock, command, *args):
        self._assert_on_action_call(state_machine_mock, command, args, is_given_by_admin=False)

    def _assert_on_action_call(self, state_machine_mock, command, args, is_given_by_admin):
        state_machine_mock.on_action.assert_called_once()
        action = state_machine_mock.on_action.call_args.args[0]
        self.assertEqual(action.command, command)
        self.assertEqual(action.args, args)
        self.assertEqual(action.is_given_by_admin, is_given_by_admin)

    def test_when_event_timer_expires_then_player_is_selected_for_the_event(self):
        players = {
            4: self._state_machine_mock(),
            7: self._state_machine_mock()
        }
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        self._rng.choices = Mock(return_value=(4,))
        timer_expiry_handler()
        self._assert_admin_on_action_call(players[4], commands.GENERATE_EVENT)
        players[7].on_action.assert_not_called()

    def test_only_players_who_are_not_in_an_event_are_eligible_to_be_selected_for_next_event(self):
        players = {
            4: self._state_machine_mock(is_waiting_for_event=False),
            7: self._state_machine_mock(is_waiting_for_event=True),
            8: self._state_machine_mock(is_waiting_for_event=False),
            12: self._state_machine_mock(is_waiting_for_event=True),
            18: self._state_machine_mock(is_waiting_for_event=False)
        }
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        self._rng.choices = Mock(return_value=(4,))
        timer_expiry_handler()
        self._rng.choices.assert_called_once()
        players = self._rng.choices.call_args.args[0]
        self.assertEqual(players, [7, 12])

    def test_players_are_selected_With_weights_based_on_selection_penalty(self):
        players = {
            4: self._state_machine_mock(has_event_selection_penalty=True),
            7: self._state_machine_mock(has_event_selection_penalty=True),
            8: self._state_machine_mock(has_event_selection_penalty=False),
            12: self._state_machine_mock(has_event_selection_penalty=True),
            18: self._state_machine_mock(has_event_selection_penalty=False)
        }
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        self._rng.choices = Mock(return_value=(4,))
        timer_expiry_handler()
        self._rng.choices.assert_called_once()
        players_weights = self._rng.choices.call_args.args[1]
        self.assertEqual(players_weights, [5, 5, 10, 5, 10])

    def test_player_whose_penalty_timer_is_up_has_penalty_flag_clearer(self):
        players = {
            4: self._state_machine_mock(
                has_event_selection_penalty=True,
                event_selection_penalty_end_dt=self._now_mock.return_value - timedelta(seconds=1))
        }
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        self._rng.choices = Mock(return_value=(4,))
        timer_expiry_handler()
        self._rng.choices.assert_called_once()
        players_weights = self._rng.choices.call_args.args[1]
        self.assertEqual(players_weights, [10])

    def test_when_there_is_no_eligible_players_then_timer_expiry_does_not_generate_actions(self):
        players = {
            4: self._state_machine_mock(is_waiting_for_event=False),
            7: self._state_machine_mock(is_waiting_for_event=False),
            8: self._state_machine_mock(is_waiting_for_event=False),
            12: self._state_machine_mock(is_waiting_for_event=False),
            18: self._state_machine_mock(is_waiting_for_event=False)
        }
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        timer_expiry_handler()
        players[4].on_action.assert_not_called()
        players[7].on_action.assert_not_called()
        players[8].on_action.assert_not_called()
        players[12].on_action.assert_not_called()
        players[18].on_action.assert_not_called()

    def test_when_selected_players_game_is_not_started_then_it_is_started(self):
        state_machine_mock = self._state_machine_mock(is_started=False)
        players = {4: state_machine_mock}
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.start_timers()
        _, _, timer_expiry_handler = self._timer_call_args()
        self._rng.choices = Mock(return_value=(4,))
        timer_expiry_handler()
        self._assert_admin_on_action_call(state_machine_mock, commands.STARTED)

    def test_when_handle_user_action_is_called_for_existing_player_then_it_is_handled(self):
        players = {4: self._state_machine_mock()}
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.handle_user_action(4, 'player', 'test_command', ('arg1', 'arg2'))
        self._assert_user_on_action_call(players[4], 'test_command', 'arg1', 'arg2')

    def test_when_handle_user_action_is_called_for_existing_player_then_player_name_is_updated(self):
        player_name_mock = PropertyMock(return_value='old player name')
        players = {4: self._state_machine_mock(player_name_mock=player_name_mock)}
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.handle_user_action(4, 'new player name', 'test_command', ())
        player_name_mock.assert_called_with('new player name')

    def test_when_handle_user_action_is_called_for_non_existing_player_then_it_is_not_handled(self):
        players = {4: self._state_machine_mock()}
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        controller.handle_user_action(5, 'player', 'test_command', ('arg1', 'arg2'))
        players[4].on_action.assert_not_called()

    def test_when_handle_admin_action_is_called_for_existing_player_then_it_is_handled(self):
        players = {4: self._state_machine_mock()}
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        self.assertTrue(controller.handle_admin_action(4, 'test_command', ('arg1', 'arg2')))
        self._assert_admin_on_action_call(players[4], 'test_command', 'arg1', 'arg2')

    def test_when_handle_admin_action_is_called_for_non_existing_player_then_it_is_not_handled(self):
        players = {4: self._state_machine_mock()}
        self._states_files_handler.load = Mock(return_value=players)
        controller = self._create_controller()
        self.assertFalse(controller.handle_admin_action(5, 'test_command', ('arg1', 'arg2')))
        players[4].on_action.assert_not_called()


if __name__ == '__main__':
    unittest.main()
