# Pictures

Every picture on the site is an illustration of a fictional laptop and a fictional board. None is a photograph, none shows a real product, and none is evidence: the evidence is the recording. The page says so under every picture.

## How each file was made

| File                           | What it is                                                     | How it was made                                                                                                                                  |
| ------------------------------ | -------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `src/assets/laptop-dark.webp`  | The laptop before power, 1280 x 960                            | A generated picture (2400 x 1500), cropped close to the laptop, edges faded to black, resized and saved as WebP by `tools/make_assets.py`        |
| `src/assets/board-dark.webp`   | The board before power, 1920 x 1200                            | A generated picture (2400 x 1500), resized and saved as WebP by the same script                                                                  |
| `src/assets/board-awake.webp`  | The same board with every part lit, 1920 x 1200                | A generated picture of the same board from the same view, so that parts line up with the dark one; resized and saved as WebP by the same script  |
| `src/assets/masks/<part>.webp` | Eight soft masks, 600 x 375, one per part of the board         | Composed in code: a polygon per part, drawn and blurred by the same script. The shape is in the alpha channel                                    |
| `src/assets/parts.json`        | Where each part lies on the board, as fractions of the picture | Composed in code: the bounds of each part's polygon, written by the same script. A narrow window uses it to keep the parts a step lights in view |
| `public/favicon.svg`           | The mark                                                       | Drawn by hand as SVG from the geometry in `src/model/mark.ts`; a test keeps the two equal                                                        |

The full-size source pictures are not in this repository. With them in a folder, the shipped files are rebuilt by:

```
python tools/make_assets.py <folder with the source pictures>
```

It needs Python 3 with Pillow, and is run from this folder.

## How a stop's picture is put together

No stop has a picture file of its own. The page draws `board-dark.webp` and stacks `board-awake.webp` over it once per part, each copy cut out by that part's mask. A step of the story sets which copies are seen, and the stylesheet fades them in one after another, so light spreads across the board. Because every stop is made from the same two pictures, a part never moves between stops.

Which parts are lit at a stop is not decided here. It is read from the `picture` field of that stop's screen in `content/`.

## Fonts

Inter (variable) and IBM Plex Mono, both under the SIL Open Font License, bundled from the `@fontsource` packages. Nothing is fetched from another site when the page loads.
