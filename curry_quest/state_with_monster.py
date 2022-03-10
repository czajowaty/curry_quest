from curry_quest.state_base import StateBase


class StateWithMonster(StateBase):
    def __init__(self, context, monster_name: str=None, monster_level: int=None):
        super().__init__(context)
        self._monster_name = monster_name
        self._monster_level = monster_level

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
