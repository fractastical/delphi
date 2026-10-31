# Live imports

`2026-10-31-register-250-receipt.json`: the 250 `curated_question` Problem records imported from the morphoswarm open-problems
register into the `delphi-frontier` namespace as **proposed** records (actor `codex-03`, operator `local-fleet`; not an
independent reviewer). It lists every `id`, exact `version`, `content_sha256`, idempotency key and creation time, the register and
draft-file sha256, the importer commit, and the read-back result. The credential was read from a mode-600 file inside the process
and appears nowhere.

Reproduce or re-run (a re-run with unchanged inputs writes nothing; changed content revises the exact head, never a duplicate;
any other author, fork, branch or reviewed head stops the run before anything is written):

```
python3 -I scripts/import_register.py REGISTER.yaml --assessments findings --out drafts.jsonl
FRONTIER_DSN='host=... port=... dbname=... user=...' python3 -I scripts/submit_drafts.py drafts.jsonl --namespace NS \
  --credential-file PATH --expect-actor ACTOR --expect-operator OPERATOR --register-sha256 SHA --receipt receipt.json   # dry run
... --execute                                                                                                          # write
```
