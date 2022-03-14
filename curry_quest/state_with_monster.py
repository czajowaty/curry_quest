from curry_quest.jsonable import JsonReaderHelper
from curry_quest.state_base import StateBase
from curry_quest.unit import Unit
from curry_quest.unit_creator import UnitCreator


class StateWithMonster(StateBase):
    def __init__(self, context, monster_name: str=None, monster_level: int=None):
        super().__init__(context)
        self._monster_name = monster_name
        self._monster_level = monster_level

    def _to_json_object(self):
        return {
            'monster_name': self._monster_name,
            'monster_level': self._monster_level
        }

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        monster_name = json_reader_helper.read_optional_value_of_type('monster_name', str)
        monster_level = json_reader_helper.read_optional_value_of_type('monster_level', int)
        args = []
        if monster_name is not None:
            args.append(monster_name)
            if monster_level is not None:
                args.append(monster_level)
        return cls.create(context, args)

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) == 0:
            return ()
        monster_name = args[0]
        if monster_name not in context.game_config.monsters_traits.keys():
            raise cls.ArgsParseError('Unknown monster')
        monster_level = None
        if len(args) > 1:
            try:
                monster_level = int(args[1])
            except ValueError:
                raise cls.ArgsParseError('Monster level is not a number')
        return monster_name, monster_level

    def is_waiting_for_user_action(self) -> bool:
        return True

    def _generate_monster_or_non_evolved(self, default_level=1) -> Unit:
        monster_level = self._monster_level or default_level
        if self._monster_name is None:
            return self._context.generate_non_evolved_monster(monster_level)
        else:
            monsters_traits = self._context.game_config.monsters_traits
            return UnitCreator(monsters_traits[self._monster_name]) \
                .create(level=monster_level, levels=self.game_config.levels)
