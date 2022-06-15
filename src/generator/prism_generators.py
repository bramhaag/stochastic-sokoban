import decimal
import itertools
import textwrap

from generator.generator import Generator, _multi_range, _move_bounds
from generator.string_generators import SokGenerator
from parser.level import Level, TileType

STATES = {
    1: "u",
    2: "U",
    3: "d",
    4: "D",
    5: "l",
    6: "L",
    7: "r",
    8: "R",
    9: "b",
}


def _indent(s: str, n: int = 12):
    return s.replace('\n', '\n' + (' ' * n))


class PrismNonDGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, decimal.Decimal]) -> str:
        level_str = "\n".join("// " + line for line in SokGenerator().generate_model(level, probabilities).splitlines())
        return level_str + "\n" + textwrap.dedent(f"""
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};
        
        const double mu;

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};

            {_indent(self._generate_board(level))}

            {_indent((chr(10) * 2).join(self._generate_actions(i, level) for i in sorted(level.reachable_tiles)))}
        endmodule
        
        rewards
            true: 1;
        endrewards""").strip()

    @staticmethod
    def _generate_board(level: Level):
        def to_variable(name: str, value: bool):
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in sorted(level.reachable_tiles))

    @staticmethod
    def _generate_actions(position: int, level: Level):
        def to_move(direction: str, first_pos: int, second_pos: int) -> str:
            return f"[{direction}] position={first_pos} & !box_{second_pos} -> (position'={second_pos});"

        def to_move_and_push(direction: str, x: int, y: int, z: int) -> str:
            return f"[{direction}] position={x} & !(box_{y} & box_{z}) " \
                   f"->  (position'={y}) & (box_{y}'=false) & (box_{z}'=box_{y} | box_{z});"

        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        commands = []
        for d, o in offsets.items():
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                commands.append(to_move_and_push(d, position, position + o, position + 2 * o))
            elif position + o in level.reachable_tiles:
                commands.append(to_move(d, position, position + o))

        return '\n'.join(commands)


class PrismSNonDGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, decimal.Decimal]) -> str:
        level_str = "\n".join("// " + line for line in SokGenerator().generate_model(level, probabilities).splitlines())
        return level_str + "\n" + textwrap.dedent(f"""
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};

        const double mu = 0.9;

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};

            {_indent(self._generate_board(level))}

            {_indent((chr(10) * 2).join(self._generate_actions(i, level) for i in sorted(level.reachable_tiles)))}
        endmodule

        rewards
            true: 1;
        endrewards""").strip()

    @staticmethod
    def _generate_board(level: Level):
        def to_variable(name: str, value: bool):
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in sorted(level.reachable_tiles))

    @staticmethod
    def _generate_actions(position: int, level: Level):
        # cond -> mu:M + (1-mu)/N:down + (1-mu)/N:up

        def to_push_expression(y: int, z: int) -> str:
            return f"(position'=box_{y} & !box_{z} ? {y} : position) " \
                   f"& (box_{y}'=box_{y} & box_{z}) " \
                   f"& (box_{z}'=box_{y} | box_{z})"

        def to_move_expression(y: int) -> str:
            return f"(position'=!box_{y} ? {y} : position)"

        def to_expressions(direction: str) -> [str]:
            expressions = []
            for current_direction, offset in offsets.items():
                if current_direction == direction:
                    continue

                y, z = position + offset, position + 2 * offset
                if y in level.reachable_tiles and z in level.reachable_tiles:
                    expressions.append(to_push_expression(y, z))
                elif y in level.reachable_tiles:
                    expressions.append(to_move_expression(y))

            probability = "(1-mu)" if len(expressions) == 1 else f"(1-mu)/{len(expressions)}"
            return [f"{probability}:{e}" for e in expressions]

        def to_move_command(direction: str, x: int, y: int) -> tuple[str, str]:
            return f"[{direction}] position={x} & !box_{y}", f"(position'={y})"

        def to_push_command(direction: str, x: int, y: int, z: int) -> tuple[str, str]:
            return f"[{direction}] position={x} & !(box_{y} & box_{z})", \
                   f"(position'={y}) & (box_{y}'=false) & (box_{z}'=box_{y} | box_{z})"

        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        commands = []
        for d, o in offsets.items():
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                guard, expression = to_push_command(d, position, position + o, position + 2 * o)
            elif position + o in level.reachable_tiles:
                guard, expression = to_move_command(d, position, position + o)
            else:
                continue

            exprs = to_expressions(d)
            if len(exprs) == 0:
                commands.append(f"{guard} -> {expression};")
            else:
                commands.append(f"{guard} -> mu:{expression} + {' + '.join(exprs)};")

        return '\n'.join(commands)


class PrismPosGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, decimal.Decimal]) -> str:
        return textwrap.dedent(f"""
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};
            state: [0..9] init 0;

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
            
            {_indent(self._generate_random_push(level, -level.columns))}
            {_indent(self._generate_random_push(level, level.columns))}
            {_indent(self._generate_random_push(level, -1))}
            {_indent(self._generate_random_push(level, 1))}
        endmodule
        """).strip()

    @staticmethod
    def _generate_board(level: Level):
        def to_variable(name: str, value: bool):
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in level.reachable_tiles)

    @staticmethod
    def _generate_prob_edges(probabilities: dict[str, decimal.Decimal]):
        def to_edge(state: int, label: str) -> str:
            return f"{probabilities[label]}:(state'={state})"

        return f"[] state=0 -> {' + '.join(to_edge(k, v) for k, v in STATES.items())};"

    @staticmethod
    def _generate_move(state: int, level: Level, offset: int):
        def to_line(pos: int, next_pos: int) -> str:
            return f"[move] state={state} & position={pos} & box_{next_pos}=false -> (position'={next_pos}) & (state'=0);"

        start, end = _move_bounds(level, offset)
        return '\n'.join(to_line(i, j) for i, j in _multi_range(start, end, [offset], level.reachable_tiles))

    @staticmethod
    def _generate_push(state: int, level: Level, offset: int):
        def to_line(pos: int, next_pos: int, box_pos: int) -> str:
            return f"[push] state={state} & position={pos} & box_{next_pos}=true & box_{box_pos}=false -> " \
                   f"(position'={next_pos}) & (box_{next_pos}'=false) & (box_{box_pos}'=true) & (state'=0);"

        start, end = _move_bounds(level, 2 * offset)
        return '\n'.join(to_line(i, j, k)
                         for i, j, k in _multi_range(start, end, [offset, 2 * offset], level.reachable_tiles))

    @staticmethod
    def _generate_random_push(level: Level, offset: int):
        def to_line(pos: int, next_pos: int) -> str:
            return f"[r_push] state=9 & box_{pos}=true & box_{next_pos}=false & position != {next_pos} -> " \
                   f"(box_{pos}'=false) & (box_{next_pos}'=true) & (state'=0);"

        start, end = _move_bounds(level, offset)
        return '\n'.join(to_line(i, j) for i, j in _multi_range(start, end, [offset], level.reachable_tiles))


class PrismBoxGenerator(Generator):
    BOX_LINE = "box_{0}: [{1}..{2}] init {3};"

    def generate_model(self, level: Level, probabilities: dict[str, decimal.Decimal]) -> str:
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
    def _generate_prob_edges(probabilities: dict[str, decimal.Decimal]):
        def to_edge(state: int, label: str) -> str:
            return f"{probabilities[label]}:(state'={state})"

        return f"[] state=0 -> {' + '.join(to_edge(k, v) for k, v in STATES.items())};"

    @staticmethod
    def _generate_move(state: int, level: Level, offset: int):
        def to_box_guard(pos: int):
            return " & ".join([f"box_{i} != {pos}" for i in range(len(level.boxes))])

        def to_line(pos: int, next_pos: int):
            return f"[move] state={state} & position={pos} & {to_box_guard(next_pos)} -> " \
                   f"(position'={next_pos}) & (state'=0);"

        start, end = _move_bounds(level, offset)

        return '\n'.join(to_line(i, j) for i, j in _multi_range(start, end, [offset], level.reachable_tiles))

    @staticmethod
    def _generate_push(state: int, level: Level, offset: int):
        def to_box_guard(box: int, pos: int, next_pos: int):
            return " & ".join([f"box_{box}={pos}"] + [f"box_{i} != {pos} & box_{i} != {next_pos}"
                                                      for i in range(len(level.boxes)) if box != i])

        def to_line(box: int, pos: int, next_pos: int, box_pos: int):
            return f"[push] state={state} & position={pos} & {to_box_guard(box, next_pos, box_pos)} -> " \
                   f"(position'={next_pos}) & (box_{box}'={box_pos}) & (state'=0);"

        start, end = _move_bounds(level, 2 * offset)

        return '\n'.join(to_line(b, i, j, k)
                         for b in range(len(level.boxes))
                         for i, j, k in _multi_range(start, end, [offset, 2 * offset], level.reachable_tiles))
