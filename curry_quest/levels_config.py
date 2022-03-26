class Levels:
    def __init__(self):
        self._experience_per_level = []

    @property
    def max_level(self) -> int:
        return len(self._experience_per_level)

    def add_level(self, experience_required: int):
        self._experience_per_level.append(experience_required)

    def experience_for_next_level(self, level: int) -> int:
        return self._experience_per_level[level]
