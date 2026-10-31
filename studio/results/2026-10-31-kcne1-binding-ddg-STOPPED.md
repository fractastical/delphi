# KCNE1 binding-ΔΔG test — STOPPED at the preregistered coverage floor

**Verdict: INCONCLUSIVE by the preregistered criterion, decided before any GPU job was submitted.**
Coverage of the assay by the preregistered structure is **20.27%** against a **75%** floor, and the
preregistered negative control **D76N is not present in the structure at all**. Both of these are
stop conditions written into `preregistrations/2026-10-31-kcne1-binding-ddg.md` (commit
`dcdc5f4d9414a17bc9802b4c75093e20cd8b3b9b`, 2026-10-31 10:48:27 −0700). Nothing in the protocol was
adjusted. No ΔΔG was computed, so there is no ρ to report.

This is the preregistration working. The floor was not a formality: §*What the floor was protecting*
below shows that running the test anyway would have produced a **false positive by construction**.

---

## 1. Coverage — the headline number

| | |
|---|---|
| Assay | ProteinGym `KCNE1_HUMAN_Muhammad_2023_expression`, **N = 2,339** missense, 127 distinct positions (1–128) |
| Structure | **PDB 9VEC**, human KCNQ1–KCNE1–CaM, cryo-EM 2.7 Å |
| KCNE1 in 9VEC | entity 2, chains **C, F, I, L** — **25 residues modelled, auth 41–65**, contiguous. SEQRES is 129 aa; **104 of 129 residues are unmodelled.** |
| Variants at resolved positions | **474 / 2,339 = 20.27%** |
| Variants **usable** (structure WT == assay WT) | **455 / 2,339 = 19.45%** |
| Preregistered floor | **75%** → **FAIL → INCONCLUSIVE** |

The 19-variant gap between "resolved" and "usable" is **position 41**: 9VEC's KCNE1 carries an
engineered **K41C** mutation (`_entity.pdbx_mutation = K41C`), so the structure's residue 41 is
cysteine where the assay's wild type is lysine. `submit_stab_ddg` requires `wild_type` to match the
PDB residue, so those 19 variants could not be submitted honestly at all.

### Mapping method, and how it was checked

9VEC's KCNE1 `auth_seq_id` **is** UniProt P15382 numbering — the mapping is the identity, not an
offset. Checked residue by residue: the 25 modelled residues read `CLEALYVLMVLGFFGFFTLGIMLSY` at
auth 41–65, and ProteinGym's `target_seq` positions 41–65 read `KLEALYVLMVLGFFGFFTLGIMLSY`. The
**single** mismatch is the engineered K41C. The 9VEC SEQRES (129 aa) and ProteinGym's `target_seq`
(129 aa) differ at exactly **two** positions: `G38S` (a known common KCNE1 polymorphism; position 38
is unmodelled, so it does not touch the usable set) and `K41C`.

Independent confirmation that the mapping is right, from the assay data itself — the two
preregistered controls behave exactly as the source paper describes:

| variant | measured surface expression | percentile | measured function |
|---|---|---|---|
| **L51H** (known trafficking-null) | **−0.056** | **0.0** (lowest in the assay) | −0.035 |
| **D76N** (known gating variant) | **+1.053** | 63.4 (above the +0.982 median) | +0.045 (low) |

L51H is the lowest-expression variant of 2,339 and D76N sits above the median with near-dead
function. That is the trafficking/gating split the paper names, recovered from the data under my
numbering. The mapping is sound; the structure is the problem.

## 2. The controls could not be run — a second, independent stop

**D76 is not modelled in 9VEC** (the KCNE1 chain stops at 65). The preregistration says: *"If these
two are not separated, stop. Nothing downstream is worth reading."* The pair cannot be separated
because one of them **does not exist in the preregistered structure**. There is no result to report
for step 2, and no amount of GPU time would produce one.

## 3. This is not a 9VEC problem — no deposited structure can support the test

I checked whether another structure would rescue it. **It is reported, not acted on**: swapping the
structure would change the preregistered protocol, which is the team lead's call, not mine.

RCSB search on UniProt **P15382** returns **exactly 5 entries** (negative control: a bogus accession
returns HTTP **204** with **0 bytes**, so the search can come back empty):

| PDB | KCNE1 modelled | positions | coverage of the 2,339 | 75% floor | has L51 | has D76 |
|---|---|---|---|---|---|---|
| **9VEC** (preregistered) | auth 41–65 | 25/127 | 474 → **20.27%** | FAIL | yes | **no** |
| 9U7F | auth 39–66 | 28/127 | 531 → 22.70% | FAIL | yes | **no** |
| 9UC8 | auth 39–68 | 30/127 | 568 → 24.28% | FAIL | yes | **no** |
| 9VEI | auth 41–81 | 41/127 | 776 → **33.18%** | FAIL | yes | **yes** |
| 2K21 | — | — | — | — | — | — |

2K21 is *"NMR structure of human KCNE1 in LMPG micelles"* — **KCNE1 alone, no KCNQ1 entity**. A
binding ΔΔG needs two partners, so it cannot serve regardless of its coverage.

**Every experimental KCNQ1–KCNE1 structure resolves only the transmembrane helix.** The best
(9VEI, 3.9 Å) reaches **33.18%** — less than half the floor. 9VEI is the only one that contains D76,
so it is the only structure on which the preregistered control pair could even be attempted.

**The conclusion is structural, not procedural: as preregistered, this test is not executable on any
currently deposited experimental structure.** A redesign must either lower the floor with eyes open,
use a predicted KCNE1 model (which reintroduces exactly the prediction-not-measurement objection
that ruled out 9A06), or accept that it is a test of the TM helix only — and §5 says what that costs.

## 4. Partner definition — computed, as asked

Asked to decide whether `partner_b` is one KCNQ1 chain or all four, from contacts rather than
assumption. Heavy-atom contacts ≤ 5.0 Å between KCNE1 chain **C** and each KCNQ1 chain:

| KCNQ1 chain | atom pairs | KCNQ1 residues involved |
|---|---|---|
| **A** | 226 | 18 |
| **D** | **0** | **0** |
| **G** | 194 | 8 |
| **J** | 210 | 13 |

**`partner_b` = `["A","G","J"]`** — three of the four subunits, not one and not all four. One KCNE1
copy sits in a groove contacting three KCNQ1 subunits and never touches the fourth. 22 of the 25
modelled KCNE1 residues contact KCNQ1 (all but 44, 52, 56), so the modelled fragment is essentially
all interface. `partner_a` = `["C"]`.

## 5. What the floor was protecting — the restricted test would have been rigged

This is the part worth keeping even though the test stopped.

I reproduced the published baselines from ProteinGym's own zero-shot score file (95 models × 2,339
variants), as a positive control on my parsing and correlation code:

| model | my ρ over all 2,339 | preregistration cites |
|---|---|---|
| ProSST-2048 | **+0.2877** | +0.288 |
| ESM2-650M | **+0.1060** | +0.106 |
| Site-Independent | **+0.1299** | +0.130 |
| ESM2-3B | **+0.0623** | +0.062 |
| best / median / worst | **+0.2877 / +0.1095 / −0.1698** | +0.288 / +0.111 / −0.170 |

Every cited number reproduces. So the pipeline is sound — which makes the next table trustworthy.

**Restricted to the 9VEC-resolved positions 41–65 (n = 474), every model gets substantially better:**

| model | ρ over all 2,339 | ρ over 41–65 | Δ |
|---|---|---|---|
| ProSST-4096 | +0.2599 | **+0.4341** | +0.1742 |
| ProSST-2048 | +0.2877 | **+0.4265**  (95% CI [+0.337, +0.511]) | +0.1388 |
| Progen3-219m | +0.1511 | +0.4141 | +0.2631 |
| ESM2-650M | +0.1060 | +0.1479 | +0.0419 |
| **best / median** | **+0.288 / +0.110** | **+0.434 / +0.214** | **+0.146 / +0.104** |

**The acceptance threshold of +0.288 was computed over all 2,339 variants. On the subset 9VEC can
actually score, the field's best is +0.434 and the median is +0.214.** A ΔΔG scored on 474 variants
and compared against +0.288 would be compared against the wrong number: anything landing between
+0.288 and +0.434 would **clear the preregistered bar while losing to ProSST on the very same
variants**, and would be written up as beating the field. **22 of the 95 published models already
exceed +0.288 on this subset** (23.2%) without computing anything, where **none of the 95** exceeds
it over the full assay.

The subset is biased, and measurably so. Resolved (41–65) vs unresolved surface-expression scores:
mean **0.859 vs 0.987**, median 0.826 vs 0.995, **Mann-Whitney two-sided p = 4.95 × 10⁻¹²**, and the
resolved region carries **3.1× the variance**. That is the expected biology — the TM helix is where
mutations actually destroy trafficking and the disordered termini are flat — and it is exactly why
the restricted problem is *easier*, not merely smaller.

**So the 75% floor was not protecting against low power. It was protecting against a baseline
swap that manufactures a win.** Had the floor not been there, this run would very likely have
reported a "positive" result.

If the test is redesigned on a restricted region, **the comparator must be recomputed on the same
restricted set** (+0.434 best / +0.214 median for expression). The restricted numbers for the
function arm, for a future double-dissociation design: ProSST-4096 +0.5166, ProSST-2048 +0.4828,
ESM2-650M **+0.5877** (CI [+0.526, +0.643]). The dissociation itself survives restriction — ESM2-650M
scores +0.148 on expression and +0.588 on function over the same 473–474 variants — so the
*mechanism* claim in §3.1 is not damaged by any of this. Only this particular way of testing it is.

## 6. GPU status — the tool was unavailable, and that is not why we stopped

The stop is on coverage, which is a fact about the structure and holds whatever the GPU does. For
completeness, and so the stop cannot be mistaken for a tooling failure dressed up as a protocol
stop, the submission path was taken as far as it goes:

- MCP endpoint `https://89.169.99.188/mcp` — `initialize` HTTP **200**, serverInfo
  `Nebius Scientific AI 0.1.0`, **69 tools**.
- `get_model_schema` for `stab-ddg` — HTTP 200, 25,829 bytes. Runtime revision
  `stab-ddg-b19a5d7-29c874d-20261024`. **`graph_deadline_s` = 1800** (a 30-minute hard deadline per
  job — the full 2,339-variant run would have needed splitting).
- Artifact upload verified **end to end**: `begin_scientific_artifact_upload` → presigned PUT
  (**HTTP 200**) → `finalize_scientific_artifact_upload` → `"state": "finalized"`, for a 665,600-byte
  workload archive. Max content 16 MiB.
- `submit_stab_ddg` returns **HTTP 503 `MODEL_MAINTENANCE`**, *"This App is temporarily paused for
  maintenance; the request was not submitted"*, `admission: "not-submitted"`. Still in maintenance on
  every attempt from **10:59 to 11:02 PDT**; a retry probe at 60 s intervals is still running.

**No job was created** — every attempt was refused at admission. No GPU was consumed, nothing was
queued behind another team, and no job belonging to anyone else was touched. The one-GPU rule was
never at issue: `capabilities.gpus_per_compute_stage` is 1 by construction.

A 9VEC PDB containing chains C (KCNE1) + A, G, J (the contacting KCNQ1 subunits), 8,322 atoms, is
built and staged, so if the App returns and the team lead decides a restricted test is worth running
under a **new** preregistration with the **+0.434** comparator, it is one submit away.

## 7. What this does and does not establish

- **Establishes**: 9VEC resolves 20.27% of the assay; no deposited KCNQ1–KCNE1 structure exceeds
  33.18%; D76N is absent from 9VEC; the published baselines reproduce exactly; the resolved subset is
  significantly biased and easier, so +0.288 is the wrong comparator for any restricted test.
- **Does not establish**: anything about whether interface binding ΔΔG predicts KCNE1 trafficking.
  That question is untouched. It was not answered and was not answerable as preregistered.
- **Unverified here**: that StaB-ddG runs at all on this input — the App was in maintenance for the
  whole window. The upload path is verified; the compute path is not.
- Nothing here is evidence about a patient, a cardiac phenotype, or any variant's clinical
  significance.

## 8. Provenance

| artifact | evidence |
|---|---|
| Preregistration | commit `dcdc5f4d9414a17bc9802b4c75093e20cd8b3b9b`, 2026-10-31 10:48:27 −0700, before any submission |
| 9VEC | `9vec.cif`, 1,719,739 B; 15,880 `atom_site` rows parsed |
| 9U7F / 9UC8 / 9VEI / 9A06 | files.rcsb.org, HTTP 200, judged by content (`data_XXXX` header), not status. Controls `0000`/`ZZZZ`: HTTP 404 with an HTML body |
| Assay data | ProteinGym v1.3 `DMS_ProteinGym_substitutions.zip`, extracted by HTTP range (91,909 B fetched of 43,021,128 B). `KCNE1_HUMAN_Muhammad_2023_expression.csv` 348,639 B, sha256 `145d094f06d1c35f3775983cec566f407dc5d3730a0fcce408d22d07d598005e`; `..._function.csv` 345,069 B, sha256 `0032d9ff5d8d19459b131f6432969ffb716c15b641dd565147aefec267d00b89`. All 2,339 and 2,315 wild-type residues match `target_seq` — 0 mismatches |
| Model scores | ProteinGym v1.3 `zero_shot_substitutions_scores.zip`, extracted by HTTP range (1,794,898 B fetched of 1,911,045,703 B); 95 models × 2,339 variants |
| Reference table | `reference_files/DMS_substitutions.csv`, 208,734 B, sha256 `a8f498011532a74aa9fe556a50555a75e928c5837d19c06a87592ae04049b308`; 217 rows |
| Structure survey | RCSB search API on P15382 → 5 entries; bogus accession → HTTP 204, 0 bytes |

Caveats carried rather than smoothed: 9VEC's KCNQ1 carries an **I145C** mutation and is the 76–620
construct (modelled 104–569, 353 of 466 residues); its KCNE1 carries **K41C** and the **G38S** allele.
Read-levels: the PDB files, both ProteinGym CSV sets and the MCP schema are `full-text` (fetched and
parsed here). The ProteinGym *published* ρ values are `full-text` as to what ProteinGym reports and
`source-only` as to whether each is right — though the four I recomputed agree to three decimals.
