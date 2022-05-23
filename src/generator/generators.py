import textwrap
from abc import ABC, abstractmethod
from decimal import Decimal

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

        return '\n'.join(self.MOVE_LINE.format(state, i, i + offset)
                         for i in range(start, end)
                         if not level.is_wall(i)
                         and not level.is_wall(i + offset))

    def _generate_push(self, state: int, level: Level, offset: int):
        if offset < 0:
            start, end = max(-2 * offset, level.first_pos), level.last_pos + 1
        else:
            start, end = level.first_pos, min(level.size - 2 * offset, level.last_pos + 1)

        return '\n'.join(self.PUSH_LINE.format(state, i, i + offset, i + 2 * offset)
                         for i in range(start, end)
                         if not level.is_wall(i)
                         and not level.is_wall(i + offset)
                         and not level.is_wall(i + 2 * offset))

    @staticmethod
    def _indent(s: str, n: int = 12):
        return s.replace('\n', '\n' + (' ' * n))


class JaniGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        pass
