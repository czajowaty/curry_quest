import argparse
from ad_rando.seed_generator import RandoCommandHandler
import asyncio
from curry_quest import Controller as CurryQuestController, CurryQuest, Config as CurryQuestConfig, StateFilesHandler
import discord
import discord_helpers
import logging.handlers
import traceback
import sys


class CurryQuestDiscordClient(discord.Client):
    def __init__(self, curry_quest_config, state_files_directory):
        super().__init__()
        self._curry_quest_config = curry_quest_config
        curry_quest_controller = CurryQuestController(curry_quest_config, StateFilesHandler(state_files_directory))
        self._curry_quest_client = CurryQuest(curry_quest_controller, curry_quest_config)

    async def on_ready(self):
        logger.info(f"Logged in as f{self.user.name}.")
        curry_quest_channel = self.get_channel(self._curry_quest_config.channel_id)
        curry_quest_admin_channel = self.get_channel(self._curry_quest_config.admin_channel_id)
        logger.info(f"Curry quest channel: {curry_quest_channel.name}")
        logger.info(f"Curry quest admin channel: {curry_quest_admin_channel.name}")
        curry_quest_admins = []
        for admin_id in self._curry_quest_config.admins:
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


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('token')
    parser.add_argument('curry_quest_config', type=argparse.FileType('r'))
    parser.add_argument('-d', '--state_files_directory', default='.')
    return parser.parse_args()


def configure_logger():
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(message)s')
    file_handler = logging.handlers.RotatingFileHandler(
        'curry_quest.log',
        maxBytes=megabytes_to_bytes(100),
        backupCount=1)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.INFO)
    stream_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(stream_handler)


def megabytes_to_bytes(mb):
    return mb * 1000 ** 2


def main():
    args = parse_args()
    configure_logger()
    curry_quest_config = CurryQuestConfig.from_file(args.curry_quest_config)
    CurryQuestDiscordClient(curry_quest_config, args.state_files_directory).run(args.token)


if __name__ == '__main__':
    main()
