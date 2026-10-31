# Claim tests against data

Each directory `claim-tests/<project>/<claim-id>/` holds one attempt to resolve a claim
(confirm or refute it) against public data that already exists, following the
operationalization proposed in that claim's dataset-resolvability assessments. These are the
empirical tests the README's goal calls for; they are not nanopubs yet.

Projects: `darwin-origin`, `thompson-growth-form`, `wolfram-nks`.

## Rules

1. **Pre-register before you look.** Write `result.json` with `hypothesis`, `pass_criterion`,
   `fail_criterion` and `planned_datasets` *before* downloading or inspecting any data, and
   commit that file first. Then run the analysis and fill in the rest.
2. **Only real data.** Use datasets that exist and are public. Record for every file used the
   download URL, retrieval time, byte size and SHA-256. Never invent a dataset, accession, DOI,
   URL or number. If the data cannot be obtained, the verdict is `inconclusive` with
   `reason: "data-unavailable"`.
3. **Keep the repo small.** Do not commit downloaded data over 1 MB. Commit the script that
   fetches it and the checksum of what was fetched. Small derived tables (< 200 KB) may be
   committed under `derived/`.
4. **Runnable.** `analysis.py` (or `analysis.mjs`) must re-run from a clean checkout with only
   standard tooling (`python3` with `requests`, `pandas`, `numpy`, `scipy`; or Node 20+) and
   reproduce `measured` in `result.json`.
5. **Do not touch** the claim files, assessments or nanopubs, and never sign or publish
   anything. Tests become evidence nanopubs later, through the normal test-then-production path.
6. **Scope as stated.** Test the claim as the author stated it and within its stated scope
   (`delphi:context`). If a test is only possible after modern reinterpretation, say so in
   `interpretation`.

## `result.json`

```json
{
  "claim_id": "darwin1859-ch09-03",
  "claim_iri": "https://w3id.org/delphi/resource/claim/darwin1859-ch09-03",
  "project": "darwin-origin",
  "status": "complete",
  "hypothesis": "One sentence: what must be true of the data if the claim holds.",
  "pass_criterion": "Pre-registered: the measured value and threshold that confirms the claim.",
  "fail_criterion": "Pre-registered: what measured result refutes it.",
  "planned_datasets": ["<dataset id>"],
  "interpretation": "How the author's terms were mapped to measurable quantities; note any modern reinterpretation.",
  "datasets": [
    {
      "id": "icc-chronostratigraphic-chart-2023-09",
      "name": "International Chronostratigraphic Chart v2023/09",
      "landing_url": "https://stratigraphy.org/chart",
      "doi": null,
      "version": "2023/09",
      "license": "CC BY 4.0",
      "files": [
        {
          "download_url": "https://...",
          "retrieved_at": "2026-10-31T06:00:00Z",
          "byte_size": 12345,
          "sha256": "..."
        }
      ],
      "role": "ages of the Cretaceous–Paleogene boundary"
    }
  ],
  "method": "Two to five sentences: the analysis actually run.",
  "measured": { "value": 66.0, "unit": "Myr", "n": 1, "uncertainty": "±0.1", "extra": {} },
  "verdict": "refutes",
  "confidence": 0.95,
  "caveats": ["..."],
  "agent": { "kind": "cloud-agent", "model": "<model id>", "run": "<branch or agent id>", "date": "2026-10-31" }
}
```

- `status`: `preregistered` | `complete` | `abandoned`.
- `verdict`: `supports` | `refutes` | `inconclusive` | `mixed`. `inconclusive` carries `reason`:
  `data-unavailable`, `underpowered`, `not-operationalizable`, `other`.
- `confidence`: your confidence in the verdict, in [0, 1].
- Every number in `measured` must come from `analysis.*`.
