import enum
from enum import auto


class Statuses(enum.Flag):
    Sleep = auto()
    Paralyze = auto()
    Blind = auto()
    StatsBoost = auto()
    Upheavel = auto()
    Crack = auto()
    Poison = auto()
    Confuse = auto()
    FireProtection = auto()
    WaterProtection = auto()
    WindProtection = auto()
    FireReflect = auto()
    Reflect = auto()
    WindReflect = auto()
