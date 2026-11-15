# Pictures

Every picture on the site is an illustration of a fictional laptop and a fictional board. None is a photograph, none shows a real product, and none is evidence: the evidence is the recording. The page says so under every picture.

## How each file was made

| File                            | What it is                                                             | How it was made                                                                                                                                                                                                                          |
| ------------------------------- | ---------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/assets/laptop-dark.webp`   | The laptop before power, 1280 x 960                                    | A generated picture (2400 x 1500), lifted (see below), cropped close to the laptop, edges faded to black, resized and saved as WebP by `tools/make_assets.py`                                                                            |
| `src/assets/laptop-inside.webp` | The same laptop with its inside awake and its screen black, 1280 x 960 | A generated picture of the same laptop from the same view, lifted (see below), cropped, faded and saved alike, so that one picture can fade into the next                                                                                |
| `src/assets/laptop-awake.webp`  | The same laptop with its screen lit by a dawn sky, 1280 x 960          | From a second generated picture of the same laptop in which the light under the keys is turned down, with only its body under the hinge lifted. The sky on its screen is part of the generated picture and is not changed                |
| `src/assets/board-dark.webp`    | The board before power, 1920 x 1200                                    | A generated picture (2400 x 1500), lifted (see below), resized and saved as WebP by the same script                                                                                                                                      |
| `src/assets/board-awake.webp`   | The same board with every part lit, 1920 x 1200                        | A generated picture of the same board from the same view, so that parts line up with the dark one; resized and saved as WebP by the same script                                                                                          |
| `src/assets/masks/<part>.webp`  | Eight soft masks, 600 x 375, one per part of the board                 | Composed in code: a polygon per part, drawn and blurred by the same script. The shape is in the alpha channel                                                                                                                            |
| `src/assets/masks/whole.webp`   | One soft mask of the whole board                                       | Composed in code the same way, with a wider blur                                                                                                                                                                                         |
| `src/assets/parts.json`         | Where each part lies on the board, as fractions of the picture         | Composed in code: the bounds of each part's polygon, written by the same script. A narrow window uses it to keep the parts a step is about in view                                                                                       |
| `public/cover.jpg`              | The picture a link to the site is previewed with, 1200 x 630           | The cover picture of the README (`docs/cover.webp`, described below), scaled to the preview's height by the same script, with the same small strip cut from its left and right. A link to the site is therefore previewed with the cover |
| `public/favicon.svg`            | The mark                                                               | Drawn by hand as SVG from the geometry in `src/model/mark.ts`; a test keeps the two equal                                                                                                                                                |

The full-size source pictures are not in this repository. With them in a folder, the shipped files are rebuilt by:

```
python tools/make_assets.py <folder with the source pictures>
```

It needs Python 3 with Pillow, and is run from this folder. With `--preview-only` after the folder it writes only `public/cover.jpg`. It reads `../docs/cover.webp`, so it needs no source pictures.

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

The row for the laptop with its screen lit was printed for the first picture of it. The shipped file is now made from the second picture, in which the light under the keys is turned down, and the values of that picture were not written down here.

The lit board is not changed.

## How a stop's picture is put together

No stop has a picture file of its own. The page draws `board-dark.webp` and stacks `board-awake.webp` over it once per part, each copy cut out by that part's mask. A step of the story sets which copies are seen, and the stylesheet fades them in one after another, so light spreads across the board. Because every stop is made from the same two pictures, a part never moves between stops.

Which parts are lit at a stop is not decided here. It is read from the `picture` field of each screen in `content/`. The same field can name the lit parts a screen is about; those get a second copy of the same cut-out added on top, which makes them a little brighter, and the other lit parts are then drawn at half their light. Once every part is lit, the ground between the parts lights too, through the mask of the whole board.

The strip after the story draws the same board seven times, small, each with the parts lit that its stop ends with. A small picture of the whole board looks alike at every stop, so each is drawn close on the parts its stop is about, and the last, where every part is lit, shows the whole board. The two laptops of the experiments page are the pictures with the screen lit and with the inside awake, side by side.

At the pilot screen and at the end of the story the board gives way to the laptop with its inside awake, and on the last screen the picture with the lit screen fades in over it. The picture with the lit screen is made from a second generated picture of the same laptop, in which the light under the keys is turned down, so that light goes down by itself as the picture fades in and the lit screen is the brightest thing in view. The stylesheet lays no shade over it. The three laptop pictures are cut alike, so nothing moves when one fades into the next.

## Fonts

Inter (variable) and IBM Plex Mono, both under the SIL Open Font License, Version 1.1, bundled from the `@fontsource` packages. Nothing is fetched from another site when the page loads.

Inter: Copyright 2016 The Inter Project Authors (https://github.com/rsms/inter). IBM Plex Mono: Copyright 2017 IBM Corp. The licence text is the `LICENSE` file of each of the two packages, under `node_modules/` after `npm ci`. It is not copied into the built site, so the published site does not carry it; a deployment should carry it or link to it.

## Screenshots in the documentation

`docs/cover.webp`, the picture at the top of the README, is not a picture of the site. It is a generated illustration of the same laptop before power, in front of the first light on a horizon, 2400 x 1200, with the site's opening words set on it afterwards in the site's own font (Inter, weight 600) and colours. It shows no screen of the site.

The three files in `docs/images/` (`opening.png`, `experiment.png`, `stop-6.png`) are pictures of the running site in a window of 1440 x 900, taken in a headless browser. They hold nothing but the pictures and fonts listed above and the site's own words.
