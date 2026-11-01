"""MorphoLib / MorphoEval -> PROPOSED Claim, Evidence and Problem drafts, an equation index and a model index, frozen as importable bundles.

What this module is, and is not
  * It READS immutable git blobs (`git cat-file`) of a clone of https://github.com/fractastical/morpholib at a pinned commit. It never reads
    the working tree, never executes upstream code (no model script, no Lean, no nanopub tool), never contacts a service and never writes
    to a store. Producing a bundle is not importing it: corpus owns imports.
  * Slice: the 25 loops upstream's own audit counts as Tier A (`morphoeval/runs/science_provenance_audit.json`, `counted`), because the
    audit says those are the ones whose paper is extracted AND whose literature was scouted. Tier B (paper named only) and Tier C
    (scaffold only, deleted upstream) are NOT imported as models; they appear only as counts and exclusions.
  * Per model, three records: Claim (`source_statement`: what upstream's math_kg spec attributes to the paper; Frontier did not check it
    against the paper), Evidence (`source_assessment`: upstream's MorphoEval assessment of how closely its script matches that source) and
    Problem (the assessor's own remediation list, quoted, `recorded`). A MorphoEval score describes MATCHING A SOURCE, not biological truth.
  * The assessor is a language model working for the same author who built the script (stated in the nanopub). That is recorded as
    `independent_of_claim: false`. Nothing here is reviewed, signed or published by Frontier.
  * Nanopub flags are kept as they are in the file: `signature_block_present` means an `npx:hasSignature` block is in the .trig. Nobody here
    verified it and nobody here checked a registry, so `signature_verified` and `published` are `unknown`, never `true`.
  * Lean: an equation carries Lean TEXT and a declared locus. Frontier compiled none of it. The only checks are mechanical (upstream's own
    template markers, `sorry`, the tactics named in the declared range). SPEC-009's anti-triviality gate was NOT run, so no equation is
    L2 and none is counted as a proof.
  * Fabrication guard: this slice has no synthetic series, no slot-index scores and no template Lean by construction; the build REFUSES a
    model whose spec carries an upstream template marker, and every hash upstream states is recomputed from the blob.
"""
from __future__ import annotations

import json
import os
import re
import subprocess

import yaml

from .artifacts import entry, find_abs_paths, to_artifact_ref
from .common import canon, sha_bytes
from .engineering_manifest import Chain, Refused, _cache_key, _source, resolve_commit, _commit_utc, REPO_LABEL as _ENG_LABEL  # noqa: F401

ADAPTER_ID = "frontier_adapters.morpholib"
ADAPTER_VERSION = "0.1.0"
UPSTREAM = "https://github.com/fractastical/morpholib"
REPO_LABEL = "morpholib"
UPSTREAM_LICENSE = "MIT (upstream LICENSE, (c) 2026 Joel Dietz; embedded third-party images carry their own licences)"
AUDIT_PATH = "morphoeval/runs/science_provenance_audit.json"
STATUS = ("PROPOSED. Not submitted, accepted or published. Single-reader (MorphoLib integration worker), not Codex-reviewed, "
          "not independently reviewed.")
IMPORT_NOTE = ("Imported record of what upstream's files say. Frontier did not run upstream code and did not check the source paper's "
               "equations; the assessor is a language model working for the same author as the script, so this is not independent evidence.")
SOURCE_ACCESS = ("Public repository file at an immutable commit (git locator in the locator). Only digests are carried; bytes are not embedded. "
                 "Licence: " + UPSTREAM_LICENSE + ".")
MAX_BUNDLE_BYTES = 1_800_000   # the store refuses 2,000,000; leave room for the envelope
TEMPLATE_MARKERS = ("def law1_invariant (a b : Int) : Int := a * b", "def law2_balance (p q : Int) : Int := p + q - q",
                    "def law3_threshold_margin (lhs rhs : Int) : Int := lhs - rhs")
TEMPLATE_SUFFIXES = (".law1_invariant", ".law2_balance", ".law3_threshold_margin")

# Scale of each model. CURATED BY THIS ADAPTER'S AUTHOR from the paper titles and equations; not a field upstream states.
SCALES = {
    "gierer-hydra-activator-inhibitor": ["tissue", "organism", "developmental"],
    "sick-wnt-dkk-hair-follicle": ["tissue", "developmental"],
    "raspopovic-bmp-sox9-wnt-digits": ["tissue", "developmental"],
    "bailleul-allometric-cranial-sutures": ["tissue", "organism"],
    "hannezo-epithelial-buckling-3d": ["tissue"],
    "streichan-global-morphogenetic-flow": ["tissue", "organism"],
    "serra-gastrulation-streak-attractor": ["cellular", "tissue", "developmental"],
    "menshykau-gdnf-ret-ureteric-kidney": ["organ", "developmental"],
    "richman-cortical-gyrification-buckling": ["organ", "developmental"],
    "goriely-tendril-perversion-intrinsic-curvature": ["tissue", "organism"],
    "liang-chiral-seed-pod-opening": ["tissue", "organism"],
    "forterre-venus-flytrap-snap-buckling": ["organ"],
    "chirat-mollusc-shell-marginal-buckling": ["organism", "developmental"],
    "thomas-coral-calice-septa-insertion": ["organism", "developmental"],
    "moulton-mollusc-aperture-spine-buckling": ["organism", "developmental"],
    "pietak-bioelectric-morphogen-coupling": ["cellular", "tissue"],
    "kriegman-xenobot-evolutionary-biobots": ["organism", "evolutionary"],
    "pezzulo-bioelectric-target-morphology-memory": ["tissue", "organism"],
    "carmona-neural-crest-chase-and-run": ["cellular", "collective"],
    "odell-apical-constriction-invagination": ["cellular", "tissue"],
    "zajac-convergent-extension-intercalation": ["cellular", "tissue"],
    "asally-bacillus-biofilm-wrinkling": ["collective"],
    "yan-vibrio-biofilm-nematic-fountain": ["collective"],
    "bonabeau-social-wasp-comb-hexagons": ["collective"],
    "ocko-termite-mound-convective-chimneys": ["collective", "ecological"],
}


# --------------------------------------------------------------------------------------------------------------------------
# reading the upstream clone
# --------------------------------------------------------------------------------------------------------------------------
def list_tree(repo: str, commit: str) -> list[str]:
    out = subprocess.run(["git", "-C", repo, "ls-tree", "-r", "--name-only", commit], capture_output=True, text=True, timeout=120)
    if out.returncode != 0:
        raise Refused(f"cannot list {commit[:12]}: {out.stderr.strip()[:100]}")
    return out.stdout.split("\n")


def _lit(s: str) -> str:
    """Un-escape a TriG string literal body (only the escapes that occur: backslash, quote, n, t, r)."""
    return re.sub(r'\\(["\\ntr])', lambda m: {"n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), s)


_L = r'"((?:[^"\\]|\\.)*)"'


def parse_assessment(trig: str) -> dict:
    """The fields of a MorphoEval overall-assessment nanopub that this adapter carries. Regex over a fixed upstream layout, checked by tests."""
    def one(pat, flags=0):
        m = re.search(pat, trig, flags)
        return m.group(1) if m else None

    out = {
        "np_uri": one(r"@prefix this: <([^>]+)>"),
        "label": _lit(one(r"a pk:LLMClaimAssessment ;\s*rdfs:label " + _L) or ""),
        "date": one(r"(?:dcterms|dct):date \"([\d-]+)\""),
        "created": one(r"(?:dcterms|dct):created \"([^\"]+)\""),
        "score": one(r'pk:hasScore "([\d.]+)"'),
        "verdict": one(r'pk:hasVerdict "([^"]+)"'),
        "assessment_type": one(r'pk:assessmentType "([^"]+)"'),
        "assessor": one(r"pk:assessedBy <([^>]+)>"),
        "description": _lit(one(r"(?:dcterms|dct):description " + _L) or ""),
        "signature_block_present": "npx:hasSignature" in trig or "npx:hasSignature" in trig.replace("np:x", "npx"),
        "signed_by": one(r"npx:signedBy (orcid:[\w-]+)"),
    }
    m = re.search(r"pk:evidenceAgainst\s+((?:" + _L + r"\s*,?\s*)+)", trig)
    out["evidence_against"] = [_lit(x) for x in re.findall(_L, m.group(1))] if m else []
    d = out["description"]
    out["output_judged"] = None
    m = re.search(r"Output judged: (\S+): .*?artifact_sha256 ([0-9a-f]{64})", d)
    if m:
        out["output_judged"] = {"path": m.group(1), "artifact_sha256": m.group(2)}
    m = re.search(r"Dimension assessments: (.*?)\. Output judged", d)
    out["dimension_text"] = m.group(1) if m else None
    m = re.search(r"Claim boundary: (.*)$", d, re.S)
    boundary = {}
    if m:
        body = m.group(1)
        keys = ["reported_in_source", "reconstructed_in_script", "transfer_boundary", "does_not_claim"]
        pos = sorted((body.find(k + ":"), k) for k in keys if body.find(k + ":") >= 0)
        for i, (p, k) in enumerate(pos):
            end = pos[i + 1][0] if i + 1 < len(pos) else len(body)
            boundary[k] = body[p + len(k) + 1:end].strip(" ;")
    out["claim_boundary"] = boundary
    return out


def audit_versions(tree: list[str], sim_id: str) -> list[dict]:
    """Every version of the overall assessment present for one loop, oldest first. `-vN` suffix orders them; no suffix is version 1."""
    found = {}
    for t in tree:
        m = re.fullmatch(r"morphoeval/kg/(2026-\d\d-\d\d-[\w-]+?-audit(?:-v(\d+))?)/(signed/)?" + re.escape(sim_id) + r"-overall\.trig", t)
        if m:
            v = int(m.group(2) or 1)
            found.setdefault(v, {"version": v, "dir": m.group(1)})["signed" if m.group(3) else "unsigned"] = t
    return [found[k] for k in sorted(found)]


def _chunks(s: str, n: int = 2800) -> list[str]:
    """Split a long string at ' | ', '; ' or '. ' boundaries into pieces of at most n characters. Nothing is dropped."""
    out, rest = [], s.strip()
    while len(rest) > n:
        cut = max(rest.rfind(sep, 0, n) + len(sep) for sep in (" | ", "; ", ". ") if rest.rfind(sep, 0, n) > 0) if any(
            rest.rfind(sep, 0, n) > 0 for sep in (" | ", "; ", ". ")) else n
        out.append(rest[:cut].strip())
        rest = rest[cut:].strip()
    if rest:
        out.append(rest)
    return out


def _lean_flags(lean_text: str, locus: str, eq: dict) -> dict:
    """Mechanical flags over an equation's declared Lean range. These are NOT a proof check and NOT SPEC-009's gate."""
    m = re.fullmatch(r"([^#]+)#L(\d+)-L(\d+)", locus or "")
    lines = lean_text.split("\n")
    span = "\n".join(lines[int(m.group(2)) - 1:int(m.group(3))]) if m else ""
    no_comments = re.sub(r"/-.*?-/", "", re.sub(r"--[^\n]*", "", span), flags=re.S)
    template = (any(str(eq.get(f, "")).endswith(TEMPLATE_SUFFIXES) for f in ("lean_decl", "lean_theorem"))
                or any(k in str(eq.get("lean_code", "")) for k in TEMPLATE_MARKERS) or eq.get("formalization_status") == "template_placeholder_not_a_proof")
    tactics = sorted(set(re.findall(r":=\s*by\s+(\w+)", no_comments)))
    return {"upstream_template_marker": template, "locus_range_found": bool(span.strip()), "has_sorry": bool(re.search(r"\bsorry\b", no_comments)),
            "tactics_named_in_range": tactics, "only_trivial_tactics": bool(tactics) and set(tactics) <= {"decide", "rfl", "trivial", "omega"},
            "compiled_by_frontier": False, "spec009_anti_triviality_gate_run": False}


# --------------------------------------------------------------------------------------------------------------------------
# one model -> Claim, Evidence, Problem
# --------------------------------------------------------------------------------------------------------------------------
def _artifact(c: Chain, role: str, path: str, data: bytes, note: str, license_: str | None = UPSTREAM_LICENSE) -> dict:
    e = entry(role, data, path=path, repo_label=REPO_LABEL, commit=c.commit, note=note)
    e["license"] = license_
    ref = to_artifact_ref(e)
    ref["title"] = (f"{role}: {path} [git:{REPO_LABEL}@{c.commit[:12]}] {note}")[:3000]
    return ref


def model_chain(repo: str, commit: str, tree: list[str], item: dict, *, namespace: str, issuer: str, created_at: str) -> tuple[Chain, dict, list[dict]]:
    sim = item["sim_id"]
    c = Chain(repo, commit, namespace, issuer, created_at, sim)
    c.check("audit.tier_a", True, f"{sim} is in `counted` of {AUDIT_PATH} (slot {item['slot']})")
    # inputs: spec, script, reference dataset
    spec_path = f"morphoeval/math_kg_loops/{sim}.yaml"
    spec_b = c.blob(spec_path)
    spec = yaml.safe_load(spec_b)
    c.check("spec.sim_id", spec.get("sim_id") == sim, f"yaml sim_id {spec.get('sim_id')!r}")
    eqs = spec.get("equations") or []
    c.check("spec.has_equations", bool(eqs), f"{len(eqs)} equations in {spec_path}")
    models = [t for t in tree if t.startswith("models/") and t.endswith(f"-{sim}.py")]
    c.check("script.unique", len(models) == 1, f"models/*-{sim}.py: {models}")
    script_path = models[0]
    script_b = c.blob(script_path)
    ddir = item["dataset_dir"]
    cands = [t for t in tree if t.startswith(ddir + "/") and t.endswith("_reference.json")]
    primary_name = f"{ddir}/{ddir.rsplit('/', 1)[-1]}_reference.json"
    ref_paths = [primary_name] if primary_name in cands else cands   # several reference files: the one named for the dataset dir is primary
    extra_refs = [x for x in cands if x not in ref_paths]
    c.check("reference.unique", len(ref_paths) == 1, f"{ddir}/*_reference.json: {cands}; primary {ref_paths}")
    ref_b = c.blob(ref_paths[0])
    ref = json.loads(ref_b)
    meta = ref.get("metadata") if isinstance(ref.get("metadata"), dict) else {}
    sources = meta.get("sources") or []
    doi_in_reference = item["doi"].lower() in ref_b.decode("utf-8", "replace").lower()
    c.check("reference.doi_in_text", doi_in_reference, f"audit DOI {item['doi']} {'appears' if doi_in_reference else 'does NOT appear'} in {ref_paths[0]}", refuse=False)
    primary = next((s for s in sources if s.get("doi") == item["doi"]), None)
    if primary:
        citation, citation_from = f"{primary['citation']} (doi:{primary['doi']})", "reference dataset metadata.sources"
    else:
        citation, citation_from = f"{(spec.get('model_spec') or {}).get('model') or spec.get('math_family')} (audit DOI doi:{item['doi']})", "math_kg spec model_spec.model (the reference dataset has no matching metadata.sources entry)"
    c.check("citation.source", True, f"citation text from {citation_from}", refuse=False)
    # every sha the reference dataset states about its siblings is recomputed
    arts: list[dict] = []
    for name, sp in (meta.get("specimens") or {}).items():
        stated, f = sp.get("sha256"), sp.get("file")
        if not (stated and f):
            continue
        data = c.same_hash(f"specimen.{name}", f, stated)
        lic = sp.get("license")
        if not lic and not f.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff")):
            lic = UPSTREAM_LICENSE   # a text/json sibling file is upstream's own; an image with no stated licence stays licence-less
        arts.append(_artifact(c, "input", f, data, f"specimen/reference ({name}); stated licence: {lic or 'none stated'}; source: {sp.get('source_url') or 'n/a'}",
                              license_=(lic or None)))
    for x in extra_refs:
        arts.append(_artifact(c, "input", x, c.blob(x), "additional reference file in the same dataset directory that also names the DOI"))
    # Lean
    lean_files = sorted({e.get("lean_locus", "").split("#")[0] for e in eqs if e.get("lean_locus")})
    c.check("lean.one_file", len(lean_files) == 1, f"lean files named by the spec: {lean_files}")
    lean_b = c.blob(lean_files[0])
    lean_text = lean_b.decode("utf-8")
    flags = [_lean_flags(lean_text, e.get("lean_locus", ""), e) for e in eqs]
    tmpl = [i for i, f in enumerate(flags) if f["upstream_template_marker"]]
    c.check("lean.no_template", not tmpl, f"equations carrying upstream's template markers: {tmpl}")
    # assessment: latest version, both copies
    vers = audit_versions(tree, sim)
    c.check("audit.has_signed_copy", bool(vers) and "signed" in vers[-1], f"versions {[v['version'] for v in vers]}")
    latest = vers[-1]
    signed_b, unsigned_b = c.blob(latest["signed"]), (c.blob(latest["unsigned"]) if "unsigned" in latest else None)
    a = parse_assessment(signed_b.decode("utf-8"))
    c.check("assessment.parsed", all(a[k] for k in ("np_uri", "score", "verdict", "date", "description", "assessor")),
            f"np {a['np_uri']}, score {a['score']}, verdict {a['verdict']}, date {a['date']}")
    c.check("assessment.sig_block_in_signed_copy", a["signature_block_present"], "signed copy contains npx:hasSignature (presence only; not verified)")
    c.check("assessment.sig_block_not_in_unsigned", unsigned_b is None or b"hasSignature" not in unsigned_b, "unsigned copy carries no signature block")
    c.check("assessment.remediation_items", True, f"{len(a['evidence_against'])} remediation items (pk:evidenceAgainst) in the latest assessment; no Problem is written when there are none")
    history = []
    for v in vers:
        sc = None
        if "signed" in v:
            m = re.search(r'pk:hasScore "([\d.]+)"', c.blob(v["signed"]).decode("utf-8"))
            sc = m.group(1) if m else None
        history.append({"version": v["version"], "audit_dir": v["dir"], "score_0_1": sc})
    # the judged output: its hash is stated in the assessment text; recompute it when the file is in the tree
    oj = a["output_judged"]
    judged_note = "no judged-output hash found in the assessment text"
    if oj:
        if oj["path"] in tree:
            got = sha_bytes(c.blob(oj["path"]))
            same = got == oj["artifact_sha256"]
            c.check("assessment.output_judged_hash", same, f"{oj['path']}: assessment states {oj['artifact_sha256'][:16]}..., blob hashes to {got[:16]}...", refuse=False)
            judged_note = ("the file at the pin matches the hash stated in the assessment" if same else
                           "the file at the pin DOES NOT match the hash stated in the assessment (the assessed output was regenerated or replaced after the audit)")
            arts.append(_artifact(c, "output", oj["path"], c.blob(oj["path"]), f"rendered comparison output the assessor judged; {judged_note}"))
        else:
            judged_note = (f"{oj['path']} named by the assessment is not in the pinned tree (no commit in upstream history adds it); "
                           "the digest below is the one the assessment states and was NOT recomputed")
            c.check("assessment.output_judged_in_tree", False, judged_note, refuse=False)
            mb = re.search(r"image/png, (\d+) B", a["description"])
            arts.append({"title": f"output: {oj['path']} [stated by the signed assessment; bytes not in git:{REPO_LABEL}@{commit[:12]}; digest NOT recomputed]"[:3000],
                         "uri": "urn:sha256:" + oj["artifact_sha256"], "sha256": oj["artifact_sha256"], "byte_size": int(mb.group(1)) if mb else 0,
                         "media_type": "image/png", "role": "output", "availability": "unavailable", "license": None})
    base = ddir.rsplit("/", 1)[-1]
    media = sorted(x for x in tree if x.startswith(f"docs/media/{base}_"))   # names only: no blob was fetched, no hash, no licence check
    arts[0:0] = [_artifact(c, "code", script_path, script_b, "the model script (NOT executed by Frontier)"),
                 _artifact(c, "input", spec_path, spec_b, "math_kg spec: equations, parameters, citations, Lean loci"),
                 _artifact(c, "input", ref_paths[0], ref_b, "reference dataset: governing equations and reference values as extracted upstream"),
                 _artifact(c, "code", lean_files[0], lean_b, "Lean source (text only; NOT compiled by Frontier; not a proof claim)"),
                 _artifact(c, "log", latest["signed"], signed_b, f"signed MorphoEval overall assessment nanopub, v{latest['version']} (signature block present, NOT verified)")]
    if unsigned_b is not None:
        arts.append(_artifact(c, "log", latest["unsigned"], unsigned_b, f"unsigned copy of the same assessment, v{latest['version']}"))
    seen, uniq = set(), []
    for x in arts:
        if (x["sha256"], x["role"]) not in seen:
            seen.add((x["sha256"], x["role"]))
            uniq.append(x)
    arts = uniq

    # ----- records
    spec_src = _source(c, spec_path, spec_b, "Claim text is the math_kg spec's own equations, as extracted by upstream.")
    spec_src["license"] = UPSTREAM_LICENSE
    params = (spec.get("model_spec") or {}).get("parameters") or {}
    eq_lines = []
    for i, e in enumerate(eqs):
        eq_lines.append(f"E{i + 1}. {e.get('law_name')} | cite: {e.get('source_citation')} | code: {e.get('code_locus')} | lean: {e.get('lean_locus')}"[:900])
    cite = citation
    bnd = a["claim_boundary"]
    src_uri = f"urn:frontier:adapter:morpholib:{sim}"
    claim_id = f"morpholib-{sim}-claim"
    claim_ref = c.add(c.draft("Claim", claim_id, {
        "title": f"{sim}: governing equations that MorphoLib attributes to {citation.split('(')[0].strip()[:200]} (as extracted upstream)"[:2900],
        "statement": (f"Upstream's math_kg spec for `{sim}` registers {len(eqs)} governing equations for this model ({spec.get('math_family')}), attributed to {cite}. "
                      "This Claim is about what the source is reported to contain and how upstream transcribed it; Frontier has not checked it against the paper."),
        "context": ("Equations (upstream's own labels and loci):\n" + "\n".join(eq_lines)
                    + (f"\n\nWhat the assessor says the source reports: {bnd['reported_in_source']}" if bnd.get("reported_in_source") else "")
                    + (f"\n\nModel parameters declared by the script (script defaults, not measurements): {canon(params)}" if params else ""))[:11900],
        "assumptions": [x for x in [bnd.get("reconstructed_in_script") and "Reconstructed in the script (assessor's words): " + bnd["reconstructed_in_script"]] if x],
        "limitations": [IMPORT_NOTE] + ([] if doi_in_reference and primary else [f"Citation provenance: text taken from {citation_from}; the audit's DOI {item['doi']} "
                        + ("appears" if doi_in_reference else "does NOT appear") + f" in the reference dataset text, and the script's file name ({script_path.split('/')[-1]}) is upstream's own label."])
                        + _chunks(bnd.get("transfer_boundary", "")) + _chunks(bnd.get("does_not_claim", "")),
        "source": spec_src, "source_record_version": None,
        "prior_review": {"status": "none: not reviewed by anyone"}, "origin": "source_statement"}, src_uri))
    assess_src = _source(c, latest["signed"], signed_b, f"Assessment text is the signed nanopub's dcterms:description (np {a['np_uri']}).")
    assess_src["license"] = "CC BY 4.0 (stated in the nanopub's dcterms:license)"
    dims = a["dimension_text"] or "not found in the assessment text"
    ev_id = f"morpholib-{sim}-evidence-morphoeval"
    c.add(c.draft("Evidence", ev_id, {
        "target": claim_ref, "evidence_kind": "source_assessment", "source": assess_src,
        "created_time": {"value": a["created"], "basis": "declared"}, "retrieved_time": {"value": created_at, "basis": "declared"},
        "method": (f"Upstream MorphoEval rubric 0.1.0 assessment, pass {latest['version']}, by `{a['assessor']}` for the script's author: the assessor read the script, "
                   f"the reference dataset and a rendered comparison and scored how closely the script reproduces the source. Overall {a['score']} (0-1), verdict "
                   f"`{a['verdict']}`. Dimensions: {dims}."),
        "context": ("Applicability: only to this script at upstream's checkpoint; scores describe matching a source, NOT biological validity or correctness of the paper. "
                    + IMPORT_NOTE),
        "assumptions": ["The assessor's reading of the paper is taken as stated; it was not re-derived."],
        "provenance": {"system": "morpholib/morphoeval", "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION}, "source_commit": commit,
                       "nanopub": {"uri": a["np_uri"], "signature_block_present": True, "signed_by": a["signed_by"], "signature_verified": "unknown (not checked by this adapter)",
                                   "published_to_registry": "unknown (not checked by this adapter)", "copy_without_signature_also_in_repo": unsigned_b is not None},
                       "score_history_0_1": history, "judged_output": oj, "judged_output_note": judged_note,
                       "lean": {"equations_with_lean_text": sum(1 for e in eqs if e.get("lean_code")), "compiled_by_frontier": 0, "l2_claimed": 0,
                                "mechanical_flags": flags},
                       "checks_performed_by_adapter": [k["id"] for k in c.checks if k["ok"]],
                       "execution": "none: upstream code was not executed and no signature or proof was checked"},
        "source_dependence": {"declared": True, "group": f"assessor `{a['assessor']}` worked for the script's author; the script, spec and assessment share one author",
                              "independent_of_claim": False},
        "uncertainty": "Not quantified. One assessor, one pass per version, a rubric defined by the same project.",
        "limitations": [IMPORT_NOTE, "A fidelity score says the script matches its source as the assessor judged it, not that the source is right."]
                       + ([f"Judged output: {judged_note}."] if oj else [])
                       + _chunks(bnd.get("does_not_claim", ""))[:2],
        "local_id": None, "provider_assessment": {"assessor": a["assessor"], "rubric": a["assessment_type"], "overall_0_1": float(a["score"]), "verdict": a["verdict"],
                                                  "independent": False, "scope": "fidelity to source, not biological validity"},
        "relation": "context_only", "produced_by": None, "artifacts": arts[:30]}, src_uri))
    gaps = a["evidence_against"]
    prob_id = f"morpholib-{sim}-problem-remediation" if gaps else None
    prob_src = _source(c, latest["signed"], signed_b, "Problem text is the assessor's pk:evidenceAgainst list, quoted in full.")
    prob_src["license"] = "CC BY 4.0 (stated in the nanopub's dcterms:license)"
    if gaps:
        c.add(c.draft("Problem", prob_id, {
            "title": f"Do the assessor's {len(gaps)} remediation items for the {sim} reproduction remain open at the pinned upstream commit?",
            "known_state": f"At the audit (pass {latest['version']}, {a['date']}) the assessor listed these remediation items, quoted:\n- " + "\n- ".join(gaps),
            "question": (f"Which of these {len(gaps)} items still apply to `{script_path}` at upstream commit {commit[:12]}, and does closing them change how closely the script "
                         "reproduces the source? Producer's own list; not re-assessed here."),
            "problem_kind": "project_gap", "novelty_status": "Not searched. The items are upstream's own self-assessed gaps, not a field-level open problem.",
            "data_access": f"All inputs are public upstream files at git:{REPO_LABEL}@{commit[:12]}; licence " + UPSTREAM_LICENSE,
            "completeness": "recorded", "acceptance_criteria": [], "falsifiers": [], "next_action": None,
            "required_capabilities": ["python3 with numpy/scipy/matplotlib (versions per upstream's own environment note)"], "cost_stop_bounds": None,
            "downstream_uses": ["Decides whether this reproduction can be used as a faithful readable model of the source."],
            "dependencies": [claim_ref], "source": prob_src,
            "original": {"producer_field": "pk:evidenceAgainst", "adapter": ADAPTER_ID, "np_uri": a["np_uri"]},
            "approach": "theory_fit", "scales": SCALES[sim],
            "context_tags": ["morpholib", "tier-a", "scale-assignment:adapter-curated"]}, src_uri))

    eq_rows = []
    for i, (e, f) in enumerate(zip(eqs, flags)):
        eq_rows.append({"model": sim, "index": i + 1, "law_name": e.get("law_name"), "formula": e.get("formula"), "variables": e.get("variables"),
                        "role": e.get("role"), "source_citation": e.get("source_citation"), "code_locus": e.get("code_locus"),
                        "lean_decl": e.get("lean_decl"), "lean_theorem": e.get("lean_theorem"), "lean_locus": e.get("lean_locus"),
                        "lean_code": e.get("lean_code"), "lean_flags": f, "spec_sha256": sha_bytes(spec_b), "locator": f"git:{REPO_LABEL}@{commit}:{spec_path}",
                        "claim_id": claim_id, "kind": "mathematical_representation", "proof_status": "lean text present, not compiled by Frontier, anti-triviality gate not run"})
    index_row = {"model": sim, "slot": item["slot"], "organism_stated_by_audit": item["organism"], "doi": item["doi"], "citation": citation, "citation_from": citation_from, "doi_in_reference_dataset_text": doi_in_reference,
                 "math_family": spec.get("math_family"), "scales_adapter_curated": SCALES[sim], "script": script_path, "script_sha256": sha_bytes(script_b),
                 "spec": spec_path, "spec_sha256": sha_bytes(spec_b), "reference": ref_paths[0], "reference_sha256": sha_bytes(ref_b),
                 "lean_file": lean_files[0], "lean_sha256": sha_bytes(lean_b), "equations": len(eqs), "audit_versions": history,
                 "latest_assessment": {"np_uri": a["np_uri"], "score_0_1": float(a["score"]), "verdict": a["verdict"], "date": a["date"],
                                       "signature_block_present": True, "signature_verified": "unknown", "published": "unknown",
                                       "assessor": a["assessor"], "independent": False},
                 "remediation_items": len(gaps), "media_candidates_names_only": media, "judged_output": oj, "judged_output_note": judged_note,
                 "record_ids": {"claim": claim_id, "evidence": ev_id, "problem": prob_id}}
    return c, index_row, eq_rows


# --------------------------------------------------------------------------------------------------------------------------
# broader index and exclusions (metadata only; no claim is made about any of these models)
# --------------------------------------------------------------------------------------------------------------------------
def filename_index(tree: list[str], audit: dict) -> list[dict]:
    """Every `models/*.py`, with year/author/slug split FROM THE FILENAME (a parse, not a validated mapping) and the audit tier where the audit itemises it."""
    tier_a = {x["sim_id"] for x in audit["counted"]}
    named_b = {x.get("sim_id") for x in audit.get("promotable_first_100", [])}
    rows = []
    for t in tree:
        if not (t.startswith("models/") and t.endswith(".py") and t.count("/") == 1):
            continue
        m = re.fullmatch(r"models/((\d{4})-([a-z0-9]+(?:-[a-z0-9]+)*))\.py", t)
        stem = t[len("models/"):-3]
        sim = next((s for s in tier_a if stem.endswith("-" + s)), None)
        if sim:
            tier = "A"
        elif any(s and stem.endswith("-" + s) for s in named_b):
            tier = "B (itemised in promotable_first_100)"
        else:
            tier = "not itemised by the audit file"
        rows.append({"path": t, "filename_parse": "ok" if m else "unparsed (name does not match year-slug)", "year_from_filename": int(m.group(2)) if m else None,
                     "slug_from_filename": m.group(3) if m else None, "audit_tier": tier, "imported": sim is not None})
    return rows


def exclusions(repo: str, commit: str, audit: dict) -> dict:
    lean_audit = json.loads(git_blob_text(repo, commit, "morphoeval/runs/lean_proof_audit.json"))
    tc = json.loads(git_blob_text(repo, commit, "morphoeval/runs/tier_c_deletion_manifest.json"))
    return {
        "source": f"git:{REPO_LABEL}@{commit}", "read_level": "full-text of the JSON files named; counts are upstream's own statements, not re-run",
        "audit_tier_counts": audit["tier_counts"], "audit_rule": audit["rule"],
        "imported": f"{len(audit['counted'])} Tier A loops (audit `counted`)",
        "not_imported": ["Tier B (paper named only, no extracted equations/scouted literature): " + str(audit["tier_counts"].get("B_paper_named_only")),
                         "Tier C (scaffold only): " + str(audit["tier_counts"].get("C_scaffold_only")),
                         "every loop deleted upstream as Tier C: " + str(tc["loops"]) + " loops, " + str(tc["files"]) + " files (manifest `applied`: " + str(tc["applied"]) + ")"],
        "lean_template_gate": {"template_trivial_files": lean_audit["lean_classification"]["template_trivial"],
                               "substantive_files": lean_audit["lean_classification"]["substantive"],
                               "kg_template_equations_blocked_by_gate": lean_audit["kg_template_equations_blocked_by_gate"],
                               "problem_as_upstream_states_it": lean_audit["problem"]},
        "never_resurrected": ["synthetic 'empirical' curves and specimen plates", "slot-index scores", "template Lean theorems counted as proof"],
        "frontier_policy": "No imported record cites a Lean theorem as proof, and none counts a template equation.",
    }


def git_blob_text(repo: str, commit: str, path: str) -> str:
    from .artifacts import git_blob
    return git_blob(repo, commit, path).decode("utf-8")


# --------------------------------------------------------------------------------------------------------------------------
# bundles, reports, freeze
# --------------------------------------------------------------------------------------------------------------------------
def link_checks(records: list[dict]) -> list[dict]:
    from .engineering_manifest import _refs_in
    by = {(r["namespace"], r["kind"], r["id"], r["version"]): r for r in records}
    out = []
    for r in records:
        for field, ref in _refs_in(r):
            out.append({"id": f"{r['id']}.{field}", "ok": (ref["namespace"], ref["kind"], ref["id"], ref["version"]) in by, "detail": f"{field} -> {ref['kind']}/{ref['id']}@{ref['version'][:12]}"})
        for a in r["payload"].get("artifacts", []):
            ok = a["availability"] in ("referenced", "unavailable") and a["uri"] == "urn:sha256:" + a["sha256"]
            out.append({"id": f"{r['id']}.artifact.{a['sha256'][:10]}", "ok": ok, "detail": f"{a['role']} availability={a['availability']} licence={a.get('license') or 'NONE STATED'}"})
    return out


def build_bundles(chains: list[Chain], *, exporting_node: str | None = None) -> list[dict]:
    """Frozen `frontier-bundle-0.1` bundles. A model's three records never split across bundles; a bundle stays under the byte budget."""
    from frontier.models import MAX_BUNDLE_RECORDS, POLICY, Record, digest
    for ch in chains:
        for r in ch.records:
            Record.model_validate(r)
    ids = [(r["namespace"], r["kind"], r["id"]) for ch in chains for r in ch.records]
    if len(set(ids)) != len(ids):
        raise Refused("duplicate record ids")
    bad = [x for x in link_checks([r for ch in chains for r in ch.records]) if not x["ok"]]
    if bad:
        raise Refused(f"link checks failed: {bad[:3]}")
    groups, cur, size = [], [], 0
    for ch in chains:
        n = len(canon(ch.records).encode())
        if cur and (size + n > MAX_BUNDLE_BYTES or sum(len(g.records) for g in cur) + len(ch.records) > MAX_BUNDLE_RECORDS):
            groups.append(cur)
            cur, size = [], 0
        cur.append(ch)
        size += n
    if cur:
        groups.append(cur)
    bundles = []
    for g in groups:
        records = [r for ch in g for r in ch.records]
        ns = sorted({r["namespace"] for r in records})
        body = {"schema_version": "frontier-bundle-0.1", "exporting_node": exporting_node or ns[0], "records": records, "review_claims": [],
                "policy_version": POLICY, "trust": "Digest proves integrity only; reviews require receiving-node policy."}
        b = {**body, "bundle_sha256": digest(body)}
        if len(canon(b).encode()) > 2_000_000:
            raise Refused("a single model's records exceed the store's bundle byte limit")
        bundles.append(b)
    return bundles


def build_all(repo: str, source_commit: str, *, models: list[str] | None = None, namespace: str = "node-a", issuer: str = "importer",
              created_at: str | None = None) -> dict:
    commit = resolve_commit(repo, source_commit)
    created_at = created_at or _commit_utc(repo, commit)
    tree = list_tree(repo, commit)
    audit = json.loads(git_blob_text(repo, commit, AUDIT_PATH))
    items = [x for x in audit["counted"] if models is None or x["sim_id"] in models]
    if models is not None and len(items) != len(set(models)):
        raise Refused(f"requested models not in the audit's Tier A: {sorted(set(models) - {x['sim_id'] for x in items})}")
    missing = [x["sim_id"] for x in items if x["sim_id"] not in SCALES]
    if missing:
        raise Refused(f"no adapter-curated scale for {missing}")
    chains, index, eq_rows = [], [], []
    for it in items:
        ch, row, eqs = model_chain(repo, commit, tree, it, namespace=namespace, issuer=issuer, created_at=created_at)
        chains.append(ch)
        index.append(row)
        eq_rows += eqs
    return {"commit": commit, "created_at": created_at, "audit": audit, "chains": chains, "index": index, "equations": eq_rows,
            "bundles": build_bundles(chains), "filename_index": filename_index(tree, audit), "exclusions": exclusions(repo, commit, audit)}


def report(out: dict) -> dict:
    chains, index, eqs = out["chains"], out["index"], out["equations"]
    records = [r for ch in chains for r in ch.records]
    arts = [a for r in records for a in r["payload"].get("artifacts", [])]
    uniq_arts = {a["sha256"] for a in arts}
    npub = [x["latest_assessment"] for x in index]
    fi = out["filename_index"]
    return {
        "status": STATUS, "adapter": {"id": ADAPTER_ID, "version": ADAPTER_VERSION},
        "source": {"upstream": UPSTREAM, "commit": out["commit"], "licence": UPSTREAM_LICENSE, "read": "immutable git blobs only; working tree not read; nothing executed"},
        "counts": {
            "unique_models_imported": len({x["model"] for x in index}),
            "organisms_explicit_in_audit": sorted({x["organism_stated_by_audit"] for x in index}),
            "organisms_explicit_in_audit_note": "strings the upstream audit file states per loop; not a validated taxon mapping",
            "claims": sum(1 for r in records if r["kind"] == "Claim"), "claim_versions": len({(r["id"], r["version"]) for r in records if r["kind"] == "Claim"}),
            "evidence": sum(1 for r in records if r["kind"] == "Evidence"), "problems": sum(1 for r in records if r["kind"] == "Problem"),
            "actions": 0, "records": len(records),
            "equations_as_mathematical_representations": len(eqs),
            "equations_with_lean_text": sum(1 for e in eqs if e["lean_code"]),
            "equations_compiled_by_frontier": 0, "equations_l2_or_proof_claimed": 0,
            "equations_with_upstream_template_marker": sum(1 for e in eqs if e["lean_flags"]["upstream_template_marker"]),
            "equations_with_only_trivial_tactics_in_range": sum(1 for e in eqs if e["lean_flags"]["only_trivial_tactics"]),
            "equations_with_sorry": sum(1 for e in eqs if e["lean_flags"]["has_sorry"]),
            "artifact_references": len(arts), "artifact_references_referenced": sum(1 for a in arts if a["availability"] == "referenced"),
            "artifact_references_unavailable": sum(1 for a in arts if a["availability"] == "unavailable"),
            "unique_artifact_digests": len(uniq_arts), "artifact_bytes_available": 0,
            "artifact_bytes_hashed_by_adapter": sum({a["sha256"]: a["byte_size"] for a in arts if a["availability"] == "referenced"}.values()),
            "nanopub_assessments": len(npub), "nanopub_signature_block_present": sum(1 for n in npub if n["signature_block_present"]),
            "nanopub_signature_verified": 0, "nanopub_published_to_registry_checked": 0,
            "bundles": len(out["bundles"]), "filename_index_models": len(fi), "filename_index_tier_a": sum(1 for r in fi if r["imported"]),
        },
        "execution_statement": "No upstream code, Lean file or signature check was run by Frontier or this adapter. Every record states what upstream's files say.",
        "chains": [{"name": ch.name, "records": [{"kind": r["kind"], "id": r["id"], "version": r["version"]} for r in ch.records], "checks": ch.checks} for ch in chains],
        "link_checks": link_checks(records),
        "bundles": [{"bundle_sha256": b["bundle_sha256"], "records": len(b["records"]), "bytes": len(canon(b).encode())} for b in out["bundles"]],
        "known_exclusions": out["exclusions"],
        "fidelity_statement": "Every MorphoEval score here describes how closely a script matches its cited source, as judged by a language model for the script's author. It says nothing about whether the source is right.",
    }


def write_frozen(out_dir: str, out: dict) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    rep = report(out)
    files = {}
    for i, b in enumerate(out["bundles"], 1):
        files[f"bundle-{i:03d}.frontier-bundle-0.1.json"] = json.dumps(b, indent=1, sort_keys=True) + "\n"
    files["chain.json"] = json.dumps(rep, indent=1, sort_keys=True) + "\n"
    files["models_index.json"] = json.dumps({"source": rep["source"], "status": STATUS, "models": out["index"]}, indent=1, sort_keys=True) + "\n"
    files["equations.jsonl"] = "".join(json.dumps(e, sort_keys=True, ensure_ascii=False) + "\n" for e in out["equations"])
    files["filename_index.jsonl"] = "".join(json.dumps(e, sort_keys=True) + "\n" for e in out["filename_index"])
    files["exclusions.json"] = json.dumps(out["exclusions"], indent=1, sort_keys=True) + "\n"
    bad = [find_abs_paths(json.loads(t)) for n, t in files.items() if n.endswith(".json")]
    if any(bad):
        raise Refused(f"absolute local paths in output: {bad}")
    for n, t in files.items():
        with open(os.path.join(out_dir, n), "w") as fh:
            fh.write(t)
    manifest = {"status": STATUS, "source": rep["source"], "file_sha256": {n: sha_bytes(t.encode()) for n, t in files.items()},
                "bundle_sha256": [b["bundle_sha256"] for b in out["bundles"]], "publication": "none. Not written to any store; corpus owns imports.",
                "records": [{"kind": r["kind"], "id": r["id"], "namespace": r["namespace"], "version": r["version"]} for ch in out["chains"] for r in ch.records]}
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        fh.write(json.dumps(manifest, indent=1, sort_keys=True) + "\n")
    return {"report": rep, "manifest": manifest}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(prog="python -m frontier_adapters.morpholib",
                                 description="Freeze MorphoLib Tier-A model bundles from immutable git blobs. Writes files only; never touches a store, never runs upstream code.")
    ap.add_argument("--repo", required=True, help="a clone of fractastical/morpholib (blobless is fine; blobs are fetched on demand)")
    ap.add_argument("--source-commit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--models", nargs="*", default=None, help="restrict to these sim_ids (must be Tier A)")
    ap.add_argument("--namespace", default="node-a")
    ap.add_argument("--issuer", default="importer")
    ap.add_argument("--created-at", default=None)
    a = ap.parse_args(argv)
    out = build_all(a.repo, a.source_commit, models=a.models, namespace=a.namespace, issuer=a.issuer, created_at=a.created_at)
    w = write_frozen(a.out, out)
    print(json.dumps({"counts": w["report"]["counts"], "bundles": w["report"]["bundles"], "out": a.out}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
