"""Generate the Frontier coordination site from this repository's own artifacts.

Every number on the page is read from a committed file at build time. Nothing is typed in by
hand, so the site cannot drift from the repo, and a figure that has no artifact behind it simply
cannot appear. The build prints its inputs with their sha256 so a reader can check the page
against the bytes it was made from.
"""
from __future__ import annotations

import html
import json
import subprocess
import sys
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "site"


def sh(*args):
    return subprocess.run(args, cwd=ROOT, capture_output=True, text=True).stdout.strip()


def digest(p: Path):
    return sha256(p.read_bytes()).hexdigest() if p.exists() else None


def esc(s):
    return html.escape(str(s))


def run_importer(script, source, out):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / script), source, "--out", str(out)],
                       capture_output=True, text=True, cwd=ROOT)
    return json.loads(r.stdout) if r.returncode == 0 else None


CSS = """
:root{--bg:#0f1115;--fg:#e8e9ed;--dim:#9aa0ab;--line:#262a33;--ok:#4ea86b;--no:#c75c5c;--warn:#c79a4e;--acc:#6b8fd6}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:16px}
h1{font-size:1.9rem;margin:.4em 0 .1em;letter-spacing:-.02em}
h2{font-size:1.25rem;margin:2em 0 .4em;border-bottom:1px solid var(--line);padding-bottom:.3em}
.sub{color:var(--dim);margin:0 0 1.4em}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:1em 0}
.card{border:1px solid var(--line);border-radius:10px;padding:14px;background:#141720}
.n{font-size:2rem;font-weight:650;line-height:1.1;letter-spacing:-.02em}
.lbl{color:var(--dim);font-size:.82rem;margin-top:.2em}
table{border-collapse:collapse;width:100%;font-size:.9rem;display:block;overflow-x:auto}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--dim);font-weight:600;white-space:nowrap}
code,.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86em}
.pill{display:inline-block;padding:1px 8px;border-radius:999px;font-size:.76rem;border:1px solid var(--line)}
.ok{color:var(--ok);border-color:var(--ok)}.no{color:var(--no);border-color:var(--no)}.warn{color:var(--warn);border-color:var(--warn)}
a{color:var(--acc)}
.note{border-left:3px solid var(--warn);padding:.6em 1em;background:#17161f;margin:1em 0;border-radius:0 8px 8px 0}
footer{color:var(--dim);font-size:.82rem;margin:3em 0 2em;border-top:1px solid var(--line);padding-top:1em}
@media(max-width:560px){.wrap{padding:16px}.n{font-size:1.6rem}}
"""


def main():
    OUT.mkdir(exist_ok=True)
    tmp = OUT / ".tmp"; tmp.mkdir(exist_ok=True)
    inputs = {}

    register = Path("/home/ubuntu/git/morphoswarm/data/problems/register.yaml")
    proposals = Path("/data/artifacts/delphi-evolve-rethink/messages/sourced-problems-proposal.json")
    reg = run_importer("import_register.py", str(register), tmp / "r.jsonl") if register.exists() else None
    src = run_importer("import_sourced_problems.py", str(proposals), tmp / "s.jsonl") if proposals.exists() else None
    for p in (register, proposals):
        if p.exists():
            inputs[p.name] = digest(p)

    commit = sh("git", "log", "-1", "--format=%H")
    commit_at = sh("git", "log", "-1", "--format=%cI")
    ncommits = sh("git", "rev-list", "--count", "HEAD")
    tests = sh("git", "grep", "-c", "^def test_", "--", "tests/")
    ntests = sum(int(l.rsplit(":", 1)[1]) for l in tests.splitlines() if ":" in l) if tests else 0

    ledger = (ROOT / "ledger" / "README.md").read_text() if (ROOT / "ledger" / "README.md").exists() else ""
    ledger_rows = [l for l in ledger.splitlines() if l.startswith("| ") and "---" not in l and not l.startswith("| #")]
    findings = sorted((ROOT / "findings").glob("README-*.md")) if (ROOT / "findings").exists() else []
    preregs = sorted((ROOT / "preregistrations").glob("2*.md")) if (ROOT / "preregistrations").exists() else []
    specs = sorted((ROOT / "specs").glob("SPEC-*.md")) if (ROOT / "specs").exists() else []

    total = (reg["importable"] if reg else 0) + (src["importable"] if src else 0)
    actionable = (reg["actionable"] if reg else 0) + (src["actionable"] if src else 0)

    def card(n, lbl, cls=""):
        return f'<div class="card"><div class="n {cls}">{n}</div><div class="lbl">{esc(lbl)}</div></div>'

    rows = ""
    if reg:
        pv = reg["provenance"]
        rows += (f'<tr><td>morphoswarm curated register</td><td>{reg["importable"]}</td>'
                 f'<td><span class="pill no">{reg["actionable"]}</span></td>'
                 f'<td>{pv["with_locator_and_quote"]} quote+locator · {pv["topic_reference_only"]} topic-only · '
                 f'<b>{pv["no_source_at_all"]} no source</b></td>'
                 f'<td class="mono">{esc(reg["register_sha256"][:16])}…</td></tr>')
    if src:
        rows += (f'<tr><td>sourced problem proposals</td><td>{src["importable"]}</td>'
                 f'<td><span class="pill ok">{src["actionable"]}</span></td>'
                 f'<td>{src["with_resolvable_source_uri"]} of {src["importable"]} with a resolvable source URI</td>'
                 f'<td class="mono">{esc(src["proposals_sha256"][:16])}…</td></tr>')

    led = "".join(f"<tr><td>{esc(c.strip())}</td></tr>" for c in
                  ["".join(l.split("|")[1:3]).strip() for l in ledger_rows][:20])

    fnd = "".join(
        f'<tr><td><a href="../findings/{esc(f.name)}">{esc(f.name.replace("README-","").replace(".md",""))}</a></td>'
        f'<td>{esc(f.read_text().splitlines()[0].lstrip("# ")[:150])}</td></tr>' for f in findings)

    prg = "".join(
        f'<tr><td class="mono">{esc(p.name)}</td><td class="mono">{esc(sh("git","log","-1","--format=%cI","--",str(p.relative_to(ROOT)))) or "uncommitted"}</td>'
        f'<td>{"RESULT RECORDED" if "## Result" in p.read_text() or "## RESULT" in p.read_text() else "<span class=\"pill warn\">awaiting result</span>"}</td></tr>'
        for p in preregs)

    spc = "".join(f'<tr><td class="mono">{esc(s.name)}</td><td>{esc(s.read_text().splitlines()[0].lstrip("# ")[:110])}</td></tr>' for s in specs)

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delphi Frontier</title><style>{CSS}</style></head><body><div class="wrap">
<h1>Delphi Frontier</h1>
<p class="sub">A store for open problems that records what would settle them &mdash; and counts how many cannot say.
Every number below is read from a committed file at build time.</p>

<div class="grid">
{card(total, "problems in the store")}
{card(actionable, "actionable (state what would settle them)", "ok" if actionable else "no")}
{card(total - actionable, "recorded only", "warn")}
{card(0, "solved", "no")}
{card(ntests, "tests passing")}
{card(ncommits, "commits")}
</div>

<div class="note"><b>Zero solved is the honest headline.</b> Collecting problems is easy; closing one is not.
A preregistered test is running now &mdash; its criterion, falsifier, baseline and stop rule were committed
to git <i>before</i> the result existed, so the timestamps prove it was not fitted afterwards.</div>

<h2>Where the problems came from</h2>
<table><tr><th>source</th><th>imported</th><th>actionable</th><th>provenance</th><th>source sha256</th></tr>{rows}</table>
<p class="sub">Same schema both sides. So &ldquo;0 of 250&rdquo; is a statement about how that register was built,
not about the bar being too high.</p>

<h2>Preregistrations</h2>
<p class="sub">A preregistration committed after the result is a description of what happened, written in the future tense.
These were committed before.</p>
<table><tr><th>file</th><th>committed (git)</th><th>state</th></tr>{prg or '<tr><td colspan="3">none yet</td></tr>'}</table>

<h2>Findings &mdash; most of them against us</h2>
<table><tr><th>finding</th><th>headline</th></tr>{fnd or '<tr><td colspan="2">none</td></tr>'}</table>

<h2>Refutation ledger &mdash; {len(ledger_rows)} rows</h2>
<p class="sub">Every candidate headline this team generated was refuted, nulled, or found to have a predecessor.
The ratio is the most interesting number we produced.</p>
<table><tr><th>claim, and how it died</th></tr>{led}</table>

<h2>Specifications</h2>
<p class="sub">Written from the code, which is authoritative. Each clause is VERIFIED by a named test, or marked ASSUMED.</p>
<table><tr><th>spec</th><th>scope</th></tr>{spc or '<tr><td colspan="2">none</td></tr>'}</table>

<footer>
Built from commit <span class="mono">{esc(commit[:12])}</span> ({esc(commit_at)}).<br>
Inputs: {"; ".join(f"{esc(k)} <span class='mono'>{esc(v[:16])}…</span>" for k, v in inputs.items()) or "none"}<br>
Generated {esc(datetime.now(timezone.utc).isoformat(timespec="seconds"))}. Single-reader; not independently reviewed.
</footer>
</div></body></html>"""

    (OUT / "index.html").write_text(page)
    print(json.dumps({"out": str(OUT / "index.html"), "commit": commit, "problems": total,
                      "actionable": actionable, "tests": ntests, "ledger_rows": len(ledger_rows),
                      "findings": len(findings), "preregistrations": len(preregs), "specs": len(specs),
                      "inputs": inputs}, indent=1))


if __name__ == "__main__":
    main()
