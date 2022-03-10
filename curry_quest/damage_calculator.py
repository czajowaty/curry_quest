import enum
from curry_quest.genus import Genus
from curry_quest.statuses import Statuses


class DamageCalculator:
    class DamageRoll(enum.Enum):
        Low = 0
        Normal = 1
        High = 2

    class RelativeHeight(enum.Enum):
        Lower = -1
        Same = 0
        Higher = 1

        def opposite(self) -> '__class__':
            if self is DamageCalculator.RelativeHeight.Lower:
                return DamageCalculator.RelativeHeight.Higher
            elif self is DamageCalculator.RelativeHeight.Higher:
                return DamageCalculator.RelativeHeight.Lower
            else:
                return DamageCalculator.RelativeHeight.Same

    GENUS_PROTECTION_STATUS_MAPPING = {
        Genus.Fire: Statuses.WaterProtection,
        Genus.Water: Statuses.WindProtection,
        Genus.Wind: Statuses.FireProtection
    }

    def __init__(self, attacker, defender):
        self._attacker = attacker
        self._defender = defender

    def physical_damage(self, damage_roll: DamageRoll, relative_height: RelativeHeight, is_critical: bool) -> int:
        base_damage = 2 * self._attacker.attack + damage_roll.value
        combat_advantage = relative_height.value
        if self._does_defender_has_elemental_protection_against_attacker():
            base_damage //= 4
        else:
            combat_advantage += self._physical_elemental_combat_advantage()
        damage_dealt = base_damage + (base_damage * combat_advantage // 8) - self._base_defense()
        damage_dealt = int(damage_dealt / 2 * self._critical_hit_multiplier(is_critical))
        return max(damage_dealt, 1)

    def spell_damage(self, raw_spell_damage) -> int:
        spell = self._attacker.spell
        base_damage = (raw_spell_damage + spell.level) * 2
        if self._does_defender_has_elemental_protection_against_attacker():
            base_damage //= 4
            combat_damage = 0
        else:
            combat_damage = self._spell_combat_damage(base_damage)
        damage_dealt = int((base_damage + combat_damage - self._base_defense()) // 2)
        return max(damage_dealt, 1)

    def _does_defender_has_elemental_protection_against_attacker(self):
        necessary_protection_status = self.GENUS_PROTECTION_STATUS_MAPPING.get(self._attacker.genus)
        if necessary_protection_status is not None:
            return self._defender.has_status(necessary_protection_status)
        else:
            return False

    def _base_defense(self):
        return self._defender.defense

    def _physical_elemental_combat_advantage(self):
        if self._attacker.genus.is_strong_against(self._defender.genus):
            return 1
        elif self._attacker.genus.is_weak_against(self._defender.genus):
            return -2
        else:
            return 0

    def _spell_combat_damage(self, base_damage):
        combat_advantage = self._spell_combat_advantage()
        combat_damage = base_damage * combat_advantage
        if combat_advantage < 0:
            combat_damage = (combat_damage + 3) // 4
        return combat_damage

    def _spell_combat_advantage(self):
        if self._attacker.genus.is_strong_against(self._defender.genus):
            return 1
        elif self._attacker.genus.is_weak_against(self._defender.genus):
            return -1
        else:
            return 0

    def _critical_hit_multiplier(self, is_critical: bool) -> float:
        return 1.5 if is_critical else 1.0
