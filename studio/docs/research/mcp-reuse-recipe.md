# Use the Delphi Studio MCP from your own project — no account, no token

**Endpoint:** `https://frontier.morphoswarm.ai/mcp`
**Reads and calculations need no credential.** Writes need one and will be refused without it.
**Transport:** streamable-http, stateless. One `POST` per request, at exactly that path. No
session handshake is required for the calls below.

Every command here was run against the live endpoint on 2026-10-31 at about 22:08-22:10 UTC
(3:08-3:10 PM PDT) with no `Authorization` header. The saved responses are in
`data/research/mcp-probe-2026-10-31/`. If a command below does not work for you, the endpoint has
changed — the recipe is a measurement, not a promise about the future.

Two preliminaries that save ten minutes:

- Send **both** content types in `Accept`, or the server may not answer:
  `-H 'Accept: application/json, text/event-stream'`
- A tool error comes back as HTTP **200** with `result.isError = true`. Check that field, not the
  status code.

---

## 0. Check it is alive and see what it will do

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call",
       "params":{"name":"frontier_capabilities","arguments":{}}}'
```

Returns a manifest: `anonymous_reads: true`, `principal: null`, the exact tool list with each
tool's `kind` (`read` or `write`) and `requires_role`. **Call this first.** It states what is
deliberately not available, so you do not spend time looking for it.

There are **18 tools**. The manifest marks **15 as `kind: read`** (this includes the bounded calculators) and **3 as `kind: write`**; the three
(`frontier_propose`, `frontier_lease`, `frontier_transition`) are writes and need a bearer token.

---

## 1. Search ~1,287 claim versions for the classical result you are leaning on

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call",
       "params":{"name":"frontier_search",
                 "arguments":{"query":"Turing instability","limit":5}}}'
```

Each hit carries `namespace`, `kind`, `id`, an exact content-addressed `version`, `source_uri`,
`why_matched`, and — the field that matters — **`local_status`**, e.g. `imported_unreviewed`.

> **Read `local_status` before you cite anything.** `imported_unreviewed` means the record was
> imported and nobody at this node has reviewed it. The search is lexical; `score` is relevance,
> **not truth**. Pin the `version` hash in your own notes: ids are reused across namespaces,
> versions are not.

`frontier_get` retrieves one exact version. `frontier_neighborhood` returns up to 50 typed edges
at depth one, **including dispute and review edges** — that is where you find out whether anyone
has contested the claim you are about to build on.

---

## 2. Get counts you can quote, including the ones we do not have

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"frontier_catalogue","arguments":{}}}'
```

Measured 2026-10-31: 1,287 claim versions, 1,190 carrying an upstream Delphi claim id, 1,214 with
no declared origin, 451 artifact declarations.

Several fields come back `null` with a reason — `species.mapped_species`,
`conditions_and_math.structured_conditions`. `artifacts.hosted_and_byte_checked` is `0` and says
so explicitly: *"0 is the absence of any check, not a finding that hosted files are wrong or
right."* Those nulls are deliberate. Do not fill them in with a guess.

---

## 3. Run a bounded simulation without installing anything

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":4,"method":"tools/call",
       "params":{"name":"frontier_simulate",
                 "arguments":{"model":"bioelectric","parameters":{}}}}'
```

`model` is `bioelectric` or `mechanobio`. Empty `parameters` uses the declared defaults, which the
response echoes back in `effective_request` (for `bioelectric`: `dt_ms` 0.025, `duration_ms` 30.0).
Took **1.10 s** when measured.

What comes back with the numbers, and why you should care:

| field | what it gives you |
|---|---|
| `calibrated` | `false`. The model says so itself |
| `scope` | *"An ephemeral numerical scenario, not an observation or biological validation"* |
| `code_sha256` | the simulation API file plus six model files, each hashed |
| `effective_request_sha256` | hash of the exact request, so you can prove what you ran |
| `environment` + `environment_sha256` | python 3.13.12, numpy 2.4.4, thread pinning, platform |
| `persisted` | whether anything was stored (it is ephemeral) |

**This is the part worth stealing even if you never use our data:** a calculation endpoint whose
result carries the hash of the code, the hash of the request and its own calibration status. You
can cite it in a write-up and anyone can re-run it.

Two more bounded calculators, same no-credential rule: `frontier_engineer` (an
aircraft-constraint solver) and `frontier_belief` (a finite-scenario belief solver whose
consequences are conditional on declared inputs). `frontier_formalize` proposes exact
expressions / Lean; its result is **not** a persisted formal proof.

---

## 4. The control you should run before trusting any of this

An endpoint that cannot refuse anything has not been tested. Send a **well-formed** write with no
credential:

```bash
curl -s -X POST https://frontier.morphoswarm.ai/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":5,"method":"tools/call",
       "params":{"name":"frontier_propose","arguments":{
         "idempotency_key":"your-control-probe-1",
         "draft":{"namespace":"delphi-frontier","kind":"Claim","id":"your-control-probe",
                  "issuer":"anonymous","source_uri":"urn:frontier:probe:anon",
                  "visibility":"public","predecessor":null,
                  "payload":{"statement":"anonymous write control probe"}}}}}'
```

Expected, and what we measured:

```
isError = true
Error executing tool frontier_propose: unauthorized: Authenticated operator token required
```

> **Make the draft well-formed.** A malformed one is rejected by argument validation *before*
> authentication, so you learn nothing about whether writes are protected. We made exactly that
> mistake on the first attempt: the refusal said `Field required`, which is a schema error, not an
> auth error.

If you get a write accepted without a credential, tell us — that is a security finding, not a
feature.

---

## 5. Smallest useful thing another team can do with this

If you are relying on a classical result — a Turing condition, an allometric scaling law, a
population-genetics limit — then:

1. `frontier_search` for it, and read `local_status` on every hit.
2. `frontier_neighborhood` on the version you care about, to see whether it is disputed here.
3. If it is a reaction-diffusion criterion, read
   [`bench/mispredication/`](https://github.com/kganjam/delphi-frontier) in our repository — the
   repo is **public** — before using the continuum condition on a finite domain. We published a claim that the criterion is reliable above ~1.5 critical
   wavelengths and **withdrew it**: the error is windowed, exactly 0 at half-integer multiples of
   the critical wavelength (which is where we had sampled) and 6.22% at 1.25 λc, still 0.58% at
   4.25 λc. If your domain length is not a half-integer multiple of λc, the textbook test can pass
   while no unstable mode exists.

That last point is the one most likely to change what another team does, and it costs them one
search call to find.

**Caveats, stated once:** the mispredication numbers come from a **toy ensemble** with a declared
prior (Jacobian entries uniform on [-2,2], Dv/Du log-uniform, n=20,000, seed 12345). They describe
that sampling distribution and nothing else — not real Turing systems, not nonlinear outcomes, not
any organism.

---

## Writes, if you want them

Per request: `Authorization: Bearer <your operator credential>`, header only — never a query
string, never a tool argument. Each request authenticates as its own principal; the server holds
no shared token. A credential that fails verification is **refused, not downgraded to anonymous**.

There is deliberately **no review or accept tool**. `frontier_propose` returns `proposed`, never
`accepted`; acceptance requires an independent operator elsewhere. That is the point of the
design, not a missing feature.

Ask us for a credential if you need one. Reads and calculations never need one.

---

## The source

`https://github.com/kganjam/delphi-frontier` — public as of 2026-10-31. Verified anonymously:
the repo API returns `"private": false, "visibility": "public"`, and `README.md` fetches over raw
with HTTP 200 while a nonexistent path returns 404, so the 200 is a real read and not a
catch-all.
