import itertools
from abc import ABC, abstractmethod
from decimal import Decimal

from parser.level import Level


class Generator(ABC):

    @abstractmethod
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        pass


def _multi_range(start: int, end: int, offset: list[int], valid: set[int]):
    return [x for x in zip(range(start, end), *[range(start + o, end + o) for o in offset]) if set(x).issubset(valid)]


def _move_bounds(level: Level, offset: int):
    if offset < 0:
        return max(-offset, level.first_pos), level.last_pos + 1
    else:
        return level.first_pos, min(level.size - offset, level.last_pos + 1)


def _flatten(list_2d):
    return list(itertools.chain.from_iterable(list_2d))
