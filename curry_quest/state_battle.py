from curry_quest import commands
from curry_quest.jsonable import JsonReaderHelper
from curry_quest.item_use_unit_action import ItemUseActionHandler
from curry_quest.items import Item
from curry_quest.state_base import StateBase
from curry_quest.state_with_inventory_item import StateWithInventoryItemAndTarget
from curry_quest.stats_calculator import StatsCalculator
from curry_quest.state_machine_context import BattleContext, StateMachineContext
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.unit_traits import UnitTraits
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext, UnitActionHandler
from curry_quest.unit_creator import UnitCreator
from curry_quest.words import Words, FamiliarWords, UnitWords


class StateBattleEvent(StateBase):
    def __init__(self, context, monster_traits: UnitTraits=None, monster_level: int=0):
        super().__init__(context)
        self._monster_traits = monster_traits
        self._monster_level = monster_level

    def _to_json_object(self):
        return {
            'monster_name': None if self._monster_traits is None else self._monster_traits.name,
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

    def on_enter(self):
        self._context.generate_action(commands.START_BATTLE, self._select_enemy())

    def _select_enemy(self):
        if self._monster_traits is None:
            return self._context.generate_floor_monster(floor=self._context.floor)
        else:
            monster_level = self._monster_level if self._monster_level > 0 else self._context.familiar.level
            return UnitCreator(self._monster_traits).create(monster_level, levels=self.game_config.levels)

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) == 0:
            return ()
        monster_traits = cls._find_monster_traits(args[0], context)
        monster_level = 0
        if len(args) > 1:
            try:
                monster_level = int(args[1])
            except ValueError:
                raise cls.ArgsParseError('Monster level is not a number')
        return monster_traits, monster_level

    @classmethod
    def _find_monster_traits(cls, monster_name, context: StateMachineContext):
        for known_monster_name, monster_traits in context.game_config.monsters_traits.items():
            if known_monster_name.lower() == monster_name.lower():
                return monster_traits
        raise cls.ArgsParseError('Unknown monster')


class StateBattleBase(StateBase):
    @property
    def _battle_context(self) -> BattleContext:
        return self._context.battle_context

    def _is_familiar_unit(self, unit: Unit):
        return unit is self._context.familiar

    def _familiar_words(self) -> FamiliarWords:
        return FamiliarWords()

    def _enemy_words(self) -> UnitWords:
        return UnitWords(self._battle_context.enemy)


class StateStartBattle(StateBattleBase):
    def __init__(self, context, enemy: Unit):
        super().__init__(context)
        self._enemy = enemy

    def _to_json_object(self):
        return {'enemy': self._enemy.to_json_object()}

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        return cls.create(context, (context.create_monster_from_json_object(json_reader_helper.read_dict('enemy')),))

    def on_enter(self):
        enemy = self._enemy
        self._context.add_response(f"You encountered a LVL {enemy.level} {enemy.name} ({enemy.hp} HP).")
        self._context.add_response(f"{enemy.to_string()}.")
        self._context.start_battle(self._enemy)
        self._battle_context.start_prepare_phase(counter=3)
        self._context.generate_action(commands.BATTLE_PREPARE_PHASE, True)

    @classmethod
    def _parse_args(cls, context, args):
        return args[0],


class StateBattlePreparePhase(StateBattleBase):
    def __init__(self, context, prepare_phase_turn_used: bool):
        super().__init__(context)
        self._prepare_phase_turn_used = prepare_phase_turn_used

    def _to_json_object(self):
        return {'prepare_phase_turn_used': self._prepare_phase_turn_used}

    @classmethod
    def create_from_json_object(cls, json_reader_helper: JsonReaderHelper, context):
        return cls.create(context, (json_reader_helper.read_bool('prepare_phase_turn_used'),))

    def on_enter(self):
        if self._context.familiar.has_status(Statuses.Sleep):
            self._context.add_response(
                "You are very sleepy. As you're nodding off, an enemy approaches you. Time to battle!")
            self._battle_context.finish_prepare_phase()
        else:
            if self._prepare_phase_turn_used:
                self._battle_context.dec_prepare_phase_counter()
            if not self._battle_context.is_prepare_phase():
                self._context.add_response("The enemy approaches you. Time to battle!")
            elif self._prepare_phase_turn_used:
                self._context.add_response("The enemy is close, but you still have time to prepare.")
        if not self._battle_context.is_prepare_phase():
            self._context.familiar.clear_status(Statuses.Sleep)
            self._context.generate_action(commands.BATTLE_PREPARE_PHASE_FINISHED)

    def is_waiting_for_user_action(self) -> bool:
        return True

    @classmethod
    def _parse_args(cls, context, args):
        return args[0],


class StateBattleApproach(StateBattleBase):
    def on_enter(self):
        self._battle_context.finish_prepare_phase()
        self._context.add_response("Time to battle!")
        self._context.generate_action(commands.BATTLE_PREPARE_PHASE_FINISHED)


class StateBattlePhaseBase(StateBattleBase):
    @property
    def is_player_turn(self) -> bool:
        return self._battle_context.is_player_turn

    def _acting_unit(self) -> Unit:
        return self._context.familiar if self.is_player_turn else self._battle_context.enemy

    def _waiting_unit(self) -> Unit:
        return self._battle_context.enemy if self.is_player_turn else self._context.familiar

    def _acting_unit_words(self) -> Words:
        return self._familiar_words() if self._battle_context.is_player_turn else self._enemy_words()

    def _waiting_unit_words(self) -> Words:
        return self._enemy_words() if self._battle_context.is_player_turn else self._familiar_words()

    def _unit_words(self, unit: Unit) -> Words:
        return self._familiar_words() if unit is self._context.familiar else self._enemy_words()

    def _perform_physical_attack(self, attacker: Unit, defender: Unit):
        self._perform_action(self._context.create_physical_attack_with_target, attacker, defender)

    def _cast_spell(self, caster: Unit, other_unit: Unit):
        self._perform_action(self._context.create_spell_with_target, caster, other_unit)

    def _perform_action(self, action_creator, performer: Unit, other_unit: Unit):
        action_handler, action_context = action_creator(performer, other_unit)
        response = action_handler.perform(action_context)
        self._context.add_response(response)


class StateBattlePhase(StateBattlePhaseBase):
    CONFUSED_PLAYER_ACTION_DELAY = 1

    def on_enter(self):
        if self._is_battle_finished():
            self._handle_battle_finished()
        else:
            self._handle_battle_next_turn()

    def _is_battle_finished(self) -> bool:
        return self._battle_context.is_finished() or self._is_enemy_dead() or self._is_familiar_dead()

    def _is_enemy_dead(self) -> bool:
        return self._battle_context.enemy.is_dead()

    def _is_familiar_dead(self) -> bool:
        return self._context.familiar.is_dead()

    def _handle_battle_finished(self):
        self._clear_statuses()
        if self._is_enemy_dead():
            self._handle_enemy_defeated()
        self._context.finish_battle()
        if self._is_familiar_dead():
            self._context.add_response("You died...")
            self._context.generate_action(commands.YOU_DIED)
        else:
            self._context.generate_action(commands.EVENT_FINISHED)

    def _clear_statuses(self):
        familiar = self._context.familiar
        if familiar.has_any_status():
            familiar.clear_statuses()
            self._context.add_response(f"All statuses have been cleared.")

    def _handle_enemy_defeated(self):
        enemy = self._battle_context.enemy
        response = f'You defeated the {enemy.name}'
        familiar = self._context.familiar
        if not familiar.is_max_level():
            gained_exp = self._calculate_gained_exp()
            response += f' and gained {gained_exp} EXP.'
            has_leveled_up = familiar.gain_exp(gained_exp)
            if has_leveled_up:
                response += f' You leveled up! Your new stats - {familiar.stats_to_string()}.'
        else:
            response += '.'
        self._context.add_response(response)

    def _calculate_gained_exp(self):
        enemy = self._battle_context.enemy
        given_experience = StatsCalculator(enemy.traits).given_experience(enemy.level)
        if enemy.level > self._context.familiar.level:
            given_experience *= 2
        return given_experience

    def _handle_battle_next_turn(self):
        player_turn_flag_changed = self._handle_is_player_turn_flag()
        self._apply_common_statuses_effects()
        self._handle_timed_statuses_counters()
        self._handle_counters(player_turn_flag_changed)
        skip_turn, skip_turn_reason = self._does_unit_skip_turn()
        if skip_turn:
            self._context.add_response(skip_turn_reason)
            self._context.generate_action(commands.SKIP_TURN)
        else:
            unit_to_act = self._acting_unit()
            if unit_to_act.has_status(Statuses.Confuse):
                if self._battle_context.is_player_turn:
                    self._context.generate_delayed_action(
                        self.CONFUSED_PLAYER_ACTION_DELAY,
                        commands.CONFUSED_UNIT_TURN)
                else:
                    self._context.generate_action(commands.CONFUSED_UNIT_TURN)
            elif self._battle_context.is_player_turn:
                self._context.generate_action(commands.PLAYER_TURN)
            else:
                self._context.generate_action(commands.ENEMY_TURN)

    def _handle_is_player_turn_flag(self):
        if self._battle_context.is_first_turn:
            self._battle_context.is_first_turn = False
            return False
        if self._acting_unit().talents.has(Talents.Quick) and not self._waiting_unit().talents.has(Talents.Quick):
            max_turn_counter = 2
        else:
            max_turn_counter = 1
        self._battle_context.inc_turn_counter()
        if self._battle_context.turn_counter >= max_turn_counter:
            self._battle_context.is_player_turn = not self._battle_context.is_player_turn
            self._battle_context.clear_turn_counter()
            return True
        else:
            return False

    def _apply_common_statuses_effects(self):
        unit_to_act = self._acting_unit()
        if unit_to_act.has_status(Statuses.Poison):
            self._apply_poison_damage(unit_to_act)
        elif unit_to_act.has_status(Statuses.Sleep):
            pass

    def _apply_poison_damage(self, unit: Unit):
        poison_damage = (unit.max_hp + 15) // 16
        if poison_damage >= unit.hp:
            poison_damage = unit.hp - 1
        if poison_damage > 0:
            unit_words = self._unit_words(unit)
            unit.deal_damage(poison_damage)
            response = f'{unit_words.name.capitalize()} {unit_words.s_verb("lose")} {poison_damage} HP. ' \
                f'{unit_words.pronoun.capitalize()} {unit_words.have_verb} {unit.hp} HP left.'
            self._context.add_response(response)

    def _handle_timed_statuses_counters(self):
        unit_to_act = self._acting_unit()
        cleared_statuses_list = unit_to_act.decrease_timed_status_counters()
        for cleared_status in cleared_statuses_list:
            self._context.add_response(self._prepare_status_clear_response(unit_to_act, cleared_status))

    def _prepare_status_clear_response(self, unit: Unit, status: Statuses):
        if status in [Statuses.Blind, Statuses.Poison, Statuses.Confuse]:
            return self._prepare_debuff_status_clear_response(unit, status)
        elif status in [Statuses.FireProtection, Statuses.WaterProtection, Statuses.WindProtection]:
            return self._prepare_element_protection_status_clear_response(unit, status)
        elif status in [Statuses.FireReflect, Statuses.Reflect, Statuses.WindReflect]:
            return self._prepare_reflect_status_clear_response(unit, status)
        else:
            return self._prepare_unknown_status_clear_response(unit, status)

    def _prepare_debuff_status_clear_response(self, unit, status):
        def status_label():
            if status == Statuses.Blind:
                return 'blind'
            elif status == Statuses.Poison:
                return 'poisoned'
            elif status == Statuses.Confuse:
                return 'confused'
            else:
                raise ValueError(f'Unexpected status - {unit}, {status}')

        unit_words = self._unit_words(unit)
        return f'{unit_words.name.capitalize()} {unit_words.be_verb} no longer {status_label()}.'

    def _prepare_element_protection_status_clear_response(self, unit, status):
        def element_label():
            if status == Statuses.FireProtection:
                return 'fire'
            elif status == Statuses.WaterProtection:
                return 'water'
            elif status == Statuses.WindProtection:
                return 'wind'
            else:
                raise ValueError(f'Unexpected status - {unit}, {status}')

        unit_words = self._unit_words(unit)
        return f'{unit_words.name.capitalize()} no longer {unit_words.have_verb} protection of {element_label()}.'

    def _prepare_reflect_status_clear_response(self, unit, status):
        def reflect_label():
            if status == Statuses.FireReflect:
                return 'fire'
            elif status == Statuses.Reflect:
                return ''
            elif status == Statuses.WindReflect:
                return 'wind'
            else:
                raise ValueError(f'Unexpected status - {unit}, {status}')

        unit_words = self._unit_words(unit)
        response = f'{unit_words.name.capitalize()} no longer {unit_words.s_verb("reflect")} {reflect_label()}'
        if len(reflect_label()) > 0:
            response += ' '
        response += 'spells.'
        return response

    def _prepare_unknown_status_clear_response(self, unit, status):
        return f'You no longer have {status}.'

    def _handle_counters(self, player_turn_flag_changed):
        if not player_turn_flag_changed:
            return
        self._handle_holy_scroll_counter()

    def _handle_holy_scroll_counter(self):
        if not self._battle_context.is_holy_scroll_active():
            return
        if self._battle_context.is_player_turn:
            self._battle_context.dec_holy_scroll_counter()
        if not self._battle_context.is_holy_scroll_active():
            self._context.add_response("The Holy Scroll's beams dissipate.")

    def _does_unit_skip_turn(self):
        unit = self._acting_unit()
        unit_words = self._acting_unit_words()
        if unit.has_status(Statuses.Sleep):
            response = f'{unit_words.name.capitalize()} {unit_words.s_verb("sleep")} through ' \
                f'{unit_words.possessive_pronoun} turn.'
            return True, response
        elif unit.has_status(Statuses.Paralyze):
            response = f'{unit_words.name.capitalize()} {unit_words.be_verb} paralyzed. ' \
                f'{unit_words.pronoun.capitalize()} {unit_words.s_verb("skip")} a turn.'
            return True, response
        else:
            return False, ''


class StateBattlePlayerTurn(StateBattlePhaseBase):
    def on_enter(self):
        self._context.add_response(f"Your turn.")

    def is_waiting_for_user_action(self) -> bool:
        return True


class StateEnemyStats(StateBattleBase):
    def on_enter(self):
        self._context.add_response(f"Enemy stats: {self._battle_context.enemy.to_string()}.")
        self._context.generate_action(commands.PLAYER_TURN)


class StateBattleSkipTurn(StateBattlePhaseBase):
    def on_enter(self):
        self._context.add_response("You skip turn.")
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)


class StateBattleAttack(StateBattlePhaseBase):
    def on_enter(self):
        familiar = self._context.familiar
        enemy = self._battle_context.enemy
        self._perform_physical_attack(attacker=familiar, defender=enemy)
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)

    @classmethod
    def _verify_preconditions(cls, context: StateMachineContext, parsed_args):
        familiar: Unit = context.familiar
        action_handler, action_context = context.create_physical_attack_with_target(
            attacker=familiar,
            other_unit=context._battle_context.enemy)
        can_cast, reason = action_handler.can_perform(action_context)
        if not can_cast:
            raise cls.PreConditionsNotMet(reason)


class StateBattleUseSpell(StateBattlePhaseBase):
    def on_enter(self):
        familiar = self._context.familiar
        self._cast_spell(caster=familiar, other_unit=self._battle_context.enemy)
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)

    @classmethod
    def _verify_preconditions(cls, context: StateMachineContext, parsed_args):
        familiar: Unit = context.familiar
        if not familiar.has_spell():
            raise cls.PreConditionsNotMet('You do not have a spell.')
        spell_cast_action_handler, spell_cast_context = context.create_spell_with_target(
            caster=familiar,
            other_unit=context._battle_context.enemy)
        can_cast, reason = spell_cast_action_handler.can_perform(spell_cast_context)
        if not can_cast:
            raise cls.PreConditionsNotMet(reason)


class StateBattleUseItem(StateWithInventoryItemAndTarget):
    @property
    def _battle_context(self) -> BattleContext:
        return self._context.battle_context

    def on_enter(self):
        item = self._context.inventory.peek_item(self._item_index)
        action_handler, action_context = self._context.create_item_use_with_target(item, self._target)
        if action_context.target is None:
            command, args = self._handle_no_target(item)
        else:
            can_use, reason = action_handler.can_perform(action_context)
            if not can_use:
                command, args = self._handle_cannot_use_item(item, reason)
            else:
                command, args = self._handle_can_use_item(action_handler, action_context)
        self._context.generate_action(command, *args)

    def _handle_no_target(self, item: Item):
        self._context.add_response(
            f"You cannot use {item.name} without target. Add \"on self\" or \"on enemy\" to the command.")
        return self._cannot_use_item_command()

    def _cannot_use_item_command(self):
        if self._battle_context.is_prepare_phase():
            return commands.CANNOT_USE_ITEM_PREPARE_PHASE, (False, )
        else:
            return commands.CANNOT_USE_ITEM_BATTLE_PHASE, ()

    def _handle_cannot_use_item(self, item: Item, reason: str):
        self._context.add_response(f"You cannot use {item.name}. {reason}")
        return self._cannot_use_item_command()

    def _handle_can_use_item(self, action_handler: ItemUseActionHandler, action_context: UnitActionContext):
        response = action_handler.perform(action_context)
        self._context.inventory.take_item(self._item_index)
        self._context.add_response(response)
        if self._battle_context.is_prepare_phase():
            return commands.BATTLE_PREPARE_PHASE_ACTION_PERFORMED, (True, )
        else:
            return commands.BATTLE_ACTION_PERFORMED, ()


class StateBattleTryToFlee(StateBattlePhaseBase):
    def on_enter(self):
        if self._context.familiar.has_status(Statuses.Paralyze):
            self._context.add_response("You are paralyzed and cannot flee.")
            self._context.generate_action(commands.CANNOT_FLEE)
            return
        if self._context.does_action_succeed(success_chance=self.game_config.probabilities.flee):
            self._battle_context.finish_battle()
            self._context.add_response("You successfully flee from the battle.")
        else:
            self._context.add_response("You attempt to flee from battle, but your path is blocked!")
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)


class StateBattleEnemyTurn(StateBattlePhaseBase):
    def on_enter(self):
        enemy = self._battle_context.enemy
        if self._battle_context.is_holy_scroll_active():
            self._context.add_response(f"The field is engulfed in the Holy Scroll's beams. {enemy.name} cannot act.")
        else:
            familiar = self._context.familiar
            enemy = self._battle_context.enemy

            def cast_spell():
                self._cast_spell(caster=enemy, other_unit=familiar)

            def perform_physical_attack():
                self._perform_physical_attack(attacker=enemy, defender=familiar)

            action_with_weights = {}
            summed_actions_weights = 0
            action_weight = self._calculate_unit_action_weight(
                has_action=True,
                create_action=self._context.create_physical_attack_with_target,
                can_perform_action_weight=self._action_weights.physical_attack)
            action_with_weights[perform_physical_attack] = action_weight
            summed_actions_weights += action_weight
            action_weight = self._calculate_unit_action_weight(
                has_action=self._battle_context.enemy.has_spell(),
                create_action=self._context.create_spell_with_target,
                can_perform_action_weight=self._action_weights.spell)
            summed_actions_weights += action_weight
            if summed_actions_weights == 0:
                self._context.add_response(f'{enemy.name.capitalize()} cannot do anything and skips a turn.')
            else:
                action = self._context.random_selection_with_weights(
                    {
                        perform_physical_attack: self._calculate_unit_action_weight(
                            has_action=True,
                            create_action=self._context.create_physical_attack_with_target,
                            can_perform_action_weight=self._action_weights.physical_attack),
                        cast_spell: self._calculate_unit_action_weight(
                            has_action=self._battle_context.enemy.has_spell(),
                            create_action=self._context.create_spell_with_target,
                            can_perform_action_weight=self._action_weights.spell)
                    })
                action()
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)

    @property
    def _action_weights(self) -> UnitTraits.ActionWeights:
        return self._battle_context.enemy.traits.action_weights

    def _calculate_unit_action_weight(self, has_action, create_action, can_perform_action_weight):
        enemy = self._battle_context.enemy
        if not has_action:
            return 0
        action_handler, action_context = create_action(enemy, self._context.familiar)
        can_perform, _ = action_handler.can_perform(action_context)
        return can_perform_action_weight if can_perform else 0


class StateBattleConfusedUnitTurn(StateBattlePhaseBase):
    def on_enter(self):
        unit_words = self._acting_unit_words()
        self._context.add_response(f'{unit_words.name.capitalize()} {unit_words.be_verb} confused.')
        actions_descriptors = [
            descriptor
            for descriptor
            in [
                self._skip_turn_action_descriptor(),
                self._physical_attack_action_descriptor(),
                self._spell_cast_action_descriptor(),
                self._use_item_action_descriptor()
            ]
            if descriptor is not None]
        action, context_creator = self._context.rng.choice(actions_descriptors)
        response = action(context_creator())
        self._context.add_response(response)
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)

    def _physical_attack_action_descriptor(self):
        acting_unit = self._acting_unit()
        if not acting_unit.has_enough_mp_for_physical_attack():
            return None
        action_handler, action_context = self._context.create_physical_attack_without_target(attacker=acting_unit)

        def create_action_context():
            self._fill_unit_action_context(action_context, action_handler)
            return action_context

        return action_handler.perform, create_action_context

    def _fill_unit_action_context(self, context: UnitActionContext, action_handler: UnitActionHandler):
        performer = self._acting_unit()
        context.performer = performer
        targets = []
        if action_handler.can_target_self():
            targets.append(self._acting_unit())
        if action_handler.can_target_other_unit():
            targets.append(self._waiting_unit())
        if action_handler.can_have_no_target():
            targets.append(None)
        context.target = self._context.rng.choice(targets)
        context.state_machine_context = self._context

    def _spell_cast_action_descriptor(self):
        acting_unit = self._acting_unit()
        if not acting_unit.has_spell():
            return None
        if not acting_unit.has_enough_mp_for_spell_cast():
            return None
        action_handler, action_context = self._context.create_spell_without_target(caster=acting_unit)

        def create_action_context():
            self._fill_unit_action_context(action_context, action_handler)
            target = action_context.target
            if target is not None:
                action_context.reflected_target = self._waiting_unit() if target is acting_unit else acting_unit
            return action_context

        return action_handler.perform, create_action_context

    def _use_item_action_descriptor(self):
        if not self.is_player_turn:
            return None
        if self._context.inventory.is_empty():
            return None

        def action_handler(_):
            item_index = self._context._rng.randrange(0, self._context.inventory.size)
            item = self._context.inventory.take_item(item_index)
            item_use_action_handler, action_context = self._context.create_item_use_without_target(item)
            self._fill_unit_action_context(action_context, item_use_action_handler)
            return item_use_action_handler.perform(action_context)

        return action_handler, lambda: None

    def _skip_turn_action_descriptor(self):
        def skip_turn(_):
            unit_words = self._acting_unit_words()
            return f'{unit_words.name.capitalize()} {unit_words.s_verb("decide")} to skip a turn.'

        return skip_turn, lambda: None
