"""The limbless-mouse block pins every figure by the bytes it copied, and the markdown twin is generated, not written.

Two failure modes are worth a test here. The first is a figure drifting away from the digest the page prints beside it, which
would make the digest decorative. The second is the markdown document and the page disagreeing, which is what happens to every
pair of hand-maintained twins: `--check` is the thing that stops it, so it is exercised in both directions.
"""
import json
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAP = json.loads((ROOT / "site/data/snapshot.json").read_text())
BLOCK = SNAP["limbless"]
INDEX = json.loads((ROOT / "results/limbless-mouse/index.json").read_text())


def test_the_block_is_built_from_the_authored_files_and_names_both_digests():
    assert BLOCK["content_sha256"] == sha256((ROOT / "site/content/limbless-mouse.json").read_bytes()).hexdigest()
    assert BLOCK["index_sha256"] == sha256((ROOT / "results/limbless-mouse/index.json").read_bytes()).hexdigest()
    assert [s["id"] for s in BLOCK["studies"]] == [s["id"] for s in INDEX["studies"]], "the index decides which studies exist"


def test_every_present_figure_matches_the_bytes_the_page_offers():
    served = ROOT / "site"
    seen = 0
    for study in BLOCK["studies"]:
        for fig in study["figures"]:
            if fig["state"] != "present":
                assert fig["href"] is None and fig["sha256"] is None, "an absent figure must not carry a link or a digest"
                continue
            copied = served / fig["href"]
            assert copied.is_file(), f"{fig['href']} is offered by the page and is not in the site tree"
            raw = copied.read_bytes()
            assert sha256(raw).hexdigest() == fig["sha256"] and len(raw) == fig["bytes"]
            source = ROOT / "results/limbless-mouse/figures" / fig["file"]
            assert source.read_bytes() == raw, "the copy served must be the recorded result, byte for byte"
            seen += 1
    assert seen == BLOCK["counts"]["figures_present"]


def test_a_declared_study_that_is_absent_is_reported_rather_than_dropped():
    for study in BLOCK["studies"]:
        on_disk = (ROOT / study["data_path"]).exists()
        assert study["present"] is on_disk
        if not on_disk:
            assert study["data"] is None and study["data_href"] is None
    assert BLOCK["counts"]["studies_declared"] == len(INDEX["studies"])


def test_every_figure_carries_an_authored_caption_and_alt_text():
    for study in INDEX["studies"]:
        for fig in study.get("figures", []):
            assert fig.get("caption", "").strip(), f"{fig['file']} has no caption"
            assert fig.get("alt", "").strip(), f"{fig['file']} has no alt text"


def test_the_markdown_twin_is_current_and_check_can_fail():
    doc = ROOT / "docs/dossier/13-limbless-mouse-design-space.md"
    run = lambda *a: subprocess.run([sys.executable, "scripts/limbless_doc.py", *a], cwd=ROOT, capture_output=True, text=True)
    assert run("--check").returncode == 0, "the committed document is stale; run python3 scripts/limbless_doc.py"
    original = doc.read_bytes()
    try:                                     # the positive control: --check must notice a document that has drifted
        doc.write_bytes(original + b"\ndrifted\n")
        assert run("--check").returncode == 1
    finally:
        doc.write_bytes(original)
    assert run("--check").returncode == 0
