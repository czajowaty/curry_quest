import unittest
from unittest.mock import Mock
from curry_quest.ability import Ability
from curry_quest.ability_use_unit_action import AbilityUseActionHandler
from curry_quest.config import Config
from curry_quest.state_machine_context import StateMachineContext
from curry_quest.unit import Unit
from curry_quest.unit_action import UnitActionContext
from curry_quest.unit_traits import UnitTraits


class AbilityStub(Ability):
    def __init__(self, ability_mock):
        self._ability_mock = ability_mock
        self.mp_cost = 8

    @property
    def name(self):
        return 'AbilityStub'

    @property
    def mp_cost(self):
        return self._mp_cost

    @mp_cost.setter
    def mp_cost(self, new_mp_cost):
        self._mp_cost = new_mp_cost

    def select_target(self, user, other_unit):
        return self._ability_mock.select_target(user, other_unit)

    def can_target_self(self) -> bool:
        return self._ability_mock.can_target_self()

    def can_target_other_unit(self) -> bool:
        return self._ability_mock.can_target_other_unit()

    def can_have_no_target(self) -> bool:
        return self._ability_mock.can_have_no_target()

    def can_use(self, action_context) -> tuple[bool, str]:
        return self._ability_mock.can_use(action_context)

    def use(self, action_context) -> str:
        return self._ability_mock.use(action_context)


class AbilityUseUnitActionHandlerTest(unittest.TestCase):
    def setUp(self):
        self._ability_mock = Mock()
        self._ability_mock.perform.return_value = ''
        self._ability = AbilityStub(self._ability_mock)
        self._ability.mp_cost = 4
        self._sut = AbilityUseActionHandler(self._ability)
        self._config = Config()
        self._state_machine_context = StateMachineContext(self._config)
        unit_traits = UnitTraits()
        self._familiar = Unit(unit_traits, self._config.levels)
        self._enemy = Unit(unit_traits, self._config.levels)
        self._enemy.name = 'enemy'
        self._state_machine_context.familiar = self._familiar
        self._state_machine_context.start_battle(self._enemy)
        self._unit_action_context = UnitActionContext()
        self._unit_action_context.state_machine_context = self._state_machine_context

    def test_select_target_returns_what_ability_returns(self):
        self._ability_mock.select_target.return_value = self._enemy
        self.assertIs(self._sut.select_target(performer=self._familiar, other_unit=self._enemy), self._enemy)

    def test_select_target_forwards_parameters_to_ability(self):
        self._sut.select_target(performer=self._familiar, other_unit=self._enemy)
        self._ability_mock.select_target.assert_called_with(self._familiar, self._enemy)

    def test_can_target_self_returns_what_ability_returns(self):
        self._ability_mock.can_target_self.return_value = False
        self.assertFalse(self._sut.can_target_self())
        self._ability_mock.can_target_self.assert_called()

    def test_can_target_other_unit_returns_what_ability_returns(self):
        self._ability_mock.can_target_other_unit.return_value = True
        self.assertTrue(self._sut.can_target_other_unit())
        self._ability_mock.can_target_other_unit.assert_called()

    def test_can_have_no_target_returns_what_ability_returns(self):
        self._ability_mock.can_have_no_target.return_value = False
        self.assertFalse(self._sut.can_have_no_target())
        self._ability_mock.can_have_no_target.assert_called()

    def _set_ability_for_unit(self, unit: Unit):
        unit.ability = self._ability

    def _set_ability_for_familiar(self):
        self._set_ability_for_unit(self._familiar)

    def _set_ability_for_enemy(self):
        self._set_ability_for_unit(self._enemy)

    def _set_can_use_ability(self):
        self._ability_mock.can_use.return_value = True, ''

    def _set_cannot_use_ability(self, reason: str=''):
        self._ability_mock.can_use.return_value = False, reason

    def _test_can_perform(self, performer):
        self._unit_action_context.performer = performer
        can_perform, response = self._sut.can_perform(self._unit_action_context)
        return can_perform, response

    def _test_whether_can_perform(self, performer):
        can_perform, _ = self._test_can_perform(performer)
        return can_perform

    def _test_can_perform_response(self, performer):
        _, response = self._test_can_perform(performer)
        return response

    def _set_enough_mp_for_ability(self, performer):
        performer.mp = self._ability.mp_cost

    def _set_not_enough_mp_for_ability(self, performer):
        performer.mp = self._ability.mp_cost - 1

    def test_when_unit_does_not_have_enough_mp_then_action_cannot_be_performed(self):
        self._set_can_use_ability()
        self._set_ability_for_familiar()
        self._set_not_enough_mp_for_ability(self._familiar)
        self.assertFalse(self._test_whether_can_perform(performer=self._familiar))

    def test_can_use_response_when_familiar_does_not_have_enough_mp(self):
        self._set_can_use_ability()
        self._set_ability_for_familiar()
        self._set_not_enough_mp_for_ability(self._familiar)
        self.assertEqual(self._test_can_perform_response(performer=self._familiar), 'You do not have enough MP.')

    def test_can_use_response_when_enemy_does_not_have_enough_mp(self):
        self._set_can_use_ability()
        self._set_ability_for_enemy()
        self._set_not_enough_mp_for_ability(self._enemy)
        self.assertEqual(self._test_can_perform_response(performer=self._enemy), 'Enemy does not have enough MP.')

    def test_when_unit_does_not_have_ability_then_action_cannot_be_performed(self):
        self._set_can_use_ability()
        self._set_enough_mp_for_ability(self._familiar)
        self.assertFalse(self._test_whether_can_perform(performer=self._familiar))

    def test_can_use_response_when_familiar_does_not_have_ability(self):
        self._set_can_use_ability()
        self._set_enough_mp_for_ability(self._familiar)
        self.assertEqual(self._test_can_perform_response(performer=self._familiar), 'You do not have an ability.')

    def test_can_use_response_when_enemy_does_not_have_ability(self):
        self._set_can_use_ability()
        self._set_enough_mp_for_ability(self._enemy)
        self.assertEqual(self._test_can_perform_response(performer=self._enemy), 'Enemy does not have an ability.')

    def test_when_cannot_use_ability_then_action_cannot_be_performed(self):
        self._set_cannot_use_ability()
        self._set_ability_for_familiar()
        self._set_enough_mp_for_ability(self._familiar)
        self.assertFalse(self._test_whether_can_perform(performer=self._familiar))

    def test_can_use_response_when_familiar_cannot_use_ability(self):
        self._set_cannot_use_ability(reason='Because.')
        self._set_ability_for_familiar()
        self._set_enough_mp_for_ability(self._familiar)
        self.assertEqual(self._test_can_perform_response(performer=self._familiar), 'Because.')

    def test_can_use_response_when_enemy_cannot_use_ability(self):
        self._set_cannot_use_ability(reason='Because.')
        self._set_ability_for_enemy()
        self._set_enough_mp_for_ability(self._enemy)
        self.assertEqual(self._test_can_perform_response(performer=self._enemy), 'Because.')

    def test_when_unit_has_enough_mp_then_action_can_be_performed(self):
        self._set_can_use_ability()
        self._set_ability_for_familiar()
        self._set_enough_mp_for_ability(self._familiar)
        self.assertTrue(self._test_whether_can_perform(performer=self._familiar))

    def _test_perform(self, performer: Unit, target: Unit, ability_response: str=''):
        self._set_ability_for_unit(performer)
        self._ability_mock.use.return_value = ability_response
        self._unit_action_context.performer = performer
        self._unit_action_context.target = target
        return self._sut.perform(self._unit_action_context)

    def test_perform_decreases_mp_by_mp_cost(self):
        self._familiar.mp = 20
        self._test_perform(performer=self._familiar, target=self._enemy)
        self.assertEqual(self._familiar.mp, 16)

    def test_when_there_is_no_target_then_ability_is_not_used(self):
        self._test_perform(performer=self._familiar, target=None)
        self._ability_mock.use.assert_not_called()

    def test_response_when_used_by_familiar_and_there_is_no_target(self):
        self.assertEqual(
            self._test_perform(performer=self._familiar, target=None),
            'You use AbilityStub targeting nothing but air.')

    def test_response_when_used_by_enemy_and_there_is_no_target(self):
        self.assertEqual(
            self._test_perform(performer=self._enemy, target=None),
            'Enemy uses AbilityStub targeting nothing but air.')

    def test_when_there_is_target_then_ability_is_used(self):
        self._test_perform(performer=self._familiar, target=self._enemy)
        self._ability_mock.use.assert_called_once_with(self._unit_action_context)

    def test_response_when_used_by_familiar_on_familiar_and_there_is_target(self):
        self.assertEqual(
            self._test_perform(performer=self._familiar, target=self._familiar, ability_response='Ability used.'),
            'You use AbilityStub on yourself. Ability used.')

    def test_response_when_used_by_familiar_on_enemy_and_there_is_target(self):
        self.assertEqual(
            self._test_perform(performer=self._familiar, target=self._enemy, ability_response='Ability used.'),
            'You use AbilityStub on enemy. Ability used.')

    def test_response_when_used_by_enemy_on_enemy_and_there_is_target(self):
        self.assertEqual(
            self._test_perform(performer=self._enemy, target=self._enemy, ability_response='Ability used.'),
            'Enemy uses AbilityStub on itself. Ability used.')

    def test_response_when_used_by_enemy_on_familiar_and_there_is_target(self):
        self.assertEqual(
            self._test_perform(performer=self._enemy, target=self._familiar, ability_response='Ability used.'),
            'Enemy uses AbilityStub on you. Ability used.')


if __name__ == '__main__':
    unittest.main()
