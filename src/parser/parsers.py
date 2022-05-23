from abc import ABC, abstractmethod

from parser.level import Level, TileType


class Parser(ABC):

    @abstractmethod
    def parse_level(self, text: str) -> Level:
        pass


class SokParser(Parser):
    def parse_level(self, text: str) -> Level:
        board = []
        player = None
        goals = []

        for i, c in enumerate(text.replace('\n', '')):
            match c:
                case ' ':
                    board.append(TileType.FLOOR)
                case 'b':
                    board.append(TileType.BOX)
                case '#':
                    board.append(TileType.WALL)
                case 'p':
                    board.append(TileType.FLOOR)
                    player = i
                case '.':
                    board.append(TileType.FLOOR)
                    goals.append(i)

        rows = len(text.split('\n'))
        columns = len(text.split('\n')[0])

        return Level(board, player, goals, rows, columns)
