// The addresses of the board's pictures: the dark plate, the awake plate, and one soft mask per part.
import boardAwake from "../assets/board-awake.webp";
import boardDark from "../assets/board-dark.webp";
import { PARTS, type Part } from "../content/types";

const maskFiles = import.meta.glob<string>("../assets/masks/*.webp", { eager: true, import: "default" });
const maskOf = (name: string) => maskFiles[`../assets/masks/${name}.webp`];

export const DARK = boardDark;
export const AWAKE = boardAwake;
/** The mask picture of each part, by part name. */
export const MASKS = Object.fromEntries(PARTS.map((part) => [part, maskOf(part)])) as Record<Part, string>;
/** The mask of the whole board: the ground between the parts. */
export const WHOLE_MASK = maskOf("whole");
/** Every mask by the name of what it lights. */
export const MASK_OF: Record<Part | "whole", string> = { ...MASKS, whole: WHOLE_MASK };
