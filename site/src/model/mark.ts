// The mark: a lens of light opening in a dark disc. Drawn from geometry, so the navigation bar and the
// favicon cannot drift apart.

/** The mark's box is 24 units square; the disc sits in its middle. */
export const MARK = { box: 24, centre: 12, disc: 11, halfWidth: 8, discFill: "#151517", light: "#ffe3ad" } as const;

const round = (n: number) => Math.round(n * 100) / 100;

/**
 * The lens as an SVG path: two curves between the same two points on the disc's middle line.
 * `open` runs from 0, a closed line, to 1, the widest lens the disc holds.
 */
export function lensPath(open: number): string {
  const { centre: c, halfWidth: w } = MARK;
  const h = Math.min(1, Math.max(0, open)) * 11;
  return `M${c - w} ${c}Q${c} ${round(c - h)} ${c + w} ${c}Q${c} ${round(c + h)} ${c - w} ${c}Z`;
}

/** How far the lens is open in the mark as shipped. */
export const MARK_OPEN = 0.8;
