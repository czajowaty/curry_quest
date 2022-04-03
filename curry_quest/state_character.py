from curry_quest import commands, items
from curry_quest.state_base import StateBase
from curry_quest.unit_creator import UnitCreator
from curry_quest.state_with_inventory_item import StateWithInventoryItem
from curry_quest.statuses import Statuses
from curry_quest.jsonable import JsonReaderHelper
from discord_helpers import Emoji


class StateCharacterEvent(StateBase):
    def __init__(self, context, character=None):
        super().__init__(context)
        self._character = character

    def _to_json_object(self):
        return {'character': self._character}

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        character = json_reader_helper.read_optional_value_of_type('character', str)
        return cls.create(context, () if character is None else (character,))

    def on_enter(self):
        character = self._select_character()
        self._context.set_character_weight_penalty(character)
        encounter_handler = self.ENCOUNTERS[character]
        (next_command, args), response = encounter_handler(self)
        self._context.add_response(f'You meet {character}. {response}')
        self._context.generate_action(next_command, *args)

    def _select_character(self):
        return self._character or self._context.random_selection_with_weights(self._character_events_weights())

    def _character_events_weights(self):
        character_events_weights = self._context.characters_weights

        def remove_weight(character):
            if character in character_events_weights:
                del character_events_weights[character]

        if not self._context.familiar.does_evolve():
            remove_weight('Mia')
        if self._context.familiar.is_hp_at_max():
            remove_weight('Cherrl')
        if self._context.familiar.has_status(Statuses.StatsBoost):
            remove_weight('Patty')
        return character_events_weights

    def _handle_cherrl_encounter(self):
        familiar = self._context.familiar
        familiar.restore_hp()
        familiar.restore_mp()
        return (commands.EVENT_FINISHED, ()), 'She offers to patch you up. You are fully healed.'

    def _handle_nico_encounter(self):
        return (commands.EVENT_FINISHED, ()), 'She gives you a lesson about culture and walks away.. '

    def _handle_patty_encounter(self):
        self._context.familiar.set_status(Statuses.StatsBoost)
        return (commands.EVENT_FINISHED, ()), \
            f'She offers you a giant plate of {Emoji.CURRY}. It smells amazing! ' \
            'You devour it without hesitation. You feel much stronger and sorry for the next monster you encounter.'

    def _handle_fur_encounter(self):
        if self.inventory.is_empty():
            return (commands.EVENT_FINISHED, ()), \
                'She wanted to offer you an item exchange, but you don\'t have any items... ' \
                'She scoffs at your lack of preparation and walks off.'
        else:
            item = self._context.rng.choice(items.all_items())
            self._context.buffer_item(item)
            return (commands.START_ITEM_TRADE, ()), 'She offers you an item exchange.'

    def _handle_selfi_encounter(self):
        familiar_for_trade_traits = self._context.rng.choice(self._create_selfi_familiars_list())
        familiar_for_trade = \
            UnitCreator(familiar_for_trade_traits) \
            .create(self._context.familiar.level, levels=self.game_config.levels)
        familiar_for_trade.exp = self._context.familiar.exp
        self._context.buffer_unit(familiar_for_trade)
        return (commands.START_FAMILIAR_TRADE, ()), 'She offers you a familiar exchange.'

    def _create_selfi_familiars_list(self):
        return [
            monster_traits
            for monster_traits
            in self.game_config.non_evolved_monster_traits.values()
            if monster_traits.name != self._context.familiar.name
        ]

    def _handle_mia_encounter(self):
        return (commands.EVOLVE_FAMILIAR, ()), \
            'She gazes upon you while mumbling incoherently. ' \
            'Suddenly she throws a mysterious potion at your familiar and something weird happens to it...'

    def _handle_vivianne_encounter(self):
        return (commands.EVENT_FINISHED, ()), 'She starts dancing. After watching for a while you leave.'

    def _handle_ghosh_encounter(self):
        ghosh_traits = self.game_config.special_units_traits.ghosh
        ghosh = UnitCreator(ghosh_traits).create(self._context.familiar.level, levels=self.game_config.levels)
        return (commands.START_BATTLE, (ghosh,)), 'He wants to fight you!'

    def _handle_beldo_encounter(self):
        floor = min(self._context.floor + 1, self.game_config.highest_floor)
        monster = self._context.generate_floor_monster(floor, level_increase=1)
        return (commands.START_BATTLE, (monster,)), \
            'He is accompanied by a strong monster, which takes an interest in you... ' \
            'Beldo leaves laughing maniacally.'

    ENCOUNTERS = {
        'Cherrl': _handle_cherrl_encounter,
        'Nico': _handle_nico_encounter,
        'Patty': _handle_patty_encounter,
        'Fur': _handle_fur_encounter,
        'Selfi': _handle_selfi_encounter,
        'Mia': _handle_mia_encounter,
        'Vivianne': _handle_vivianne_encounter,
        'Ghosh': _handle_ghosh_encounter,
        'Beldo': _handle_beldo_encounter
    }

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) == 0:
            return ()
        character = args[0].lower().capitalize()
        if character not in cls.ENCOUNTERS.keys():
            raise cls.ArgsParseError('Unknown character')
        return character,


class StateItemTrade(StateBase):
    def on_enter(self):
        inventory_string = ', '.join(self._context.inventory.items)
        item = self._context.peek_buffered_item()
        self._context.add_response(f"You have: {inventory_string}. Fur offers {item.name}. Do you want to trade?")

    def is_waiting_for_user_action(self) -> bool:
        return True


class StateItemTradeAccepted(StateWithInventoryItem):
    def on_enter(self):
        item_to_trade = self._context.inventory.peek_item(self._item_index)
        item_to_receive = self._context.take_buffered_item()
        if isinstance(item_to_trade, item_to_receive.__class__):
            self._context.add_response("\"Are you kidding me?!\", Fur says and walks away angrily...")
        else:
            self._context.inventory.take_item(self._item_index)
            self._context.inventory.add_item(item_to_receive)
            self._context.add_response(
                "Fur is very happy with what she got. She leaves with a smug smile on her face. "
                "Did you make a mistake?")
        self._context.generate_action(commands.EVENT_FINISHED)


class StateItemTradeRejected(StateBase):
    def on_enter(self):
        self._context.clear_item_buffer()
        self._context.add_response(f"Fur leaves looking a bit mad. Maybe you made a mistake...")
        self._context.generate_action(commands.EVENT_FINISHED)


class StateFamiliarTrade(StateBase):
    def on_enter(self):
        familiar_for_trade = self._context.peek_buffered_unit()
        familiar = self._context.familiar
        self._context.add_response(
            f"You have: {familiar.to_string()}. Selfi offers {familiar_for_trade.to_string()}. "
            "Do you want to trade?")

    def is_waiting_for_user_action(self) -> bool:
        return True


class StateFamiliarTradeAccepted(StateBase):
    def on_enter(self):
        self._context.familiar = self._context.take_buffered_unit()
        self._context.add_response(
            "Selfi hapilly says \"Thank you, Puffy Lips!\" and quickly walks away with your familiar.")
        self._context.generate_action(commands.EVENT_FINISHED)


class StateFamiliarTradeRejected(StateBase):
    def on_enter(self):
        self._context.clear_unit_buffer()
        self._context.add_response(
            "Selfi turns around and leaves immediately. From afar you can hear her saying \"Stupid, Puffy Lips...\".")
        self._context.generate_action(commands.EVENT_FINISHED)


class StateEvolveFamiliar(StateBase):
    def on_enter(self):
        familiar = self._context.familiar
        if familiar.traits.evolves_into is None:
            self._context.add_response(f"Your familiar cannot evolve.")
        else:
            evolved_monster_traits = self.game_config.monsters_traits[familiar.traits.evolves_into]
            familiar.evolve(evolved_monster_traits)
            self._context.add_response(f"Your familiar evolved into {familiar.name}!")
        self._context.generate_action(commands.EVENT_FINISHED)
