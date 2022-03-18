import datetime
from curry_quest import commands
from curry_quest.config import Config
from curry_quest.errors import InvalidOperation
from curry_quest.items import normalize_item_name, all_items
from curry_quest.spell import Spells
from curry_quest.state_base import StateBase
from curry_quest.state_battle import StateBattleEvent, StateStartBattle, StateBattlePreparePhase, StateBattleApproach, \
    StateBattlePhase, StateBattlePlayerTurn, StateEnemyStats, StateBattleAttack, StateBattleSkipTurn, \
    StateBattleUseSpell, StateBattleUseItem, StateBattleTryToFlee, StateBattleEnemyTurn
from curry_quest.state_character import StateCharacterEvent, StateItemTrade, StateItemTradeAccepted, \
    StateItemTradeRejected, StateFamiliarTrade, StateFamiliarTradeAccepted, StateFamiliarTradeRejected, \
    StateEvolveFamiliar
from curry_quest.state_elevator import StateElevatorEvent, StateGoUp, StateElevatorOmitted, StateNextFloor,\
    StateElevatorUsed
from curry_quest.state_event import StateWaitForEvent, StateGenerateEvent
from curry_quest.state_familiar import StateFamiliarEvent, StateMetFamiliarIgnore, StateFamiliarFusion, \
    StateFamiliarReplacement
from curry_quest.state_initialize import StateInitialize, StateEnterTower
from curry_quest.state_item import StateItemEvent, StateItemPickUp, StateItemPickUpFullInventory, \
    StateItemPickUpIgnored, StateItemEventFinished
from curry_quest.state_machine_action import StateMachineAction
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.state_trap import StateTrapEvent
import logging
from curry_quest.statuses import Statuses
from curry_quest.jsonable import Jsonable, JsonReaderHelper, InvalidJson

logger = logging.getLogger(__name__)


class Transition:
    def __init__(self, nextState: StateBase, guard):
        self.nextState = nextState
        self.guard = guard

    @classmethod
    def _action_by_admin_guard(cls, action):
        return action.is_given_by_admin

    @classmethod
    def _no_guard(cls, action):
        return True

    @classmethod
    def by_admin(cls, nextState: StateBase):
        return Transition(nextState, guard=cls._action_by_admin_guard)

    @classmethod
    def by_user(cls, nextState):
        return Transition(nextState, guard=cls._no_guard)


class StateStart(StateBase):
    pass


class StateRestartByUser(StateBase):
    def on_enter(self):
        self._context.generate_action(commands.STARTED)


class StateGameOver(StateBase):
    pass


class StateMachine(Jsonable):
    VERSION = 3
    TRANSITIONS = {
        StateStart: {commands.STARTED: Transition.by_admin(StateInitialize)},
        StateRestartByUser: {commands.STARTED: Transition.by_admin(StateInitialize)},
        StateInitialize: {commands.ENTER_TOWER: Transition.by_user(StateEnterTower)},
        StateEnterTower: {commands.ENTERED_TOWER: Transition.by_admin(StateGenerateEvent)},
        StateWaitForEvent: {
            commands.GENERATE_EVENT: Transition.by_admin(StateGenerateEvent),
            commands.BATTLE_EVENT: Transition.by_admin(StateBattleEvent),
            commands.ITEM_EVENT: Transition.by_admin(StateItemEvent),
            commands.TRAP_EVENT: Transition.by_admin(StateTrapEvent),
            commands.CHARACTER_EVENT: Transition.by_admin(StateCharacterEvent),
            commands.ELEVATOR_EVENT: Transition.by_admin(StateElevatorEvent),
            commands.FAMILIAR_EVENT: Transition.by_admin(StateFamiliarEvent),
            commands.GO_UP: Transition.by_admin(StateGoUp)
        },
        StateGenerateEvent: {commands.EVENT_GENERATED: Transition.by_admin(StateWaitForEvent)},
        StateBattleEvent: {commands.START_BATTLE: Transition.by_admin(StateStartBattle)},
        StateStartBattle: {commands.BATTLE_PREPARE_PHASE: Transition.by_admin(StateBattlePreparePhase)},
        StateBattlePreparePhase: {
            commands.USE_ITEM: Transition.by_user(StateBattleUseItem),
            commands.APPROACH: Transition.by_user(StateBattleApproach),
            commands.BATTLE_PREPARE_PHASE_FINISHED: Transition.by_admin(StateBattlePhase)
        },
        StateBattleApproach: {commands.BATTLE_PREPARE_PHASE_FINISHED: Transition.by_admin(StateBattlePhase)},
        StateBattlePhase: {
            commands.PLAYER_TURN: Transition.by_admin(StateBattlePlayerTurn),
            commands.ENEMY_TURN: Transition.by_admin(StateBattleEnemyTurn),
            commands.SKIP_TURN: Transition.by_admin(StateBattlePhase),
            commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent),
            commands.YOU_DIED: Transition.by_admin(StateGameOver)
        },
        StateBattlePlayerTurn: {
            commands.ENEMY_STATS: Transition.by_user(StateEnemyStats),
            commands.SKIP_TURN: Transition.by_user(StateBattleSkipTurn),
            commands.ATTACK: Transition.by_user(StateBattleAttack),
            commands.USE_SPELL: Transition.by_user(StateBattleUseSpell),
            commands.USE_ITEM: Transition.by_user(StateBattleUseItem),
            commands.FLEE: Transition.by_user(StateBattleTryToFlee)
        },
        StateEnemyStats: {commands.PLAYER_TURN: Transition.by_admin(StateBattlePlayerTurn)},
        StateBattleSkipTurn: {commands.BATTLE_ACTION_PERFORMED: Transition.by_admin(StateBattlePhase)},
        StateBattleAttack: {commands.BATTLE_ACTION_PERFORMED: Transition.by_admin(StateBattlePhase)},
        StateBattleUseSpell: {
            commands.BATTLE_ACTION_PERFORMED: Transition.by_admin(StateBattlePhase),
            commands.CANNOT_USE_SPELL: Transition.by_admin(StateBattlePlayerTurn)
        },
        StateBattleUseItem: {
            commands.BATTLE_PREPARE_PHASE_ACTION_PERFORMED: Transition.by_admin(StateBattlePreparePhase),
            commands.BATTLE_ACTION_PERFORMED: Transition.by_admin(StateBattlePhase),
            commands.CANNOT_USE_ITEM_PREPARE_PHASE: Transition.by_admin(StateBattlePreparePhase),
            commands.CANNOT_USE_ITEM_BATTLE_PHASE: Transition.by_admin(StateBattlePlayerTurn)
        },
        StateBattleTryToFlee: {
            commands.CANNOT_FLEE: Transition.by_admin(StateBattlePlayerTurn),
            commands.BATTLE_ACTION_PERFORMED: Transition.by_admin(StateBattlePhase),
            commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)
        },
        StateBattleEnemyTurn: {commands.BATTLE_ACTION_PERFORMED: Transition.by_admin(StateBattlePhase)},
        StateItemEvent: {
            commands.ACCEPTED: Transition.by_user(StateItemPickUp),
            commands.REJECTED: Transition.by_user(StateItemEventFinished)
        },
        StateItemPickUp: {
            commands.ITEM_PICKED_UP: Transition.by_admin(StateItemEventFinished),
            commands.DROP_ITEM: Transition.by_user(StateItemPickUpFullInventory),
            commands.IGNORE: Transition.by_user(StateItemPickUpIgnored)
        },
        StateItemPickUpFullInventory: {commands.ITEM_PICKED_UP: Transition.by_admin(StateItemEventFinished)},
        StateItemPickUpIgnored: {commands.EVENT_FINISHED: Transition.by_admin(StateItemEventFinished)},
        StateItemEventFinished: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateTrapEvent: {
            commands.GO_UP: Transition.by_admin(StateGoUp),
            commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)
        },
        StateElevatorEvent: {
            commands.ACCEPTED: Transition.by_user(StateElevatorUsed),
            commands.REJECTED: Transition.by_user(StateElevatorOmitted)
        },
        StateElevatorUsed: {commands.GO_UP, Transition.by_admin(StateGoUp)},
        StateGoUp: {commands.ENTERED_NEXT_FLOOR: Transition.by_admin(StateNextFloor)},
        StateElevatorOmitted: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateNextFloor: {
            commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent),
            commands.FINISH_GAME: Transition.by_admin(StateGameOver)
        },
        StateCharacterEvent: {
            commands.START_ITEM_TRADE: Transition.by_admin(StateItemTrade),
            commands.START_FAMILIAR_TRADE: Transition.by_admin(StateFamiliarTrade),
            commands.EVOLVE_FAMILIAR: Transition.by_admin(StateEvolveFamiliar),
            commands.START_BATTLE: Transition.by_admin(StateStartBattle),
            commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)
        },
        StateItemTrade: {
            commands.TRADE_ITEM: Transition.by_user(StateItemTradeAccepted),
            commands.REJECTED: Transition.by_user(StateItemTradeRejected)
        },
        StateItemTradeAccepted: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateItemTradeRejected: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateFamiliarTrade: {
            commands.ACCEPTED: Transition.by_user(StateFamiliarTradeAccepted),
            commands.REJECTED: Transition.by_user(StateFamiliarTradeRejected)
        },
        StateFamiliarTradeAccepted: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateFamiliarTradeRejected: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateEvolveFamiliar: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateFamiliarEvent: {
            commands.IGNORE: Transition.by_user(StateMetFamiliarIgnore),
            commands.FUSE: Transition.by_user(StateFamiliarFusion),
            commands.REPLACE: Transition.by_user(StateFamiliarReplacement)
        },
        StateMetFamiliarIgnore: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateFamiliarFusion: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateFamiliarReplacement: {commands.EVENT_FINISHED: Transition.by_admin(StateWaitForEvent)},
        StateGameOver: {commands.RESTART: Transition.by_user(StateRestartByUser)}
    }

    def __init__(self, game_config: Config, player_id: int, player_name: str):
        self._context = StateMachineContext(game_config)
        self._player_id = player_id
        self._player_name = player_name
        self._last_responses = []
        self._state = StateStart(self._context)
        self._event_selection_penalty_end_dt = None
        self._generic_actions_handlers = {
            commands.HELP: (False, self._show_available_commands),
            commands.RESTART: (True, self._restart_state_machine),
            commands.SHOW_FAMILIAR_STATS: (False, self._handle_familiar_stats_query),
            commands.SHOW_INVENTORY: (False, self._handle_inventory_query),
            commands.SHOW_FLOOR: (False, self._handle_floor_query),
            commands.SHOW_STATE: (False, self._handle_state_query),
            commands.RECORDS: (False, self._handle_records_query),
            commands.HALL_OF_FAME: (False, lambda *args, **kwargs: None),
            commands.GIVE_ITEM: (True, self._give_item),
            commands.RESTORE_HP: (True, self._restore_hp),
            commands.RESTORE_MP: (True, self._restore_mp),
            commands.GIVE_FAMILIAR_SPELL: (True, self._give_familiar_spell),
            commands.GIVE_FAMILIAR_STATUS: (True, self._give_familiar_status),
            commands.GIVE_ENEMY_SPELL: (True, self._give_enemy_spell),
            commands.GIVE_ENEMY_STATUS: (True, self._give_enemy_status),
            commands.TURN_COUNTERS: (True, self._handle_turn_counters_query),
            commands.SET_FLOOR: (True, self._set_floor)
        }

    @property
    def player_id(self) -> int:
        return self._player_id

    @property
    def player_name(self) -> str:
        return self._player_name

    @player_name.setter
    def player_name(self, new_name) -> str:
        self._player_name = new_name

    def set_records_events_handler(self, new_records_events_handler):
        self._context.records_events_handler = new_records_events_handler

    def has_event_selection_penalty(self) -> bool:
        return self._event_selection_penalty_end_dt is not None

    def clear_event_selection_penalty(self):
        self._event_selection_penalty_end_dt = None

    def set_event_selection_penalty(self, duration_in_seconds):
        self._event_selection_penalty_end_dt = datetime.datetime.now() + datetime.timedelta(seconds=duration_in_seconds)

    @property
    def event_selection_penalty_end_dt(self) -> datetime.datetime:
        return self._event_selection_penalty_end_dt

    def to_json_object(self):
        return {
                'version': self.VERSION,
                'player_id': self.player_id,
                'player_name': self.player_name,
                'responses': self._last_responses,
                'context': self._context.to_json_object(),
                'state': self._state.to_json_object()
            }

    def from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        self._player_name = json_reader_helper.read_non_empty_string('player_name')
        self._last_responses = json_reader_helper.read_value_of_type_with_default('responses', list, default=[])
        self._context.from_json_object(json_reader_helper.read_value_of_type_with_default('context', dict, default={}))
        self._create_state_from_json_object(json_reader_helper.read_dict('state'))

    @classmethod
    def player_id_from_json_object(cls, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        return json_reader_helper.read_int_with_min('player_id', min_value=1)

    def _create_state_from_json_object(self, json_object):
        json_reader_helper = JsonReaderHelper(json_object)
        state_name = json_reader_helper.read_string('state_name')
        state_class = self._find_state_class(state_name)
        if state_class is None:
            raise InvalidJson(f'Unknown state "{state_name}". JSON object: {json_object}.')
        self._state = state_class.create_from_json_object(json_reader_helper, self._context)

    def _find_state_class(self, state_name):
        for state_class in self.TRANSITIONS.keys():
            if state_class.state_name() == state_name:
                return state_class
        return None

    def is_started(self) -> bool:
        return type(self._state) is not StateStart

    def is_finished(self) -> bool:
        return type(self._state) is StateGameOver

    def is_waiting_for_user_action(self) -> bool:
        return self._state.is_waiting_for_user_action()

    def is_waiting_for_event(self) -> bool:
        return self._state.is_waiting_for_event()

    def on_action(self, action):
        try:
            if not self._handle_generic_action(action):
                if self._handle_non_generic_action(action):
                    if self.is_finished():
                        self._context.add_response(f'Use command "{commands.RESTART}" to play again.')
                    self._last_responses = self._context.peek_responses()
        except InvalidOperation as exc:
            self._context.add_response(str(exc))
        return self._context.take_responses()

    def _handle_generic_action(self, action: StateMachineAction) -> bool:
        for command, (is_admin_command, handler) in self._generic_actions_handlers.items():
            if command == action.command:
                if not is_admin_command or action.is_given_by_admin:
                    handler(action)
                    return True
        else:
            return False

    def _show_available_commands(self, action: StateMachineAction):
        available_specific_commands = self._available_specific_commands(action.is_given_by_admin)
        if len(available_specific_commands) > 0:
            self._context.add_response(f"Specific commands: {', '.join(available_specific_commands)}.")
        available_generic_commands = self._available_generic_commands(action.is_given_by_admin)
        if len(available_generic_commands) > 0:
            self._context.add_response(f"Generic commands: {', '.join(available_generic_commands)}.")

    def _restart_state_machine(self, action):
        if action.is_given_by_admin:
            self._state = StateInitialize.create(self._context, action.args)
            logger.info(f"Restarted game for {self.player_id}.")
            self._state.on_enter()

    def _available_specific_commands(self, is_admin: bool):
        available_specific_commands = []
        for command, transition in self._current_state_transition_table().items():
            if transition.guard(StateMachineAction(command, is_given_by_admin=is_admin)):
                available_specific_commands.append(command)
        return available_specific_commands

    def _available_generic_commands(self, is_admin: bool):
        available_generic_commands = []
        for command, (is_admin_command, _) in self._generic_actions_handlers.items():
            if not is_admin_command or is_admin:
                available_generic_commands.append(command)
        return available_generic_commands

    def _handle_familiar_stats_query(self, action):
        if self._has_entered_tower():
            familiar = self._context.familiar
            self._context.add_response(f"{familiar.to_string()}.")
        else:
            self._handle_generic_action_before_entering_tower()

    def _handle_inventory_query(self, action):
        if self._has_entered_tower():
            inventory_string = ', '.join(self._context.inventory.items)
            self._context.add_response(f"You have: {inventory_string}.")
        else:
            self._handle_generic_action_before_entering_tower()

    def _handle_floor_query(self, action):
        if self._has_entered_tower():
            self._context.add_response(f"You are on {self._context.floor + 1}F.")
        else:
            self._handle_generic_action_before_entering_tower()

    def _handle_state_query(self, action):
        if not self.is_started():
            self._handle_generic_action_before_entering_tower()
        elif self.is_waiting_for_event():
            self._context.add_response(f"You are not in an event.")
        elif len(self._last_responses) == 0:
            self._context.add_response(f"There is no information about previous state.")
        else:
            for response in self._last_responses:
                self._context.add_response(response)

    def _handle_records_query(self, action):
        if not self.is_started():
            self._handle_generic_action_before_entering_tower()
        else:
            self._context.add_response("Records:")
            records = self._context.records
            self._context.add_response(f"  Turns in tower: {records.turns_counter}")
            self._context.add_response(f"  Used elevators: {records.used_elevators_counter}")

    def _give_item(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        item = self._find_item(*action.args)
        if item is None:
            logger.warning(f"Item by name '{' '.join(action.args)}' does not exist.")
            return
        self._context.inventory.add_item(item)
        self._context.add_response(f"You were given {item.name} by an unknown power.")

    def _find_item(self, *item_name_parts):
        if len(item_name_parts) < 1:
            return None
        searched_item_name = normalize_item_name(*item_name_parts)
        for item in all_items():
            if normalize_item_name(item.name).startswith(searched_item_name):
                return item
        return None

    def _restore_hp(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        self._context.familiar.restore_hp()
        self._context.add_response(f"Your HP was restored by an unknown power.")

    def _restore_mp(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        self._context.familiar.restore_mp()
        self._context.add_response(f"Your MP was restored by an unknown power.")

    def _give_familiar_spell(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        self._give_spell(action, self._context.familiar, 'You were')

    def _give_enemy_spell(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        if not self._context.is_in_battle():
            logger.warning(f"{self.player_id} is not in battle.")
            return
        enemy = self._context.battle_context.enemy
        self._give_spell(action, enemy, f'{enemy.name.capitalize()} was')

    def _give_spell(self, action, target_unit, response_prefix):
        try:
            spell_traits = self._parse_give_spell_action_spell(action, target_unit)
            spell_level = self._parse_give_spell_action_spell_level(action, target_unit)
        except InvalidOperation as exc:
            logger.warning(''.join(exc.args))
            return
        target_unit.set_spell(spell_traits, spell_level)
        self._context.add_response(
            f"{response_prefix} given level {spell_level} {spell_traits.name} spell by an unknown power.")

    def _parse_give_spell_action_spell(self, action, target_unit):
        if len(action.args) < 1:
            raise InvalidOperation(f"Not enough arguments.")
        spell_base_name = action.args[0]
        try:
            return Spells.find_spell_traits(spell_base_name, target_unit.genus)
        except ValueError as exc:
            raise InvalidOperation(exc.args)

    def _parse_give_spell_action_spell_level(self, action, target_unit):
        if len(action.args) > 1:
            spell_level_string = action.args[1]
            try:
                return int(spell_level_string)
            except ValueError:
                raise InvalidOperation(f"'{spell_level_string}' is not valid spell level.")
        else:
            return target_unit.level

    def _give_familiar_status(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        self._give_status(action, self._context.familiar, 'You were')

    def _give_enemy_status(self, action):
        if not self._has_entered_tower():
            logger.warning(f"{self.player_id} has not entered the tower yet.")
            return
        if not self._context.is_in_battle():
            logger.warning(f"{self.player_id} is not in battle.")
            return
        enemy = self._context.battle_context.enemy
        self._give_status(action, enemy, f'{enemy.name.capitalize()} was')

    def _give_status(self, action, target_unit, response_prefix):
        status = self._parse_give_status_action_status(action)
        response = f'{response_prefix} given {status.name} status'
        if len(action.args) == 1:
            target_unit.set_status(status)
        else:
            status_duration = self._parse_give_status_action_status_duration(action)
            target_unit.set_timed_status(status, status_duration)
            response += f' for {status_duration} turns'
        response += ' by an unknown power.'
        self._context.add_response(response)

    def _parse_give_status_action_status(self, action):
        if len(action.args) < 1:
            raise InvalidOperation(f"Not enough arguments.")
        status_name = action.args[0]
        try:
            return Statuses[status_name]
        except KeyError:
            raise InvalidOperation(f"'{status_name}' is not valid status.")

    def _parse_give_status_action_status_duration(self, action):
        status_duration_string = action.args[1]
        try:
            return int(status_duration_string)
        except ValueError:
            raise InvalidOperation(f"'{status_duration_string}' is not valid duration.")

    def _handle_turn_counters_query(self, action):
        if self._has_entered_tower():
            response = f'Floor turns counter: {self._context.floor_turns_counter}.\n'
            response += f'Earthquake: '
            turns_until_eq = self._context.turns_until_earthquake()
            response += 'done' if turns_until_eq <= 0 else f'in {turns_until_eq} turns.'
            response += f'\nFloor collapse: in {self._context.turns_until_floor_collapse()} turns.'
            self._context.add_response(response)
        else:
            self._handle_generic_action_before_entering_tower()

    def _set_floor(self, action):
        if not self._has_entered_tower():
            self._handle_generic_action_before_entering_tower()
            return
        floor = self._parse_floor(action)
        self._context.floor = floor
        self._context.add_response(f'You were teleported to {floor + 1}F by an unknown power.')

    def _parse_floor(self, action):
        if len(action.args) < 1:
            raise InvalidOperation(f"Not enough arguments.")
        floor_string = action.args[0]
        try:
            floor = int(floor_string)
        except ValueError:
            raise InvalidOperation(f"'{floor_string}' is not valid floor.")
        floor -= 1
        highest_floor = self._context.game_config.highest_floor
        if floor < 0 or floor > highest_floor:
            raise InvalidOperation(f'Floor must be in range [1, {highest_floor + 1}].')
        return floor

    def _handle_generic_action_before_entering_tower(self):
        self._context.add_response(f"You did not enter the tower yet.")

    def _has_entered_tower(self) -> bool:
        return self.is_started() and type(self._state) is not StateInitialize

    def _handle_non_generic_action(self, action):
        state_transition_table = self._current_state_transition_table()
        if state_transition_table is None:
            self._on_unknown_state()
            return False
        transition = state_transition_table.get(action.command)
        if transition is None:
            self._on_unexpected_action(action)
            return False
        else:
            self._change_state(transition, action)
            if self._context.has_action():
                self._handle_non_generic_action(self._context.take_action())
            return True

    def _current_state_transition_table(self) -> dict:
        return self.TRANSITIONS.get(type(self._state))

    def _on_unknown_state(self):
        logger.error(f"{self} is in state {self._state} for which there is no transition.")
        self._context.add_response(f'{self._state} does not have any transitions.')

    def _on_unexpected_action(self, action):
        logger.warning(f"{self} in state {self._state} does not have transition for '{action.command}'")
        self._context.add_response(f'Unknown command "{action.command}".')

    def _change_state(self, transition, action):
        if transition.guard(action):
            self._state = transition.nextState.create(self._context, action.args)
            logger.debug(f"{self} changed state to {self._state}.")
            self._state.on_enter()

    def __str__(self):
        return f'SM for "{self.player_id}"'
