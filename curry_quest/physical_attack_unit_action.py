from curry_quest.damage_calculator import DamageCalculator
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.words import Words
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext, MpRequiringActionHandler

DamageRoll = DamageCalculator.DamageRoll
RelativeHeight = DamageCalculator.RelativeHeight


class PhysicalAttackExecuter:
    def __init__(self, unit_action_context: UnitActionContext):
        from curry_quest.state_machine_context import StateMachineContext

        self._unit_action_context = unit_action_context
        self._state_machine_context: StateMachineContext = unit_action_context.state_machine_context

    @property
    def attacker(self) -> Unit:
        return self._unit_action_context.performer

    @property
    def defender(self) -> Unit:
        return self._unit_action_context.target

    @property
    def _context(self):
        return self._state_machine_context

    @property
    def attacker_words(self) -> Words:
        return self._unit_action_context.performer_words

    @property
    def defender_words(self) -> Words:
        return self._unit_action_context.target_words

    def execute(self) -> str:
        if not self._unit_action_context.has_target():
            return self._no_target_response()
        if not self._is_attack_accurate():
            return self._miss_response()
        attack_descriptor = self._perform_attack()
        response = self._hit_response(attack_descriptor)
        if self.defender.talents.has(Talents.ElectricShock):
            damage, _, _ = attack_descriptor
            response += ' '
            response += self._deal_shock_damage(damage)
        return response

    def _no_target_response(self):
        attacker_words = self.attacker_words
        return f'{attacker_words.name} {attacker_words.s_verb("attack")} in opposite direction hitting ' \
            'nothing but air.'

    def _is_attack_accurate(self):
        if self.attacker.luck <= 0:
            return False
        else:
            hit_chance = (self.attacker.luck - 1) / self.attacker.luck
            if self.attacker.has_status(Statuses.Blind):
                hit_chance /= 2
            return self._context.does_action_succeed(success_chance=hit_chance)

    def _miss_response(self):
        attacker_words = self.attacker_words
        defender_words = self.defender_words
        return f'{attacker_words.name.capitalize()} {attacker_words.ies_verb("try")} to hit {defender_words.name}, ' \
            f'but {defender_words.pronoun} {defender_words.s_verb("dodge")} swiftly.'

    def _select_damage_roll(self) -> DamageRoll:
        return self._context.rng.choices([DamageRoll.Low, DamageRoll.Normal, DamageRoll.High], weights=[1, 2, 1])[0]

    def _select_relative_height(self) -> RelativeHeight:
        def unit_height(unit: Unit):
            unit_height = 0
            if unit.has_status(Statuses.Crack):
                unit_height -= 1
            if unit.has_status(Statuses.Upheaval):
                unit_height += 1
            return unit_height

        attacker_height = unit_height(self.attacker)
        defender_height = unit_height(self.defender)
        relative_height = attacker_height - defender_height
        if relative_height > 0:
            return RelativeHeight.Higher
        elif relative_height < 0:
            return RelativeHeight.Lower
        else:
            return RelativeHeight.Same

    def _select_whether_attack_is_critical(self) -> bool:
        divider = 2 if self.attacker.talents.has(Talents.Atrocious) else 64
        crit_chance = (self.attacker.luck // divider + 1) / 128
        return self._context.does_action_succeed(success_chance=crit_chance)

    def _perform_attack(self):
        damage_calculator = DamageCalculator(self.attacker, self.defender)
        relative_height = self._select_relative_height()
        is_critical = self._select_whether_attack_is_critical()
        damage = damage_calculator.physical_damage(self._select_damage_roll(), relative_height, is_critical)
        self.defender.deal_damage(damage)
        return damage, relative_height, is_critical

    def _hit_response(self, physical_attack_descriptor):
        damage, relative_height, is_critical = physical_attack_descriptor
        attacker_words = self.attacker_words
        defender_words = self.defender_words
        response = f'{attacker_words.name.capitalize()} {attacker_words.s_verb("hit")} '
        if is_critical:
            response += 'hard '
        if relative_height is RelativeHeight.Higher:
            response += 'from above '
        elif relative_height is RelativeHeight.Lower:
            response += 'from below '
        response += f'dealing {damage} damage. {defender_words.name.capitalize()} {defender_words.have_verb}' \
            f' {self.defender.hp} HP left.'
        return response

    def _deal_shock_damage(self, original_damage):
        shock_damage = max(original_damage // 4, 1)
        self.attacker.deal_damage(shock_damage)
        attacker_words = self.attacker_words
        return f'An electrical shock runs through {attacker_words.possessive_name} body dealing ' \
            f'{shock_damage} damage. {attacker_words.name.capitalize()} {attacker_words.have_verb} ' \
            f'{self.attacker.hp} HP left.'


class PhysicalAttackUnitActionHandler(MpRequiringActionHandler):
    def select_target(self, performer: Unit, other_unit: Unit) -> Unit:
        return other_unit

    def can_target_self(self) -> bool:
        return False

    def can_target_other_unit(self) -> bool:
        return True

    def can_have_no_target(self) -> bool:
        return True

    def can_perform(self, unit_action_context: UnitActionContext) -> tuple[bool, str]:
        return super().can_perform(unit_action_context)

    def perform(self, unit_action_context: UnitActionContext) -> str:
        super().perform(unit_action_context)
        return PhysicalAttackExecuter(unit_action_context).execute()
