# Pre-publication security review

## October 31 returned-artifact increment

Root ran gitleaks 8.30.1 with redaction on `ae6fa6f..fc3cf8d`:
25 commits, 3.07 MB, two findings. Both are the `weakdeps.oneAPI` package
UUID in `artifacts/cfd3d/gpu-v1/resolved-Manifest.toml`, under
AcceleratedKernels and Atomix. Root parsed the TOML and both UUIDs, and checked
the corresponding oneAPI extension entries. These are dependency identifiers,
the same class as finding B below, not account credentials. No blanket scanner
allowlist was added. This incremental history scan does not replace the earlier
full scans or prove absence of all possible secrets.

The bounded MCP text-preview review found a cached-path policy bypass when a
public path was replaced with an in-tree symlink to the same previously published
bytes. The fix preserves the lexical path through no-follow descriptor opening,
rechecks serving policy and MIME, and still verifies the complete digest. Root
ran all 37 media tests, including in-tree and escaping symlink regressions. The
finding did not establish arbitrary new-secret disclosure. This remains a
limited source and regression review, not a proof of all race freedom.

Sanitised record of the secret scan and the public web/MCP review done before this repository was considered for public visibility.
**No secret value appears here or in the receipts it cites.** Findings are identified by rule, file, line and commit only.
This is not a complete penetration test and does not claim the absence of all vulnerabilities or of all credentials.

## 1. Secret scan receipts

| Item | Value |
|---|---|
| Tool | gitleaks 8.30.1 (`/data/tools/gitleaks-8.30.1/gitleaks version` printed `8.30.1`), default rules, run locally; nothing was uploaded to an external scanner |
| History scan | `security/gitleaks-history.redacted.json`, sha256 prefix `6bcbfad5b36f956d`. Its tool log (`gitleaks-history.log`) reads "367 commits scanned, leaks found: 20". Root's 477 was a reachable-commit count and the scanner's 367 was the number of commits it diffed; these are different quantities (see section 7), not a disagreement. The final rescan in section 7 supersedes this first run. |
| Current-tree scan | `security/gitleaks-tree.redacted.json`, sha256 prefix `c322d524e2a5a50a`, scan of a copy of commit `b53e0cd` of `codex/frontier-demo-20261031` (log: ~95.8 MB, "leaks found: 16") |
| Redaction | Every `Secret` field in both JSON receipts is the literal `REDACTED`, and every `Match` field contains `REDACTED` (checked by script, 20 of 20 and 16 of 16). The receipts live under `/data/artifacts/delphi-evolve-rethink/security/` and are not copied into git. |

Reading limits: I read the receipts, the tool logs, and the historical file lines the findings point at. For the signed-URL items I parsed only the host, path prefix and query-parameter *names*, `X-Amz-Expires` and `X-Amz-Date`, never the credential or signature values.

## 2. Classification of the 20 history candidates

| # | Count | Rule | Location (commit, file, line) | Classification | Evidence |
|---|---|---|---|---|---|
| A | 15 | generic-api-key | `30b41e3c`, `findings/attestation-sample-15.json`, lines 28, 42, 56 ... 224 (every 14th line) | **Not a secret.** Deterministic SHA-256 sampling keys | For all 15 findings the flagged line holds a `"key": "<64 hex>"` entry, and recomputing `sha256("frontier-attestation-sample-v1\|<slug>\|<index>\|<register_sha256>")`, the rule declared in `findings/select_attestation_sample.py`, from that item's slug and index and the file's own `register_sha256` reproduces the stored key: 15 of 15 equal, 15 distinct lines. The keys are a public, reproducible function of public inputs. |
| B | 1 | generic-api-key | `609d1cf2`, `engineering/cfd3d/env/Manifest.toml`, line 17 | **Not a secret.** A Julia package UUID | The line has the shape `    oneAPI = "<uuid>"` under `[deps.AcceleratedKernels.weakdeps]`. A Julia `Manifest.toml` lists package UUIDs, which are public identifiers in the General registry. I did not look the UUID up in the registry. The file is not in commit `b53e0cd` (the `engineering/cfd3d/env/` directory is absent there), so it is present only in history. |
| C | 1 | generic-api-key | `388b19c6`, `tests/test_system_status.py`, line 160 | **Test fixture marker, not a credential.** | The test sets the `FRONTIER_ACCESS_TOKEN` environment variable to a literal marker string (not quoted here, because quoting it makes this document a scanner hit). The test sets it to prove `/api/system` never echoes the environment, and asserts `"ENV-SECRET-MARKER"` is absent from the response (line 168). Still present in the current tree, which is why the current-tree report has it. |
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
2. The engineering and belief workers had no memory or CPU cap, unlike the simulation worker: shared `frontier/worker_limits.cap_worker`. The first cap (2 GiB) did not guarantee failure before the 1 GiB service MemoryMax, so it was re-sized from measurement: least RLIMIT_AS at which a valid request still completed was bioelectric 158 MiB, mechanobio 268, engineering 127, beliefs 79 (formalize caps at 384); the cap is 384 MiB, and all four adapters share a process-wide budget of two workers (768 MiB together; the web process's own size was not measured). Tests in `tests/test_worker_limits.py`.
3. Anonymous session minting was unlimited against a 500-entry evicting table: 60 per 600 s per client. Test in `tests/test_web.py`.
4. The checked-in public web unit no longer loads `studio.env`. The installed unit was not read and is root's to install.

Tests (capped scope, `scripts/test_postgres.sh`): web and media 104 passed; worker limits plus engineering, beliefs and simulation API 84 passed; `test_mcp_remote.py` 27 passed. `tests/test_mcp_demo.py` had 2 failures that occur identically on clean `279fff3` (this branch's base) and on the upstream tip `df98621`, so they were not caused by these changes: `scripts/mcp_demo.py` pinned six read tools while the server registers sixteen. Fixed by pinning the sixteen, as `test_mcp_remote.py` and `test_interfaces.py` already do; those tests pass (15).

Open recommendation, not applied: a stricter nginx `limit_req` for the four solver POST routes. The installed config is root's.

## 7. Final rescan (supersedes sections 1-3 for counts)

| Item | Value |
|---|---|
| Scan time | 2026-10-31 15:38-15:40 PDT (22:38-22:40 UTC) |
| Tool | the same gitleaks 8.30.1 binary, sha256 prefix `88f91962aa2f93ac`; no config file, no `.gitleaksignore` (none is tracked in git history, none in the archived tree); `--redact`, `--max-archive-depth 3`, `--max-decode-depth 3`; run in a scope capped at MemoryMax 4G, MemorySwapMax 0, TasksMax 128, CPUQuota 100% |
| Tree scanned | `git archive` of `origin/codex/frontier-demo-20261031` at **`87a6844e35f4`** (full: `87a6844e35f4283d01082c3fa07b23a3d5aeabc9`), 1,838 files, 168.65 MB, 15 archive-type files inside it (archive traversal on; none produced a hit of their own). This tip contains `b4b1c43`. |
| History scanned | `git . --log-opts=--remotes=origin` over the 70 `refs/remotes/origin/*` refs present after `git fetch` at the scan time, and a second run over `--all`. Both found the same 23 fingerprints. |
| Commit counts, three different quantities | **548** commits reachable from the origin refs (`git rev-list --remotes=origin --count`), of which 127 are merges and **422** are not; gitleaks reported "422 commits scanned" because it scans commit diffs and merge commits carry none. `git rev-list --all` gives 550 (two local-only commits). The tip's own ancestry is 469. Root's 477 was a reachable count at an earlier moment; the first scan's 367 was its diffed (non-merge) count at an earlier moment. |
| Findings | history: 23; tree at the tip: 20. All `Secret` fields are `REDACTED` and all `Match` fields contain `REDACTED` (checked by script, 23 of 23, 23 of 23 and 20 of 20). |
| Receipts (local, `/data/artifacts/delphi-evolve-rethink/security/final-20261031/`) | `history-remotes-origin.redacted.json` sha256 prefix `fcc98d7251854102`; `history-all-refs.redacted.json` the same prefix (identical content); `tree-tip.redacted.json` prefix `52a5fcb6b6eb965c`; the `.log` files and `scanned-tip.txt` beside them |

New since section 2 (23 history findings = the 20 above + these 3):

| Count | Location | Classification | Evidence |
|---|---|---|---|
| 2 | `f593f0c1`, `engineering/cfd3d/env_gpu/Manifest.toml`, lines 31 and 72 | **Not a secret.** The same Julia `oneAPI` package UUID as class B | Both lines match `^\s*oneAPI = "<36-char uuid>"$`, and the value is identical across these two lines and class B's line in `env/Manifest.toml` (one distinct value; compared by script, not printed). A Manifest lists package UUIDs. These files are in the tree, so the tree report has them (class B's file is in the tree now too: 3 Manifest hits in total). |
| 1 | `61a44ae4`, `docs/security-review.md`, line 24 | **Not a secret. This document quoted the test marker of class C.** | The flagged span is the test line's `setenv` argument ending in the marker. The line is reworded in this revision so it no longer appears; the history keeps the earlier text. |

The tree's 20 are: 15 class A, 3 oneAPI UUID lines, 1 class C, and 1 line in this document (class C quotation, removed by this revision, so the next tree scan should show 19). The three expired Figshare URLs (class D) are history-only; none is in the tree. No new rule type appeared.

Not covered: nested archives deeper than three levels, content encoded deeper than three levels, files above gitleaks' size limits, and any ref created after 15:38 PDT. The first-run limits in section 5 still apply. This is the receipt for the commit and time above; a later tip needs a new scan.

## 7a. Final delta rescan before the visibility change (15:53-15:55 PDT, 22:53-22:55 UTC)

Same gitleaks 8.30.1 binary and flags as section 7 (no config, redacted, archive and decode depth 3, capped scope). The scanned refs were frozen first, so every count below comes from one rev-list.

| Item | Value |
|---|---|
| Frozen refs | 71 `refs/remotes/origin/*` entries (hashes in `scanref-manifest.txt`, receipt directory `/data/artifacts/delphi-evolve-rethink/security/final2-20261031/`), copied to local `refs/freeze/*` before scanning |
| Commits | **581** reachable = **135** merges + **446** non-merge (135 + 446 = 581, one `git rev-list --glob='refs/freeze/*'` set). Root branch ancestry: 478. The earlier "548 = 127 + 422" was off by one because it was two separate counts taken at different moments; it is superseded by this set. |
| Root tree | `origin/codex/frontier-demo-20261031` at `17edd4480f46`, 1,872 files |
| Incoming | `origin/work/fish3d-v3` at `8dc5cc47c9e3`, not merged into the root branch at the time of the scan (`merge-base --is-ancestor` said no); its commits are inside the 581 history set |
| Merged tree | `git merge-tree --write-tree 17edd4480f46 8dc5cc47c9e3` was conflict-free (tree `3387e8f6cac0`), archived and scanned, 2,034 files. This is a simulated merge, not root's actual merge commit; scan the real one if its tree differs |
| Findings | history **23**, root tree **19**, merged tree **19** (root and merged have the same rule, file and line set). All `Secret` fields `REDACTED`, all `Match` fields contain `REDACTED`. |
| Delta vs section 7 | History: the 23 fingerprints are identical to the previous run's 23, so the 33 commits added since section 7's set (581 against 548, including `work/fish3d-v3`) added no hit; the receipt file is byte-identical to the earlier one (same prefix). Tree: 19, the previous 20 minus the quotation in this document removed in `aee47f5` |
| Classification of the 19 tree hits | 15 sampling keys (class A) + 3 `oneAPI` package UUID lines (class B, in `env/Manifest.toml` and twice in `env_gpu/Manifest.toml`) + 1 test marker (class C). The 23 history hits are these plus 3 expired Figshare URLs (class D, history only) plus the earlier quotation (history only). Nothing new. |
| Receipts | sha256 prefixes: `history.redacted.json` `fcc98d7251854102`, `tree-root.redacted.json` `f9bdb3a5855c4142`, `tree-merged.redacted.json` `9b7f16701770fd63`, `scanref-manifest.txt` `0163330a2dec150d`. These files are local and are not in git |

Not covered, beyond section 5: the actual merge commit if it differs from the simulated tree, refs pushed after 15:53 PDT, and nested archives or encodings deeper than three levels. Root's own check for those is the last step before the flip.

## 7b. Final scan at root tip `35db5773b8fe` (15:58-16:00 PDT, 22:58-23:00 UTC)

Same binary and flags as section 7. Receipt directory `/data/artifacts/delphi-evolve-rethink/security/final3-20261031/`. A first run that morning pinned `7e3e228` because the root branch advanced during my fetch; it was discarded and redone at the tip below.

| Item | Value |
|---|---|
| Frozen refs | 72 `refs/remotes/origin/*` entries (hashes in `scanref-manifest.txt`) |
| Commits | **604** reachable = **143** merges + **461** non-merge, from one rev-list; gitleaks reported "461 commits scanned". Root branch ancestry 519. |
| Tree | `git archive` of `origin/codex/frontier-demo-20261031` at `35db5773b8fe` (full `35db5773b8fe` prefix recorded in `tip.txt`), 2,162 files, includes `7e3e228` and `work/fish3d-v3` |
| Findings | history **23**, tree **19**; all `Secret` fields `REDACTED`, all `Match` fields contain `REDACTED` |
| Delta vs section 7a | History: the 23 fingerprints are identical (none new, none dropped). Tree: the same 19 rule/file/line entries (15 sampling keys, 3 `oneAPI` UUID lines, 1 test marker). Nothing new. |
| Receipt hashes (sha256 prefix) | `history.redacted.json` `fcc98d7251854102`, `tree-tip.redacted.json` `3b8848b16957ec1e`, `scanref-manifest.txt` `d7e1b34f76dc13bc` |

Not covered: refs or commits after 16:00 PDT, nested archives or encodings deeper than three levels, and the usual limits in section 5. Future additions need their own scan.

## 8. Before any visibility change

Root's final rescan of the latest refs, and the nested-archive scan result, are required. This document changes no repository visibility.

## 9. Publication checkpoint

At 4:06pm PDT on October31, the repository visibility was changed to public after
PR7 merged. Anonymous GitHub metadata and current-main README requests succeeded;
`deploy/receipts/public-repository-check.json` records those checks. Public read
access does not grant collaborator write permission.

The final incremental scan, completed at 2026-10-31T23:05:32.544774+00:00, covered
23 additional reachable commits after section7b's frozen refs and
69 changed tree files through `0ad318877a583d4870bae1f720c952a99397fc54`.
Gitleaks8.30.1 reported 0 new history findings and
0 changed-tree findings. Redacted reports and the exact ref set
are retained under `/data/artifacts/delphi-evolve-rethink/security/publication-final/`.
This supplements the full-history/current-tree scan above; it does not replace
its classifications or extend coverage beyond archive/decode depth3. Later pushes
require their own review. No claim of complete vulnerability coverage is made.
