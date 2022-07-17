import unittest
from unittest.mock import create_autospec
from curry_quest.config import Config
from curry_quest.genus import Genus
from curry_quest.levels_config import Levels
from curry_quest.spell_cast_unit_action import SpellCastContext, SpellCastActionHandler
from curry_quest.spell_handler import SpellHandler
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.spell_traits import SpellTraits
from curry_quest.statuses import Statuses
from curry_quest.unit import Unit
from curry_quest.unit_traits import UnitTraits


class SpellCastActionHandlerTest(unittest.TestCase):
    def setUp(self):
        self._familiar = Unit(UnitTraits(), Levels())
        self._familiar.name = 'familiar'
        self._familiar.mp = 10
        self._enemy = Unit(UnitTraits(), Levels())
        self._enemy.name = 'enemy'
        self._enemy.mp = 10
        self._spell_handler = create_autospec(spec=SpellHandler)
        self._spell_handler.can_cast.return_value = True, ''
        self._state_machine_context = StateMachineContext(Config())
        self._state_machine_context.familiar = self._familiar
        self._spell_traits = SpellTraits()
        self._spell_traits.name = 'test_spell'
        self._spell_traits.handler = self._spell_handler
        self._spell_traits.mp_cost = 4
        self._spell_cast_context = SpellCastContext(spell_level=1)
        self._spell_cast_context.performer = self._familiar
        self._spell_cast_context.target = self._enemy
        self._spell_cast_context.reflected_target = self._familiar
        self._spell_cast_context.state_machine_context = self._state_machine_context
        self._sut = SpellCastActionHandler(self._spell_traits)

    def test_select_target_forwards_call_to_spell_handler(self):
        self._spell_handler.select_target.return_value = self._familiar
        self.assertEqual(self._sut.select_target(performer=self._familiar, other_unit=self._enemy), self._familiar)
        self._spell_handler.select_target.assert_called_with(self._familiar, self._enemy)

    def test_can_target_self_forwards_call_to_spell_handler(self):
        self._spell_handler.can_target_self.return_value = False
        self.assertFalse(self._sut.can_target_self())
        self._spell_handler.can_target_self.assert_called()

    def test_can_target_other_unit_forwards_call_to_spell_handler(self):
        self._spell_handler.can_target_other_unit.return_value = False
        self.assertFalse(self._sut.can_target_other_unit())
        self._spell_handler.can_target_other_unit.assert_called()

    def test_can_have_no_target_returns_True(self):
        self.assertTrue(self._sut.can_have_no_target())

    def _set_familiar_as_caster(self):
        self._familiar.set_spell(self._spell_traits, level=1)
        self._spell_cast_context.performer = self._familiar
        self._spell_cast_context.target = self._enemy
        self._spell_cast_context.reflected_target = self._familiar

    def _set_enemy_as_caster(self):
        self._enemy.set_spell(self._spell_traits, level=1)
        self._spell_cast_context.performer = self._enemy
        self._spell_cast_context.target = self._familiar
        self._spell_cast_context.reflected_target = self._enemy

    def _call_can_perform(self):
        return self._sut.can_perform(self._spell_cast_context)

    def _test_spell_can_be_casted(self):
        can_cast, _ = self._call_can_perform()
        self.assertTrue(can_cast)

    def _test_spell_cannot_be_casted(self, expected_reason=None):
        can_cast, reason = self._call_can_perform()
        self.assertFalse(can_cast)
        if expected_reason is not None:
            self.assertEqual(reason, expected_reason)

    def test_action_cannot_be_performed_when_unit_does_not_have_enough_mp(self):
        self._set_familiar_as_caster()
        self._familiar.mp = 3
        self._test_spell_cannot_be_casted('You do not have enough MP.')

    def test_familiar_action_cannot_be_performed_when_familiar_has_seal_status(self):
        self._set_familiar_as_caster()
        self._familiar.set_status(Statuses.Seal)
        self._test_spell_cannot_be_casted('Your magic is sealed.')

    def test_enemy_action_cannot_be_performed_when_enemy_has_seal_status(self):
        self._set_enemy_as_caster()
        self._enemy.set_status(Statuses.Seal)
        self._test_spell_cannot_be_casted('Enemy\'s magic is sealed.')

    def _test_spell_cast(self, caster=None, target=None, reflected_target=None, spell_cast_response: str=''):
        recorded_caster = None
        recorded_target = None

        def record_caster_and_target(spell_cast_context: SpellCastContext):
            nonlocal recorded_caster
            nonlocal recorded_target
            recorded_caster = spell_cast_context.performer  # @UnusedVariable
            recorded_target = spell_cast_context.target  # @UnusedVariable
            return spell_cast_response

        self._spell_cast_context.performer = caster or self._familiar
        self._spell_cast_context.target = target or self._enemy
        self._spell_cast_context.reflected_target = reflected_target or self._familiar
        self._spell_handler.select_target.return_value = target
        self._spell_handler.cast.side_effect = record_caster_and_target
        response = self._sut.perform(self._spell_cast_context)
        return response, recorded_caster, recorded_target

    def _test_spell_reflect(self, caster_genus: Genus, target_status: Statuses, is_reflected: bool):
        self._familiar.genus = caster_genus
        self._enemy.set_status(target_status)
        response, caster, target = self._test_spell_cast(target=self._enemy, reflected_target=self._familiar)
        self.assertIs(caster, self._familiar)
        self.assertIs(target, self._familiar if is_reflected else self._enemy)
        return response

    def test_when_target_has_fire_reflect_status_then_fire_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Fire, target_status=Statuses.FireReflect, is_reflected=True)

    def test_when_target_has_reflect_status_then_fire_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Fire, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_fire_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Fire, target_status=Statuses.WindReflect, is_reflected=False)

    def test_when_target_has_fire_reflect_status_then_water_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Water, target_status=Statuses.FireReflect, is_reflected=False)

    def test_when_target_has_reflect_status_then_water_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Water, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_water_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Water, target_status=Statuses.WindReflect, is_reflected=False)

    def test_when_target_has_fire_reflect_status_then_wind_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Wind, target_status=Statuses.FireReflect, is_reflected=False)

    def test_when_target_has_reflect_status_then_wind_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Wind, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_wind_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Wind, target_status=Statuses.WindReflect, is_reflected=True)

    def test_when_target_has_fire_reflect_status_then_non_elemental_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Empty, target_status=Statuses.FireReflect, is_reflected=False)

    def test_when_target_has_reflect_status_then_non_elemental_spell_is_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Empty, target_status=Statuses.Reflect, is_reflected=True)

    def test_when_target_has_wind_reflect_status_then_non_elemental_spell_is_not_reflected_at_other_unit(self):
        self._test_spell_reflect(caster_genus=Genus.Empty, target_status=Statuses.WindReflect, is_reflected=False)

    def _test_spell_reflect_response(self, caster, target, spell_cast_response):
        target.set_status(Statuses.Reflect)
        response, _, _ = self._test_spell_cast(
            caster=caster,
            target=target,
            reflected_target=self._enemy if self._familiar is target else self._familiar,
            spell_cast_response=spell_cast_response)
        return response

    def test_reflected_spell_response_when_spell_is_casted_by_familiar_on_itself(self):
        response = self._test_spell_reflect_response(
            caster=self._familiar,
            target=self._familiar,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'You cast test_spell on yourself. It is reflected at enemy. CASTED')

    def test_reflected_spell_response_when_spell_is_casted_by_familiar_on_enemy(self):
        response = self._test_spell_reflect_response(
            caster=self._familiar,
            target=self._enemy,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'You cast test_spell on enemy. It is reflected back at you. CASTED')

    def test_reflected_spell_response_when_spell_is_casted_by_enemy_on_familiar(self):
        response = self._test_spell_reflect_response(
            caster=self._enemy,
            target=self._familiar,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'Enemy casts test_spell on you. It is reflected back at enemy. CASTED')

    def test_reflected_spell_response_when_spell_is_casted_by_enemy_on_itself(self):
        response = self._test_spell_reflect_response(
            caster=self._enemy,
            target=self._enemy,
            spell_cast_response='CASTED')
        self.assertEqual(response, 'Enemy casts test_spell on itself. It is reflected at you. CASTED')


if __name__ == '__main__':
    unittest.main()
