"""Collect GEO SOFT metadata and expose literal coverage without guessing labels."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import resource
import subprocess
import time

import httpx

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts/regulatory-metadata"
BASE_URL = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def parse_soft(data, accession):
    """Retain repeated fields, require exact requested SOFT identity."""
    if not re.fullmatch(r"GS[EM][0-9]+", accession):
        raise ValueError("invalid accession")
    kind = "SERIES" if accession.startswith("GSE") else "SAMPLE"
    prefix = "Series" if kind == "SERIES" else "Sample"
    text = data.decode("utf-8")
    if text.splitlines()[0].strip() != f"^{kind} = {accession}":
        raise ValueError("metadata header identity mismatch or challenge")
    fields = {}
    for line in text.splitlines()[1:]:
        if line.startswith("!") and " = " in line:
            key, value = line[1:].split(" = ", 1)
            fields.setdefault(key, []).append(value)
    if fields.get(f"{prefix}_geo_accession") != [accession]:
        raise ValueError("metadata accession field mismatch")
    return fields


def children(fields):
    return sorted(
        {
            match.group(1)
            for value in fields.get("Series_relation", [])
            if (match := re.fullmatch(r"SuperSeries of: (GSE[0-9]+)", value))
        }
    )


def samples(fields):
    values = fields.get("Series_sample_id", [])
    if any(not re.fullmatch(r"GSM[0-9]+", value) for value in values):
        raise ValueError("invalid enumerated sample identity")
    return sorted(set(values))


def describe_sample(accession, fields):
    """Labels stay literal and carry their original metadata selectors."""
    selected = {"time_or_age": [], "replicate_labels": [], "cell_or_tissue": []}
    for key, values in fields.items():
        for value in values:
            if key.startswith("Sample_characteristics") and ":" in value:
                label, literal = value.split(":", 1)
                item = {"selector": key, "label": label, "value": literal.strip()}
                if re.search(r"age|time|stage|dpa|hpf", label, re.I):
                    selected["time_or_age"].append(item)
                if "replicate" in label.lower():
                    selected["replicate_labels"].append(item)
                if re.search(r"cell|tissue|organ|sort|genotype", label, re.I):
                    selected["cell_or_tissue"].append(item)
    title = fields.get("Sample_title", [])
    references = [
        {"selector": key, "value": value}
        for key, values in fields.items()
        for value in values
        if key in ("Sample_data_processing", "Sample_genome_build")
        and re.search(r"genome|annotation|GRCz|danRer|Ensembl|Lawson|release|reference", value, re.I)
    ]
    supplementary = [
        {"selector": key, "url": value, "fetched": False, "sha256": None}
        for key, values in fields.items()
        for value in values
        if key.startswith("Sample_supplementary_file") and value != "NONE"
    ]
    return {
        "accession": accession,
        "title": title,
        "organism": fields.get("Sample_organism_ch1", []),
        "source": fields.get("Sample_source_name_ch1", []),
        "assay_metadata": {
            key: fields.get(key, [])
            for key in ["Sample_type", "Sample_library_strategy", "Sample_library_source", "Sample_library_selection", "Sample_molecule_ch1"]
        },
        **selected,
        "title_labels_unresolved": title,
        "reference_processing_text": references,
        "processed_file_links": supplementary,
        "raw_characteristics": {
            key: value for key, value in fields.items() if key.startswith("Sample_characteristics")
        },
        "cell_level_labels_checked": False,
        "biological_replicate_identity_resolved": False,
        "identity_note": "Exact GSM validated; donor/biological independence is not inferred from GSM, library, title, lane or barcode.",
    }


def analyze(out):
    receipt = json.loads((out / "receipt.json").read_text())
    records = {}
    for entry in receipt["requests"]:
        if entry["status"] != "valid-metadata":
            continue
        data = (out / entry["path"]).read_bytes()
        if sha(data) != entry["sha256"] or len(data) != entry["bytes"]:
            raise ValueError("raw metadata digest/size mismatch")
        records[entry["accession"]] = parse_soft(data, entry["accession"])
    sample_rows = {acc: describe_sample(acc, f) for acc, f in records.items() if acc.startswith("GSM")}
    coverage = []
    for target in receipt["targets"]:
        series = [target] + children(records[target]) if target in records else []
        member_ids = sorted({acc for series_id in series for acc in samples(records.get(series_id, {}))})
        found = [sample_rows[acc] for acc in member_ids if acc in sample_rows]
        coverage.append({
            "target": target,
            "series_ids": series,
            "enumerated_unique_samples": len(member_ids),
            "retrieved_unique_samples": len(found),
            "unresolved_accessions": sorted(set(member_ids) - sample_rows.keys()),
            "organisms_literal": sorted({v for x in found for v in x["organism"]}),
            "source_labels_literal": sorted({v for x in found for v in x["source"]}),
            "time_or_age_values_literal": sorted({x["value"] for row in found for x in row["time_or_age"]}),
            "samples_with_explicit_time_or_age_characteristic": sum(bool(x["time_or_age"]) for x in found),
            "samples_with_explicit_replicate_characteristic": sum(bool(x["replicate_labels"]) for x in found),
            "samples_with_reference_processing_text": sum(bool(x["reference_processing_text"]) for x in found),
            "listed_sample_processed_file_links": sum(len(x["processed_file_links"]) for x in found),
            "cell_level_labels_checked": False,
            "biological_replicate_identities_resolved": False,
            "downstream_status": "blocked pending donor/replicate and cell-label audit; no independence guessed",
            "questions": [
                "Which library records share the same biological tissue/donor or paired multiome source?",
                "Where are cell-level annotations and their exact barcode/sample mapping?",
                "Do listed reference and annotation versions match across the desired comparisons?",
                "Do processed files contain appropriate fin compartments/stages, and what are their checksums? Files were not fetched.",
            ],
        })
    series_rows = []
    for acc, fields in records.items():
        if acc.startswith("GSE"):
            series_rows.append({"accession": acc, "metadata": fields, "sample_ids": samples(fields), "children": children(fields)})
    result = {
        "schema": "frontier.regulatory-metadata-coverage/1",
        "protocol_sha256": receipt["protocol_sha256"],
        "protocol_commit": receipt["protocol_commit"],
        "status": "metadata retrieved; downstream biological identity unresolved" if not receipt["errors"] else "incomplete retrieval; see errors",
        "coverage": coverage,
        "series": series_rows,
        "samples": list(sample_rows.values()),
        "errors": receipt["errors"],
        "limitations": ["No sequencing arrays, supplementary files or cell annotations downloaded.", "Linked-file sizes/checksums and biological independence remain unverified.", "A stated library strategy does not establish per-cell assay pairing.", "Metadata audit is not an empirical replication or regulatory prediction."],
    }
    write(out / "coverage.json", result)
    return result


def collect(out):
    if out.exists():
        raise ValueError("output exists; refuse duplicate collection")
    protocol_bytes = (ART / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    commit = subprocess.check_output(["git", "log", "-1", "--format=%H", "--", "artifacts/regulatory-metadata/protocol.json"], cwd=ROOT, text=True).strip()
    pinned = subprocess.check_output(["git", "show", f"{commit}:artifacts/regulatory-metadata/protocol.json"], cwd=ROOT)
    if pinned != protocol_bytes:
        raise ValueError("protocol is not committed")
    bounds = protocol["bounds"]
    out.mkdir(parents=True)
    (out / "raw").mkdir()
    started, started_cpu = time.monotonic(), time.process_time()
    receipt = {
        "schema": "frontier.metadata-audit.receipt/1", "targets": protocol["targets"],
        "protocol_commit": commit, "protocol_sha256": sha(protocol_bytes),
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_sha256": sha(Path(__file__).read_bytes()),
        "environment": {"python": platform.python_version(), "httpx": httpx.__version__, "platform": platform.platform()},
        "started_utc": datetime.now(timezone.utc).isoformat(), "requests": [], "errors": [],
        "supplementary_files_fetched": 0, "inference_calls": 0, "dollars": None,
    }
    total_bytes = 0
    records = {}
    with httpx.Client(timeout=bounds["request_timeout_seconds"], follow_redirects=False) as client:
        def fetch(acc):
            nonlocal total_bytes
            if acc in records:
                return records[acc]
            if len(receipt["requests"]) >= bounds["max_responses"] or time.monotonic() - started > bounds["wall_seconds"]:
                raise ValueError("response/time budget reached")
            if not re.fullmatch(r"GS[EM][0-9]+", acc):
                raise ValueError("invalid enumerated accession")
            params = {"acc": acc, "targ": "self", "form": "text", "view": "full"}
            entry = {"accession": acc, "started_utc": datetime.now(timezone.utc).isoformat()}
            receipt["requests"].append(entry)
            data = b""
            try:
                with client.stream("GET", BASE_URL, params=params) as response:
                    entry.update(url=str(response.url), http_status=response.status_code)
                    for chunk in response.iter_bytes():
                        if len(data) + len(chunk) > bounds["max_response_bytes"] or total_bytes + len(chunk) > bounds["max_total_response_bytes"]:
                            raise ValueError("metadata byte budget reached")
                        data += chunk
                        total_bytes += len(chunk)
                path = f"raw/{acc}.soft.txt"
                (out / path).write_bytes(data)
                entry.update(path=path, bytes=len(data), sha256=sha(data))
                if entry["http_status"] != 200:
                    raise ValueError("non-200 metadata response")
                fields = parse_soft(data, acc)
                records[acc] = fields
                entry["status"] = "valid-metadata"
                return fields
            except Exception as exc:
                entry.update(status="failed", error=f"{type(exc).__name__}: {exc}")
                receipt["errors"].append({"accession": acc, "error": entry["error"]})
                raise
            finally:
                write(out / "receipt.json", receipt)
        try:
            series_ids = list(protocol["targets"])
            for acc in protocol["targets"]:
                fields = fetch(acc)
                series_ids.extend(children(fields))
            for acc in sorted(set(series_ids)):
                fetch(acc)
            gsm_ids = sorted({gsm for acc in set(series_ids) for gsm in samples(records[acc])})
            if len(gsm_ids) + len(records) > bounds["max_responses"]:
                raise ValueError("enumerated samples exceed frozen response budget")
            for acc in gsm_ids:
                fetch(acc)
        except Exception as exc:
            receipt["errors"].append({"stage": "collection stopped", "error": f"{type(exc).__name__}: {exc}"})
        finally:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            receipt.update(finished_utc=datetime.now(timezone.utc).isoformat(), wall_seconds=time.monotonic()-started, process_cpu_seconds=time.process_time()-started_cpu, max_rss_KiB=usage.ru_maxrss, response_bytes=total_bytes)
            write(out / "receipt.json", receipt)
    return analyze(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["collect", "analyze"])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    result = collect(args.out) if args.mode == "collect" else analyze(args.out)
    print(json.dumps({"status": result["status"], "samples": len(result["samples"]), "series": len(result["series"]), "errors": result["errors"]}))
    return 1 if result["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
