# Pictures

Every picture on the site is an illustration of a fictional laptop and a fictional board. None is a photograph, none shows a real product, and none is evidence: the evidence is the recording. The page says so under every picture.

## How each file was made

| File                            | What it is                                                             | How it was made                                                                                                                                               |
| ------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/assets/laptop-dark.webp`   | The laptop before power, 1280 x 960                                    | A generated picture (2400 x 1500), lifted (see below), cropped close to the laptop, edges faded to black, resized and saved as WebP by `tools/make_assets.py` |
| `src/assets/laptop-inside.webp` | The same laptop with its inside awake and its screen black, 1280 x 960 | A generated picture of the same laptop from the same view, cropped, faded and saved alike, so that one picture can fade into the next                         |
| `src/assets/laptop-awake.webp`  | The same laptop with its screen lit by a dawn sky, 1280 x 960          | As above. The sky on its screen is part of the generated picture                                                                                              |
| `src/assets/board-dark.webp`    | The board before power, 1920 x 1200                                    | A generated picture (2400 x 1500), lifted (see below), resized and saved as WebP by the same script                                                           |
| `src/assets/board-awake.webp`   | The same board with every part lit, 1920 x 1200                        | A generated picture of the same board from the same view, so that parts line up with the dark one; resized and saved as WebP by the same script               |
| `src/assets/masks/<part>.webp`  | Eight soft masks, 600 x 375, one per part of the board                 | Composed in code: a polygon per part, drawn and blurred by the same script. The shape is in the alpha channel                                                 |
| `src/assets/masks/whole.webp`   | One soft mask of the whole board                                       | Composed in code the same way, with a wider blur                                                                                                              |
| `src/assets/parts.json`         | Where each part lies on the board, as fractions of the picture         | Composed in code: the bounds of each part's polygon, written by the same script. A narrow window uses it to keep the parts a step is about in view            |
| `public/favicon.svg`            | The mark                                                               | Drawn by hand as SVG from the geometry in `src/model/mark.ts`; a test keeps the two equal                                                                     |

The full-size source pictures are not in this repository. With them in a folder, the shipped files are rebuilt by:

```
python tools/make_assets.py <folder with the source pictures>
```

It needs Python 3 with Pillow, and is run from this folder.

## The machine before power is lifted

As generated, the laptop and the board before power were close to the black of the page, and on an ordinary screen in a lit room the laptop was hard to tell from the background. The script raises their midtones and lit edges with one curve per picture (`LIFT` in `tools/make_assets.py`): a level becomes `gain * level ** gamma`, levels at or under a black point are left alone, and the change is complete a few levels above it. The background therefore stays black, and no colour is added, so the machine still reads as not powered.

The script prints the mean brightness of the machine's region of each source picture, on a scale of 0 to 255, before and after:

| Picture             | Before | After | Background corner |
| ------------------- | ------ | ----- | ----------------- |
| Laptop before power | 9.6    | 25.2  | 0.19, unchanged   |
| Board before power  | 10.1   | 26.9  | 0.06, unchanged   |

The two later pictures of the laptop and the lit board are not changed.

## How a stop's picture is put together

No stop has a picture file of its own. The page draws `board-dark.webp` and stacks `board-awake.webp` over it once per part, each copy cut out by that part's mask. A step of the story sets which copies are seen, and the stylesheet fades them in one after another, so light spreads across the board. Because every stop is made from the same two pictures, a part never moves between stops.

Which parts are lit at a stop is not decided here. It is read from the `picture` field of each screen in `content/`. The same field can name the lit parts a screen is about; those get a second copy of the same cut-out added on top, which makes them a little brighter. Once every part is lit, the ground between the parts lights too, through the mask of the whole board.

At the pilot screen and at the end of the story the board gives way to the laptop with its inside awake, and on the last screen the picture with the lit screen fades in over it. The three laptop pictures are cut alike, so nothing moves when one fades into the next.

## Fonts

Inter (variable) and IBM Plex Mono, both under the SIL Open Font License, bundled from the `@fontsource` packages. Nothing is fetched from another site when the page loads.
