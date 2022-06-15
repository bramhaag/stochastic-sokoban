import json
from numbers import Number

from generator.generator import Generator, _flatten
from parser.level import Level, TileType

Identifier = str
Expr = Identifier | dict | Number | bool


def _binary_op(op: str, left: Expr, right: Expr):
    return {
        "op": op,
        "left": left,
        "right": right
    }


def _and(head: Expr, *tail: [Expr]) -> Expr:
    return head if len(tail) == 0 else _binary_op("∧", head, _and(*tail))


def _or(head, *tail) -> Expr:
    return head if len(tail) == 0 else _binary_op("∨", head, _and(*tail))


def _eq(left: Expr, right: Expr) -> Expr:
    return _binary_op("=", left, right)


def _neq(left: Expr, right: Expr) -> Expr:
    return _binary_op("≠", left, right)


def _neg(exp: Expr) -> Expr:
    return {
        "op": "¬",
        "exp": exp,
    }


def _if(cond: Expr, then: Expr, otherwise: Expr) -> Expr:
    return {
        "op": "ite",
        "if": cond,
        "then": then,
        "else": otherwise
    }


def _sub(left: Expr, right: Expr) -> Expr:
    return _binary_op("-", left, right)


def _div(left: Expr, right: Expr) -> Expr:
    return _binary_op("/", left, right)


def _assignment(name: Identifier, value: Expr) -> Expr:
    return {
        "ref": name,
        "value": value
    }


def _edge(action: Identifier, guard: Expr, destinations: [Expr] = None) -> Expr:
    return {
        "location": "move",
        "action": action,
        "guard": {
            "exp": guard
        },
        "destinations": destinations
    }


def _pmax_property(name: Identifier, exp: Expr) -> Expr:
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


def _destination(location: Identifier, probability: Expr = 1.0, assignments: [Expr] = None) -> Expr:
    return {
        "location": location,
        "probability": {
            "exp": probability
        },
        "assignments": assignments or []
    }


def _location(name: Identifier) -> Expr:
    return {"name": name}


def _model(variables: [Expr] = None, constants: [Expr] = None, properties: [Expr] = None, edges: [Expr] = None):
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
    def generate_model(self, level: Level) -> str:
        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

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
            edges=_flatten([self._generate_edges(i, level, offsets) for i in sorted(level.reachable_tiles)])
        )

        return json.dumps(output, indent=4)

    @staticmethod
    def _generate_board(level: Level) -> [Expr]:
        return [{
            "name": f"box_{i}",
            "type": "bool",
            "initial-value": level.board[i] == TileType.BOX
        } for i in sorted(level.reachable_tiles)]

    @staticmethod
    def _generate_property(level: Level) -> Expr:
        return _pmax_property("goal_reached", _and(*[_eq(f"box_{goal}", True) for goal in level.goals]))

    @staticmethod
    def _generate_edges(position: int, level: Level, offsets: dict[str, int]) -> [Expr]:
        def to_move(direction: str, x: int, y: int) -> Expr:
            return _edge(action=direction,
                         guard=_and(_eq("position", x), _neg(f"box_{y}")),
                         destinations=[_destination(location="move", assignments=[_assignment("position", y)])])

        def to_move_and_push(direction: str, x: int, y: int, z: int) -> Expr:
            return _edge(action=direction,
                         guard=_and(_eq("position", x), _neg(_and(f"box_{y}", f"box_{z}"))),
                         destinations=[_destination("move", assignments=[
                             _assignment("position", y),
                             _assignment(f"box_{y}", False),
                             _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
                         ])])

        edges = []
        for d, o in offsets.items():
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                edges.append(to_move_and_push(d, position, position + o, position + 2 * o))
            elif position + o in level.reachable_tiles:
                edges.append(to_move(d, position, position + o))

        return edges


class JaniGenerator(Generator):
    def generate_model(self, level: Level) -> str:
        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

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
            edges=_flatten([self._generate_edges(i, level, offsets) for i in sorted(level.reachable_tiles)])
        )

        return json.dumps(output, indent=4)

    @staticmethod
    def _generate_board(level: Level) -> [Expr]:
        return [{
            "name": f"box_{i}",
            "type": "bool",
            "initial-value": level.board[i] == TileType.BOX
        } for i in sorted(level.reachable_tiles)]

    @staticmethod
    def _generate_property(level: Level) -> Expr:
        return _pmax_property("goal_reached", _and(*[_eq(f"box_{goal}", True) for goal in level.goals]))

    @staticmethod
    def _generate_edges(position: int, level: Level, offsets: dict[str, int]) -> [Expr]:
        def to_push_assignments(y: int, z: int) -> [Expr]:
            return [
                _assignment("position", _if(_and(f"box_{y}", _neg(f"box_{z}")), y, "position")),
                _assignment(f"box_{y}", _and(f"box_{y}", f"box_{z}")),
                _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
            ]

        def to_move_assignment(y: int) -> [Expr]:
            return [_assignment("position", _if(_neg(f"box_{y}"), y, "position"))]

        def to_assignments(direction: str) -> [[Expr]]:
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

        def to_move_command(x: int, y: int) -> tuple[Expr, [Expr]]:
            return _and(_eq("position", x), _neg(f"box_{y}")), [_assignment("position", y)]

        def to_push_command(x: int, y: int, z: int) -> tuple[Expr, [Expr]]:
            return _and(_eq("position", x), _neg(_and(f"box_{y}", f"box_{z}"))), [
                _assignment("position", y),
                _assignment(f"box_{y}", False),
                _assignment(f"box_{z}", _or(f"box_{y}", f"box_{z}"))
            ]

        edges = []
        for d, o in offsets.items():
            destinations = []
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                guard, assignment = to_push_command(position, position + o, position + 2 * o)
            elif position + o in level.reachable_tiles:
                guard, assignment = to_move_command(position, position + o)
            else:
                continue

            prob_assignments = to_assignments(d)
            if len(prob_assignments) == 0:
                destinations.append(_destination("move", 1, assignment))
            else:
                destinations.append(_destination("move", "mu", assignment))
                prob = _sub(1, "mu") if len(prob_assignments) == 1 else _div(_sub(1, "mu"), len(prob_assignments))
                destinations += [_destination("move", prob, pa) for pa in prob_assignments]

            edges.append(_edge(d, guard, destinations))

        return edges
