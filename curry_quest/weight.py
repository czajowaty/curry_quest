from abc import abstractmethod, ABC


class WeightPenaltyHandler(ABC):
    @abstractmethod
    def apply_penalty(self, value) -> int: pass

    @property
    @abstractmethod
    def penalty_duration(self) -> int: pass


class Weight(ABC):
    @abstractmethod
    def value(self, context): pass


class WeightHandler:
    def __init__(self, weight: Weight):
        self._penalty_timer = 0
        self._weight = weight
        self._penalty_handler: WeightPenaltyHandler = NoWeightPenaltyHandler()

    @classmethod
    def from_descriptor(cls, weight_descriptor):
        weight, penalty_handler = weight_descriptor
        weight_handler = WeightHandler(weight)
        if penalty_handler is not None:
            weight_handler.set_penalty_handler(penalty_handler)
        return weight_handler

    def set_penalty_handler(self, penalty_handler):
        self._penalty_handler = penalty_handler

    @property
    def penalty_timer(self):
        return self._penalty_timer

    @penalty_timer.setter
    def penalty_timer(self, value):
        self._penalty_timer = value

    def has_penalty(self) -> bool:
        return self._penalty_timer > 0

    def set_penalty(self):
        self._penalty_timer = self._penalty_handler.penalty_duration

    def clear_penalty(self):
        self._penalty_timer = 0

    def decrease_penalty_timer(self):
        if self.has_penalty():
            self._penalty_timer -= 1

    def value(self, context):
        value = self._weight.value(context)
        if self.has_penalty():
            value = self._penalty_handler.apply_penalty(value)
        return max(value, 0)

    def __str__(self) -> str:
        return f"Weight({self._weight}), Penalty: {self._penalty_handler}"


class NoWeightPenaltyHandler(WeightPenaltyHandler):
    def apply_penalty(self, value) -> int:
        return value

    @property
    def penalty_duration(self) -> int:
        return 0

    def __str__(self):
        return '-'


class NonZeroWeightPenaltyHandler(WeightPenaltyHandler):
    def __init__(self, penalty_duration: int):
        self._penalty_duration = penalty_duration

    @property
    def penalty_duration(self) -> int:
        return self._penalty_duration

    def __str__(self):
        return f'{self._name}({self._str_args()})'

    @property
    @abstractmethod
    def _name(self) -> str: pass

    def _str_args(self) -> str:
        return f'duration: {self._penalty_duration}'


class StaticWeightPenaltyHandler(NonZeroWeightPenaltyHandler):
    def __init__(self, penalty, penalty_duration):
        super().__init__(penalty_duration)
        self._penalty = penalty

    def apply_penalty(self, value) -> int:
        return value - self._penalty

    @property
    def _name(self) -> str:
        return 'Static'

    def _str_args(self) -> str:
        return f'value: {self._penalty}, {super()._str_args()}'


class MaxWeightPenaltyHandler(NonZeroWeightPenaltyHandler):
    def apply_penalty(self, value) -> int:
        return 0

    @property
    def _name(self) -> str:
        return 'No repeat'


class StaticWeight(Weight):
    def __init__(self, weight):
        super().__init__()
        self._weight = weight

    def value(self, context):
        return self._weight

    def __str__(self):
        return str(self._weight)


class ProratedWeight(Weight):
    def __init__(self, min_weight, max_weight):
        super().__init__()
        self._min_weight = min_weight
        self._max_weight = max_weight

    def value(self, context):
        fraction = self._calculate_fraction(context)
        weight = round((1.0 - fraction) * self._min_weight + fraction * self._max_weight)
        return weight

    @abstractmethod
    def _calculate_fraction(self, context): pass

    def __str__(self):
        return f'min: {self._min_weight}, max: {self._max_weight}'


class FloorProgressionProratedWeight(ProratedWeight):
    def _calculate_fraction(self, context):
        turns_counter = context.floor_turns_counter
        collapse_turn = context.game_config.eq_settings.floor_collapse_turn
        if turns_counter <= 0:
            return 0
        if turns_counter >= collapse_turn:
            return 1
        range_length = context.game_config.eq_settings.floor_collapse_turn - 2
        zero_based_turn_counter = context.floor_turns_counter - 1
        return zero_based_turn_counter / range_length


class LevelProratedWeight(ProratedWeight):
    def __init__(self, min_weight, max_weight, level_for_max_weight):
        super().__init__(min_weight, max_weight)
        self._level_for_max_weight = level_for_max_weight

    def _calculate_fraction(self, context):
        level = context.familiar.level
        if level <= 1:
            return 0
        if level >= self._level_for_max_weight:
            return 1
        return (level - 1) / (self._level_for_max_weight - 1)

    def __str__(self):
        return f'{super().__str__()}, max weight LVL: {self._level_for_max_weight}'
