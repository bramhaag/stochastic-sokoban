from decimal import Decimal

from generator.generator import Generator
from parser.level import Level, TileType


class SokGenerator(Generator):
    def generate_model(self, level: Level, probabilities: dict[str, Decimal]) -> str:
        output = ""
        for i in range(level.rows):
            for j in range(level.columns):
                index = i * level.columns + j
                tile = level.board[index]
                match tile:
                    case TileType.FLOOR:
                        if index in level.goals and level.player == index:
                            output += "P"
                        elif level.player == index:
                            output += "p"
                        elif index in level.goals:
                            output += "."
                        else:
                            output += "-"
                    case TileType.BOX:
                        output += "B" if index in level.goals else "b"
                    case TileType.WALL:
                        output += "#"

            output += "\n"

        return output
