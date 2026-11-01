// The shared header (portal navigation plus the claims-atlas sub-navigation) and footer of every
// built page. Templates carry <!--__SITE_HEAD__--> and <!--__SITE_FOOT__-->; the markup lives in
// templates/partials/ so the five pages cannot drift apart. docs/css/delphi.css styles it.
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const PARTIALS = join(dirname(fileURLToPath(import.meta.url)), "templates/partials");
const part = name => readFileSync(join(PARTIALS, name), "utf8");

/** Fill the header and footer placeholders; `page` is the built page's name, e.g. "claim-graph". */
export function withChrome(html, page) {
  const head = part("site-head.html")
    .replace(`data-page="${page}"`, 'aria-current="page"')
    .replace(/ data-page="[^"]*"/g, "");
  return html.replace("<!--__SITE_HEAD__-->", () => head).replace("<!--__SITE_FOOT__-->", () => part("site-foot.html"));
}
