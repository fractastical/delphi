# claim-tests/nanopubs — evidence-item drafts for the pre-registered claim tests

**Everything in `unsigned/` is an unsigned draft.** Nothing here is signed or published. Target is the nanopub test registry first; production needs the ORCID key owner's explicit approval, every time.

## What is here

| path | content |
|---|---|
| `build.py` | Generator. Reads every `claim-tests/<project>/<id>/result.json` named in `RECORDS`, the git history of that file (pre-registration commit, amendments, results commit) and writes one TriG per record. Refuses to build if a number in its hand-written text is not in the result file, or if the first data retrieval is not after the pre-registration commit. |
| `unsigned/*.trig` | 15 records, one `delphi:EvidenceItem` each, linked from the existing claim IRI with `delphi:hasEvidence`. |
| `manifest.json` | Per record: claim IRI, evidence IRI, status, commits, retrieval times, `np check` result; `signed: false`, `published: false`. |
| `check.log` | Verbose output of `java -jar nanopub.jar check -v` per file (nanopub-java 1.95.0). |
| `lint.log` | Output of the Delphi pipeline lint (project-delphi-ontology `pipeline/lint.ts` at 6ba5f9a). |
| `DECISIONS.md` | Every choice not settled by the `delphi` skill, with date and reasoning. |

## Records

| record | status | claim |
|---|---|---|
| maynardsmith-hitchhiking | supported | diversity rises with recombination rate, human chr22 |
| fisher-infinitesimal | supported | Galton families: constant residual variance, sibling r ≥ parent-offspring r |
| kimura-fixation-probability | supported | Buri 1956: 28 fixed vs 30 lost of 58 |
| darwin1859-ch11-13 | supported | long, two-hemisphere glacial states (LR04 + EPICA Dome C) |
| thompson1917-ch03-07 | supported | weight ~ height^2.7–2.9 in NHANES children |
| thompson1917-ch16-13 | supported | pinnipeds and cetaceans lack the withers spine peak |
| kimura-heterozygosity | refuted | diversity vs census size slope 0.107, not ~1 (Lewontin's paradox) |
| thompson1917-ch04-13 | refuted | 34% of plant species have n > 16 |
| thompson1917-ch10-02 | refuted | Turritella whorls exceed the conical-geodesic bound |
| thompson1917-ch11-06 | refuted | ammonoid conch shape changes through growth |
| darwin1859-ch09-03--numeric | refuted | end of the Chalk is 66 Ma, not ≥ 225 Ma |
| darwin1859-ch09-03--qualitative | inconclusive | "geological time is immense" was not operationalized; not tested |
| fisher-sex-ratio | partially supported | all country-years within 10% of parity; median 105.2 outside the 5% band |
| hamilton-senescence | partially supported | adult mortality rises in 20 of 35 species |
| thompson1917-ch03-10 | partially supported | asymptotic growth favoured in 7 of 11 species, threshold 2/3 |

Not recorded (open tasks, no evidence item): `hamilton-lmc`, `maynardsmith-war-of-attrition` (Dryad blocks scripted downloads).

## Each record carries

1. the plain-language statement and the hypothesis as tested;
2. the status under the pre-registered rule;
3. the evidence: dataset(s) with identifier, licence, version, every retrieved file's download URL, byte size, SHA-256 and retrieval time; the measured value, sample and uncertainty; the result.json and analysis.py at their commits;
4. the pre-registration: the commit that added pass and fail criteria with verdict null, its time, the first retrieval time and the gap in seconds (amendment commits where they exist);
5. what the result does not establish, plus every caveat from result.json.

## Validate

```
python claim-tests/nanopubs/build.py --check C:/Temp/nanopub/nanopub.jar
cd C:/Temp/project-delphi-ontology/pipeline && npx tsx lint.ts <repo>/claim-tests/nanopubs/unsigned
```

`check` exits 0 even on an RDF parse error, so `build.py` reads the checker's text ("Valid (but not trusty)", no "RDF ERROR") and fails the build otherwise.

## Not done here

No signing, no publishing, no key files. Signing adds the key holder's ORCID and replaces the temp URIs with trusty URIs; see the nanopub skill. Corrections after publication are supersedes, withdrawals are retractions, both by the same signer.
