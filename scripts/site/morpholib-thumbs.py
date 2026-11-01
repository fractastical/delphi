#!/usr/bin/env python3
"""Thumbnails of the MorphoEval simulations that test or model our claims.

For every morpholib model linked from test-data/morpholib/links.json, find its committed
animation or figure under docs/media/ in github.com/fractastical/morpholib at the commit the
links were made against, take the final frame (the grown form) and write a small JPEG to
docs/thumbs/<morpholib-id>.jpg. docs/thumbs/index.json records, per model, which file and frame
each thumbnail came from, so a card on the claim graph can link back to the full animation.

    python3 scripts/site/morpholib-thumbs.py            # fetch what is missing, rebuild the index
    python3 scripts/site/morpholib-thumbs.py --force    # regenerate every thumbnail

Downloads are cached in ~/.cache/delphisci/morpholib-media. Needs Pillow (`pip install pillow`).
"""
import io, json, os, re, sys, urllib.request
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
LINKS = ROOT / "test-data/morpholib/links.json"
OUT = ROOT.parent / "docs/thumbs"  # ROOT is 
CACHE = Path(os.path.expanduser("~/.cache/delphisci/morpholib-media"))
REPO = "fractastical/morpholib"
# Thumbnail pixel size: the card box is 146x58 CSS px; render at 2x for retina.
SIZE = (292, 116)
# Models whose media file does not carry the model's slug.
OVERRIDES = {"menshykau-fgf10-shh-lung-turing": "lung_stereotyped_branching_modes_growth.gif"}

FORCE = "--force" in sys.argv


def fetch(url, binary=True):
    req = urllib.request.Request(url, headers={"User-Agent": "delphisci-thumbs"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read() if binary else r.read().decode()


def media_files(commit):
    """Names and sizes of everything under docs/media/ at the pinned commit (one API call, cached)."""
    cached = CACHE / f"tree-{commit}.json"
    if cached.exists():
        tree = json.loads(cached.read_text())
    else:
        tree = json.loads(fetch(f"https://api.github.com/repos/{REPO}/git/trees/{commit}?recursive=1", binary=False))["tree"]
        CACHE.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(tree))
    return {t["path"][len("docs/media/"):]: t["size"] for t in tree
            if t["path"].startswith("docs/media/") and "/" not in t["path"][len("docs/media/"):] and t["type"] == "blob"}


def resolve(model_id, names):
    """The media file for a model: its slug (author prefix dropped) is the file's prefix.
    Prefer the growth animation, then any animation, then the comparison figure."""
    if model_id in OVERRIDES:
        return OVERRIDES[model_id]
    toks = re.sub(r"^thompson1917-", "", model_id).split("-")
    for k in range(len(toks) - 1):
        pre = "_".join(toks[k:])
        hits = [n for n in names if n.startswith(pre + "_") or n.startswith(pre + ".")]
        if not hits:
            continue
        rank = lambda n: (0 if n.endswith("_growth.gif") else 1 if n.endswith(".gif") else 2 if n.endswith("_comparison.png") else 3, n)
        return sorted(hits, key=rank)[0]
    return None


def thumbnail(data):
    """Final frame of an animation (or the still), cover-cropped to SIZE. Returns (jpeg bytes, frame, n_frames)."""
    im = Image.open(io.BytesIO(data))
    n = getattr(im, "n_frames", 1)
    im.seek(n - 1)
    frame = im.convert("RGB")
    frame = ImageOps.fit(frame, SIZE, method=Image.LANCZOS, centering=(0.5, 0.5))
    buf = io.BytesIO()
    frame.save(buf, "JPEG", quality=82, optimize=True, progressive=True)
    return buf.getvalue(), n - 1, n


def main():
    links = json.loads(LINKS.read_text())
    commit = links["source"]["commit"]
    ids = sorted({l["morpholib"] for l in links["links"]})
    names = media_files(commit)
    OUT.mkdir(parents=True, exist_ok=True)
    CACHE.mkdir(parents=True, exist_ok=True)
    prev = json.loads((OUT / "index.json").read_text())["thumbs"] if (OUT / "index.json").exists() else {}
    index, missing = {}, []
    for mid in ids:
        name = resolve(mid, names)
        if not name:
            missing.append(mid)
            continue
        out = OUT / f"{mid}.jpg"
        source = f"https://github.com/{REPO}/blob/{commit}/docs/media/{name}"
        raw = f"https://raw.githubusercontent.com/{REPO}/{commit}/docs/media/{name}"
        old = prev.get(mid)
        if out.exists() and old and old.get("media") == name and old.get("commit") == commit and not FORCE:
            index[mid] = old
            continue
        cached = CACHE / f"{commit}-{name}"
        if not cached.exists():
            print(f"fetching {name} ({names[name] / 1e6:.1f} MB)")
            cached.write_bytes(fetch(raw))
        jpeg, frame, n = thumbnail(cached.read_bytes())
        out.write_bytes(jpeg)
        index[mid] = {"file": f"thumbs/{mid}.jpg", "media": name, "source": source, "frame": frame, "frames": n, "commit": commit}
        print(f"{mid}: {name} frame {frame + 1}/{n} -> {out.relative_to(ROOT)} ({len(jpeg) // 1024} KB)")
    (OUT / "index.json").write_text(json.dumps({"source": {"repo": f"https://github.com/{REPO}", "commit": commit, "media": "docs/media"},
                                               "size": SIZE, "thumbs": index, "no_media": missing}, indent=1) + "\n")
    print(f"{len(index)} thumbnails for {len(ids)} linked morpholib models; no media for: {', '.join(missing) or 'none'}")


if __name__ == "__main__":
    main()
