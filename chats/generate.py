#!/usr/bin/env python3
"""Rebuild the chats/ folder from Cursor agent transcripts.

Usage: python3 chats/generate.py
"""
import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

TRANSCRIPTS = Path.home() / ".cursor/projects/Users-jdietz-Documents-GitHub-dev-delphisci/agent-transcripts"
OUT = Path(__file__).resolve().parent
TZ = "UTC-4 (EDT)"

TITLES = {
    "3eb906a8-fa17-4377-bc46-c211f956a5f4": "README, best-practice guide and project goals",
    "22da6dfb-dc5d-445d-93e6-8169cc277bdd": "Science Claw sponsor integration issues and BioNeMo",
    "716bbd91-2dc4-4418-ae0d-8f6fcaa2864c": "Discord agent that chats with other agents",
    "c29e9980-5788-4107-9e35-7144377c4fde": "Math-meets-biology thinkers, theorem claims as nanopubs",
    "8d4f37ad-4e36-4c5c-a37d-c0e094f85b68": "Darwin's Origin of Species claims as nanopubs",
    "2a7af20d-910d-49d9-b275-fa134c462b29": "Which Delphi ontology version are we using",
    "eca66075-1d01-412c-9f7b-6380a3cf5e8e": "README tagline and seal logo",
    "efd0db8b-51dc-4640-87f3-2816ca4734b7": "Documenting our chats (this folder)",
    "6641d501-6ed5-46f4-9bbd-1243e29d389f": "Thompson's On Growth and Form claims as nanopubs",
    "8a9f75b5-8c3b-4101-b2b5-850610a06c1e": "Wolfram's A New Kind of Science claims as nanopubs",
    "c8a29bd7-8d22-4063-87dc-1a56f4d1371d": "Interactive claim graph site (docs/) with truth and testability scores",
    "115c00dc-6e8d-4f14-8adf-cefcf5f26ab7": "OpenResearch (orx) harness setup and sharing the dashboard",
    "06a78db4-bb53-4975-b8f9-44d2717a03a5": "Making claims and math queryable: the delphisci MCP server",
    "ed56352c-1c98-4638-b111-ca274c2a46f7": "ScienceClaw compute credits sign-up (Nebius and others)",
    "013fd3ac-fc8a-4f13-ba0c-62a1f641b134": "What can we do with this? Adding formal math to Thompson claims",
    "af1a15aa-03d5-4247-bfe6-2af141c1bbf5": "Publishing the MCP server and which Darwin claims models think are false",
    "1d4b5bec-3491-4b9c-b648-fb2717728413": "Architecture issue: five-agent pipeline, orx and BioNeMo roles",
    "e1b218ed-6945-42cf-9dc6-871a2d416134": "Claims grouped by thinker and by testability",
    "aa3b4a4a-f637-43f9-bf8e-f2c4e32c5fb9": "Animated GIF and snapshot summaries of the project",
    "d73ead47-2735-4099-9a9d-3b0aad449e3a": "Overnight cloud agents to test claims against data",
    "27028139-575c-4d52-88a4-7cf0e6427c36": "Overnight run: provenanced datasets for every animal taxon",
    "3af5b1b0-11d8-4ed7-a9a6-cbf60c36c714": "Ranking animal datasets by completeness (incl. bioelectric data)",
}

# Chats not related to this repo, or about work that was deleted before being committed.
EXCLUDED = {
    "f524b202-f8ab-4cca-bdac-b37bc3f1011b",  # problem-graph overview, deleted uncommitted
    "5771f114-6100-49ab-8966-d66c2d0f6800",  # the deletion of that problem-graph work and its log
    "0c3f5dd6-dcd6-46f5-ab48-0bef9db30840",  # disk cleanup of other GitHub folders, unrelated
}

TS_RE = re.compile(r"<timestamp>(.*?)</timestamp>")
QUERY_RE = re.compile(r"<user_query>(.*?)</user_query>", re.S)
TAG_BLOCK_RE = re.compile(r"<(\w+)[^>]*>.*?</\1>", re.S)
AUTOMATED_PREFIXES = ("Briefly inform the user", "Perform any necessary follow-up actions")
ASSESS_RE = re.compile(r"assessment/inputs/(batch-\d+)\.json.*?assessment/raw/([\w.-]+)/", re.S)


def parse_ts(s):
    s = re.sub(r"\s*\(UTC[^)]*\)", "", s)
    return datetime.strptime(s, "%A, %b %d, %Y, %I:%M %p")


def fmt(dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else "unknown"


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60]


def load(path):
    records = []
    for line in path.read_text().splitlines():
        if line.strip():
            records.append(json.loads(line))
    return records


def text_of(msg):
    return "\n".join(c.get("text", "") for c in msg["message"]["content"] if c.get("type") == "text")


def parse_turns(records):
    """Group records into turns, each starting at a user message."""
    turns, cur, last_ts = [], None, None
    for r in records:
        role = r.get("role")
        if role == "user":
            raw = text_of(r)
            m = TS_RE.search(raw)
            ts = parse_ts(m.group(1)) if m else last_ts
            last_ts = ts
            q = QUERY_RE.search(raw)
            if q:
                body, kind = q.group(1).strip(), "user"
                if body.startswith(AUTOMATED_PREFIXES):
                    kind = "system"
            else:
                body = TAG_BLOCK_RE.sub("", raw).strip()
                kind = "system"
            if raw.lstrip().startswith("[Image]"):
                body = ("[Image attached] " + body).strip()
            if kind == "system" and not body:
                continue
            cur = {"ts": ts, "kind": kind, "prompt": body, "replies": [], "tools": {}, "status": None}
            turns.append(cur)
        elif role == "assistant" and cur is not None:
            for c in r["message"]["content"]:
                if c.get("type") == "text" and c["text"].strip():
                    cur["replies"].append(c["text"].strip())
                elif c.get("type") == "tool_use":
                    name = c["name"]
                    if name == "CallDynamicTool":
                        name = c["input"].get("toolName", name)
                    cur["tools"][name] = cur["tools"].get(name, 0) + 1
        elif r.get("type") == "turn_ended" and cur is not None:
            cur["status"] = r.get("status") + (f" ({r['error']})" if r.get("error") else "")
    return turns


def task_descriptions(records):
    """Map subagent id or prompt -> Task description from a parent transcript."""
    by_id, by_prompt = {}, {}
    for r in records:
        for c in r.get("message", {}).get("content", []):
            if c.get("type") != "tool_use":
                continue
            args = c["input"].get("arguments", c["input"]) if c["name"] == "CallDynamicTool" else c["input"]
            if c["name"] not in ("Task", "CallDynamicTool") or "description" not in args:
                continue
            if args.get("resume"):
                by_id[args["resume"]] = args["description"]
            if args.get("prompt"):
                by_prompt[args["prompt"].strip()[:200]] = args["description"]
    return by_id, by_prompt


def render_turns(turns):
    out = []
    for i, t in enumerate(turns, 1):
        who = "User" if t["kind"] == "user" else "System / automated message"
        out.append(f"### {fmt(t['ts'])} — Turn {i} ({who})\n")
        out.append("> " + t["prompt"].replace("\n", "\n> ") + "\n")
        if t["replies"]:
            out.append("**Assistant:**\n")
            out.append("\n\n".join(t["replies"]) + "\n")
        if t["tools"]:
            tools = ", ".join(f"{k} ×{v}" if v > 1 else k for k, v in sorted(t["tools"].items()))
            out.append(f"_Tools used: {tools}_\n")
        if t["status"] and t["status"] != "success":
            out.append(f"_Turn ended: {t['status']}_\n")
    return "\n".join(out)


def first_last(turns, path):
    start = turns[0]["ts"] if turns else None
    end = datetime.fromtimestamp(path.stat().st_mtime)
    return start, end


def main():
    for p in OUT.glob("*.md"):
        p.unlink()
    shutil.rmtree(OUT / "subagents", ignore_errors=True)
    (OUT / "subagents").mkdir()

    all_dirs = [d for d in TRANSCRIPTS.iterdir() if (d / f"{d.name}.jsonl").exists()]
    subagent_ids = {p.stem for d in TRANSCRIPTS.iterdir() for p in (d / "subagents").glob("*.jsonl")}
    chats = []
    for d in all_dirs:
        if d.name in subagent_ids or d.name in EXCLUDED:
            continue
        path = d / f"{d.name}.jsonl"
        records = load(path)
        turns = parse_turns(records)
        start, end = first_last(turns, path)
        title = TITLES.get(d.name) or (turns[0]["prompt"][:60] if turns else d.name)
        chats.append({"id": d.name, "dir": d, "path": path, "records": records,
                      "turns": turns, "start": start, "end": end, "title": title})
    chats.sort(key=lambda c: (c["start"] or datetime.max, c["id"]))

    index_rows = []
    for n, c in enumerate(chats, 1):
        fname = f"{c['start'].strftime('%Y-%m-%d_%H%M') if c['start'] else 'unknown'}_{slug(c['title'])}.md"
        by_id, by_prompt = task_descriptions(c["records"])
        subs = []
        for sp in sorted((c["dir"] / "subagents").glob("*.jsonl")):
            srec = load(sp)
            sturns = parse_turns(srec)
            sstart, send = first_last(sturns, sp)
            desc = by_id.get(sp.stem)
            if not desc and sturns:
                desc = by_prompt.get(sturns[0]["prompt"].strip()[:200])
            if not desc and sturns:
                m = ASSESS_RE.search(sturns[0]["prompt"])
                if m:
                    desc = f"Assess claims {m.group(1)} ({m.group(2)})"
            desc = desc or (sturns[0]["prompt"].splitlines()[0][:60] if sturns else sp.stem)
            sname = f"{sstart.strftime('%Y-%m-%d_%H%M') if sstart else 'unknown'}_{slug(desc)}_{sp.stem[:8]}.md"
            status = next((r.get("status") for r in reversed(srec) if r.get("type") == "turn_ended"), "unknown")
            subs.append({"name": sname, "desc": desc, "start": sstart, "end": send, "status": status, "id": sp.stem})
            body = [
                f"# Subagent: {desc}\n",
                f"- **Parent chat:** [{c['title']}](../{fname})",
                f"- **Started:** {fmt(sstart)} {TZ}",
                f"- **Last activity:** {fmt(send)} {TZ}",
                f"- **Final status:** {status}",
                f"- **Transcript ID:** `{sp.stem}`\n",
                "---\n",
                render_turns(sturns),
            ]
            (OUT / "subagents" / sname).write_text("\n".join(body))
        subs.sort(key=lambda s: (s["start"] or datetime.max, s["name"]))

        user_turns = sum(1 for t in c["turns"] if t["kind"] == "user")
        body = [
            f"# {c['title']}\n",
            f"- **Started:** {fmt(c['start'])} {TZ}",
            f"- **Last activity:** {fmt(c['end'])} {TZ}",
            f"- **User messages:** {user_turns}",
            f"- **Subagents:** {len(subs)}",
            f"- **Transcript ID:** `{c['id']}`\n",
        ]
        if subs:
            body.append("## Subagents\n")
            body.append("| Started | Task | Status |\n|---|---|---|")
            for s in subs:
                body.append(f"| {fmt(s['start'])} | [{s['desc']}](subagents/{s['name']}) | {s['status']} |")
            body.append("")
        body += ["## Conversation\n", render_turns(c["turns"])]
        (OUT / fname).write_text("\n".join(body))
        index_rows.append(f"| {n} | {fmt(c['start'])} | {fmt(c['end'])} | [{c['title']}]({fname}) | {user_turns} | {len(subs)} |")

    timeline = []
    for c in chats:
        for t in c["turns"]:
            if t["kind"] == "user":
                first = t["prompt"].splitlines()[0] if t["prompt"] else "(empty message)"
                timeline.append((t["ts"] or datetime.max, c["title"], first[:140]))
    timeline.sort(key=lambda x: x[0])

    readme = [
        "# Chat log\n",
        "Record of the Cursor agent chats used to build this project, generated from the agent transcripts.",
        f"All times are local, {TZ}. Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}.",
        "Rebuild with `python3 chats/generate.py`.\n",
        "Each chat file lists every user message with its timestamp, the assistant's written replies,",
        "and a summary of tools used. Subagent runs launched by a chat are in `subagents/` and linked from their parent.\n",
        "## Chats (by start time)\n",
        "| # | Started | Last activity | Chat | User messages | Subagents |",
        "|---|---|---|---|---|---|",
        *index_rows,
        "",
        "## Timeline of user messages\n",
        "| Time | Chat | Message |",
        "|---|---|---|",
        *[f"| {fmt(ts)} | {title} | {msg.replace('|', '\\|')} |" for ts, title, msg in timeline],
        "",
    ]
    (OUT / "README.md").write_text("\n".join(readme))
    print(f"Wrote {len(chats)} chats to {OUT}")


if __name__ == "__main__":
    main()
