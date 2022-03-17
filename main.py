import argparse
from ad_rando.seed_generator import RandoCommandHandler
import asyncio
from bot_config import BotConfig
from curry_quest import Controller as CurryQuestController, CurryQuest, Config as CurryQuestConfig, StateFilesHandler, \
    HallsOfFameHandler
import discord
import discord_helpers
import logging.handlers
import traceback
import sys


class CurryQuestDiscordClient(discord.Client):
    def __init__(
            self,
            bot_config: BotConfig,
            curry_quest_config: CurryQuestConfig,
            hall_of_fame_handler,
            state_files_handler):
        super().__init__()
        self._bot_config = bot_config
        curry_quest_controller = CurryQuestController(curry_quest_config, hall_of_fame_handler, state_files_handler)
        self._curry_quest_client = CurryQuest(curry_quest_controller, bot_config)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user.name}.")
        curry_quest_channel = self.get_channel(self._bot_config.channel_id)
        curry_quest_admin_channel = self.get_channel(self._bot_config.admin_channel_id)
        logger.info(f"Curry quest channel: {curry_quest_channel.name}")
        logger.info(f"Curry quest admin channel: {curry_quest_admin_channel.name}")
        curry_quest_admins = []
        for admin_id in self._bot_config.admins:
            user = await self.fetch_user(admin_id)
            if user is None:
                logger.warning(f"Admin with ID {admin_id} does not exist.")
            else:
                curry_quest_admins.append(user.display_name)
        logger.info(f"Curry quest admins: {curry_quest_admins}")

        def send_curry_quest_message(message):
            asyncio.create_task(curry_quest_channel.send(message))
            return True

        def send_curry_quest_admin_message(message):
            asyncio.create_task(curry_quest_admin_channel.send(message))
            return True

        self._curry_quest_client.start(send_curry_quest_message, send_curry_quest_admin_message)

    async def on_disconnect(self):
        await self.change_presence(afk=True)
        logger.info("Disconnected.")

    async def on_error(self, event_method, *args, **kwargs):
        await self.change_presence(afk=True)
        logger.error(f"Error in {event_method}{args}{kwargs}")
        for line in traceback.format_exception(*sys.exc_info()):
            logger.error(line.strip())

    async def on_message(self, message):
        if message.author.bot:
            return
        if self._curry_quest_client.is_curry_quest_message(message):
            self._curry_quest_client.process_message(message)

    async def _process_commands(self, message: discord.Message):
        if not message.content.startswith("!"):
            return
        splitted_message = message.content.split()
        command = splitted_message[0][1:]
        args = splitted_message[1:]
        if command == 'seed':
            await self._seed_command_handler(message.channel, args)

    async def _seed_command_handler(self, channel: discord.TextChannel, args):
        responses = RandoCommandHandler(args).handle()
        await channel.send('\n'.join(discord_helpers.curry_message(response) for response in responses))


class CurryQuestOfflineClient:
    EXIT_COMMAND = 'exit'
    JOIN_COMMAND = 'join'
    PART_COMMAND = 'part'
    SPECIAL_COMMANDS = [EXIT_COMMAND, JOIN_COMMAND, PART_COMMAND]
    PLAYER_ID = 1

    class InvalidCommand(Exception):
        pass

    def __init__(self, curry_quest_config: CurryQuestConfig, halls_of_fame_handler, state_files_handler):
        self._controller = CurryQuestController(curry_quest_config, halls_of_fame_handler, state_files_handler)
        self._controller.set_response_event_handler(lambda msg: print(f"Response - {msg}"))

    def run(self):
        asyncio.run(self._main_loop())

    async def _main_loop(self):
        self._controller.start_timers()
        while True:
            is_by_admin, (command, args) = await asyncio.to_thread(self._get_command)
            if command == self.EXIT_COMMAND:
                return
            if command == self.JOIN_COMMAND:
                self._controller.add_player(self.PLAYER_ID, 'Test player')
            elif command == self.PART_COMMAND:
                self._controller.remove_player(self.PLAYER_ID)
            else:
                if is_by_admin:
                    self._controller.handle_admin_action(self.PLAYER_ID, command, args)
                else:
                    self._controller.handle_user_action(self.PLAYER_ID, command, args)

    def _get_command(self):
        while True:
            command_line = input("Enter command [command arg1 arg2 arg3 ...]: ")
            try:
                return self._parse(command_line)
            except self.InvalidCommand as exc:
                print(f"Invalid command: {exc}")

    def _parse(self, command_line: str):
        splitted = command_line.split()
        if len(splitted) == 0:
            raise self.InvalidCommand('Cannot be empty.')
        if splitted[0] in self.SPECIAL_COMMANDS:
            return True, self._build_command(command=splitted[0])
        command, args = splitted[0], splitted[1:]
        if command == 'USER':
            if len(args) == 0:
                raise self.InvalidCommand('Cannot be empty.')
            is_by_admin = False
            command, args = args[0], args[1:]
        else:
            is_by_admin = True
        return is_by_admin, self._build_command(command, args)

    def _build_command(self, command: str='', args: list[str]=[]):
        return command, args


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('token')
    parser.add_argument('bot_config', type=argparse.FileType('r'))
    parser.add_argument('curry_quest_config', type=argparse.FileType('r'))
    parser.add_argument('halls_of_fame_file', type=str)
    parser.add_argument('-d', '--state_files_directory', default='.')
    parser.add_argument('--offline', action='store_true')
    return parser.parse_args()


def configure_logger(stream_handler_logging_level):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    file_handler = logging.handlers.RotatingFileHandler(
        'curry_quest.log',
        maxBytes=megabytes_to_bytes(100),
        backupCount=1)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(stream_handler_logging_level)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def megabytes_to_bytes(mb):
    return mb * 1000 ** 2


def main():
    args = parse_args()
    configure_logger(logging.DEBUG if args.offline else logging.INFO)
    bot_config = BotConfig.Parser(args.bot_config).parse()
    curry_quest_config = CurryQuestConfig.Parser(args.curry_quest_config).parse()
    halls_of_fame_handler = HallsOfFameHandler.from_file(args.halls_of_fame_file)
    state_files_handler = StateFilesHandler(args.state_files_directory)
    if args.offline:
        CurryQuestOfflineClient(curry_quest_config, halls_of_fame_handler, state_files_handler).run()
    else:
        client = CurryQuestDiscordClient(bot_config, curry_quest_config, halls_of_fame_handler, state_files_handler)
        client.run(args.token)


if __name__ == '__main__':
    main()
