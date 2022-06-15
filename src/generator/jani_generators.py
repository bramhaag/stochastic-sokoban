import json
from decimal import Decimal
from numbers import Number

from generator.generator import Generator, _flatten
from parser.level import Level, TileType

Expr = str | dict | Number


def _and(head, *tail) -> dict:
    if len(tail) == 0:
        return head

    return {
        "op": "∧",
        "left": head,
        "right": _and(*tail) if len(tail) > 1 else tail[0]
    }


def _or(head, *tail) -> dict:
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


def _neg(exp: Expr):
    return {
        "op": "¬",
        "exp": exp,
    }


def _if(cond: Expr, then: Expr, otherwise: Expr):
    return {
        "op": "ite",
        "if": cond,
        "then": then,
        "else": otherwise
    }


def _sub(left: Expr, right: Expr) -> dict:
    return {
        "op": "-",
        "left": left,
        "right": right
    }


def _div(left: Expr, right: Expr) -> dict:
    return {
        "op": "/",
        "left": left,
        "right": right
    }


def _assignment(name: str, value):
    return {
        "ref": name,
        "value": value
    }


def _edge(action: str, guard, assignments):
    return {
        "location": "move",
        "action": action,
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


def _pmax_property(name: str, exp):
    return {
        "name": name,
        "expression": {
            "op": "filter",
            "fun": "max",
            "values": {
                "op": "Pmax",
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


def _destination(loc: str, probability, assignments: list[dict]):
    return {
        "location": loc,
        "probability": {
            "exp": probability
        },
        "assignments": assignments
    }


def _location(loc: str):
    return {"name": loc}


def _model(variables=None, constants=None, properties=None, edges=None):
    return {
        "jani-version": 1,
        "name": "sokoban",
        "type": "mdp",
        "variables": variables or [],
        "properties": properties or [],
        "constants": constants or [],
        "actions": [{"name": d} for d in ["up", "down", "left", "right"]],
        "automata": [
            {
                "name": "player",
                "locations": [_location("move")],
                "initial-locations": [
                    "move"
                ],
                "edges": edges or []
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


class JaniNonStochasticGenerator(Generator):
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
            edges=_flatten([self._generate_edges(i, level) for i in sorted(level.reachable_tiles)])
        )

        return json.dumps(output, indent=4)

    @staticmethod
    def _generate_board(level) -> list[dict]:
        return [{
            "name": f"box_{i}",
            "type": "bool",
            "initial-value": level.board[i] == TileType.BOX
        } for i in sorted(level.reachable_tiles)]

    @staticmethod
    def _generate_property(level) -> dict:
        return _pmax_property("Goal state reached", _and(*[_eq(f"box_{goal}", True) for goal in level.goals]))

    @staticmethod
    def _generate_edges(position: int, level: Level) -> list[dict]:
        def to_move(direction: str, x: int, y: int) -> dict:
            return _edge(action=direction,
                         guard=_and(_eq("position", x), _neg(f"box_{y}")),
                         assignments=[_assignment("position", y)])

        def to_move_or_push(direction: str, x: int, y: int, z: int) -> dict:
            return _edge(action=direction,
                         guard=_and(_eq("position", x), _neg(_and(f"box_{y}", f"box_{z}"))),
                         assignments=[
                             _assignment("position", y),
                             _assignment(f"box_{y}", False),
                             _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
                         ])

        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        edges = []
        for d, o in offsets.items():
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                edges.append(to_move_or_push(d, position, position + o, position + 2 * o))
            elif position + o in level.reachable_tiles:
                edges.append(to_move(d, position, position + o))

        return edges


class JaniGenerator(Generator):
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
            constants=[{
                "name": "mu",
                "type": "real"
            }],
            properties=[self._generate_property(level)],
            edges=_flatten([self._generate_edges(i, level) for i in sorted(level.reachable_tiles)])
        )

        return json.dumps(output, indent=4)

    @staticmethod
    def _generate_board(level) -> list[dict]:
        return [{
            "name": f"box_{i}",
            "type": "bool",
            "initial-value": level.board[i] == TileType.BOX
        } for i in sorted(level.reachable_tiles)]

    @staticmethod
    def _generate_property(level) -> dict:
        return _pmax_property("Goal state reached", _and(*[_eq(f"box_{goal}", True) for goal in level.goals]))

    @staticmethod
    def _generate_edges(position: int, level: Level) -> list[dict]:
        def to_push_assignments(y: int, z: int) -> list[dict]:
            return [
                _assignment("position", _if(_and(f"box_{y}", _neg(f"box_{z}")), y, "position")),
                _assignment(f"box_{y}", _and(f"box_{y}", f"box_{z}")),
                _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
            ]

        def to_move_assignment(y: int) -> list[dict]:
            return [_assignment("position", _if(_neg(f"box_{y}"), y, "position"))]

        def to_assignments(direction: str) -> list[list[dict]]:
            assignments = []
            for current_direction, offset in offsets.items():
                if current_direction == direction:
                    continue

                y, z = position + offset, position + 2 * offset
                if y in level.reachable_tiles and z in level.reachable_tiles:
                    assignments.append(to_push_assignments(y, z))
                elif y in level.reachable_tiles:
                    assignments.append(to_move_assignment(y))

            return assignments
            # probability = _sub(1, "mu") if len(assignments) == 1 else _div(_sub(1, "mu"), len(assignments))
            # return _destination("move", probability, _flatten(assignments))

        def to_move_command(x: int, y: int) -> tuple[dict, list[dict]]:
            return _and(_eq("position", x), _neg(f"box_{y}")), [_assignment("position", y)]

        def to_push_command(x: int, y: int, z: int) -> tuple[dict, list[dict]]:
            return _and(_eq("position", x), _neg(_and(f"box_{y}", f"box_{z}"))), [
                _assignment("position", y),
                _assignment(f"box_{y}", False),
                _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
            ]

        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        edges = []
        for d, o in offsets.items():
            destinations = []
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                guard, assignment = to_push_command(position, position + o, position + 2 * o)
            elif position + o in level.reachable_tiles:
                guard, assignment = to_move_command(position, position + o)
            else:
                continue

            assignments = to_assignments(d)
            if len(assignments) == 0:
                destinations.append(_destination("move", 1, assignment))
            else:
                destinations.append(_destination("move", "mu", assignment))
                for ass in assignments:
                    destinations.append(_destination("move", _sub(1, "mu") if len(assignments) == 1 else _div(_sub(1, "mu"), len(assignments)), ass))

            edges.append({
                "location": "move",
                "action": d,
                "guard": {
                    "exp": guard
                },
                "destinations": destinations
            })

        return edges

        # def to_move(direction: str, x: int, y: int) -> dict:
        #     return _edge(action=direction,
        #                  guard=_and(_eq("position", x), _neg(f"box_{y}")),
        #                  assignments=[_assignment("position", y)])
        #
        # def to_move_or_push(direction: str, x: int, y: int, z: int) -> dict:
        #     return _edge(action=direction,
        #                  guard=_and(_eq("position", x), _neg(_and(f"box_{y}", f"box_{z}"))),
        #                  assignments=[
        #                      _assignment("position", y),
        #                      _assignment(f"box_{y}", False),
        #                      _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
        #                  ])
        #
        # offsets = {
        #     "up": -level.columns,
        #     "down": level.columns,
        #     "left": -1,
        #     "right": 1
        # }
        #
        # edges = []
        # for d, o in offsets.items():
        #     if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
        #         edges.append(to_move_or_push(d, position, position + o, position + 2 * o))
        #     elif position + o in level.reachable_tiles:
        #         edges.append(to_move(d, position, position + o))
        #
        # return edges
