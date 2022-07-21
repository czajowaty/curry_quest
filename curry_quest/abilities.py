from abc import abstractmethod
from curry_quest.ability import Ability
from curry_quest.unit_action import UnitActionContext
from curry_quest.physical_attack_unit_action import PhysicalAttackExecutor
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents


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
        target = action_context.target
        if self._is_target_immune(target):
            return self._response_when_target_is_immune(action_context)
        self._apply_status_to_target(target)
        return self._create_use_response(action_context)

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

    def _create_use_response(self, action_context: UnitActionContext) -> str:
        target_words = action_context.target_words
        return f'{target_words.name.capitalize()} {target_words.be_verb} confused.'
