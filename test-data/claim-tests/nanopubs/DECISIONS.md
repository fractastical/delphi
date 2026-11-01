# Decisions for the claim-tests nanopublication drafts

Recorded as the `delphi` skill asks: anything not settled by the skill is proposed, decided, and logged here with the date and the reasoning. All records in `unsigned/` are unsigned drafts; nothing is signed or published.

## 2026-10-31 — Evidence items, not new claims

All 16 tested claims already have claim nanopubs (darwin-origin, thompson-growth-form and math-bio-theorems `nanopubs/` folders, test and in some cases production registry). A test result is therefore recorded as one `delphi:EvidenceItem` per record, linked from the existing claim IRI with `delphi:hasEvidence`, and never as a second claim record. Evidence IRIs are minted as `delphir:evidence/claim-test-<claim-id>[--<reading>]` so that they are stable before signing (the template's artifact-code minting only works after signing).

## 2026-10-31 — Status vocabulary and the mixed verdicts

`delphi:hasVerdict` has domain `delphi:Assessment`, so it is not used on evidence items. The status is carried as a `schema:PropertyValue` with `propertyID "status"` and one of `supported`, `refuted`, `partially supported`, `inconclusive`, and repeated in the evidence item's label. No new ontology term was minted for "mixed" (AGENTS.md standing order; hub decision of the same day):

- **Mixed across readings of the claim → one record per reading.** `darwin1859-ch09-03` becomes `darwin1859-ch09-03--numeric` (refuted: 66.0 Ma against 306.7 Myr) and `darwin1859-ch09-03--qualitative` (inconclusive: "geological time is immense" had no pre-registered criterion, so it is recorded as not tested, not as supported). Both link to the same claim IRI; neither is hedged.
- **Mixed inside one reading → one record labelled `partially supported`**, with the supported and the unsupported component as separate statements (`supported_component`, `unsupported_component`). Applied to `fisher-sex-ratio` (criterion B met, criterion A missed), `hamilton-senescence` (57% rising, between the 50% and 80% lines) and `thompson1917-ch03-10` (late increments met, species fraction 0.636 under the two-thirds line). Reason: the components are two criteria of one reading of the claim and cannot be separated into readings.
- The two Dryad-blocked tests (`hamilton-lmc`, `maynardsmith-war-of-attrition`) are open tasks, not evidence records.

## 2026-10-31 — Kinds kept apart

Observation (`measured_value`, `sample`, `uncertainty`, dataset distributions with byte size, SHA-256 and retrieval time), the pre-registered decision rule (`pre_registered_rule`, marked as an assumption fixed before the data were opened, plus the pre-registration commit in the provenance graph), and interpretation (`does_not_establish`, the caveats as `rdfs:comment`) are separate statements on the evidence item. No simulation results are involved.

## 2026-10-31 — No human ORCID in the drafts

Earlier records in this repository name the repository operator's ORCID as `dct:creator` and `prov:actedOnBehalfOf`. These drafts do not: `dct:creator` and `prov:wasAttributedTo` are the software agent `delphir:agent/delphisci-claim-tests-runner`, there is no `actedOnBehalfOf`, and each pubinfo says that the key holder's ORCID is added only when that person approves and signs. Reason (hub, 2026-10-31): consistency with past records is not consent for new ones, and several of these records refute claims.

## 2026-10-31 — No assertion or pubinfo template declared

The published Project Delphi evidence item template `https://w3id.org/np/RAk4kcX4zA_touv8CeKku9tTUnbR5xiTLSLwFbrKSl3BE` (created 2026-10-01) still carries the legacy `https://w3id.org/probknow/ontology/` namespace (1 occurrence, checked 2026-10-31 on the live network); the 2.0 source in project-delphi-ontology `nanopubs/src/05` is not yet published. `nt:wasCreatedFromTemplate` asserts that the record was created from the template, which is false for hand-authored 2.0 records whose statements cannot be instantiated from it, so the triple is omitted rather than caveated (hub decision, 2026-10-31, after the organism thread's conformance check). The provenance template `https://w3id.org/np/RAaYeFYF-Cz2bM5S1wPQsnvs5X6BBxsphL03UkbVZ1lcA` carries no legacy IRI (0 occurrences) and is declared. No pubinfo template is declared because none was verified. Each record states this in its pubinfo. This is itself a methodological finding worth a record of its own.

## 2026-10-31 — Datasets described inline

The dataset convention (ONTOLOGY.md) wants one nanopub per dataset; the ontology repository says its dataset template does not exist yet. Until it does, each evidence record describes its dataset(s) inline as `dcat:Dataset` under `delphir:dataset/<id>` with identifier (DOI, else landing URL), licence, version, role, structured counts (`n_files`, `byte_size_total`, and `n_<unit>` where the record's own text states a single count), and one `dcat:Distribution` per retrieved file with download URL, byte size, SHA-256 and retrieval time. These can be split into dataset nanopubs later without changing the evidence IRIs.

## 2026-10-31 — Lint residuals accepted rather than invented

`np check -v` (nanopub-java 1.95.0): all 15 valid (not trusty); the only notes are the expected ones for unsigned temp-URI drafts. Delphi pipeline lint (project-delphi-ontology at 6ba5f9a, no `--extracted`): 25 findings left on purpose:

- 18 `DATASET-CREATOR`: result.json records no creator for any dataset; a creator will not be guessed from the dataset name.
- 6 `COUNT-UNSTRUCTURED`: the prose names two different numbers for one unit on the same node (for example 35 species analysed and 8 held out), and one is a regex artefact ("0.636 species"); a structured count is emitted only where the unit has a single number.
- 1 `DATASET-URL`: the Buri 1956 `fly` object is a member of the popgenr CRAN tarball and has no download URL of its own; it is linked to the tarball with `dct:isPartOf`.

## 2026-10-31 — Pre-registration margins stated verbatim

Each record's provenance states the pre-registration commit time, the first retrieval time and the gap in seconds. For the 8 math-bio tests the gap between commit 9b73128 and the first download is 31 s; it is reported as measured, not smoothed.
