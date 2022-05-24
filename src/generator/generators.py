import itertools
import json
import textwrap
from abc import ABC, abstractmethod
from decimal import Decimal
from functools import reduce

from parser.level import Level, TileType


class Generator(ABC):

    @abstractmethod
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        pass


class PrismGenerator(Generator):
    BOX_LINE = "box_{0}: bool init {1};"

    MOVE_LINE = "[] state={0} & position={1} & box_{2}=false -> " \
                "(position'={2}) & (state'=0);"

    PUSH_LINE = "[] state={0} & position={1} & box_{2}=true & box_{3}=false -> " \
                "(position'={2}) & (box_{2}'=false) & (box_{3}'=true) & (state'=0);"

    STATES = {
        1: "u",
        3: "d",
        5: "l",
        7: "r"
    }

    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        return textwrap.dedent(f"""
        mdp
        
        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};
            state: [0..8] init 0;
            
            {self._indent(self._generate_board(level))}

            {self._generate_prob_edges(probabilities)}
            
            {self._indent(self._generate_move(1, level, -level.columns))}
            {self._indent(self._generate_push(2, level, -level.columns))}
            
            {self._indent(self._generate_move(3, level, level.columns))}
            {self._indent(self._generate_push(4, level, level.columns))}
            
            {self._indent(self._generate_move(5, level, -1))}
            {self._indent(self._generate_push(6, level, -1))} 
            
            {self._indent(self._generate_move(7, level, 1))}
            {self._indent(self._generate_push(8, level, 1))}
        endmodule
        """).strip()

    def _generate_board(self, level: Level):
        return '\n'.join(self.BOX_LINE.format(i, str(level.board[i] == TileType.BOX).lower())
                         for i in level.reachable_tiles)

    def _generate_prob_edges(self, probabilities: dict[str, Decimal]):
        edges = [f"{probabilities[v] / 2}:(state'={k}) + {probabilities[v] / 2}:(state'={k + 1})"
                 for k, v in self.STATES.items()]
        return f"[] state=0 -> {' + '.join(edges)};"

    def _generate_move(self, state: int, level: Level, offset: int):
        if offset < 0:
            start, end = max(-offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - offset, level.last_pos + 1)

        return '\n'.join(self.MOVE_LINE.format(state, i, j)
                         for i, j in self._multi_range(start, end, [offset], level.reachable_tiles))

    def _generate_push(self, state: int, level: Level, offset: int):
        if offset < 0:
            start, end = max(-2 * offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - 2 * offset, level.last_pos + 1)

        return '\n'.join(self.PUSH_LINE.format(state, i, j, k)
                         for i, j, k in self._multi_range(start, end, [offset, 2 * offset], level.reachable_tiles))

    @staticmethod
    def _indent(s: str, n: int = 12):
        return s.replace('\n', '\n' + (' ' * n))

    @staticmethod
    def _multi_range(start: int, end: int, offset: list[int], valid: set[int]):
        return [x for x in zip(range(start, end), *[range(start + o, end + o) for o in offset])
                if set(x).issubset(valid)]


class Prism2Generator(Generator):
    BOX_LINE = "box_{0}: [{1}..{2}] init {3};"

    MOVE_LINE = "[] state={0} & position={1} & {2} -> " \
                "(position'={2}) & (state'=0);"

    PUSH_LINE = "[] state={0} & position={1} & box_{2}=true & box_{3}=false -> " \
                "(position'={2}) & (box_{2}'=false) & (box_{3}'=true) & (state'=0);"

    STATES = {
        1: "u",
        3: "d",
        5: "l",
        7: "r"
    }

    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        return textwrap.dedent(f"""
        mdp

        {self._generate_goal_label(level)}

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};
            state: [0..8] init 0;
            
            {self._indent(self._generate_board(level))}

            {self._generate_prob_edges(probabilities)}

            {self._indent(self._generate_move(1, level, -level.columns))}
            {self._indent(self._generate_push(2, level, -level.columns))}

            {self._indent(self._generate_move(3, level, level.columns))}
            {self._indent(self._generate_push(4, level, level.columns))}

            {self._indent(self._generate_move(5, level, -1))}
            {self._indent(self._generate_push(6, level, -1))} 

            {self._indent(self._generate_move(7, level, 1))}
            {self._indent(self._generate_push(8, level, 1))}
        endmodule
        """).strip()

    def _generate_goal_label(self, level: Level):
        goal_states = []
        for permutation in itertools.permutations(level.goals):
            goal_states.append(
                "(" + "&".join(f"box_{b}={v}" for b, v in zip(range(len(level.goals)), permutation)) + ")")

        return f'label "goal_reached" = {"|".join(goal_states)};'

    def _generate_board(self, level: Level):
        return '\n'.join(self.BOX_LINE.format(i, level.first_pos, level.last_pos, p) for i, p in enumerate(level.boxes))

    def _generate_prob_edges(self, probabilities: dict[str, Decimal]):
        edges = [f"{probabilities[v] / 2}:(state'={k}) + {probabilities[v] / 2}:(state'={k + 1})"
                 for k, v in self.STATES.items()]
        return f"[] state=0 -> {' + '.join(edges)};"

    def _generate_move(self, state: int, level: Level, offset: int):
        if offset < 0:
            start, end = max(-offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - offset, level.last_pos + 1)

        box_guard = ' & '.join([f"box_{i} != {{0}}" for i in range(len(level.boxes))])
        return '\n'.join(f"[] state={state} & position={i} & {box_guard.format(j)} -> (position'={j}) & (state'=0);"
                         for i, j in self._multi_range(start, end, [offset], level.reachable_tiles))

    def _generate_push(self, state: int, level: Level, offset: int):
        if offset < 0:
            start, end = max(-2 * offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - 2 * offset, level.last_pos + 1)

        statements = []
        for b in range(len(level.boxes)):
            box_guard = ' & '.join([f"box_{i} != {{0}} & box_{i} != {{1}}" for i in range(len(level.boxes)) if b != i])
            box_guard += f" & box_{b}={{0}}"

            statements.extend(
                f"[] state={state} & position={i} & {box_guard.format(j, k)} "
                f"-> (position'={j}) & (box_{b}'={k}) & (state'=0);"
                for i, j, k in self._multi_range(start, end, [offset, 2 * offset], level.reachable_tiles))

        return '\n'.join(statements)

    @staticmethod
    def _indent(s: str, n: int = 12):
        return s.replace('\n', '\n' + (' ' * n))

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
