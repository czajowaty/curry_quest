import logging
from curry_quest import commands, items
from curry_quest.state_base import StateBase
from curry_quest.state_with_monster import StateWithMonster

logger = logging.getLogger(__name__)


class StateInitialize(StateWithMonster):
    def on_enter(self):
        self._context.floor = 0
        self._context.familiar = self._generate_monster_or_non_evolved()
        self._set_start_inventory()
        self._context.clear_battle_context()
        self._context.clear_item_buffer()
        self._context.clear_unit_buffer()
        if not self._context.is_tutorial_done:
            self._context.add_response(
                "Welcome to CurryQuest! To interact, type '!' before any commands. Some commands will require "
                "additional input.\n"
                "Example: !use_item Medicinal Herb\n"
                "You can check what commands are available at any given time by using '!help'.\n"
                "Have fun and good luck!")
            self._context.set_tutorial_done()
        self._context.add_response_line_break()
        self._context.add_response(
            "While you're out on a stroll, off on the far distant horizon, you see a looming tower. "
            "Local legend speaks of a dangerous tower full of monsters... and loot! Could this really be it?! "
            "You journey through the desert towards the ancient structure, thinking of all the riches inside. "
            "After many days of travel, you finally reach the imposing doors. Will you brave the dangers within?")

    def _set_start_inventory(self):
        inventory = self._context.inventory
        inventory.clear()
        inventory.add_item(items.Pita())
        inventory.add_item(items.MedicinalHerb())


class StateEnterTower(StateBase):
    def on_enter(self):
        self._context.add_response(
            f"At the entrance of the tower you find a newborn {self._context.familiar.name}. "
            f"It looks up at you like it wants to join you. You enter the Tower with your new friend "
            f"(who is definitely not going to betray you once you reach the top floor...).")
        self._context.add_response_line_break()
        self._context.generate_action(commands.ENTERED_TOWER)
