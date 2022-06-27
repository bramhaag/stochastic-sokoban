import textwrap

from generator.generator import Generator
from generator.string_generators import SokGenerator
from parser.level import Level, TileType

STRING_GENERATOR = SokGenerator()


def _indent(s: str, n: int = 12) -> str:
    return s.replace('\n', '\n' + (' ' * n))


def _level_to_string(level) -> str:
    return "\n".join(f"// {line}" for line in STRING_GENERATOR.generate_model(level, {}).splitlines())


class PrismNonStochasticGenerator(Generator):
    def generate_model(self, level: Level) -> str:
        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        return textwrap.dedent(f"""
        {_indent(_level_to_string(level), 8)}
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};
        
        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};

            {_indent(self._generate_board(level))}

            {_indent((chr(10) * 2).join(self._generate_actions(i, level, offsets)
                                        for i in sorted(level.reachable_tiles)))}
        endmodule
        
        rewards
            true: 1;
        endrewards""").strip()

    @staticmethod
    def _generate_board(level: Level) -> str:
        def to_variable(name: str, value: bool) -> str:
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in
                         sorted(level.reachable_tiles | set(level.goals)))

    @staticmethod
    def _generate_actions(position: int, level: Level, offsets: dict[str, int]) -> str:
        def to_move(direction: str, first_pos: int, second_pos: int) -> str:
            return f"[{direction}] position={first_pos} & !box_{second_pos} -> (position'={second_pos});"

        def to_move_and_push(direction: str, x: int, y: int, z: int) -> str:
            return f"[{direction}] position={x} & !(box_{y} & box_{z}) " \
                   f"-> (position'={y}) & (box_{y}'=false) & (box_{z}'=box_{y} | box_{z});"

        commands = []
        for d, o in offsets.items():
            if position + o in level.reachable_tiles and position + 2 * o in level.reachable_tiles:
                commands.append(to_move_and_push(d, position, position + o, position + 2 * o))
            elif position + o in level.reachable_tiles:
                commands.append(to_move(d, position, position + o))

        return '\n'.join(commands)


class PrismGenerator(Generator):
    def generate_model(self, level: Level) -> str:
        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        return textwrap.dedent(f"""
        {_indent(_level_to_string(level), 8)}
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};

        const double mu;

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};

            {_indent(self._generate_board(level))}

            {_indent((chr(10) * 2).join(self._generate_actions(i, level, offsets)
                                        for i in sorted(level.reachable_tiles)))}
        endmodule

        rewards
            true: 1;
        endrewards""").strip()

    @staticmethod
    def _generate_board(level: Level) -> str:
        def to_variable(name: str, value: bool) -> str:
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in
                         sorted(level.reachable_tiles | set(level.goals)))

    @staticmethod
    def _generate_actions(position: int, level: Level, offsets: dict[str, int]) -> str:
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


class PrismBGenerator(Generator):
    def generate_model(self, level: Level) -> str:
        offsets = {
            "up": -level.columns,
            "down": level.columns,
            "left": -1,
            "right": 1
        }

        return textwrap.dedent(f"""
        {_indent(_level_to_string(level), 8)}
        mdp

        label "goal_reached" = {"&".join(f"box_{g}=true" for g in level.goals)};

        const double mu;

        module Player
            position: [{level.first_pos}..{level.last_pos}] init {level.player};

            {_indent(self._generate_board(level))}

            {_indent((chr(10) * 2).join(self._generate_actions(i, level, offsets)
                                        for i in sorted(level.reachable_tiles)))}
        endmodule

        rewards
            true: 1;
        endrewards""").strip()

    @staticmethod
    def _generate_board(level: Level) -> str:
        def to_variable(name: str, value: bool) -> str:
            return f"{name}: bool init {str(value).lower()};"

        return '\n'.join(to_variable(f"box_{i}", level.board[i] == TileType.BOX) for i in
                         sorted(level.reachable_tiles | set(level.goals)))

    @staticmethod
    def _generate_actions(position: int, level: Level, offsets: dict[str, int]) -> str:
        def to_move_expression(y: int) -> str:
            return f"(position'=!box_{y} ? {y} : position)"

        def to_expressions(direction: str) -> [str]:
            expressions = []
            for current_direction, offset in offsets.items():
                if current_direction == direction:
                    continue

                y = position + offset
                if y in level.reachable_tiles:
                    expressions.append(to_move_expression(y))

            probability = "(1-mu)" if len(expressions) == 1 else f"(1-mu)/{len(expressions)}"
            return [f"{probability}:{e}" for e in expressions]

        def to_move_command(direction: str, x: int, y: int) -> tuple[str, str]:
            return f"[{direction}] position={x} & !box_{y}", f"(position'={y})"

        def to_push_command(direction: str, x: int, y: int, z: int) -> tuple[str, str]:
            return f"[{direction}] position={x} & !(box_{y} & box_{z})", \
                   f"(position'={y}) & (box_{y}'=false) & (box_{z}'=box_{y} | box_{z})"

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
