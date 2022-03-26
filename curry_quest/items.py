from curry_quest.errors import InvalidOperation
from curry_quest.genus import Genus
from curry_quest.jsonable import InvalidJson, Jsonable, JsonReaderHelper


def normalize_item_name(*item_name_parts: str):
    item_name = ''.join(item_name_parts)
    return item_name.replace(' ', '').lower()


class Item(Jsonable):
    def to_json_object(self):
        return {'name': self.name}

    def from_json_object(self):
        pass

    @classmethod
    @property
    def name(cls) -> str:
        raise NotImplementedError(f'{cls.__name__}.name')

    @classmethod
    def matches_normalized_name(cls, normalized_item_name):
        return normalize_item_name(cls.name).startswith(normalized_item_name)

    @classmethod
    def matches_name(cls, *item_name_parts):
        return normalize_item_name(cls.name).startswith(normalize_item_name(item_name_parts))

    def can_use(self, context) -> tuple[bool, str]:
        reason = self._cannot_use_reason(context)
        return (False, reason) if reason else (True, '')

    def _cannot_use_reason(self, context) -> str:
        raise NotImplementedError(f'{self.__class__.__name__}.{self._cannot_use_reason}')

    def _cannot_use_value(self, reason: str):
        return False, reason

    def _can_use_value(self):
        return True, ''

    def use(self, context) -> str:
        can_use, reason = self.can_use(context)
        if not can_use:
            raise InvalidOperation(f'Cannot use {self.name}. {reason}')
        effect = self._use(context)
        return f"You used the {self.name}. {effect}"

    def _use(self, context) -> str:
        raise NotImplementedError(f"{self.__class__.__name__}.{self.use}")


class Pita(Item):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Pita'

    def _cannot_use_reason(self, context) -> str:
        if context.familiar.is_mp_at_max():
            return 'Your MP is already at max.'

    def _use(self, context) -> str:
        context.familiar.restore_mp()
        return 'Your MP has been restored to max.'


class BattlePhaseOnlyItem(Item):
    def _cannot_use_reason(self, context) -> str:
        if not context.is_in_battle():
            return 'You are not in combat.'
        elif context.battle_context.is_prepare_phase():
            return 'Combat has not started yet.'


class Oleem(BattlePhaseOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Oleem'

    def _use(self, context) -> bool:
        context.battle_context.finish_battle()
        return 'The enemy vanished!'


class HolyScroll(BattlePhaseOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Holy Scroll'

    def _use(self, context) -> str:
        context.battle_context.set_holy_scroll_counter(3)
        return 'You are invulnerable for the next 3 turns.'


class MedicinalHerb(Item):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Medicinal Herb'

    def _cannot_use_reason(self, context) -> str:
        if context.familiar.is_hp_at_max():
            return 'Your HP is already at max.'

    def _use(self, context) -> str:
        context.familiar.restore_hp()
        return 'Your HP has been restored to max.'


class CureAllHerb(Item):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Cure-All Herb'

    def _cannot_use_reason(self, context) -> str:
        if not context.familiar.has_any_status():
            return 'You do not have any statuses.'

    def _use(self, context) -> str:
        context.familiar.clear_statuses()
        return 'All statuses have been restored.'


class FireBall(BattlePhaseOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Fire Ball'

    def _use(self, context) -> str:
        damage = context.battle_context.enemy.max_hp // 2
        enemy = context.battle_context.enemy
        enemy.deal_damage(damage)
        return f'Flames spew forth from the {self.name} dealing {damage} damage. ' \
            f'{enemy.name.capitalize()} has {enemy.hp} HP left.'


class WaterCrystal(Item):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Water Crystal'

    def _cannot_use_reason(self, context) -> str:
        familiar = context.familiar
        if familiar.is_hp_at_max() and familiar.is_mp_at_max():
            return 'Your HP and MP are already at max.'

    def _use(self, context) -> str:
        familiar = context.familiar
        familiar.restore_hp()
        familiar.restore_mp()
        return 'Your HP and MP have been restored to max.'


def create_genus_seed_class(name: str, genus: Genus):
    class GenusSeed(Item):
        @classmethod
        @property
        def name(cls) -> str:
            return f'{name} Seed'

        def _cannot_use_reason(self, context) -> str:
            familiar = context.familiar
            if familiar.genus == genus:
                return f'Your genus is already {genus.name}.'

        def _use(self, context) -> str:
            context.familiar.genus = genus
            return f'Your genus changed to {genus.name}.'

    return GenusSeed


LightSeed = create_genus_seed_class('Light', Genus.Fire)
SeaSeed = create_genus_seed_class('Sea', Genus.Water)
WindSeed = create_genus_seed_class('Wind', Genus.Wind)


class ItemJsonLoader:
    @classmethod
    def from_json_object(cls, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        item_name = json_reader_helper.read_string('name')
        for item in all_items():
            if item.name == item_name:
                return item
        raise InvalidJson(f'Unknown item JSON object. JSON object: {json_object}.')


def all_items():
    return [
        Pita(), Oleem(), HolyScroll(), MedicinalHerb(), CureAllHerb(), FireBall(), WaterCrystal(), LightSeed(),
        SeaSeed(), WindSeed()
    ]
