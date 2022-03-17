from curry_quest import commands
from curry_quest.damage_calculator import DamageCalculator
from curry_quest.jsonable import JsonReaderHelper
from curry_quest.items import Item
from curry_quest.state_base import StateBase
from curry_quest.state_with_inventory_item import StateWithInventoryItem
from curry_quest.stats_calculator import StatsCalculator
from curry_quest.state_machine_context import BattleContext
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.traits import UnitTraits
from curry_quest.unit import Unit
from curry_quest.unit_creator import UnitCreator

DamageRoll = DamageCalculator.DamageRoll
RelativeHeight = DamageCalculator.RelativeHeight


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
        monster_name = args[0]
        if monster_name not in context.game_config.monsters_traits.keys():
            raise cls.ArgsParseError('Unknown monster')
        monster_traits = context.game_config.monsters_traits[monster_name]
        monster_level = 0
        if len(args) > 1:
            try:
                monster_level = int(args[1])
            except ValueError:
                raise cls.ArgsParseError('Monster level is not a number')
        return monster_traits, monster_level


class StateBattleBase(StateBase):
    @property
    def _battle_context(self) -> BattleContext:
        return self._context.battle_context

    def _is_familiar_unit(self, unit: Unit):
        return unit is self._context.familiar

    def _unit_label(self, unit: Unit):
        return 'you' if self._is_familiar_unit(unit) else unit.name

    def _capitalized_unit_label(self, unit: Unit):
        return self._unit_label(unit).capitalize()

    def _unit_be_verb(self, unit: Unit):
        return 'are' if self._is_familiar_unit(unit) else 'is'


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
    def _is_enemy_dead(self) -> bool:
        return self._battle_context.enemy.is_dead()

    def _is_familiar_dead(self) -> bool:
        return self._context.familiar.is_dead()

    def _is_battle_finished(self) -> bool:
        return self._battle_context.is_finished() or self._is_enemy_dead() or self._is_familiar_dead()

    def _perform_physical_attack(self, attacker: Unit, defender: Unit):
        if not self._is_physical_attack_accurate(attacker):
            return self._physical_attack_miss_response(attacker, defender)
        else:
            damage_calculator = DamageCalculator(attacker, defender)
            relative_height = self._select_relative_height(attacker, defender)
            is_critical = self._select_whether_attack_is_critical(attacker)
            damage = damage_calculator.physical_damage(self._select_damage_roll(), relative_height, is_critical)
            defender.deal_damage(damage)
            physical_attack_descriptor = damage, relative_height, is_critical
            response = self._physical_attack_hit_response(attacker, defender, physical_attack_descriptor)
            if defender.talents.has(Talents.ElectricShock):
                shock_damage = max(damage // 4, 1)
                attacker.deal_damage(shock_damage)
                response += ' ' + self._shock_damage_response(attacker, defender, shock_damage)
            return response

    def _is_physical_attack_accurate(self, attacker: Unit):
        if attacker.luck <= 0:
            return False
        else:
            hit_chance = (attacker.luck - 1) / attacker.luck
            if attacker.has_status(Statuses.Blind):
                hit_chance /= 2
            return self._context.does_action_succeed(success_chance=hit_chance)

    def _select_damage_roll(self) -> DamageRoll:
        return self._context.rng.choices([DamageRoll.Low, DamageRoll.Normal, DamageRoll.High], weights=[1, 2, 1])[0]

    def _select_relative_height(self, attacker: Unit, defender: Unit) -> RelativeHeight:
        def unit_height(unit: Unit):
            unit_height = 0
            if unit.has_status(Statuses.Crack):
                unit_height -= 1
            if unit.has_status(Statuses.Upheavel):
                unit_height += 1
            return unit_height

        attacker_height = unit_height(attacker)
        defender_height = unit_height(defender)
        relative_height = attacker_height - defender_height
        if relative_height > 0:
            return RelativeHeight.Higher
        elif relative_height < 0:
            return RelativeHeight.Lower
        else:
            return RelativeHeight.Same

    def _select_whether_attack_is_critical(self, attacker: Unit) -> bool:
        divider = 2 if attacker.talents.has(Talents.Atrocious) else 64
        crit_chance = (attacker.luck // divider + 1) / 128
        return self._context.does_action_succeed(success_chance=crit_chance)

    def _physical_attack_miss_response(self, attacker: Unit, defender: Unit):
        def is_familiar_attack() -> bool:
            return self._is_familiar_unit(attacker)

        response = 'You try' if is_familiar_attack() else f'{attacker.name} tries'
        response += ' to hit '
        response += f'{defender.name}' if is_familiar_attack() else 'you'
        response += ', but '
        response += 'it' if is_familiar_attack() else f'you'
        response += ' dodge'
        if is_familiar_attack():
            response += 's'
        response += ' swiftly.'
        return response

    def _physical_attack_hit_response(self, attacker: Unit, defender: Unit, physical_attack_descriptor):
        def is_familiar_attack() -> bool:
            return self._is_familiar_unit(attacker)

        def attacker_name() -> str:
            return 'you' if is_familiar_attack() else attacker.name

        def defender_name() -> str:
            return defender.name if is_familiar_attack() else 'you'

        damage, relative_height, is_critical = physical_attack_descriptor
        response = f'{attacker_name().capitalize()} hit'
        if not is_familiar_attack():
            response += 's'
        response += ' '
        if is_critical:
            response += 'hard '
        if relative_height is RelativeHeight.Higher:
            response += 'from above '
        elif relative_height is RelativeHeight.Lower:
            response += 'from below '
        response += f'dealing {damage} damage. {defender_name().capitalize()} '
        response += 'has' if is_familiar_attack() else 'have'
        response += f' {defender.hp} HP left.'
        return response

    def _shock_damage_response(self, attacker: Unit, defender: Unit, shock_damage: int):
        def is_familiar_attack() -> bool:
            return attacker is self._context.familiar

        response = 'An electrical shock runs through '
        response += 'your' if is_familiar_attack() else f'{attacker.name}\'s'
        response += f' body dealing {shock_damage} damage. '
        response += 'You have' if is_familiar_attack() else f'{attacker.name} has'
        response += f' {attacker.hp} HP left.'
        return response

    def _cast_spell(self, caster: Unit, other_unit: Unit):
        spell_cast_context = self._context.create_spell_cast_context(caster, other_unit)
        return caster.spell.cast(spell_cast_context)


class StateBattlePhase(StateBattlePhaseBase):
    def on_enter(self):
        if self._is_battle_finished():
            self._clear_statuses()
            if self._is_enemy_dead():
                self._handle_enemy_defeated()
            self._context.finish_battle()
            if self._is_familiar_dead():
                self._context.add_response("You died...")
                self._context.generate_action(commands.YOU_DIED)
            else:
                self._context.generate_action(commands.EVENT_FINISHED)
        else:
            next_one_to_act_changed = self._select_next_one_to_act()
            self._apply_common_statuses_effects()
            self._handle_timed_statuses_counters()
            self._handle_counters(next_one_to_act_changed)
            skip_turn, skip_turn_reason = self._does_unit_skip_turn()
            if skip_turn:
                self._context.add_response(skip_turn_reason)
                self._context.generate_action(commands.SKIP_TURN)
            elif self._battle_context.is_player_turn:
                self._context.generate_action(commands.PLAYER_TURN)
            else:
                self._context.generate_action(commands.ENEMY_TURN)

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

    def _select_next_one_to_act(self):
        if self._battle_context.is_first_turn:
            self._battle_context.is_first_turn = False
            return False
        attacker, defender = self._select_attacker_defender()
        if attacker.talents.has(Talents.Quick) and not defender.talents.has(Talents.Quick):
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

    def _select_attacker_defender(self):
        if self._battle_context.is_player_turn:
            attacker = self._context.familiar
            defender = self._battle_context.enemy
        else:
            attacker = self._battle_context.enemy
            defender = self._context.familiar
        return attacker, defender

    def _apply_common_statuses_effects(self):
        unit_to_act, _ = self._select_attacker_defender()
        if unit_to_act.has_status(Statuses.Poison):
            self._apply_poison_damage(unit_to_act)
        elif unit_to_act.has_status(Statuses.Sleep):
            pass

    def _apply_poison_damage(self, unit: Unit):
        poison_damage = (unit.max_hp + 15) // 16
        if poison_damage >= unit.hp:
            poison_damage = unit.hp - 1
        if poison_damage > 0:
            unit.deal_damage(poison_damage)
            response = f'{self._capitalized_unit_label(unit)} lose'
            if not self._is_familiar_unit(unit):
                response += 's'
            response += f' {poison_damage} HP. '
            response += 'You have' if self._is_familiar_unit(unit) else 'It has'
            response += f' {unit.hp} HP left.'
            self._context.add_response(response)

    def _handle_timed_statuses_counters(self):
        unit_to_act, _ = self._select_attacker_defender()
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

        return f'{self._capitalized_unit_label(unit)} {self._unit_be_verb(unit)} no longer {status_label()}.'

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

        response = f'{self._capitalized_unit_label(unit)} no longer '
        response += 'have' if self._is_familiar_unit(unit) else 'has'
        response += f' protection of {element_label()}.'
        return response

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

        response = f'{self._capitalized_unit_label(unit)} no longer reflect'
        if not self._is_familiar_unit(unit):
            response += 's'
        response += f' {reflect_label()}'
        if len(reflect_label()) > 0:
            response += ' '
        response += 'spells.'
        return response

    def _prepare_unknown_status_clear_response(self, unit, status):
        return f'You no longer have {status}.'

    def _handle_counters(self, next_one_to_act_changed):
        if not next_one_to_act_changed:
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
        unit, _ = self._select_attacker_defender()
        if unit.has_status(Statuses.Sleep):
            response = f'{self._capitalized_unit_label(unit)} sleep'
            if not self._is_familiar_unit(unit):
                response += 's'
            response += ' through '
            response += 'your' if self._is_familiar_unit(unit) else 'its'
            response += ' turn.'
            return True, response
        elif unit.has_status(Statuses.Paralyze):
            response = f'{self._capitalized_unit_label(unit)} {self._unit_be_verb(unit)} paralyzed. '
            response += 'You' if self._is_familiar_unit(unit) else 'It'
            response += ' skip'
            if not self._is_familiar_unit(unit):
                response += 's'
            response += ' a turn.'
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
        response = self._perform_physical_attack(attacker=familiar, defender=enemy)
        self._context.add_response(response)
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)


class StateBattleUseSpell(StateBattlePhaseBase):
    def on_enter(self):
        familiar = self._context.familiar
        response = self._cast_spell(caster=familiar, other_unit=self._battle_context.enemy)
        self._context.add_response(response)
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)

    @classmethod
    def _verify_preconditions(cls, context, parsed_args):
        familiar = context.familiar
        if not familiar.has_spell():
            raise cls.PreConditionsNotMet('You do not have a spell.')
        if not familiar.has_enough_mp_for_spell():
            raise cls.PreConditionsNotMet('You do not have enough MP.')
        spell_cast_context = context.create_spell_cast_context(familiar, context.battle_context.enemy)
        can_cast, reason = familiar.spell.can_cast(spell_cast_context)
        if not can_cast:
            raise cls.PreConditionsNotMet(reason)


class StateBattleUseItem(StateWithInventoryItem):
    @property
    def _battle_context(self) -> BattleContext:
        return self._context.battle_context

    def on_enter(self):
        item = self._context.inventory.peek_item(self._item_index)
        can_use, reason = item.can_use(self._context)
        if not can_use:
            command, args = self._handle_cannot_use_item(item, reason)
        else:
            command, args = self._handle_can_use_item(item)
        self._context.generate_action(command, *args)

    def _handle_cannot_use_item(self, item: Item, reason: str):
        self._context.add_response(f"You cannot use {item.name}. {reason}")
        if self._battle_context.is_prepare_phase():
            return commands.CANNOT_USE_ITEM_PREPARE_PHASE, (False, )
        else:
            return commands.CANNOT_USE_ITEM_BATTLE_PHASE, ()

    def _handle_can_use_item(self, item: Item):
        item.use(self._context)
        self._context.inventory.take_item(self._item_index)
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
                return self._cast_spell(caster=enemy, other_unit=familiar)

            def perform_physical_attack():
                return self._perform_physical_attack(attacker=enemy, defender=familiar)

            action = self._context.random_selection_with_weights(
                {
                    perform_physical_attack: enemy.traits.action_weights.physical_attack,
                    cast_spell: self._calculate_spell_weight()
                })
            response = action()
            self._context.add_response(response)
        self._context.generate_action(commands.BATTLE_ACTION_PERFORMED)

    def _calculate_spell_weight(self):
        enemy = self._battle_context.enemy
        if not enemy.has_spell():
            return 0
        if not enemy.has_enough_mp_for_spell():
            return 0
        familiar = self._context.familiar
        spell_cast_context = self._context.create_spell_cast_context(enemy, familiar)
        can_cast, _ = enemy.spell.can_cast(spell_cast_context)
        if not can_cast:
            return 0
        return enemy.traits.action_weights.spell
