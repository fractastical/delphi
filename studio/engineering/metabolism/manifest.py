"""Hash-pin the metabolism artifacts and code. Run last: python engineering/metabolism/manifest.py"""
import glob, hashlib, json, os

def main():
    sha = lambda f: hashlib.sha256(open(f, "rb").read()).hexdigest()
    fs = [f for f in sorted(glob.glob("artifacts/metabolism/**/*", recursive=True)) if os.path.isfile(f) and not f.endswith("/manifest.json")]
    code = sorted(glob.glob("engineering/metabolism/*.py"))
    code = [c for c in code if not c.endswith("/manifest.py")]          # this file would hash itself into the list it writes
    man = {"model": {"source": "https://github.com/SysBioChalmers/Zebrafish-GEM", "commit": "846f0b7b34701801b2f5e15f549807d2e71ffa62", "path": "model/Zebrafish-GEM.xml",
                     "sha256": "3424f584f3f48711d79a0a5af475e0ad0413af10c93345a7bb76e53874a1e217", "license": "CC-BY-4.0 (as stated by the repo; paper Wang 2021 PNAS doi:10.1073/pnas.2102344118)", "stored_in_repo": False},
           "software": {"cobra": "0.32.1", "solver": "glpk (via optlang)", "python": "3.13", "ffmpeg": "system /usr/bin/ffmpeg, libx264"},
           "files": [{"path": f, "sha256": sha(f)} for f in fs], "code": [{"path": c, "sha256": sha(c)} for c in code]}
    json.dump(man, open("artifacts/metabolism/manifest.json", "w"), indent=1); print(len(fs), "files,", len(code), "code files")

if __name__ == "__main__": main()
