import controller_test
import curry_quest_test
import physical_attack_unit_action_test
import save_load_state_test
import spells_test
import state_battle_test
import unittest


def suite():
    test_modules = [
        controller_test,
        curry_quest_test,
        physical_attack_unit_action_test,
        save_load_state_test,
        spells_test,
        state_battle_test
    ]
    loader = unittest.TestLoader()
    return unittest.TestSuite([loader.loadTestsFromModule(test) for test in test_modules])


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
