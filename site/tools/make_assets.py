"""Prepare the site's pictures from the full-size source plates.

The source plates are 2400 x 1500 PNG files and are not kept in this
repository. This script turns them into what the site ships:

  src/assets/laptop-dark.webp    the laptop before power, cropped close, edges faded to black
  src/assets/laptop-inside.webp  the same laptop with the inside awake and the screen black
  src/assets/laptop-awake.webp   the same laptop with the screen lit
  src/assets/board-dark.webp     the board before power
  src/assets/board-awake.webp    the same board with every part lit
  src/assets/masks/<part>.webp   one soft mask per part of the board
  src/assets/masks/whole.webp    one soft mask of the whole board, for the stop where every part is lit
  src/assets/parts.json          where each part lies on the board, as fractions of the plate
  public/og.jpg                  the picture a link to the site is previewed with, 1200 x 630

Four pictures are lifted on the way: the laptop and the board before power,
the laptop with its inside awake, and the body (not the screen) of the laptop
with its screen lit. Their midtones and lit edges are raised
so the machine reads as an object on an ordinary screen in a lit room, while
the background stays black and the machine before power does not look switched
on. The lid of the two laptops with a dark screen gets a second, local lift:
its thin rim is made a few pixels wider and brighter, and the glass gets a
faint cool sheen, so the lid reads as a surface and not as a hole. The script
prints the mean brightness of each machine, and of its palm rest, rim and
glass, before and after.

A stop's picture is not a file. The page stacks board-awake over board-dark
once per part, each copy cut out by that part's mask, and fades the copies in.
Because every stop is made from the same two plates, parts never move.

The preview picture is composed from the same plates: the laptop before power
on the left, the same laptop with its screen lit on the right, and the name of
the site. It carries no other words.

Usage: python tools/make_assets.py <folder with the source plates> [--preview-only]
Needs Pillow. Run from the site folder. With --preview-only, only public/og.jpg is written.
"""

import json
import sys
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageStat

PLATE = (2400, 1500)
BOARD_OUT = (1920, 1200)
# The laptop with a margin, in source pixels: left, top, right, bottom.
LAPTOP_BOX = (400, 250, 2000, 1450)
LAPTOP_OUT = (1280, 960)
# How far in from each edge the laptop pictures melt into black, in output pixels. The lid's top rim lies 40
# pixels in, so the melt ends before it: a wider one dimmed the rim to a third.
EDGE_FADE = 18
MASK_OUT = (600, 375)
FEATHER = 70  # in source pixels
WHOLE_FEATHER = 160
# The whole board, for the stop where every part is lit: the ground between the parts lights too.
WHOLE = [(0, 660), (2400, 660), (2400, 1500), (0, 1500)]

# How the two pictures of the machine before power are lifted. A level v (0 to 1) becomes gain * v ** gamma;
# levels at or under `black` are left alone and the change is complete from `full` up, so the background
# stays black. `box` is where the machine lies in the source picture, for the measurement.
LIFT = {
    "laptop-dark": {"gamma": 0.55, "gain": 1.05, "black": 4, "full": 14, "box": (480, 290, 1910, 1380)},
    "laptop-inside-awake": {
        "gamma": 0.55,
        "gain": 1.05,
        "black": 4,
        "full": 14,
        "keep_colour": True,
        "box": (480, 290, 1910, 1380),
    },
    "board-dark": {"gamma": 0.62, "gain": 1.0, "black": 1.5, "full": 7, "box": (0, 660, 2400, 1500)},
    # The laptop with its screen lit: only the body under the hinge is lifted, and less, so that it is as
    # bright as the same body in the picture before it. The lit screen is left as it is.
    "laptop-awake": {
        "gamma": 0.75,
        "gain": 1.05,
        "black": 4,
        "full": 14,
        "keep_colour": True,
        "below": 992,
        "box": (480, 290, 1910, 1380),
    },
}

# The laptop with its screen lit is taken from the picture in which the light under the keys is turned
# down, so that on the last screen the lit display is the brightest thing in view.
SOURCE = {"laptop-awake": "laptop-awake-calm"}

# The lid of the laptop, in source pixels: the box its rim lies in, and the glass inside the rim.
LID_BOX = (570, 296, 1830, 986)
GLASS = [(610, 334), (1790, 334), (1768, 972), (632, 972)]
RIM_WIDEN = 7  # the rim grows by half of this on each side
RIM_GAIN = 1.3
RIM_CAP = 140  # the widened rim is no brighter than this; pixels that were brighter keep their own value
# The sheen on the glass: a cool grey, strongest at the top left corner and falling away to the bottom right.
SHEEN = ((14, 17, 23), (2, 2, 3))
# Parts of the laptop that are measured, in source pixels.
PALM_REST = (700, 1230, 1100, 1330)
RIM_TOP = (700, 300, 1700, 330)

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


def lift(
    picture: Image.Image,
    gamma: float,
    gain: float,
    black: float,
    full: float,
    keep_colour: bool = False,
    below: int | None = None,
) -> Image.Image:
    """
    Raise midtones and lit edges, level by level, and leave what is black as it is. With `keep_colour` only
    the brightness is raised: hue and saturation stay as they were, so a warm light stays as warm. With
    `below`, only the part of the picture under that row is changed, with a soft edge.
    """
    curve = []
    for level in range(256):
        t = min(1.0, max(0.0, (level - black) / (full - black)))
        t = t * t * (3 - 2 * t)
        raised = min(255.0, 255 * gain * (level / 255) ** gamma)
        curve.append(round(level + (raised - level) * t))
    raised = picture.point(curve * 3)
    if keep_colour:
        hue, saturation, _ = picture.convert("HSV").split()
        raised = Image.merge("HSV", (hue, saturation, raised.convert("HSV").getchannel("V"))).convert("RGB")
    if below is None:
        return raised
    under = Image.new("L", picture.size, 0)
    ImageDraw.Draw(under).rectangle((0, below, picture.size[0], picture.size[1]), fill=255)
    return Image.composite(raised, picture, under.filter(ImageFilter.GaussianBlur(10)))


def brightness(picture: Image.Image, box: tuple[int, int, int, int]) -> float:
    """The mean brightness (0 to 255) of one region of a picture."""
    return ImageStat.Stat(picture.crop(box).convert("L")).mean[0]


def lid_lift(picture: Image.Image) -> Image.Image:
    """Widen and brighten the rim of the lid, and lay a faint cool sheen on its glass. Nothing else changes."""
    lid = picture.crop(LID_BOX)
    # The rim: every pixel takes the brightest value near it, so a line two pixels wide survives being made small.
    wide = lid.filter(ImageFilter.MaxFilter(RIM_WIDEN)).filter(ImageFilter.GaussianBlur(0.8))
    wide = wide.point([min(RIM_CAP, round(level * RIM_GAIN)) for level in range(256)] * 3)
    # Only the rim is widened: the glass inside it and the hinge under it keep their own pixels.
    glass = Image.new("L", PLATE, 0)
    ImageDraw.Draw(glass).polygon(GLASS, fill=255)
    keep = ImageChops.invert(glass.filter(ImageFilter.MaxFilter(21))).crop(LID_BOX)
    rim = Image.composite(wide, lid, keep)
    out = picture.copy()
    out.paste(ImageChops.lighter(lid, rim), LID_BOX[:2])
    # The sheen: a diagonal fall of a cool grey, inside the glass only, added to what is there.
    near, far = SHEEN
    left, top = min(x for x, _ in GLASS), min(y for _, y in GLASS)
    right, bottom = max(x for x, _ in GLASS), max(y for _, y in GLASS)
    down = Image.linear_gradient("L")
    ramp = ImageChops.invert(ImageChops.add(down, down.transpose(Image.TRANSPOSE), scale=2))
    ramp = ramp.resize((right - left, bottom - top), Image.BICUBIC)
    fall = Image.new("L", PLATE, 0)
    fall.paste(ramp, (left, top))
    channels = [fall.point([round(f + (n - f) * level / 255) for level in range(256)]) for n, f in zip(near, far)]
    sheen = Image.merge("RGB", channels)
    soft = glass.filter(ImageFilter.GaussianBlur(5))
    return Image.composite(ImageChops.add(out, sheen), out, soft)


def lifted(plates: Path, name: str, lid: bool = False) -> Image.Image:
    """A picture lifted, with its measurements printed. With `lid`, the laptop's lid gets its own lift as well."""
    setting = dict(LIFT[name])
    box = setting.pop("box")
    before = on_black(plates / f"lux-{SOURCE.get(name, name)}.png")
    after = lift(before, **setting)
    if lid:
        after = lid_lift(after)
    print(
        f"{name}: mean brightness of the machine {brightness(before, box):.1f} -> {brightness(after, box):.1f}, "
        f"background corner {brightness(before, (0, 0, 300, 150)):.2f} -> {brightness(after, (0, 0, 300, 150)):.2f}"
    )
    if not lid and name.startswith("laptop"):
        print(f"  palm rest {brightness(before, PALM_REST):.1f} -> {brightness(after, PALM_REST):.1f}")
    if lid:
        glass = (GLASS[0][0] + 20, GLASS[0][1] + 20, GLASS[2][0] - 20, GLASS[2][1] - 20)
        print(
            f"  palm rest {brightness(before, PALM_REST):.1f} -> {brightness(after, PALM_REST):.1f}, "
            f"glass {brightness(before, glass):.1f} -> {brightness(after, glass):.1f}, "
            f"brightest of the top rim {before.crop(RIM_TOP).convert('L').getextrema()[1]} -> "
            f"{after.crop(RIM_TOP).convert('L').getextrema()[1]}"
        )
    return after


def edge_fade(size: tuple[int, int], margin: int) -> Image.Image:
    """White in the middle, falling to black over `margin` pixels at every edge."""
    w, h = size
    fade = Image.new("L", size, 0)
    ImageDraw.Draw(fade).rectangle((margin, margin, w - margin, h - margin), fill=255)
    return fade.filter(ImageFilter.GaussianBlur(margin / 2))


def part_mask(polygon: list[tuple[int, int]], feather: int = FEATHER) -> Image.Image:
    """A feathered mask of one part. The shape is in the alpha channel, which is what a CSS mask reads."""
    shape = Image.new("L", PLATE, 0)
    ImageDraw.Draw(shape).polygon(polygon, fill=255)
    soft = shape.filter(ImageFilter.GaussianBlur(feather)).resize(MASK_OUT, Image.LANCZOS)
    mask = Image.new("RGBA", MASK_OUT, (255, 255, 255, 0))
    mask.putalpha(soft)
    return mask


PREVIEW = (1200, 630)
# Fonts tried in turn for the name on the preview picture; the last resort is the one Pillow carries.
NAME_FONTS = ("segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf")


def name_font(size: int) -> ImageFont.ImageFont:
    for name in NAME_FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def preview(plates: Path, dark: Image.Image) -> Image.Image:
    """The link preview: the laptop before power, the same laptop awake, and the name. No other words."""
    picture = Image.new("RGB", PREVIEW, (0, 0, 0))
    height = 470
    size = (round(height * LAPTOP_OUT[0] / LAPTOP_OUT[1]), height)
    fade = edge_fade(LAPTOP_OUT, EDGE_FADE).convert("RGB")
    setting = {key: value for key, value in LIFT["laptop-awake"].items() if key != "box"}
    awake = lift(on_black(plates / f"lux-{SOURCE['laptop-awake']}.png"), **setting)
    for laptop, left in ((dark, -8), (awake, PREVIEW[0] - size[0] + 8)):
        cut = ImageChops.multiply(laptop.crop(LAPTOP_BOX).resize(LAPTOP_OUT, Image.LANCZOS), fade)
        # Lighter of the two where they overlap, so neither laptop's black margin covers the other.
        layer = Image.new("RGB", PREVIEW, (0, 0, 0))
        layer.paste(cut.resize(size, Image.LANCZOS), (left, PREVIEW[1] - height - 20))
        picture = ImageChops.lighter(picture, layer)
    draw = ImageDraw.Draw(picture)
    # The mark: a lens of light in a dark disc, as in the navigation bar. Then the name.
    cx, cy, r = 86, 84, 26
    draw.ellipse((cx - r, cy - r, cx + r, cy + r), fill=(21, 21, 23), outline=(58, 58, 62))
    lens = Image.new("L", PREVIEW, 0)
    lens_draw = ImageDraw.Draw(lens)
    lens_draw.ellipse((cx - 19, cy - 9, cx + 19, cy + 9), fill=255)
    picture.paste((255, 227, 173), mask=lens.filter(ImageFilter.GaussianBlur(0.8)))
    draw.text((cx + r + 18, cy), "Lux", font=name_font(58), fill=(244, 242, 236), anchor="lm")
    return picture


def main() -> None:
    arguments = [a for a in sys.argv[1:] if a != "--preview-only"]
    if len(arguments) != 1:
        raise SystemExit(__doc__)
    plates = Path(arguments[0])
    if "--preview-only" in sys.argv:
        preview(plates, lifted(plates, "laptop-dark", lid=True)).save("public/og.jpg", quality=88, optimize=True)
        print(f"public/og.jpg  {PREVIEW}  {Path('public/og.jpg').stat().st_size} bytes")
        return
    out = Path("src/assets")
    (out / "masks").mkdir(parents=True, exist_ok=True)

    boards = {"board-dark": lifted(plates, "board-dark"), "board-awake": on_black(plates / "lux-board-awake.png")}
    for name, board in boards.items():
        board.resize(BOARD_OUT, Image.LANCZOS).save(out / f"{name}.webp", quality=84, method=6)

    # Three pictures of one laptop from one view, cut alike, so that one can fade into the next.
    laptops = {
        "laptop-dark": lifted(plates, "laptop-dark", lid=True),
        "laptop-inside": lifted(plates, "laptop-inside-awake", lid=True),
        "laptop-awake": lifted(plates, "laptop-awake"),
    }
    fade = edge_fade(LAPTOP_OUT, EDGE_FADE).convert("RGB")
    for name, laptop in laptops.items():
        cut = laptop.crop(LAPTOP_BOX).resize(LAPTOP_OUT, Image.LANCZOS)
        ImageChops.multiply(cut, fade).save(out / f"{name}.webp", quality=86, method=6)

    for part, polygon in REGIONS.items():
        part_mask(polygon).save(out / "masks" / f"{part}.webp", lossless=True, method=6)
    part_mask(WHOLE, WHOLE_FEATHER).save(out / "masks" / "whole.webp", lossless=True, method=6)

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
    (out / "parts.json").write_text(json.dumps(boxes, indent=2) + chr(10), encoding="utf-8", newline=chr(10))

    preview(plates, laptops["laptop-dark"]).save("public/og.jpg", quality=88, optimize=True)

    for path in sorted([*out.rglob("*.webp"), Path("public/og.jpg")]):
        print(f"{path.as_posix()}  {Image.open(path).size}  {path.stat().st_size} bytes")


main()
