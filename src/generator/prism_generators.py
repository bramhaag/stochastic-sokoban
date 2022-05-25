import itertools
import textwrap

from _decimal import Decimal

from generator.generator import Generator, _multi_range, _move_bounds
from parser.level import Level, TileType

STATES = {
    1: "u",
    3: "d",
    5: "l",
    7: "r"
}


def _indent(s: str, n: int = 12):
    return s.replace('\n', '\n' + (' ' * n))


class PrismBoxGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        return textwrap.dedent(f"""
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};
            state: [0..8] init 0;

            {_indent(self._generate_board(level))}

            {self._generate_prob_edges(probabilities)}

            {_indent(self._generate_move(1, level, -level.columns))}
            {_indent(self._generate_push(2, level, -level.columns))}

            {_indent(self._generate_move(3, level, level.columns))}
            {_indent(self._generate_push(4, level, level.columns))}

            {_indent(self._generate_move(5, level, -1))}
            {_indent(self._generate_push(6, level, -1))} 

            {_indent(self._generate_move(7, level, 1))}
            {_indent(self._generate_push(8, level, 1))}
        endmodule
        """).strip()

    @staticmethod
    def _generate_board(level: Level):
        def to_variable(name: str, value: bool):
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in level.reachable_tiles)

    @staticmethod
    def _generate_prob_edges(probabilities: dict[str, Decimal]):
        def to_edge(state: int, label: str) -> str:
            return f"{probabilities[label] / 2}:(state'={state}) + {probabilities[label] / 2}:(state'={state + 1})"

        return f"[] state=0 -> {' + '.join(to_edge(k, v) for k, v in STATES.items())};"

    @staticmethod
    def _generate_move(state: int, level: Level, offset: int):
        def to_line(pos: int, next_pos: int) -> str:
            return f"[] state={state} & position={pos} & box_{next_pos}=false -> (position'={next_pos}) & (state'=0);"

        start, end = _move_bounds(level, offset)
        return '\n'.join(to_line(i, j) for i, j in _multi_range(start, end, [offset], level.reachable_tiles))

    @staticmethod
    def _generate_push(state: int, level: Level, offset: int):
        def to_line(pos: int, next_pos: int, box_pos: int) -> str:
            return f"[] state={state} & position={pos} & box_{next_pos}=true & box_{box_pos}=false -> " \
                   f"(position'={next_pos}) & (box_{next_pos}'=false) & (box_{box_pos}'=true) & (state'=0);"

        start, end = _move_bounds(level, 2 * offset)
        return '\n'.join(to_line(i, j, k)
                         for i, j, k in _multi_range(start, end, [offset, 2 * offset], level.reachable_tiles))


class PrismPosGenerator(Generator):
    BOX_LINE = "box_{0}: [{1}..{2}] init {3};"

    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        return textwrap.dedent(f"""
        mdp

        {self._generate_goal_label(level)}

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};
            state: [0..8] init 0;

            {_indent(self._generate_board(level))}

            {self._generate_prob_edges(probabilities)}

            {_indent(self._generate_move(1, level, -level.columns))}
            {_indent(self._generate_push(2, level, -level.columns))}

            {_indent(self._generate_move(3, level, level.columns))}
            {_indent(self._generate_push(4, level, level.columns))}

            {_indent(self._generate_move(5, level, -1))}
            {_indent(self._generate_push(6, level, -1))} 

            {_indent(self._generate_move(7, level, 1))}
            {_indent(self._generate_push(8, level, 1))}
        endmodule
        """).strip()

    @staticmethod
    def _generate_goal_label(level: Level):
        def to_state(boxes: list[int]) -> str:
            return "(" + "&".join(f"box_{b}={v}" for b, v in zip(range(len(level.goals)), boxes)) + ")"

        # noinspection PyTypeChecker
        return f'label "goal_reached" = {"|".join([to_state(p) for p in itertools.permutations(level.goals)])};'

    @staticmethod
    def _generate_board(level: Level):
        def to_variable(box: int, pos: int):
            return f"box_{box}: [{level.first_pos}..{level.last_pos}] init {pos};"

        return '\n'.join(to_variable(i, p) for i, p in enumerate(level.boxes))

    @staticmethod
    def _generate_prob_edges(probabilities: dict[str, Decimal]):
        def to_edge(state: int, label: str) -> str:
            return f"{probabilities[label] / 2}:(state'={state}) + {probabilities[label] / 2}:(state'={state + 1})"

        return f"[] state=0 -> {' + '.join(to_edge(k, v) for k, v in STATES.items())};"

    @staticmethod
    def _generate_move(state: int, level: Level, offset: int):
        def to_box_guard(pos: int):
            return " & ".join([f"box_{i} != {pos}" for i in range(len(level.boxes))])

        def to_line(pos: int, next_pos: int):
            return f"[] state={state} & position={pos} & {to_box_guard(next_pos)} -> " \
                   f"(position'={next_pos}) & (state'=0);"

        start, end = _move_bounds(level, offset)

        return '\n'.join(to_line(i, j) for i, j in _multi_range(start, end, [offset], level.reachable_tiles))

    @staticmethod
    def _generate_push(state: int, level: Level, offset: int):
        def to_box_guard(box: int, pos: int, next_pos: int):
            return " & ".join([f"box_{box}={pos}"] + [f"box_{i} != {pos} & box_{i} != {next_pos}"
                                                      for i in range(len(level.boxes)) if box != i])

        def to_line(box: int, pos: int, next_pos: int, box_pos: int):
            return f"[] state={state} & position={pos} & {to_box_guard(box, next_pos, box_pos)} -> " \
                   f"(position'={next_pos}) & (box_{box}'={box_pos}) & (state'=0);"

        start, end = _move_bounds(level, 2 * offset)

        return '\n'.join(to_line(b, i, j, k)
                         for b in range(len(level.boxes))
                         for i, j, k in _multi_range(start, end, [offset, 2 * offset], level.reachable_tiles))
