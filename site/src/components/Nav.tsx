// The navigation bar: the mark and name on the left, three places on the right. Two of them are not built
// yet and say so; they are text, not links, so nothing leads nowhere.
import { Mark } from "./Mark";

export function Nav() {
  return (
    <nav className="lnav" aria-label="Site">
      <a className="name" href="#top">
        <Mark />
        Lux
      </a>
      <span className="links">
        <a href="#top" aria-current="location">
          The boot
        </a>
        <span className="soon">
          Experiments <small>coming</small>
        </span>
        <span className="soon">
          Sources <small>coming</small>
        </span>
      </span>
    </nav>
  );
}
