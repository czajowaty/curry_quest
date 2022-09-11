from curry_quest.damage_calculator import DamageCalculator
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents
from curry_quest.words import Words
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext

DamageRoll = DamageCalculator.DamageRoll
RelativeHeight = DamageCalculator.RelativeHeight


class PhysicalAttackExecutor:
    def __init__(self, unit_action_context: UnitActionContext):
        from curry_quest.state_machine_context import StateMachineContext

        self._unit_action_context = unit_action_context
        self._state_machine_context: StateMachineContext = unit_action_context.state_machine_context
        self._weapon_damage = 0
        self._guaranteed_critical = False

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

    def set_weapon_damage(self, weapon_damage):
        self._weapon_damage = weapon_damage

    def set_guaranteed_critical(self):
        self._guaranteed_critical = True

    def execute(self) -> str:
        if not self._unit_action_context.has_target():
            return self._no_target_response()
        if not self._is_attack_accurate():
            return self._miss_response()
        relative_height = self._select_relative_height()
        if self.defender.has_status(Statuses.Invincible):
            return self._invincible_target_response()
        damage, is_critical = self._perform_attack(relative_height)
        response = self._hit_response_prefix(relative_height, is_critical)
        response += self._hit_damage_response(damage)
        if self.defender.talents.has(Talents.ElectricShock):
            response += ' '
            response += self._deal_shock_damage(damage)
        response += self._handle_potential_debuffs_recovery()
        return response

    def _no_target_response(self):
        attacker_words = self.attacker_words
        return f'{attacker_words.name.capitalize()} {attacker_words.s_verb("attack")} in opposite direction hitting ' \
            'nothing but air.'

    def _is_attack_accurate(self):
        if self.attacker.luck <= 0:
            return False
        else:
            hit_chance = (self.attacker.luck - 1) / self.attacker.luck
            if self.attacker.has_status(Statuses.Blind):
                hit_chance /= 2
            if self.defender.has_status(Statuses.Invisible):
                hit_chance /= 2
            return self._context.does_action_succeed(success_chance=hit_chance)

    def _miss_response(self):
        attacker_words = self.attacker_words
        defender_words = self.defender_words
        return f'{attacker_words.name.capitalize()} {attacker_words.ies_verb("try")} to hit {defender_words.name}, ' \
            f'but {defender_words.pronoun} {defender_words.s_verb("dodge")} swiftly.'

    def _invincible_target_response(self):
        attacker_words = self.attacker_words
        return f'{attacker_words.name.capitalize()} {attacker_words.ies_verb("try")} attacking, but it has no effect.'

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
        if self._guaranteed_critical:
            return True
        divider = 2 if self.attacker.talents.has(Talents.Atrocious) else 64
        crit_chance = (self.attacker.luck // divider + 1) / 128
        return self._context.does_action_succeed(success_chance=crit_chance)

    def _perform_attack(self, relative_height: RelativeHeight):
        damage_calculator = DamageCalculator(self.attacker, self.defender)
        is_critical = self._select_whether_attack_is_critical()
        damage = damage_calculator.physical_damage(
            self._select_damage_roll(),
            relative_height,
            is_critical,
            self._weapon_damage)
        self.defender.deal_damage(damage)
        return damage, is_critical

    def _hit_response_prefix(self, relative_height: RelativeHeight, is_critical: bool):
        attacker_words = self.attacker_words
        response = f'{attacker_words.name.capitalize()} {attacker_words.s_verb("hit")} '
        if is_critical:
            response += 'hard '
        if relative_height is RelativeHeight.Higher:
            response += 'from above '
        elif relative_height is RelativeHeight.Lower:
            response += 'from below '
        return response

    def _hit_damage_response(self, damage: int):
        defender_words = self.defender_words
        return f'dealing {damage} damage. {defender_words.name.capitalize()} {defender_words.have_verb}' \
            f' {self.defender.hp} HP left.'

    def _deal_shock_damage(self, original_damage):
        shock_damage = max(original_damage // 4, 1)
        self.attacker.deal_damage(shock_damage)
        attacker_words = self.attacker_words
        return f'An electrical shock runs through {attacker_words.possessive_name} body dealing ' \
            f'{shock_damage} damage. {attacker_words.name.capitalize()} {attacker_words.have_verb} ' \
            f'{self.attacker.hp} HP left.'

    def _handle_potential_debuffs_recovery(self):
        response = ''
        for status, prepare_recovery_response in [
                (Statuses.Sleep, self._sleep_recovery_response),
                (Statuses.Paralyze, self._paralyze_recovery_response),
                (Statuses.Confuse, self._confuse_recovery_response)]:
            if self.defender.has_status(status) and self._context.does_action_succeed(0.25):
                self.defender.clear_status(status)
                response += '\n'
                response += prepare_recovery_response()
        return response

    def _sleep_recovery_response(self):
        defender_words = self.defender_words
        return f'{defender_words.name.capitalize()} {defender_words.s_verb("wake")} up.'

    def _paralyze_recovery_response(self):
        defender_words = self.defender_words
        return f'{defender_words.possessive_name.capitalize()} paralysis wears off.'

    def _confuse_recovery_response(self):
        defender_words = self.defender_words
        return f'{defender_words.name.capitalize()} {defender_words.be_verb} no longer confused.'
