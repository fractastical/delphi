#!/usr/bin/env node
// Animate docs/team.html as a GIF: the intro, then for each pattern the wedge hover, each species
// circle hover and the knowledge graph opened from the tab on the outer right edge, ending with the
// all-patterns graph. Every frame is a headless-Chrome screenshot of the built page in a URL state
// (?pattern=…&species=…&graph=1&demo=1; the demo flag draws a cursor and disables transitions),
// assembled by ffmpeg with per-frame hold times.
//
//   python3 scripts/site/build-team-page.py && node scripts/site/team-gif.mjs [--width 1000] [--out docs/team/team.gif]
//
// Needs Google Chrome (or CHROME=/path/to/chrome) and ffmpeg on PATH.

import { execFileSync, spawnSync } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync, statSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../..");
const args = Object.fromEntries(process.argv.slice(2).map((a, i, xs) => a.startsWith("--") ? [a.slice(2), xs[i + 1] ?? true] : []).filter(x => x.length));
const WIDTH = +(args.width ?? 1000), OUT = resolve(ROOT, args.out ?? "docs/team/team.gif");
const WIN = [1600, 1100], FPS = 5;

const chrome = [process.env.CHROME, "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/Applications/Chromium.app/Contents/MacOS/Chromium", "google-chrome", "chromium", "chromium-browser"]
  .filter(Boolean).find(c => c.includes("/") ? existsSync(c) : spawnSync("which", [c]).status === 0);
if (!chrome) { console.error("no Chrome found; set CHROME=/path/to/chrome"); process.exit(1); }
if (spawnSync("which", ["ffmpeg"]).status !== 0) { console.error("ffmpeg not on PATH"); process.exit(1); }

const page = join(ROOT, "docs/team.html");
if (!existsSync(page)) { console.error("docs/team.html missing; run scripts/site/build-team-page.py first"); process.exit(1); }
const html = readFileSync(page, "utf8");
const data = JSON.parse(html.slice(html.indexOf("const DATA = ") + 13, html.indexOf(";\nconst G = ")));
const panels = data.panels.slice().sort((a, b) => a.wedge - b.wedge);

// frame plan: [query string, seconds to hold]
const frames = [["demo=1", 1.6]];
for (const p of panels) {
  frames.push([`pattern=${p.key}&demo=1`, 2.2]);
  p.species.forEach((_, i) => frames.push([`pattern=${p.key}&species=${i}&demo=1`, 1.6]));
  frames.push([`pattern=${p.key}&graph=1&demo=1`, 2.6]);
}
frames.push(["graph=1&demo=1", 2.6]);

const tmp = mkdtempSync(join(tmpdir(), "team-gif-"));
try {
  let list = "";
  frames.forEach(([q, hold], i) => {
    const png = join(tmp, `f${String(i).padStart(2, "0")}.png`);
    execFileSync(chrome, ["--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run", "--disable-extensions",
      `--user-data-dir=${join(tmp, "profile")}`, `--window-size=${WIN.join(",")}`, "--virtual-time-budget=5000",
      `--screenshot=${png}`, `file://${page}?${q}`], { stdio: ["ignore", "ignore", "ignore"] });
    if (!existsSync(png)) throw new Error(`no screenshot for ?${q}`);
    list += `file '${png}'\nduration ${hold}\n`;
    process.stdout.write(`frame ${i + 1}/${frames.length}  ?${q}\n`);
  });
  list += `file '${join(tmp, `f${String(frames.length - 1).padStart(2, "0")}.png`)}'\n`; // concat demuxer needs the last file repeated
  writeFileSync(join(tmp, "frames.txt"), list);
  const vf = `fps=${FPS},scale=${WIDTH}:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=192:stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=4:diff_mode=rectangle`;
  execFileSync("ffmpeg", ["-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", join(tmp, "frames.txt"),
    "-vf", vf, "-loop", "0", OUT], { stdio: "inherit" });
  const secs = frames.reduce((s, [, h]) => s + h, 0);
  console.log(`${OUT.replace(ROOT + "/", "")}: ${frames.length} frames, ${secs.toFixed(1)} s, ${(statSync(OUT).size / 1024 / 1024).toFixed(1)} MB`);
} finally {
  rmSync(tmp, { recursive: true, force: true });
}
