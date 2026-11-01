"""Write the render receipt/manifest for full_horizon_chart.mp4 and extract its poster from the video itself.

Does not render. Inputs are hashed from disk; probe values come from ffprobe on the committed mp4.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ARMS = ("baseline", "nofeedback", "seed2")
CODE = ("render_full.py", "analyze.py", "make_receipt.py")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--repo-code-dir", default=str(Path(__file__).resolve().parent))
    a = ap.parse_args()
    parts, out, code = Path(a.parts), Path(a.out_dir), Path(a.repo_code_dir)
    video = out / "full_horizon_chart.mp4"
    poster = out / "full_horizon_chart_poster.png"
    # poster: the last frame of the actual video, not a re-render
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.2", "-i", str(video),
                    "-frames:v", "1", str(poster)], check=True)
    pr = json.loads(subprocess.run(
        ["ffprobe", "-v", "error", "-count_frames", "-select_streams", "v:0", "-show_entries",
         "stream=codec_name,width,height,r_frame_rate,nb_read_frames,pix_fmt:format=duration",
         "-of", "json", str(video)], check=True, capture_output=True, text=True).stdout)
    import matplotlib
    ff = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
    receipt = {
        "schema": "frontier.render-receipt.v0",
        "kind": "chart_video_from_logged_data",
        "is_spatial_movie": False,
        "disclosure": "Chart of logged cell count, mean CDK1 and mean g_l per cell. No cell shapes or fields are drawn. "
                      "Generic Morpheus example, not calibrated, not fish growth. Earlier artifacts/multicell/"
                      "{baseline,nofeedback,seed2}.mp4 are real spatial frames but PARTIAL (t<=0.46).",
        "inputs": {n: {"path": str(parts / n / "logger.csv"), "sha256": sha(parts / n / "logger.csv"),
                       "bytes": (parts / n / "logger.csv").stat().st_size} for n in ARMS},
        "source_code": {c: {"repo_path": f"engineering/multicell/{c}", "sha256": sha(code / c)} for c in CODE},
        "command_as_run": ("OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 systemd-run --user --scope -q -p CPUQuota=100% "
                           "-p TasksMax=128 -p MemoryMax=4G -p MemorySwapMax=0 -p RuntimeMaxSec=600 python3 "
                           "engineering/multicell/render_full.py --parts <parts> --out "
                           "artifacts/multicell/full/full_horizon_chart.mp4 --workdir <scratch dir>"),
        "render_params": {"frames": 100, "ffmpeg_framerate": 12, "t_end": 2.0, "dpi": 100},
        "tool_versions": {"matplotlib": matplotlib.__version__, "ffmpeg": ff},
        "runtime_s": {"value": 38.2, "status": "reported",
                      "note": "wall time from the shell `time` of the one original render; no log file was kept and it "
                              "was not re-measured. Tool versions above are those at receipt time, not proven identical "
                              "to the render's."},
        "output": {"video": {"repo_path": "artifacts/multicell/full/full_horizon_chart.mp4", "sha256": sha(video),
                             "bytes": video.stat().st_size},
                   "ffprobe": pr,
                   "poster": {"repo_path": "artifacts/multicell/full/full_horizon_chart_poster.png",
                              "sha256": sha(poster), "derived_from": "last frame of the video above (ffmpeg -sseof -0.2)"}},
        "upstream": {"source_commit": "29a26b00838736c4180f22fea075688f1d51e619",
                     "binary_sha256": "3d9a6e5a4cb86824b745500df1474596d39cce5deed24f767c0841df0f94d5ad",
                     "packet_sha256": "994eb8314f1d912e7dc16a9a9ca0e9d5591f86cf805bfa16e6e2070f2c34f4f7"},
        "index_contract": {"link_as": "chart_video", "required_label": "Chart from logged data, not a spatial movie",
                           "must_link": ["receipt", "poster", "full_summary.json", "source_code"]},
    }
    (out / "full_horizon_chart.receipt.json").write_text(json.dumps(receipt, indent=1))
    print(receipt["output"]["video"]["sha256"], pr["streams"][0]["nb_read_frames"], pr["format"]["duration"])


if __name__ == "__main__":
    main()
