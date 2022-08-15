from abc import abstractmethod
from curry_quest.ability import Ability
from curry_quest.unit_action import UnitActionContext
from curry_quest.physical_attack_unit_action import PhysicalAttackExecutor
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.errors import InvalidOperation


class BreakObstaclesAbility(Ability):
    @property
    def name(self):
        return 'Break obstacles'

    @property
    def mp_cost(self):
        return 4

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        physical_attack_executer = PhysicalAttackExecutor(action_context)
        physical_attack_executer.set_weapon_damage(int(action_context.performer.attack * 1.5))
        return physical_attack_executer.execute()


class ActionSuccessJudge:
    @abstractmethod
    def does_action_succeed(self, action_context: UnitActionContext) -> bool: pass

    @abstractmethod
    def create_action_failed_response(self, action_context: UnitActionContext) -> str: pass


class AlwaysSucceedsSuccessJudge(ActionSuccessJudge):
    def does_action_succeed(self, action_context: UnitActionContext) -> bool:
        return True


class StaticChanceSuccessJudge(ActionSuccessJudge):
    def __init__(self, chance: float):
        self._chance = chance

    def does_action_succeed(self, action_context: UnitActionContext) -> bool:
        return action_context.state_machine_context.does_action_succeed(self._chance)


class AbilityWithSuccessChance(Ability):
    def __init__(self, action_success_judge: ActionSuccessJudge):
        self._action_success_judge = action_success_judge

    def use(self, action_context) -> str:
        if not self._action_success_judge.does_action_succeed(action_context):
            return 'It has no effect.'
        return self._apply_ability_effect(action_context)

    @abstractmethod
    def _apply_ability_effect(self, action_context: UnitActionContext) -> str: pass


class ApplyStatusAbility(AbilityWithSuccessChance):
    def __init__(
            self,
            action_success_judge: ActionSuccessJudge,
            status: Statuses,
            protective_talent: Talents=Talents.Empty):
        super().__init__(action_success_judge)
        self._status = status
        self._protective_talent = protective_talent

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def _apply_ability_effect(self, action_context: UnitActionContext) -> str:
        if not action_context.has_target():
            return self._create_no_target_response(action_context)
        target = action_context.target
        if self._is_target_immune(target):
            return self._response_when_target_is_immune(action_context)
        self._apply_status_to_target(target)
        return self._create_use_response(action_context)

    @abstractmethod
    def _create_no_target_response(self, action_context: UnitActionContext) -> str: pass

    def _is_target_immune(self, target) -> bool:
        if self._protective_talent is Talents.Empty:
            return False
        return target.talents.has_any(self._protective_talent)

    def _response_when_target_is_immune(self, action_context):
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} immune.'

    def _apply_status_to_target(self, target):
        target.set_status(self._status)

    @abstractmethod
    def _create_use_response(self, action_context: UnitActionContext) -> str: pass


class ApplyTimedStatusAbility(ApplyStatusAbility):
    def __init__(
            self,
            action_success_judge: ActionSuccessJudge,
            status: Statuses,
            duration: int,
            protective_talent: Talents=Talents.Empty):
        super().__init__(action_success_judge, status, protective_talent)
        self._duration = duration

    def _apply_status_to_target(self, target):
        target.set_timed_status(self._status, self._duration)


class PlayTheFluteAbility(ApplyStatusAbility):
    def __init__(self):
        super().__init__(
            action_success_judge=AlwaysSucceedsSuccessJudge(),
            status=Statuses.Seal,
            protective_talent=Talents.SpellProof)

    @property
    def name(self):
        return 'Play the flute'

    @property
    def mp_cost(self):
        return 4

    def _create_no_target_response(self, action_context: UnitActionContext) -> str:
        return 'It has no effect.'

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.possessive_name.capitalize()} magic is sealed.'


class HypnotismAbility(ApplyTimedStatusAbility):
    def __init__(self):
        super().__init__(
            action_success_judge=StaticChanceSuccessJudge(0.5),
            status=Statuses.Sleep,
            duration=16,
            protective_talent=Talents.SleepProof)

    @property
    def name(self):
        return 'Hypnotism'

    @property
    def mp_cost(self):
        return 12

    def _create_no_target_response(self, action_context: UnitActionContext) -> str:
        return 'It has no effect.'

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} put to sleep.'


class BrainwashAbility(ApplyTimedStatusAbility):
    def __init__(self):
        super().__init__(
            action_success_judge=StaticChanceSuccessJudge(0.25),
            status=Statuses.Confuse,
            duration=16,
            protective_talent=Talents.Unbrainwashable)

    @property
    def name(self):
        return 'Brainwash'

    @property
    def mp_cost(self):
        return 16

    def _create_no_target_response(self, action_context: UnitActionContext) -> str:
        return 'It has no effect.'

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} confused.'


class BarkLoudlyAbility(ApplyTimedStatusAbility):
    def __init__(self):
        super().__init__(
            action_success_judge=StaticChanceSuccessJudge(0.125),
            status=Statuses.Paralyze,
            duration=4,
            protective_talent=Talents.BarkProof | Talents.ParalysisProof)

    @property
    def name(self):
        return 'Bark loudly'

    @property
    def mp_cost(self):
        return 8

    def _create_no_target_response(self, action_context: UnitActionContext) -> str:
        return 'It has no effect.'

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} paralyzed.'


class SpinAbility(ApplyTimedStatusAbility):
    def __init__(self):
        super().__init__(
            action_success_judge=StaticChanceSuccessJudge(0.25),
            status=Statuses.Confuse,
            duration=4,
            protective_talent=Talents.ConfusionProof)

    @property
    def name(self):
        return 'Spin'

    @property
    def mp_cost(self):
        return 8

    def _create_no_target_response(self, action_context: UnitActionContext) -> str:
        return 'It has no effect.'

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} confused.'


class DisappearAbility(ApplyTimedStatusAbility):
    def __init__(self):
        super().__init__(
            action_success_judge=AlwaysSucceedsSuccessJudge(),
            status=Statuses.Invisible,
            duration=8)

    @property
    def name(self):
        return 'Disappear'

    @property
    def mp_cost(self):
        return 8

    def select_target(self, user, other_unit):
        return user

    def can_target_self(self) -> bool:
        return True

    def can_target_other_unit(self) -> bool:
        return False

    def can_have_no_target(self) -> bool:
        return False

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        if action_context.target.has_status(Statuses.Invisible):
            target_words = action_context.target_words
            return False, f'{target_words.name.capitalize()} already {target_words.be_verb} invisible.'
        return True, ''

    def _create_no_target_response(self, action_context: UnitActionContext) -> str:
        raise InvalidOperation(f'{self.__class__.__name__}.{self._create_no_target_response}')

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.s_verb("disappear")}.'


class GetSeriousAbility(Ability):
    @property
    def name(self):
        return 'Get serious'

    @property
    def mp_cost(self):
        return 16

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        physical_attack_executer = PhysicalAttackExecutor(action_context)
        physical_attack_executer.set_guaranteed_critical()
        return physical_attack_executer.execute()


class AbductAbility(Ability):
    @property
    def name(self):
        return 'Abduct'

    @property
    def mp_cost(self):
        return 8

    def select_target(self, user, other_unit):
        return user

    def can_target_self(self)->bool:
        return True

    def can_target_other_unit(self) -> bool:
        return False

    def can_have_no_target(self) -> bool:
        return False

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        if not action_context.is_used_by_familiar():
            return False, 'Can only be used by familiar.'
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        battle_context = action_context.state_machine_context.battle_context
        battle_context.finish_battle()
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.s_verb("teleport")} away from the battle.'


class ChargedPunchAbility(Ability):
    @property
    def name(self):
        return 'Charged punch'

    @property
    def mp_cost(self):
        return 8

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        physical_attack_executer = PhysicalAttackExecutor(action_context)
        physical_attack_executer.set_weapon_damage(8)
        return physical_attack_executer.execute()


class FlyAbility(Ability):
    @property
    def name(self):
        return 'Fly'

    @property
    def mp_cost(self):
        return 16

    def select_target(self, user, other_unit):
        return user

    def can_target_self(self) -> bool:
        return True

    def can_target_other_unit(self) -> bool:
        return False

    def can_have_no_target(self) -> bool:
        return False

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        if not action_context.is_used_by_familiar():
            return False, 'Can only be used by familiar.'
        user_level = action_context.performer.level
        floor = action_context.state_machine_context.floor
        if floor >= user_level:
            return False, 'Too low level.'
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        battle_context = action_context.state_machine_context.battle_context
        battle_context.finish_battle()
        action_context.state_machine_context.set_go_up_on_next_event_finished_flag()
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.ies_verb("fly")} up to the next floor.'


class StealAbility(Ability):
    @property
    def name(self):
        return 'Steal'

    @property
    def mp_cost(self):
        return 2

    def select_target(self, user, other_unit):
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_use(self, action_context: UnitActionContext) -> tuple[bool, str]:
        return True, ''

    def use(self, action_context: UnitActionContext) -> str:
        if not action_context.has_target():
            return self._no_target_response(action_context)
        if action_context.is_used_by_familiar():
            return self._steal_from_enemy(action_context)
        else:
            return self._steal_from_familiar(action_context)

    def _no_target_response(self, action_context: UnitActionContext):
        return 'It has no effect.'

    def _steal_from_enemy(self, action_context: UnitActionContext) -> str:
        return self._nothing_to_steal_response(action_context)

    def _nothing_to_steal_response(self, action_context: UnitActionContext):
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.have_verb} nothing to steal.'

    def _steal_from_familiar(self, action_context: UnitActionContext) -> str:
        inventory = action_context.state_machine_context.inventory
        if inventory.is_empty():
            return self._nothing_to_steal_response(action_context)
        selected_item_slot = action_context.rng.randrange(inventory.capacity)
        if selected_item_slot >= inventory.size:
            return self._steal_failed_response(action_context)
        stolen_item = inventory.take_item(selected_item_slot)
        action_context.state_machine_context.battle_context.finish_battle()
        return self._steal_succeeded_response(action_context, stolen_item)

    def _steal_failed_response(self, action_context: UnitActionContext) -> str:
        performer_words = action_context.performer_words
        return f'{performer_words.name.capitalize()} {performer_words.s_verb("fail")} to steal anything.'

    def _steal_succeeded_response(self, action_context: UnitActionContext, stolen_item):
        performer_words = action_context.performer_words
        return f'{performer_words.name.capitalize()} {performer_words.s_verb("steal")} {stolen_item.name} and ' \
            f'{performer_words.s_verb("run")} away.'
