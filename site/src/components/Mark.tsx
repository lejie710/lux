// The mark, drawn from the geometry in model/mark.ts.
import { MARK, MARK_OPEN, lensPath } from "../model/mark";

export function Mark({ size = 22 }: { size?: number }) {
  return (
    <svg className="mark" width={size} height={size} viewBox={`0 0 ${MARK.box} ${MARK.box}`} aria-hidden="true">
      <circle cx={MARK.centre} cy={MARK.centre} r={MARK.disc} fill={MARK.discFill} stroke="#3a3a3e" strokeWidth="0.5" />
      <path d={lensPath(MARK_OPEN)} fill={MARK.light} />
    </svg>
  );
}
