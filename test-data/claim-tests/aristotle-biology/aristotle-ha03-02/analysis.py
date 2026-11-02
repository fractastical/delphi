"""Test aristotle-ha03-02 on hedgehog testis position and the named bird and reptiles.

Requires pdftotext. Run: python3 analysis.py
"""

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import _fetch

HERE = Path(__file__).resolve().parent
CHAI = "https://media.springernature.com/original/springer-static/esm/art%3A10.1186%2Fs12862-021-01753-5/MediaObjects/12862_2021_1753_MOESM1_ESM.pdf"
AKBARI = "https://journals.viamedica.pl/folia_morphologica/article/download/FM.a2017.0056/40712"
ADW = {
    "Gallus gallus": "https://animaldiversity.org/accounts/Gallus_gallus/",
    "Lacerta viridis": "https://animaldiversity.org/accounts/Lacerta_viridis/",
    "Testudo graeca": "https://animaldiversity.org/accounts/Testudo_graeca/",
    "Crocodylus niloticus": "https://animaldiversity.org/accounts/Crocodylus_niloticus/",
}
MONOTREMES = ("Ornithorhynchus", "Tachyglossus")


def pdf_text(data):
    with tempfile.NamedTemporaryFile(suffix=".pdf") as handle:
        handle.write(data)
        handle.flush()
        out = subprocess.run(["pdftotext", "-layout", handle.name, "-"], check=True, capture_output=True)
    return out.stdout.decode("utf-8", "replace")


def html_text(data):
    html = data.decode("utf-8", "replace")
    html = re.sub(r"(?is)<script.*?>.*?</script>", " ", html)
    html = re.sub(r"(?is)<style.*?>.*?</style>", " ", html)
    html = re.sub(r"(?s)<[^>]+>", " ", html)
    return re.sub(r"\s+", " ", html)


def chai_rows(text):
    chunk = text.split("Species for evolutionary")[0]
    rows = []
    for line in chunk.splitlines():
        match = re.search(r"(Ascrotal|Scrotal)\s+(CDT|IDT|UDT)", line)
        if not match:
            continue
        binomial = re.search(r"✭\s*([A-Z][a-z]+\s+[a-z]+)", line)
        name = binomial.group(1) if binomial else ""
        rows.append({
            "line": re.sub(r"\s+", " ", line).strip(),
            "binomial": name,
            "scrotum": match.group(1),
            "position": match.group(2),
            "monotreme": any(name.startswith(genus) for genus in MONOTREMES),
        })
    return rows


def adw_testis(text):
    sentences = re.split(r"(?<=[.!?])\s+", text)
    hits = [s.strip() for s in sentences if re.search(r"\b(testes|testis|testicle|scrotum|scrotal)\b", s, re.I)]
    blob = " ".join(hits).lower()
    if not hits:
        return "not_stated", hits
    if re.search(r"\bscrot", blob) and not re.search(r"no true scrot|without a scrot|ascrotal|intra-abdominal|abdominal", blob):
        return "fail_scrotal", hits
    if re.search(r"intra-abdominal|abdominal|internal|beside the kidne|near the kidne|loin", blob):
        return "pass_internal", hits
    return "not_stated", hits


def main():
    chai = _fetch.fetch(CHAI)
    akbari = _fetch.fetch(AKBARI)
    adw = {name: _fetch.fetch(url) for name, url in ADW.items()}
    rows = chai_rows(pdf_text(chai["data"]))
    hedgehog = next(row for row in rows if "Erinaceus europaeus" in row["binomial"] or "Erinaceus europaeus" in row["line"])
    viviparous = [row for row in rows if not row["monotreme"]]
    other_ascrotal = [row for row in viviparous if row["scrotum"] == "Ascrotal" and "Erinaceus" not in row["binomial"]]
    akbari_text = pdf_text(akbari["data"])
    akbari_sentences = [
        re.sub(r"\s+", " ", sentence).strip()
        for sentence in re.split(r"(?<=[.!?])\s+", akbari_text.replace("\n", " "))
        if re.search(r"\btestes\b", sentence, re.I) and re.search(r"inguinal|pubic|abdominal|scrot|kidney|lumbar|loin", sentence, re.I)
    ]
    akbari_low = akbari_text.lower()
    not_scrotal = ("no true scrotal" in akbari_low) or ("intra-abdominal" in akbari_low) or hedgehog["scrotum"] == "Ascrotal"
    loin_words = bool(re.search(r"kidney|lumbar|loin", akbari_low))
    inguinal_or_pubic = bool(re.search(r"inguinal region|pubic region", akbari_low))
    table_loin = hedgehog["position"] == "UDT"
    table_not_loin = hedgehog["position"] in ("IDT", "CDT")
    taxa = {}
    for name, fetched in adw.items():
        state, hits = adw_testis(html_text(fetched["data"]))
        taxa[name] = {"state": state, "sentences": hits[:4]}
    hedgehog_internal_pass = hedgehog["scrotum"] == "Ascrotal" and not_scrotal
    hedgehog_loin_fail = table_not_loin or (inguinal_or_pubic and not table_loin)
    hedgehog_loin_pass = table_loin and not inguinal_or_pubic
    sources_disagree = table_loin and inguinal_or_pubic and not loin_words
    taxon_fail = any(item["state"] == "fail_scrotal" for item in taxa.values())
    taxon_missing = any(item["state"] == "not_stated" for item in taxa.values())
    taxon_pass = all(item["state"] == "pass_internal" for item in taxa.values())
    if (not hedgehog_internal_pass) or hedgehog_loin_fail or taxon_fail:
        verdict, reason = "refutes", None
    elif sources_disagree or (hedgehog_loin_pass and taxon_fail):
        verdict, reason = "mixed", None
    elif hedgehog_internal_pass and hedgehog_loin_pass and taxon_pass:
        verdict, reason = "supports", None
    elif taxon_missing:
        verdict, reason = "inconclusive", "data-unavailable"
    else:
        verdict, reason = "mixed", None
    males = re.search(r"(\w+)\s+adult male", akbari_text)
    measured = {
        "value": len(other_ascrotal),
        "unit": "other viviparous mammals in the table coded ascrotal",
        "n": len(viviparous),
        "uncertainty": None,
        "extra": {
            "hedgehog": hedgehog,
            "hedgehog_not_scrotal": hedgehog_internal_pass,
            "hedgehog_position_code": hedgehog["position"],
            "akbari_testis_sentences": akbari_sentences[:8],
            "akbari_mentions_intra_abdominal": "intra-abdominal" in akbari_low,
            "akbari_mentions_inguinal_or_pubic": inguinal_or_pubic,
            "akbari_mentions_kidney_or_loin": loin_words,
            "adw": taxa,
            "viviparous_rows": len(viviparous),
            "ascrotal_viviparous_including_hedgehog": sum(1 for row in viviparous if row["scrotum"] == "Ascrotal"),
            "monotremes_excluded": sum(1 for row in rows if row["monotreme"]),
        },
    }
    result_path = HERE / "result.json"
    result = json.loads(result_path.read_text())
    assert result["pass_criterion"].startswith("Pre-registered.")
    result.update({
        "status": "complete",
        "data_kind": "biological",
        "verdict": verdict,
        "confidence": 0.84 if verdict == "refutes" else 0.55,
        "method": (
            "Supplementary Table S1 of Chai et al. 2021 was converted with pdftotext and each row's "
            "scrotum state and testis-position code were read. UDT was treated as the loin, and IDT or CDT "
            "as not the loin, as pre-registered. The Akbari et al. 2018 dissection PDF was converted the same "
            "way and sentences that mention the testes together with inguinal, pubic, abdominal or scrotal "
            "language were kept. Animal Diversity Web accounts for the chicken, green lizard, Greek tortoise "
            "and Nile crocodile were searched for testis sentences. One failed hedgehog clause refutes the conjunction."
        ),
        "datasets": [
            {
                "id": "chai-2021-testis-position-table-s1",
                "name": "Chai et al. 2021 Additional file 1, Table S1, testis position of mammals",
                "landing_url": "https://link.springer.com/article/10.1186/s12862-021-01753-5",
                "doi": "10.1186/s12862-021-01753-5",
                "version": "Additional file 1",
                "license": None,
                "files": [{k: chai[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
                "role": "comparative scrotal state and CDT/IDT/UDT code, including Erinaceus europaeus",
            },
            {
                "id": "akbari-2018-erinaceus-reproductive-anatomy",
                "name": "Akbari et al. 2018 gross anatomy of the male European hedgehog",
                "landing_url": "https://journals.viamedica.pl/folia_morphologica/article/view/50839",
                "doi": None,
                "version": "Folia Morphologica 2018",
                "license": None,
                "files": [{k: akbari[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")}],
                "role": "primary description of where the adult male hedgehog testes lie",
            },
            {
                "id": "adw-gallus-lacerta-testudo-crocodylus",
                "name": "Animal Diversity Web accounts for chicken, green lizard, Greek tortoise and Nile crocodile",
                "landing_url": "https://animaldiversity.org/",
                "doi": None,
                "version": "live accounts",
                "license": None,
                "files": [{k: fetched[k] for k in ("download_url", "retrieved_at", "byte_size", "sha256")} for fetched in adw.values()],
                "role": "statements, if any, of testis position in the named bird and oviparous quadrupeds",
            },
        ],
        "measured": measured,
        "caveats": [
            "IDT was pre-registered as inguinal rather than beside the loin. The table's own note expands IDT as incompletely descended testis.",
            "Akbari and colleagues also call the testes intra-abdominal and say there is no true scrotum. The same paper places them caudolaterally in the inguinal region, with scrotal pouches against the pubic muscles.",
            f"The Chai table codes {len(other_ascrotal)} other viviparous mammals as ascrotal. That count is reported and was pre-registered as not a pass or fail, because the sentence does not say the hedgehog is unique.",
            "The four Animal Diversity Web accounts do not state a testis position, so the bird, lizard, tortoise and crocodile clauses are untested. The hedgehog clause is enough to refute the conjunction.",
            "No licence line was extracted from the PDFs or the accounts.",
        ],
    })
    if males:
        result["caveats"].append(f"The dissection's opening sentence names the sample as '{males.group(0)}'.")
    if reason:
        result["reason"] = reason
    else:
        result.pop("reason", None)
    result_path.write_text(json.dumps(result, indent=2) + "\n")
    derived = HERE / "derived"
    derived.mkdir(exist_ok=True)
    (derived / "measured.json").write_text(json.dumps(measured, indent=2) + "\n")
    print(verdict, hedgehog["scrotum"], hedgehog["position"], "other_ascrotal", len(other_ascrotal), "taxa", {k: v["state"] for k, v in taxa.items()})


if __name__ == "__main__":
    main()
