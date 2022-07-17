import abilities_test
import controller_test
import curry_quest_test
import item_use_unit_action_test
import items_test
import physical_attack_executor_test
import physical_attack_unit_action_test
import save_load_state_test
import spells_test
import state_battle_test
import state_item_test
import weight_test
import unittest


def suite():
    test_modules = [
        abilities_test,
        controller_test,
        curry_quest_test,
        item_use_unit_action_test,
        items_test,
        physical_attack_executor_test,
        physical_attack_unit_action_test,
        save_load_state_test,
        spells_test,
        state_battle_test,
        state_item_test,
        weight_test
    ]
    loader = unittest.TestLoader()
    return unittest.TestSuite([loader.loadTestsFromModule(test) for test in test_modules])


if __name__ == '__main__':
    runner = unittest.TextTestRunner()
    runner.run(suite())
