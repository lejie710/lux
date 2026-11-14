# Pictures

Every picture on the site is an illustration of a fictional laptop and a fictional board. None is a photograph, none shows a real product, and none is evidence: the evidence is the recording. The page says so under every picture.

## How each file was made

| File                            | What it is                                                             | How it was made                                                                                                                                                                                                                        |
| ------------------------------- | ---------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/assets/laptop-dark.webp`   | The laptop before power, 1280 x 960                                    | A generated picture (2400 x 1500), lifted (see below), cropped close to the laptop, edges faded to black, resized and saved as WebP by `tools/make_assets.py`                                                                          |
| `src/assets/laptop-inside.webp` | The same laptop with its inside awake and its screen black, 1280 x 960 | A generated picture of the same laptop from the same view, lifted (see below), cropped, faded and saved alike, so that one picture can fade into the next                                                                              |
| `src/assets/laptop-awake.webp`  | The same laptop with its screen lit by a dawn sky, 1280 x 960          | As above, with only its body under the hinge lifted. The sky on its screen is part of the generated picture and is not changed                                                                                                         |
| `src/assets/board-dark.webp`    | The board before power, 1920 x 1200                                    | A generated picture (2400 x 1500), lifted (see below), resized and saved as WebP by the same script                                                                                                                                    |
| `src/assets/board-awake.webp`   | The same board with every part lit, 1920 x 1200                        | A generated picture of the same board from the same view, so that parts line up with the dark one; resized and saved as WebP by the same script                                                                                        |
| `src/assets/masks/<part>.webp`  | Eight soft masks, 600 x 375, one per part of the board                 | Composed in code: a polygon per part, drawn and blurred by the same script. The shape is in the alpha channel                                                                                                                          |
| `src/assets/masks/whole.webp`   | One soft mask of the whole board                                       | Composed in code the same way, with a wider blur                                                                                                                                                                                       |
| `src/assets/parts.json`         | Where each part lies on the board, as fractions of the picture         | Composed in code: the bounds of each part's polygon, written by the same script. A narrow window uses it to keep the parts a step is about in view                                                                                     |
| `public/og.jpg`                 | The picture a link to the site is previewed with, 1200 x 630           | Composed in code by the same script from two of the generated pictures: the laptop before power (lifted) on the left, the same laptop with its screen lit on the right, the mark drawn from its geometry, and the name. No other words |
| `public/favicon.svg`            | The mark                                                               | Drawn by hand as SVG from the geometry in `src/model/mark.ts`; a test keeps the two equal                                                                                                                                              |

The full-size source pictures are not in this repository. With them in a folder, the shipped files are rebuilt by:

```
python tools/make_assets.py <folder with the source pictures>
```

It needs Python 3 with Pillow, and is run from this folder. With `--preview-only` after the folder it writes only `public/og.jpg`. The name on that picture is set in the first of Segoe UI Bold, Arial Bold and DejaVu Sans Bold that the machine has, so on another machine the letters may differ slightly.

## The dark pictures are lifted

As generated, the laptop and the board before power, and the laptop with its inside awake, were close to the black of the page. On an ordinary screen in a lit room the laptop was hard to tell from the background, and the laptop that is running was dimmer than the one before power. The script raises midtones and lit edges with one curve per picture (`LIFT` in `tools/make_assets.py`): a level becomes `gain * level ** gamma`, levels at or under a black point are left alone, and the change is complete a few levels above it. The background therefore stays black. No colour is added to the machine before power, so it still reads as not powered; the laptop with its inside awake keeps the hue and saturation of its warm light and only gets brighter.

The lid of the two laptops with a dark screen gets a second, local lift (`lid_lift`). Its rim is two or three pixels wide in the source and all but vanished when the picture was made small, so every rim pixel takes the brightest value near it, which makes the rim a few pixels wider, and that widened rim is capped below the rim's own highlights. The glass inside the rim gets a faint cool sheen that falls away from the top left corner, so the lid reads as a dark surface and not as a hole. The edge fade of the laptop pictures is 18 pixels: a wider one reached the top rim and dimmed it to a third.

The laptop with its screen lit is lifted only under the hinge, and less, so its body is as bright as the same body in the picture it fades in over. Its screen is not changed.

The script prints the mean brightness of each region of each source picture, on a scale of 0 to 255, before and after:

| Picture                  | Whole machine  | Palm rest    | Glass of the lid | Background corner |
| ------------------------ | -------------- | ------------ | ---------------- | ----------------- |
| Laptop before power      | 9.6 to 31.2    | 36.7 to 91.9 | 0.0 to 9.6       | 0.19, unchanged   |
| Laptop with inside awake | 14.2 to 35.0   | 35.4 to 86.9 | 0.1 to 9.6       | 0.08, unchanged   |
| Laptop with screen lit   | 103.6 to 110.7 | 69.8 to 96.2 | not changed      | 0.09, unchanged   |
| Board before power       | 10.1 to 26.9   |              |                  | 0.06, unchanged   |

The lit board is not changed.

## How a stop's picture is put together

No stop has a picture file of its own. The page draws `board-dark.webp` and stacks `board-awake.webp` over it once per part, each copy cut out by that part's mask. A step of the story sets which copies are seen, and the stylesheet fades them in one after another, so light spreads across the board. Because every stop is made from the same two pictures, a part never moves between stops.

Which parts are lit at a stop is not decided here. It is read from the `picture` field of each screen in `content/`. The same field can name the lit parts a screen is about; those get a second copy of the same cut-out added on top, which makes them a little brighter. Once every part is lit, the ground between the parts lights too, through the mask of the whole board.

The strip after the story draws the same board seven times, small, each with the parts lit that its stop ends with. A small picture of the whole board looks alike at every stop, so each is drawn close on the parts its stop is about, and the last, where every part is lit, shows the whole board. The two laptops of the experiments page are the pictures with the screen lit and with the inside awake, side by side.

At the pilot screen and at the end of the story the board gives way to the laptop with its inside awake, and on the last screen the picture with the lit screen fades in over it. The three laptop pictures are cut alike, so nothing moves when one fades into the next.

## Fonts

Inter (variable) and IBM Plex Mono, both under the SIL Open Font License, bundled from the `@fontsource` packages. Nothing is fetched from another site when the page loads.
