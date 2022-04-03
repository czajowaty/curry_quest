from curry_quest import commands
from curry_quest.state_base import StateBase
from curry_quest.unit import Unit
from curry_quest.statuses import Statuses
from curry_quest.talents import Talents


class StateTrapEvent(StateBase):
    RESPONSE_WHEN_IMMUNE = 'You are not affected by it.'

    def __init__(self, context, trap=None):
        super().__init__(context)
        self._trap = trap

    def on_enter(self):
        trap = self._select_trap()
        self._context.set_trap_weight_penalty(trap)
        trap_handler = self.TRAPS[trap]
        command, response = trap_handler(self)
        self._context.add_response(f'You stepped on a {trap} trap! {response}')
        self._context.generate_action(command)

    def _select_trap(self):
        traps_weights = self._context.trap_weights

        def remove_weight(trap):
            if trap in traps_weights:
                del traps_weights[trap]

        if self._familiar().has_status(Statuses.Sleep):
            remove_weight('Sleep')
        if self._familiar().has_status(Statuses.Upheaval):
            remove_weight('Upheaval')
        if self._familiar().has_status(Statuses.Crack):
            remove_weight('Crack')
        if self._familiar().has_status(Statuses.Blind):
            remove_weight('Blinder')
        return self._trap or self._context.random_selection_with_weights(traps_weights)

    def _familiar(self) -> Unit:
        return self._context.familiar

    def _handle_slam_trap(self):
        slam_hp_fraction = 0.2
        lost_hp = int(self._familiar().hp * slam_hp_fraction)
        lost_hp = max(lost_hp, 1)
        if lost_hp >= self._familiar().hp:
            lost_hp = self._familiar(). hp - 1
        self._familiar().deal_damage(lost_hp)
        return commands.EVENT_FINISHED, f'A rock falls from above. You lose {lost_hp} HP.'

    def _handle_sleep_trap(self):
        if self._familiar().talents.has(Talents.SleepProof):
            response = self.RESPONSE_WHEN_IMMUNE
        else:
            self._familiar().set_status(Statuses.Sleep)
            response = 'You feel a bit drowsy.'
        return commands.EVENT_FINISHED, response

    def _handle_upheaval_trap(self):
        self._familiar().set_status(Statuses.Upheaval)
        self._familiar().clear_status(Statuses.Crack)
        return commands.EVENT_FINISHED, 'The ground suddenly rises under your feet.'

    def _handle_crack_trap(self):
        self._familiar().set_status(Statuses.Crack)
        self._familiar().clear_status(Statuses.Upheaval)
        return commands.EVENT_FINISHED, 'The ground collapses around you, leaving you in a pit.'

    def _handle_go_up_trap(self):
        return commands.GO_UP, 'A giant spring throws you up to the next floor.'

    def _handle_blinder_trap(self):
        if self._familiar().talents.has(Talents.BlinderProof):
            response = self.RESPONSE_WHEN_IMMUNE
        else:
            self._familiar().set_timed_status(Statuses.Blind, duration=4)
            response = 'Your eyes get cloudy and you\'re unable to see.'
        return commands.EVENT_FINISHED, response

    TRAPS = {
        'Slam': _handle_slam_trap,
        'Sleep': _handle_sleep_trap,
        'Upheaval': _handle_upheaval_trap,
        'Crack': _handle_crack_trap,
        'Go up': _handle_go_up_trap,
        'Blinder': _handle_blinder_trap
    }

    @classmethod
    def _parse_args(cls, context, args):
        if len(args) == 0:
            return ()
        trap = ' '.join(args).strip().lower().capitalize()
        if trap not in cls.TRAPS.keys():
            raise cls.ArgsParseError('Unknown trap')
        return trap,
