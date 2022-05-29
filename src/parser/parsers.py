from abc import ABC, abstractmethod

from parser.level import Level, TileType


class Parser(ABC):

    @abstractmethod
    def parse_levels(self, text: str) -> list[Level]:
        pass


class SimpleSokParser(Parser):
    def parse_levels(self, text: str) -> list[Level]:
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

        return [Level(board, player, goals, rows, columns)]


class SokParser(Parser):
    LINE_SEP = "|"

    # Run-length encoding characters
    RLE_DIGIT = set("0123456789")
    RLE_GROUP_OPEN = "("
    RLE_GROUP_CLOSE = ")"

    # Tile characters, some values are duplicated as they belong to multiple categories
    TILE_WALL = {"#"}
    TILE_PUSHER = {"p", "@", "P", "+"}
    TILE_BOX = {"b", "$", "B", "*"}
    TILE_GOAL = {".", "B", "*", "P", "+"}
    TILE_EMPTY = {" ", "-", "_"}
    TILE_FLOOR = TILE_EMPTY | TILE_PUSHER | {"."}

    # All tile characters
    TILE_CHARS = TILE_WALL | TILE_PUSHER | TILE_BOX | TILE_GOAL | TILE_FLOOR

    # All valid board characters, including RLE characters and alternative line separators
    BOARD_CHARS = TILE_CHARS | RLE_DIGIT | {RLE_GROUP_OPEN, RLE_GROUP_CLOSE} | {LINE_SEP}

    # Comment lines
    COMMENT = "::"

    def parse_levels(self, text: str) -> list[Level]:
        levels = []

        lines = text.splitlines()
        i = 0

        # Remove comments
        lines = [line for line in lines if not line.startswith(self.COMMENT)]

        while True:
            # Skip titles and other text
            i = self._consume_until_board(lines, i)

            # Check if the end is reached
            if i == len(lines):
                break

            # Normalize board
            input_board = []
            while i < len(lines):
                result, line = self._parse_board_line(lines[i])
                if not result:
                    break

                input_board.extend(line.split(self.LINE_SEP))
                i += 1

            levels.append(self._parse_board(input_board))

        return levels

    def _consume_until_board(self, lines: list[str], i: int = 0) -> int:
        while i < len(lines) and not self._parse_board_line(lines[i])[0]:
            i += 1

        return i

    def _parse_board(self, lines: list[str]) -> Level:
        rows, columns = len(lines), max(len(line) for line in lines)

        # Pad lines with spaces (floor tiles) to be equal length
        input_board = [line.ljust(columns) for line in lines]

        board = []
        pusher = None
        goals = []

        for i, line in enumerate(input_board):
            for j, c in enumerate(line):
                # Store goals
                if c in self.TILE_GOAL:
                    goals.append(i * columns + j)

                # Store pusher position
                if c in self.TILE_PUSHER:
                    pusher = i * columns + j

                # Convert character to tile
                if c in self.TILE_FLOOR:
                    board.append(TileType.FLOOR)

                if c in self.TILE_BOX:
                    board.append(TileType.BOX)

                if c in self.TILE_WALL:
                    board.append(TileType.WALL)

        return Level(board, pusher, goals, rows, columns)

    def _parse_board_line(self, input_line: str) -> tuple[bool, str]:
        # Check if line contains only board characters
        if not set(input_line).issubset(self.BOARD_CHARS):
            return False, ""

        # Decode RLE
        output_line = ""
        i = 0
        while i < len(input_line):
            c = input_line[i]
            if c in self.RLE_DIGIT:
                i, num = self._parse_rle_digit(i, input_line)
                i, value = self._parse_rle_group(num, i, input_line)
                output_line += value
            else:
                output_line += c
                i += 1

        # Strip trailing |
        if len(output_line) > 0 and output_line[-1] == self.LINE_SEP:
            output_line = output_line[:-1]

        # Check if line starts and ends with box on goal tile or wall tile
        s_line = output_line.strip(str(self.TILE_EMPTY))
        if len(s_line) == 0:
            return False, ""

        first, last = s_line[0], s_line[-1]

        def valid_line(line: str) -> bool:
            return line[0] in self.TILE_WALL or (line[-1] in self.TILE_GOAL and line[-1] in self.TILE_BOX)

        if not valid_line(first) or not valid_line(last):
            return False, ""

        return True, output_line

    def _parse_rle_digit(self, i: int, line: str) -> tuple[int, int]:
        digit = ""
        while (char := line[i]) in self.RLE_DIGIT:
            digit += char
            i += 1

        return i, int(digit)

    def _parse_rle_group(self, num: int, i: int, line: str) -> tuple[int, str]:
        scope = 0
        value = ""

        while True:
            if line[i] == self.RLE_GROUP_OPEN:
                scope += 1
            elif line[i] == self.RLE_GROUP_CLOSE:
                scope -= 1

            value += line[i]
            i += 1

            if scope == 0:
                break

        # Trim open and close chars
        if len(value) > 1:
            value = value[1:-1]

        return i, self._parse_board_line(value * num)[1]
