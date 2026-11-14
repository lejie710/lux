"""Prepare the site's pictures from the full-size source plates.

The source plates are 2400 x 1500 PNG files and are not kept in this
repository. This script turns them into what the site ships:

  src/assets/laptop-dark.webp    the laptop, cropped close, edges faded to black
  src/assets/board-dark.webp     the board before power
  src/assets/board-awake.webp    the same board with every part lit
  src/assets/masks/<part>.webp   one soft mask per part of the board
  src/assets/parts.json          where each part lies on the board, as fractions of the plate

A stop's picture is not a file. The page stacks board-awake over board-dark
once per part, each copy cut out by that part's mask, and fades the copies in.
Because every stop is made from the same two plates, parts never move.

Usage: python tools/make_assets.py <folder with the source plates>
Needs Pillow. Run from the site folder.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

PLATE = (2400, 1500)
BOARD_OUT = (1920, 1200)
# The laptop with a margin, in source pixels: left, top, right, bottom.
LAPTOP_BOX = (400, 250, 2000, 1450)
LAPTOP_OUT = (1280, 960)
MASK_OUT = (600, 375)
FEATHER = 70  # in source pixels

# The parts of the board, as polygons in source pixels.
REGIONS = {
    "power": [(0, 960), (500, 960), (500, 1500), (0, 1500)],
    "firmware": [(560, 1150), (780, 1150), (780, 1320), (560, 1320)],
    "processor": [(800, 860), (1480, 860), (1500, 1290), (790, 1290)],
    "memory": [(660, 710), (1470, 710), (1470, 880), (660, 880)],
    "controllers": [(1480, 880), (1810, 880), (1830, 1310), (1500, 1310)],
    "storage": [(1740, 720), (2180, 720), (2330, 1200), (2010, 1210)],
    "security": [(1820, 1150), (1980, 1150), (1980, 1260), (1820, 1260)],
    "ribbon": [(2060, 560), (2400, 560), (2400, 800), (2060, 800)],
}


def on_black(path: Path) -> Image.Image:
    """The plate as plain RGB over black, whatever transparency the file carries."""
    plate = Image.open(path).convert("RGBA")
    if plate.size != PLATE:
        raise SystemExit(f"{path.name}: expected {PLATE}, found {plate.size}")
    black = Image.new("RGBA", plate.size, (0, 0, 0, 255))
    return Image.alpha_composite(black, plate).convert("RGB")


def edge_fade(size: tuple[int, int], margin: int) -> Image.Image:
    """White in the middle, falling to black over `margin` pixels at every edge."""
    w, h = size
    fade = Image.new("L", size, 0)
    ImageDraw.Draw(fade).rectangle((margin, margin, w - margin, h - margin), fill=255)
    return fade.filter(ImageFilter.GaussianBlur(margin / 2))


def part_mask(polygon: list[tuple[int, int]]) -> Image.Image:
    """A feathered mask of one part. The shape is in the alpha channel, which is what a CSS mask reads."""
    shape = Image.new("L", PLATE, 0)
    ImageDraw.Draw(shape).polygon(polygon, fill=255)
    soft = shape.filter(ImageFilter.GaussianBlur(FEATHER)).resize(MASK_OUT, Image.LANCZOS)
    mask = Image.new("RGBA", MASK_OUT, (255, 255, 255, 0))
    mask.putalpha(soft)
    return mask


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    plates = Path(sys.argv[1])
    out = Path("src/assets")
    (out / "masks").mkdir(parents=True, exist_ok=True)

    for name in ("board-dark", "board-awake"):
        board = on_black(plates / f"lux-{name}.png").resize(BOARD_OUT, Image.LANCZOS)
        board.save(out / f"{name}.webp", quality=84, method=6)

    laptop = on_black(plates / "lux-laptop-dark.png").crop(LAPTOP_BOX).resize(LAPTOP_OUT, Image.LANCZOS)
    fade = edge_fade(LAPTOP_OUT, 56).convert("RGB")
    ImageChops.multiply(laptop, fade).save(out / "laptop-dark.webp", quality=86, method=6)

    for part, polygon in REGIONS.items():
        part_mask(polygon).save(out / "masks" / f"{part}.webp", lossless=True, method=6)

    # Where each part lies, so the page can keep the parts a step lights in view on a narrow window.
    boxes = {}
    for part, polygon in REGIONS.items():
        xs = [x / PLATE[0] for x, _ in polygon]
        ys = [y / PLATE[1] for _, y in polygon]
        boxes[part] = {
            "left": round(min(xs), 4),
            "right": round(max(xs), 4),
            "top": round(min(ys), 4),
            "bottom": round(max(ys), 4),
        }
    (out / "parts.json").write_text(json.dumps(boxes, indent=2) + chr(10), encoding="utf-8")

    for path in sorted(out.rglob("*.webp")):
        print(f"{path.as_posix()}  {Image.open(path).size}  {path.stat().st_size} bytes")


main()
