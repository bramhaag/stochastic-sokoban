import functools
import itertools
import json
from abc import ABC, abstractmethod
from decimal import Decimal
from functools import reduce

from parser.level import Level, TileType


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


class Jani2Generator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        output = {
            "jani-version": 1,
            "name": "sokoban",
            "type": "mdp",
            "variables": [
                {
                    "name": "position",
                    "type": {
                        "kind": "bounded",
                        "base": "int",
                        "lower-bound": level.first_pos,
                        "upper-bound": level.last_pos
                    },
                    "initial-value": level.player
                },
                *self._generate_board(level)
            ],
            "properties": [
                self._generate_property(level)
            ],
            "automata": [
                {
                    "name": "player",
                    "locations": [
                        {"name": "move"},

                        {"name": "move_up"},
                        {"name": "push_up"},

                        {"name": "move_down"},
                        {"name": "push_down"},

                        {"name": "move_left"},
                        {"name": "push_left"},

                        {"name": "move_right"},
                        {"name": "push_right"}

                    ],
                    "initial-locations": [
                        "move"
                    ],
                    "edges": [
                        *self._generate_prob_edges(probabilities),
                        *self._generate_move("up", level, -level.columns),
                        *self._generate_push("up", level, -level.columns),
                        *self._generate_move("down", level, level.columns),
                        *self._generate_push("down", level, level.columns),
                        *self._generate_move("left", level, -1),
                        *self._generate_push("left", level, -1),
                        *self._generate_move("right", level, 1),
                        *self._generate_push("right", level, 1)
                    ]
                }
            ],
            "system": {
                "elements": [
                    {
                        "automaton": "player"
                    }
                ]
            }
        }

        return json.dumps(output, indent=4)

    def _generate_board(self, level) -> list[dict]:
        return [{
            "name": f"box_{i}",
            "type": {
                "kind": "bounded",
                "base": "int",
                "lower-bound": level.first_pos,
                "upper-bound": level.last_pos
            },
            "initial-value": g
        } for i, g in enumerate(level.boxes)]

    def _generate_property(self, level) -> dict:
        return {
            "name": "Goal state reached",
            "expression": {
                "op": "filter",
                "fun": "max",
                "values": {
                    "op": "Pmin",
                    "exp": {
                        "op": "F",
                        "exp": functools.reduce(self._generate_or,
                                                [functools.reduce(self._generate_and,
                                                                  [self._generate_eq(f"box_{b}", v)
                                                                   for b, v in
                                                                   zip(range(len(level.goals)), permutation)])
                                                 for permutation in itertools.permutations(level.goals)])
                    }
                },
                "states": {
                    "op": "initial"
                }
            }
        }

    def _generate_prob_edges(self, probabilities: dict[str, Decimal]) -> list[dict]:
        def _destination(location: str):
            return [
                {
                    "location": f"move_{location}",
                    "probability": {
                        "exp": float(probabilities[location[0]] / 2)
                    }
                },
                {
                    "location": f"push_{location}",
                    "probability": {
                        "exp": float(probabilities[location[0]] / 2)
                    }
                }]

        return [
            {
                "location": "move",
                "destinations": [
                    *_destination("up"),
                    *_destination("down"),
                    *_destination("left"),
                    *_destination("right"),
                ]
            }
        ]

    def _generate_assignment(self, name: str, value):
        return {
            "ref": name,
            "value": value
        }

    def _generate_and(self, left, right):
        return {
            "op": "∧",
            "left": left,
            "right": right
        }

    def _generate_or(self, left, right):
        return {
            "op": "∨",
            "left": left,
            "right": right
        }

    def _generate_eq(self, name: str, value):
        return {
            "op": "=",
            "left": name,
            "right": value
        }

    def _generate_neq(self, name: str, value):
        return {
            "op": "≠",
            "left": name,
            "right": value
        }

    def _generate_move(self, loc: str, level: Level, offset: int) -> list[dict]:
        if offset < 0:
            start, end = max(-offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - offset, level.last_pos + 1)

        return [
            {
                "location": f"move_{loc}",
                "guard": {
                    "exp": self._generate_and(
                        self._generate_eq("position", i),
                        functools.reduce(self._generate_and,
                                         [self._generate_neq(f"box_{b}", j) for b in range(len(level.boxes))]))
                },
                "destinations": [
                    {
                        "location": "move",
                        "assignments": [
                            self._generate_assignment("position", j)
                        ]
                    }
                ]
            }

            for i, j in self._multi_range(start, end, [offset], level.reachable_tiles)]

    def _generate_push(self, loc: str, level: Level, offset: int):
        if offset < 0:
            start, end = max(-2 * offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - 2 * offset, level.last_pos + 1)

        def _guard(b, j, k):
            return self._generate_and(
                self._generate_eq(f"box_{b}", j),
                functools.reduce(self._generate_and,
                                 [self._generate_and(self._generate_neq(f"box_{i}", j),
                                                     self._generate_neq(f"box_{i}", k))
                                  for i in range(len(level.boxes)) if b != i]))

        return [
            {
                "location": f"push_{loc}",
                "guard": {
                    "exp": self._generate_and(self._generate_eq("position", i), _guard(b, j, k))
                },
                "destinations": [
                    {
                        "location": "move",
                        "assignments": [
                            self._generate_assignment(f"box_{b}", k),
                            self._generate_assignment("position", j)
                        ]
                    }
                ]
            }
            for i, j, k in self._multi_range(start, end, [offset, 2 * offset], level.reachable_tiles)
            for b in range(len(level.boxes))]

    @staticmethod
    def _multi_range(start: int, end: int, offset: list[int], valid: set[int]):
        return [x for x in zip(range(start, end), *[range(start + o, end + o) for o in offset])
                if set(x).issubset(valid)]


class JaniGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        output = {
            "jani-version": 1,
            "name": "sokoban",
            "type": "mdp",
            "variables": [
                {
                    "name": "position",
                    "type": {
                        "kind": "bounded",
                        "base": "int",
                        "lower-bound": level.first_pos,
                        "upper-bound": level.last_pos
                    },
                    "initial-value": level.player
                },
                *self._generate_board(level)
            ],
            "properties": [
                self._generate_property(level)
            ],
            "automata": [
                {
                    "name": "player",
                    "locations": [
                        {"name": "move"},

                        {"name": "move_up"},
                        {"name": "push_up"},

                        {"name": "move_down"},
                        {"name": "push_down"},

                        {"name": "move_left"},
                        {"name": "push_left"},

                        {"name": "move_right"},
                        {"name": "push_right"}

                    ],
                    "initial-locations": [
                        "move"
                    ],
                    "edges": [
                        *self._generate_prob_edges(probabilities),
                        *self._generate_move("up", level, -level.columns),
                        *self._generate_push("up", level, -level.columns),
                        *self._generate_move("down", level, level.columns),
                        *self._generate_push("down", level, level.columns),
                        *self._generate_move("left", level, -1),
                        *self._generate_push("left", level, -1),
                        *self._generate_move("right", level, 1),
                        *self._generate_push("right", level, 1)
                    ]
                }
            ],
            "system": {
                "elements": [
                    {
                        "automaton": "player"
                    }
                ]
            }
        }

        return json.dumps(output, indent=4)

    def _generate_board(self, level) -> list[dict]:
        return [{
            "name": f"box_{i}",
            "type": "bool",
            "initial-value": level.board[i] == TileType.BOX
        } for i in level.reachable_tiles]

    def _generate_property(self, level) -> dict:
        return {
            "name": "Goal state reached",
            "expression": {
                "op": "filter",
                "fun": "max",
                "values": {
                    "op": "Pmin",
                    "exp": {
                        "op": "F",
                        "exp": reduce(self._generate_and,
                                      [self._generate_eq(f"box_{goal}", True) for goal in level.goals])
                    }
                },
                "states": {
                    "op": "initial"
                }
            }
        }

    def _generate_prob_edges(self, probabilities: dict[str, Decimal]) -> list[dict]:
        def _destination(location: str):
            return [
                {
                    "location": f"move_{location}",
                    "probability": {
                        "exp": float(probabilities[location[0]] / 2)
                    }
                },
                {
                    "location": f"push_{location}",
                    "probability": {
                        "exp": float(probabilities[location[0]] / 2)
                    }
                }]

        return [
            {
                "location": "move",
                "destinations": [
                    *_destination("up"),
                    *_destination("down"),
                    *_destination("left"),
                    *_destination("right"),
                ]
            }
        ]

    def _generate_assignment(self, name: str, value):
        return {
            "ref": name,
            "value": value
        }

    def _generate_and(self, left, right):
        return {
            "op": "∧",
            "left": left,
            "right": right
        }

    def _generate_eq(self, name: str, value):
        return {
            "op": "=",
            "left": name,
            "right": value
        }

    def _generate_move(self, loc: str, level: Level, offset: int) -> list[dict]:
        if offset < 0:
            start, end = max(-offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - offset, level.last_pos + 1)

        return [
            {
                "location": f"move_{loc}",
                "guard": {
                    "exp": self._generate_and(
                        self._generate_eq("position", i),
                        self._generate_eq(f"box_{j}", False)
                    )
                },
                "destinations": [
                    {
                        "location": "move",
                        "assignments": [
                            self._generate_assignment("position", j)
                        ]
                    }
                ]
            }

            for i, j in self._multi_range(start, end, [offset], level.reachable_tiles)]

    def _generate_push(self, loc: str, level: Level, offset: int):
        if offset < 0:
            start, end = max(-2 * offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - 2 * offset, level.last_pos + 1)

        return [
            {
                "location": f"push_{loc}",
                "guard": {
                    "exp": self._generate_and(self._generate_and(
                        self._generate_eq("position", i),
                        self._generate_eq(f"box_{j}", True)),
                        self._generate_eq(f"box_{k}", False)
                    )
                },
                "destinations": [
                    {
                        "location": "move",
                        "assignments": [
                            self._generate_assignment(f"box_{j}", False),
                            self._generate_assignment(f"box_{k}", True),
                            self._generate_assignment("position", j)
                        ]
                    }
                ]
            }
            for i, j, k in self._multi_range(start, end, [offset, 2 * offset], level.reachable_tiles)]

    @staticmethod
    def _multi_range(start: int, end: int, offset: list[int], valid: set[int]):
        return [x for x in zip(range(start, end), *[range(start + o, end + o) for o in offset])
                if set(x).issubset(valid)]
