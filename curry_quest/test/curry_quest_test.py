from curry_quest.config import Config
from curry_quest.controller import Controller
from curry_quest.curry_quest import CurryQuest
import unittest
from unittest.mock import create_autospec, Mock


class Dummy:
    pass


class MessageBuilder:
    class DummyMessage:
        def __init__(self):
            self.author = Dummy()
            self.author.id = 0
            self.content = ''
            self.channel = Dummy()
            self.channel.id = 0

    def __init__(self):
        self._message = self.DummyMessage()

    def set_author(self, author):
        self._message.author.id = author
        return self

    def set_content(self, content):
        self._message.content = content
        return self

    def set_channel(self, channel_id):
        self._message.channel.id = channel_id
        return self

    def build(self):
        return self._message


class CurryQuestTest(unittest.TestCase):
    def _create_curry_quest(self, controller=None, config=None):
        return CurryQuest(controller or self._create_controller(), config or self._config())

    def _create_controller(self, *args, **kwargs):
        return create_autospec(Controller, *args, **kwargs)

    def _config(self, channel_id=0, admin_channel_id=0, admins=[]):
        config = Config()
        config._channel_id = channel_id
        config._admin_channel_id = admin_channel_id
        config._admins = admins
        return config

    def _start_curry_quest(self, curry_quest: CurryQuest, message_sender=None, admin_message_sender=None):
        curry_quest.start(message_sender or Mock(), admin_message_sender or Mock())

    def _message(self, author='', content='', channel_id=0):
        return MessageBuilder().set_author(author).set_content(content).set_channel(channel_id).build()

    def test_start_passes_send_message_function_to_controller(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(controller=controller)
        send_message_function = object()
        curry_quest.start(send_message_function, None)
        controller.set_response_event_handler.assert_called_once_with(send_message_function)

    def test_start_starts_timers_in_controller(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(controller=controller)
        curry_quest.start(None, None)
        controller.start_timers.assert_called_once()

    def test_is_curry_quest_message_returns_true_for_message_from_curry_quest_channel(self):
        curry_quest = self._create_curry_quest(config=self._config(channel_id=5, admin_channel_id=7))
        self.assertTrue(curry_quest.is_curry_quest_message(self._message(channel_id=5)))

    def test_is_curry_quest_message_returns_true_for_message_from_curry_quest_admin_channel(self):
        curry_quest = self._create_curry_quest(config=self._config(channel_id=5, admin_channel_id=7))
        self.assertTrue(curry_quest.is_curry_quest_message(self._message(channel_id=7)))

    def test_is_curry_quest_message_returns_false_for_message_from_other_channels(self):
        curry_quest = self._create_curry_quest(config=self._config(channel_id=5, admin_channel_id=7))
        self.assertFalse(curry_quest.is_curry_quest_message(self._message(channel_id=6)))

    def test_when_message_does_not_start_with_prefix_it_is_ignored(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(controller=controller)
        curry_quest.process_message(self._message(content='join'))
        controller.add_player.assert_not_called()
        controller.remove_player.assert_not_called()
        controller.handle_user_action.assert_not_called()
        controller.handle_admin_action.assert_not_called()

    def test_when_join_command_is_given_then_add_player_is_called(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(controller=controller, config=self._config(channel_id=8))
        curry_quest.process_message(self._message(author=3, content='!join', channel_id=8))
        controller.add_player.assert_called_once_with(3)

    def test_when_leave_command_is_given_then_remove_player_is_called(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(controller=controller, config=self._config(channel_id=8))
        curry_quest.process_message(self._message(author=3, content='!leave', channel_id=8))
        controller.remove_player.assert_called_once_with(3)

    def test_when_other_command_is_given_then_handle_user_action_is_called(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(controller=controller, config=self._config(channel_id=8))
        curry_quest.process_message(self._message(author=3, content='!use_item Medicinal Herb', channel_id=8))
        controller.handle_user_action.assert_called_once_with(3, 'use_item', ['Medicinal', 'Herb'])

    def test_when_admin_gives_command_in_non_admin_channel_then_it_is_handled_as_user_action(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(
            controller=controller,
            config=self._config(channel_id=5, admin_channel_id=9, admins=[3]))
        curry_quest.process_message(self._message(author=3, content='!use_item Medicinal Herb', channel_id=8))
        controller.handle_user_action.assert_called_once_with(3, 'use_item', ['Medicinal', 'Herb'])

    def test_when_admin_gives_command_in_admin_channel_then_it_is_handled_as_admin_action(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(
            controller=controller,
            config=self._config(channel_id=5, admin_channel_id=9, admins=[3]))
        curry_quest.process_message(self._message(author=3, content='!use_item <@!5> Medicinal Herb', channel_id=9))
        controller.handle_admin_action.assert_called_once_with(5, 'use_item', ['Medicinal', 'Herb'])

    def test_when_admin_command_does_not_have_target_player_id_then_it_is_not_handled(self):
        controller = self._create_controller()
        curry_quest = self._create_curry_quest(
            controller=controller,
            config=self._config(channel_id=5, admin_channel_id=9, admins=[3]))
        send_message = Mock()
        self._start_curry_quest(curry_quest, admin_message_sender=send_message)
        curry_quest.process_message(self._message(author=3, content='!use_item Medicinal Herb', channel_id=9))
        send_message.assert_called_once_with('<@!3>: Command is missing target player id.')

    def test_when_admin_command_is_handled_then_proper_message_is_sent_to_admin_channel(self):
        controller = self._create_controller()
        controller.handle_admin_action = Mock(return_value=True)
        curry_quest = self._create_curry_quest(
            controller=controller,
            config=self._config(channel_id=5, admin_channel_id=9, admins=[3]))
        send_message = Mock()
        self._start_curry_quest(curry_quest, admin_message_sender=send_message)
        curry_quest.process_message(self._message(author=3, content='!use_item <@!6> Medicinal Herb', channel_id=9))
        send_message.assert_called_once_with('<@!3>: Admin command handled.')

    def test_when_admin_command_is_not_handled_then_proper_message_is_sent_to_admin_channel(self):
        controller = self._create_controller()
        controller.handle_admin_action = Mock(return_value=False)
        curry_quest = self._create_curry_quest(
            controller=controller,
            config=self._config(channel_id=5, admin_channel_id=9, admins=[3]))
        send_message = Mock()
        self._start_curry_quest(curry_quest, admin_message_sender=send_message)
        curry_quest.process_message(self._message(author=3, content='!use_item <@!6> Medicinal Herb', channel_id=9))
        send_message.assert_called_once_with('<@!3>: <@!6> did not join the quest.')


if __name__ == '__main__':
    unittest.main()
