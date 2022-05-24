from dataclasses import dataclass
from enum import Enum
from functools import cached_property


class TileType(Enum):
    FLOOR = 0
    BOX = 1
    WALL = 2


@dataclass
class Level(object):
    board: list[TileType]
    player: int
    goals: list[int]
    rows: int
    columns: int

    @property
    def size(self):
        return self.rows * self.columns

    @cached_property
    def first_pos(self):
        return min(self.reachable_tiles)

    @cached_property
    def last_pos(self):
        return max(self.reachable_tiles)

    @cached_property
    def reachable_tiles(self) -> set[int]:
        def _neighbors(pos: int) -> list[int]:
            neighbors = []

            if pos >= self.columns and not self.is_wall(current - self.columns):
                neighbors.append(current - self.columns)

            if pos <= self.size - self.columns and not self.is_wall(current + self.columns):
                neighbors.append(current + self.columns)

            if pos >= 1 and not self.is_wall(current - 1):
                neighbors.append(current - 1)

            if pos <= self.size - 1 and not self.is_wall(current + 1):
                neighbors.append(current + 1)

            return neighbors

        stack, path = [self.player], set()

        while stack:
            current = stack.pop()
            if current in path:
                continue

            path.add(current)

            stack.extend(_neighbors(current))

        return path

    def is_wall(self, i: int):
        return self.board[i] == TileType.WALL
