import itertools
from abc import ABC, abstractmethod

from parser.level import Level


class Generator(ABC):

    @abstractmethod
    def generate_model(self, level: Level) -> str:
        pass


def _multi_range(start: int, end: int, offset: list[int], valid: set[int]) -> list:
    return [x for x in zip(range(start, end), *[range(start + o, end + o) for o in offset]) if set(x).issubset(valid)]


def _move_bounds(level: Level, offset: int) -> (int, int):
    if offset < 0:
        return max(-offset, level.first_pos), level.last_pos + 1
    else:
        return level.first_pos, min(level.size - offset, level.last_pos + 1)


def _flatten(list_2d: list[list]) -> list:
    return list(itertools.chain.from_iterable(list_2d))
