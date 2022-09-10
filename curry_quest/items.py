from abc import abstractmethod
from curry_quest.genus import Genus
from curry_quest.jsonable import InvalidJson, Jsonable, JsonReaderHelper
from curry_quest.unit_action import UnitActionContext


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
    @abstractmethod
    def select_target(cls, familiar, enemy): pass

    @classmethod
    @abstractmethod
    def can_target_familiar(cls) -> bool: pass

    @classmethod
    @abstractmethod
    def can_target_enemy(cls) -> bool: pass

    @classmethod
    def matches_normalized_name(cls, normalized_item_name):
        return normalize_item_name(cls.name).startswith(normalized_item_name)

    @classmethod
    def matches_name(cls, *item_name_parts):
        return normalize_item_name(cls.name).startswith(normalize_item_name(item_name_parts))

    @abstractmethod
    def cannot_use_reason(self, context: UnitActionContext) -> str: pass

    @abstractmethod
    def use(self, context: UnitActionContext) -> str: pass


class DefaultFamiliarTargetItem(Item):
    @classmethod
    def select_target(cls, familiar, enemy):
        return familiar


class DefaultEnemyTargetItem(Item):
    @classmethod
    def select_target(cls, familiar, enemy):
        return enemy


class NoDefaultTargetItem(Item):
    @classmethod
    def select_target(cls, familiar, enemy):
        return None


class FamiliarOnlyItem(DefaultFamiliarTargetItem):
    @classmethod
    def can_target_familiar(cls) -> bool:
        return True

    @classmethod
    def can_target_enemy(cls) -> bool:
        return False


class EnemyOnlyItem(DefaultEnemyTargetItem):
    @classmethod
    def can_target_familiar(cls) -> bool:
        return False

    @classmethod
    def can_target_enemy(cls) -> bool:
        return True


class FamiliarAndEnemyItem(Item):
    @classmethod
    def can_target_familiar(cls) -> bool:
        return True

    @classmethod
    def can_target_enemy(cls) -> bool:
        return True


class Pita(FamiliarOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Pita'

    @classmethod
    def select_target(cls, familiar, enemy):
        return familiar

    def cannot_use_reason(self, context: UnitActionContext) -> str:
        pass

    def use(self, context: UnitActionContext) -> str:
        target = context.target
        target_words = context.target_words
        if target.is_mp_at_max():
            target.max_mp += 1
            response = f'{target_words.possessive_name.capitalize()} max MP has increased.'
        else:
            response = f'{target_words.possessive_name.capitalize()} MP has been restored to max.'
        target.restore_mp()
        return response


class BattlePhaseOnlyItem(Item):
    def cannot_use_reason(self, context: UnitActionContext) -> str:
        if not context.state_machine_context.is_in_battle():
            return 'You are not in combat.'
        elif context.state_machine_context.battle_context.is_prepare_phase():
            return 'Combat has not started yet.'


class Oleem(BattlePhaseOnlyItem, EnemyOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Oleem'

    def use(self, context: UnitActionContext) -> bool:
        context.state_machine_context.battle_context.finish_battle()
        return 'The enemy vanished!'


class HolyScroll(BattlePhaseOnlyItem, FamiliarOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Holy Scroll'

    def use(self, context: UnitActionContext) -> str:
        context.state_machine_context.battle_context.set_holy_scroll_counter(3)
        return 'You are invulnerable for the next 3 turns.'


class MedicinalHerb(FamiliarAndEnemyItem, DefaultFamiliarTargetItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Medicinal Herb'

    def cannot_use_reason(self, context: UnitActionContext) -> str:
        pass

    def use(self, context: UnitActionContext) -> str:
        target = context.target
        target_words = context.target_words
        if target.is_hp_at_max():
            target.max_hp += 1
            response = f'{target_words.possessive_name.capitalize()} max HP has increased.'
        else:
            response = f'{target_words.possessive_name.capitalize()} HP has been restored to max.'
        target.restore_hp()
        target.mp += 3
        return response


class CureAllHerb(FamiliarAndEnemyItem, DefaultFamiliarTargetItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Cure-All Herb'

    def cannot_use_reason(self, context: UnitActionContext) -> str:
        pass

    def use(self, context: UnitActionContext) -> str:
        target_words = context.target_words
        target = context.target
        target.clear_statuses()
        target.mp += 3
        return f'{target_words.possessive_name.capitalize()} statuses have been cleared.'


class FireBall(BattlePhaseOnlyItem, EnemyOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Fire Ball'

    def use(self, context: UnitActionContext) -> str:
        enemy = context.state_machine_context.battle_context.enemy
        damage = enemy.max_hp // 2
        enemy.deal_damage(damage)
        return f'Flames spew forth from the {self.name} dealing {damage} damage. ' \
            f'{enemy.name.capitalize()} has {enemy.hp} HP left.'


class WaterCrystal(FamiliarOnlyItem):
    @classmethod
    @property
    def name(cls) -> str:
        return 'Water Crystal'

    def cannot_use_reason(self, context: UnitActionContext) -> str:
        pass

    def use(self, context: UnitActionContext) -> str:
        familiar = context.state_machine_context.familiar
        familiar.restore_hp()
        familiar.restore_mp()
        return 'Your HP and MP have been restored to max.'


def create_genus_seed_class(name: str, genus: Genus):
    class GenusSeed(FamiliarAndEnemyItem, NoDefaultTargetItem):
        @classmethod
        @property
        def name(cls) -> str:
            return f'{name} Seed'

        def cannot_use_reason(self, context: UnitActionContext) -> str:
            pass

        def use(self, context: UnitActionContext) -> str:
            target = context.target
            change_genus = target.genus != Genus.Empty
            if change_genus:
                target.genus = genus
            target.mp += 3
            target_words = context.target_words
            if change_genus:
                return f'{target_words.possessive_name.capitalize()} genus changed to {genus.name}.'
            else:
                return 'It has no effect.'

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
