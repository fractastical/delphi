# Pre-publication security review

Sanitised record of the secret scan and the public web/MCP review done before this repository was considered for public visibility.
**No secret value appears here or in the receipts it cites.** Findings are identified by rule, file, line and commit only.
This is not a complete penetration test and does not claim the absence of all vulnerabilities or of all credentials.

## 1. Secret scan receipts

| Item | Value |
|---|---|
| Tool | gitleaks 8.30.1 (`/data/tools/gitleaks-8.30.1/gitleaks version` printed `8.30.1`), default rules, run locally; nothing was uploaded to an external scanner |
| History scan | `security/gitleaks-history.redacted.json`, sha256 prefix `6bcbfad5b36f956d`. Its tool log (`gitleaks-history.log`) reads "367 commits scanned, leaks found: 20". Root reported 477 commits / 64 remote refs for the run it attributes this to; the log file I could read says 367, and I could not reconcile the two. Root's final rescan of the latest refs supersedes both. |
| Current-tree scan | `security/gitleaks-tree.redacted.json`, sha256 prefix `c322d524e2a5a50a`, scan of a copy of commit `b53e0cd` of `codex/frontier-demo-20261031` (log: ~95.8 MB, "leaks found: 16") |
| Redaction | Every `Secret` field in both JSON receipts is the literal `REDACTED`, and every `Match` field contains `REDACTED` (checked by script, 20 of 20 and 16 of 16). The receipts live under `/data/artifacts/delphi-evolve-rethink/security/` and are not copied into git. |

Reading limits: I read the receipts, the tool logs, and the historical file lines the findings point at. For the signed-URL items I parsed only the host, path prefix and query-parameter *names*, `X-Amz-Expires` and `X-Amz-Date`, never the credential or signature values.

## 2. Classification of the 20 history candidates

| # | Count | Rule | Location (commit, file, line) | Classification | Evidence |
|---|---|---|---|---|---|
| A | 15 | generic-api-key | `30b41e3c`, `findings/attestation-sample-15.json`, lines 28, 42, 56 ... 224 (every 14th line) | **Not a secret.** Deterministic SHA-256 sampling keys | For all 15 findings the flagged line holds a `"key": "<64 hex>"` entry, and recomputing `sha256("frontier-attestation-sample-v1\|<slug>\|<index>\|<register_sha256>")`, the rule declared in `findings/select_attestation_sample.py`, from that item's slug and index and the file's own `register_sha256` reproduces the stored key: 15 of 15 equal, 15 distinct lines. The keys are a public, reproducible function of public inputs. |
| B | 1 | generic-api-key | `609d1cf2`, `engineering/cfd3d/env/Manifest.toml`, line 17 | **Not a secret.** A Julia package UUID | The line has the shape `    oneAPI = "<uuid>"` under `[deps.AcceleratedKernels.weakdeps]`. A Julia `Manifest.toml` lists package UUIDs, which are public identifiers in the General registry. I did not look the UUID up in the registry. The file is not in commit `b53e0cd` (the `engineering/cfd3d/env/` directory is absent there), so it is present only in history. |
| C | 1 | generic-api-key | `388b19c6`, `tests/test_system_status.py`, line 160 | **Test fixture marker, not a credential.** | `monkeypatch.setenv("FRONTIER_ACCESS_TOKEN", "ENV-SECRET-MARKER-123456")`. The test sets it to prove `/api/system` never echoes the environment, and asserts `"ENV-SECRET-MARKER"` is absent from the response (line 168). Still present in the current tree, which is why the current-tree report has it. |
| D | 3 | aws-access-token | `535d5b45`, `data/genomics/flyingfish_receipts.json`, lines 123, 141, 159 | **Expired signed download URLs for a public dataset. No account secret.** | Each line holds an `https://s3-eu-west-1.amazonaws.com/pfigshare-u-files/...` pre-signed redirect (Figshare item 14600634, CC BY 4.0) with parameters `X-Amz-Algorithm, -Credential, -Date, -Expires, -Signature, -SignedHeaders`, `X-Amz-Expires=10` and `X-Amz-Date` 20261031T201827Z / 201830Z / 201834Z (13:18 PDT). They expired ten seconds after issue. The credential id in such a URL belongs to Figshare's storage account, not to this project, and the signature is time-limited. Current files no longer contain them: `git grep` for `X-Amz-Signature`, `X-Amz-Credential` and `AKIA` + 16 characters over the current tree finds none in receipts (see the false positive below). |

Totals: 15 + 1 + 1 + 3 = 20, matching the receipt (17 generic-api-key, 3 aws-access-token).

## 3. Current-tree report (16)

15 are class A (same file, same lines). 1 is class C. There is no Manifest or signed-URL hit in the current tree, which agrees with the history classification: the UUID file is not in this tree and the URLs were scrubbed by `sources.public_url` / `scrub_receipts`.

## 4. Things noticed, not findings

* My own looser regex (`AKIA[0-9A-Z]{16}`, no word boundary) matches one string inside `artifacts/print/viewer.html` line 95. The match sits inside a 132,160-character run of base64 alphabet (an embedded binary blob, with neighbouring characters such as `AAAAcAAAAKAAAAByAAAAcgAA`). gitleaks 8.30.1 did not report it. I classify it as a substring of encoded data and not an AWS key id. This is a judgement from the context, not a decode of the blob.

## 5. What is *not* established

* No allowlist was added to hide any finding; the classification is by evidence above, and the scanner is unchanged.
* "No active account credential identified" means gitleaks default rules plus the targeted checks above found none. Secrets in forms those rules do not describe, in binary artefacts, or in refs created after the scan, are not covered. Nested archives were reported by root as a separate, still-running scan; its result is not part of this document.
* The scanned history (367 commits per the log) is not shown here to be the whole history of every ref. Root's rescan of the latest refs, before any visibility change, is the controlling check.
* I did not verify that Figshare's URLs are unusable today by fetching them, because fetching would issue network requests for a signed URL. They are expired by their own printed lifetime.

## 6. Web / MCP review (branch `public-security`)

Scope: the code paths of `frontier/web.py`, `http.py`, `mcp.py`, `mcp_remote.py`, `mcp_surfaces.py`, the simulation, engineering, beliefs and formalize adapters, `discovery.py`, `media.py`, the nginx and systemd units in `deploy/`. I read these and ran focused local tests under a capped scope. I did not probe the live site, TLS, the installed nginx or systemd state, Postgres grants, the Store SQL in full, `admin.py`, `attention/` or the studio JavaScript.

Judged sound in what was read: durable writes need a bearer credential (a browser session never authorises one); anonymous calculators accept fixed schemas, are size-bounded, slot-limited, killed at 8 s and take no code, URLs or commands; the only outbound request in `frontier/` is the fixed embedding-provider URL; static serving rejects traversal, symlink escape, sensitive names and unlisted types; no CORS is emitted and a foreign `Origin` is refused; the MCP guard enforces path, size, concurrency and timeout, and tool bodies run in worker threads.

Fixed on `public-security`:

1. `/api/media` and the MCP artifact tool rescanned the artifact tree on every anonymous call (57 ms warm here, serialised): now `LocalMedia(scan_ttl=10)`. Test `tests/test_media.py::test_scan_ttl_bounds_rescans_from_anonymous_lookups`.
2. The engineering and belief workers had no memory or CPU cap, unlike the simulation worker: shared `frontier/worker_limits.cap_worker`. Tests in `tests/test_worker_limits.py`.
3. Anonymous session minting was unlimited against a 500-entry evicting table: 60 per 600 s per client. Test in `tests/test_web.py`.
4. The checked-in public web unit no longer loads `studio.env`. The installed unit was not read and is root's to install.

Tests (capped scope, `scripts/test_postgres.sh`): web and media 104 passed; worker limits plus engineering, beliefs and simulation API 84 passed; `test_mcp_remote.py` 27 passed. `tests/test_mcp_demo.py` has 2 failures that also occur with the last commit's edits stashed; cause not investigated.

Open recommendation, not applied: a stricter nginx `limit_req` for the four solver POST routes. The installed config is root's.

## 7. Before any visibility change

Root's final rescan of the latest refs, and the nested-archive scan result, are required. This document changes no repository visibility.
