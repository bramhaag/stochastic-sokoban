import argparse
import logging
import os.path
import sys

from PIL import Image, ImageFont, ImageDraw

from parser.level import TileType, Level
from parser.parsers import SokParser
from util.util import exit_with_error

DIR = os.path.dirname(sys.argv[0])
IMG_FLOOR = Image.open(f"{DIR}/res/floor.png").convert("RGBA")
IMG_WALL = Image.open(f"{DIR}/res/wall.png").convert("RGBA")
IMG_GOAL = Image.open(f"{DIR}/res/goal.png").convert("RGBA")
IMG_BOX = Image.open(f"{DIR}/res/box.png").convert("RGBA")
IMG_PLAYER = Image.open(f"{DIR}/res/player.png").convert("RGBA")

TILE_SIZE = 64

PARSER = SokParser()

arg_parser = argparse.ArgumentParser(add_help=False)

required = arg_parser.add_argument_group("required")
optional = arg_parser.add_argument_group("optional")

optional.add_argument("-i", "--input",
                      type=str,
                      help="input file path")
optional.add_argument("-o", "--output",
                      type=str,
                      help="output file path")
optional.add_argument("-ix", "--indices",
                      nargs="+",
                      type=int,
                      help="space seperated list of level indices. Omit to use all levels")
optional.add_argument("-f", "--force",
                      action="store_true",
                      help="overwrite output file")
optional.add_argument("-t", "--text",
                      action="store_true",
                      help="display tile position indices")
optional.add_argument("-h", "--help",
                      action="help",
                      help="show this help message and exit"
                      )

args = arg_parser.parse_args()

logging.basicConfig(format="%(levelname)s: %(message)s")


def level_to_image(level: Level, draw_indices: bool) -> Image:
    image = Image.new('RGBA', (level.columns * TILE_SIZE, level.rows * TILE_SIZE))

    for y in range(level.rows):
        for x in range(level.columns):
            i = y * level.columns + x
            c = (x * TILE_SIZE, y * TILE_SIZE)
            match level.board[i]:
                case TileType.FLOOR:
                    if i not in level.reachable_tiles:
                        continue
                    image.paste(IMG_FLOOR, c)
                case TileType.BOX:
                    image.paste(IMG_FLOOR, c)
                case TileType.WALL:
                    image.paste(IMG_WALL, c)

            if i in level.goals:
                image.paste(IMG_GOAL, c, IMG_GOAL)

            if level.player == i:
                image.paste(IMG_PLAYER, c, IMG_PLAYER)

            if level.board[i] == TileType.BOX:
                image.paste(IMG_BOX, c, IMG_BOX)

    if draw_indices:
        image = draw_tile_indices(image, level)

    return image


def draw_tile_indices(image: Image, level: Level) -> Image:
    text = Image.new("RGBA", image.size, (255, 255, 255, 0))
    font = ImageFont.truetype("arialbd.ttf", 20, encoding="unic")
    draw = ImageDraw.Draw(text)
    for y in range(level.rows):
        for x in range(level.columns):
            draw.text((x * TILE_SIZE + 2, y * TILE_SIZE + 40), str(y * level.columns + x), (0, 0, 0), font=font)

    return Image.alpha_composite(image, text)


# Read levels from input
if args.input is not None:
    try:
        with open(args.input, 'r') as in_file:
            text = in_file.read()
    except FileNotFoundError:
        exit_with_error("File not found: " + args.input)
else:
    text = sys.stdin.read().rstrip()

# Parse and filter levels
levels = PARSER.parse_levels(text)
levels = list(map(levels.__getitem__, args.indices or range(len(levels))))

if len(levels) == 0:
    exit_with_error("No parseable levels found in input")

# Generate images
images = [level_to_image(level, args.text) for level in levels]

if not args.output:
    if len(images) > 1:
        exit_with_error("Can only write one model to stdout. Specify an output file with --output instead.")

    if args.force:
        logging.warning("Argument --force ignored as no output file is specified")

    images[0].save(sys.stdout, "png")
else:
    for i, img in enumerate(images):
        file_name, extension = os.path.splitext(args.output)
        path = f"{file_name}_{i}{extension}"

        if os.path.exists(path) and not args.force:
            logging.warning(f"File '{path}' already exists. Run with the --force flag to overwrite files.")

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb+") as file:
            img.save(file, "png")
