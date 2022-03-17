from curry_quest.state_base import StateBase
from curry_quest import commands


class StateElevatorEvent(StateBase):
    def on_enter(self):
        self._context.add_response(
            f"You find an elevator. You are currently on {self._context.floor + 1}F. "
            "Do you want to go to the next floor?")


class StateGoUp(StateBase):
    def on_enter(self):
        self._context.floor += 1
        self._context.generate_action(commands.ENTERED_NEXT_FLOOR)


class StateElevatorOmitted(StateBase):
    def on_enter(self):
        self._context.add_response("You decide against using the elevator.")
        self._context.generate_action(commands.EVENT_FINISHED)


class StateNextFloor(StateBase):
    def on_enter(self):
        floor = self._context.floor + 1
        if not self._context.is_at_the_top_of_tower():
            self._context.add_response(f"You entered {floor}F.")
            self._context.generate_action(commands.EVENT_FINISHED)
        else:
            self._context.add_response(f"You have conquered the Tower! Congratulations!")
            self._context.add_response(f"Your valiant efforts are going to be remembered in the Halls of Fame!")
            self._context.records_events_handler.handle_tower_clear(self._context.records)
            self._context.generate_action(commands.FINISH_GAME)
