import itertools
import json
from decimal import Decimal

from generator.generator import Generator, _multi_range, _move_bounds, _flatten
from parser.level import Level, TileType


def _and(head, *tail):
    return {
        "op": "∧",
        "left": head,
        "right": _and(*tail) if len(tail) > 1 else tail[0]
    }


def _or(head, *tail):
    return {
        "op": "∨",
        "left": head,
        "right": _or(*tail) if len(tail) > 1 else tail[0]
    }


def _eq(name: str, value):
    return {
        "op": "=",
        "left": name,
        "right": value
    }


def _neq(name: str, value):
    return {
        "op": "≠",
        "left": name,
        "right": value
    }


def _assignment(name: str, value):
    return {
        "ref": name,
        "value": value
    }


def _edge(loc: str, guard, assignments):
    return {
        "location": loc,
        "guard": {
            "exp": guard
        },
        "destinations": [
            {
                "location": "move",
                "assignments": assignments
            }
        ]
    }


def _pmin_property(name: str, exp):
    return {
        "name": name,
        "expression": {
            "op": "filter",
            "fun": "max",
            "values": {
                "op": "Pmin",
                "exp": {
                    "op": "F",
                    "exp": exp
                }
            },
            "states": {
                "op": "initial"
            }
        }
    }


def _destination(loc: str, probability):
    return {
        "location": loc,
        "probability": {
            "exp": probability
        }
    }


def _location(loc: str):
    return {"name": loc}


def _model(variables, properties, edges):
    return {
        "jani-version": 1,
        "name": "sokoban",
        "type": "mdp",
        "variables": variables,
        "properties": properties,
        "automata": [
            {
                "name": "player",
                "locations": [_location(loc) for loc in
                              ["move",
                               "move_up", "push_up",
                               "move_down", "push_down",
                               "move_left", "push_left",
                               "move_right", "push_right"]],
                "initial-locations": [
                    "move"
                ],
                "edges": edges
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


def _generate_prob_edges(probabilities: dict[str, Decimal]) -> list[dict]:
    def _move_direction(location: str):
        return [_destination(f"move_{location}", float(probabilities[location[0]] / 2)),
                _destination(f"push_{location}", float(probabilities[location[0]] / 2))]

    return [
        {
            "location": "move",
            "destinations": _flatten([_move_direction(d) for d in ["up", "down", "left", "right"]])
        }
    ]


class JaniBoxGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        output = _model(
            variables=[
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
            properties=[self._generate_property(level)],
            edges=[
                *_generate_prob_edges(probabilities),
                *self._generate_move("up", level, -level.columns),
                *self._generate_push("up", level, -level.columns),
                *self._generate_move("down", level, level.columns),
                *self._generate_push("down", level, level.columns),
                *self._generate_move("left", level, -1),
                *self._generate_push("left", level, -1),
                *self._generate_move("right", level, 1),
                *self._generate_push("right", level, 1)
            ])

        return json.dumps(output, indent=4)

    @staticmethod
    def _generate_board(level) -> list[dict]:
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

    @staticmethod
    def _generate_property(level) -> dict:
        return _pmin_property(name="Goal state reached",
                              exp=_or(*[_and(*[_eq(f"box_{b}", v)
                                               for b, v in zip(range(len(level.goals)), permutation)])
                                        for permutation in itertools.permutations(level.goals)])
                              )

    @staticmethod
    def _generate_move(loc: str, level: Level, offset: int) -> list[dict]:
        start, end = _move_bounds(level, offset)

        return [_edge(loc=f"move_{loc}",
                      guard=_and(_eq("position", i), *[_neq(f"box_{b}", j) for b in range(len(level.boxes))]),
                      assignments=[_assignment("position", j)])
                for i, j in _multi_range(start, end, [offset], level.reachable_tiles)]

    @staticmethod
    def _generate_push(loc: str, level: Level, offset: int):
        start, end = _move_bounds(level, 2 * offset)

        return [_edge(loc=f"push_{loc}",
                      guard=_and(
                          _eq("position", i),
                          _eq(f"box_{b}", j),
                          *[_and(_neq(f"box_{i}", j), _neq(f"box_{i}", k)) for i in range(len(level.boxes)) if b != i]),
                      assignments=[_assignment(f"box_{b}", k), _assignment("position", j)])
                for i, j, k in _multi_range(start, end, [offset, 2 * offset], level.reachable_tiles)
                for b in range(len(level.boxes))]


class JaniPosGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        output = _model(
            variables=[
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
            properties=[self._generate_property(level)],
            edges=[
                *_generate_prob_edges(probabilities),
                *self._generate_move("up", level, -level.columns),
                *self._generate_push("up", level, -level.columns),
                *self._generate_move("down", level, level.columns),
                *self._generate_push("down", level, level.columns),
                *self._generate_move("left", level, -1),
                *self._generate_push("left", level, -1),
                *self._generate_move("right", level, 1),
                *self._generate_push("right", level, 1)
            ])

        return json.dumps(output, indent=4)

    @staticmethod
    def _generate_board(level) -> list[dict]:
        return [{
            "name": f"box_{i}",
            "type": "bool",
            "initial-value": level.board[i] == TileType.BOX
        } for i in level.reachable_tiles]

    @staticmethod
    def _generate_property(level) -> dict:
        return _pmin_property("Goal state reached", _and(*[_eq(f"box_{goal}", True) for goal in level.goals]))

    @staticmethod
    def _generate_move(loc: str, level: Level, offset: int) -> list[dict]:
        start, end = _move_bounds(level, offset)

        return [
            _edge(loc=f"move_{loc}",
                  guard=_and(_eq("position", i), _eq(f"box_{j}", False)),
                  assignments=[_assignment("position", j)])
            for i, j in _multi_range(start, end, [offset], level.reachable_tiles)
        ]

    @staticmethod
    def _generate_push(loc: str, level: Level, offset: int):
        start, end = _move_bounds(level, 2 * offset)

        return [
            _edge(loc=f"move_{loc}",
                  guard=_and(_eq("position", i), _eq(f"box_{j}", True), _eq(f"box_{k}", False)),
                  assignments=[_assignment(f"box_{j}", False),
                               _assignment(f"box_{k}", True),
                               _assignment("position", j)])
            for i, j, k in _multi_range(start, end, [offset, 2 * offset], level.reachable_tiles)
        ]
