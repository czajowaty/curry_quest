import asyncio
import datetime
import logging
import random

logger = logging.getLogger(__name__)


class Services:
    def rng(self):
        return random.Random()

    def timer(self, name, interval, callback):
        async def timer_task(name, interval, callback):
            logger.debug(f"'{name}' timer started ({interval}s).")
            try:
                await asyncio.sleep(interval)
                logger.debug(f"'{name}' timer expired.")
                callback()
            except asyncio.CancelledError:
                logger.debug(f"'{name}' timer cancelled.")

        return asyncio.create_task(timer_task(name, interval, callback))

    def now(self):
        return datetime.datetime.now()
