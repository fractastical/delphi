// Run a dataset-resolvability assessor against an OpenAI-compatible endpoint (vLLM, Ollama,
// OpenAI, ...) and write assessment/raw/<assessor>/batch-N.json in the same shape the
// subagent assessors produce, so build/merge-assessments.mjs treats it like any other assessor.
//
// The model sees exactly what a subagent assessor is told to use: the project's
// assessment/INSTRUCTIONS.md, rubric.json and the claims of one input batch, one claim per
// request. It never sees claims.json, the extraction, or other assessors' outputs.
//
//   node scripts/assess/run-assessor.mjs --project aristotle-biology --assessor qwen \
//     --base-url http://127.0.0.1:8000/v1 --model Qwen/Qwen3-32B-AWQ [--batches 1,2] \
//     [--concurrency 16] [--limit N] [--force]
//
// Existing per-claim results in the output file are kept unless --force, so a run can be
// resumed. Set OPENAI_API_KEY if the endpoint needs one (vLLM does not).
import { readFileSync, writeFileSync, mkdirSync, existsSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const args = Object.fromEntries(process.argv.slice(2).map((a, i, all) =>
  a.startsWith("--") ? [a.slice(2), all[i + 1]?.startsWith("--") || all[i + 1] === undefined ? true : all[i + 1]] : []).filter(x => x.length));
const need = k => { if (!args[k]) { console.error(`--${k} is required`); process.exit(2); } return args[k]; };
const project = need("project"), assessor = need("assessor"), model = need("model");
const baseUrl = (args["base-url"] ?? "http://127.0.0.1:8000/v1").replace(/\/$/, "");
const concurrency = Number(args.concurrency ?? 16);
const limit = args.limit ? Number(args.limit) : Infinity;
const maxTokens = Number(args["max-tokens"] ?? 1500);

const REPO = join(dirname(fileURLToPath(import.meta.url)), "..", "..");
const A = join(REPO, "claim-sources", project, "assessment");
const instructions = readFileSync(join(A, "INSTRUCTIONS.md"), "utf8");
const rubric = JSON.parse(readFileSync(join(A, "rubric.json"), "utf8"));
const DIMS = rubric.dimensions.map(d => d.id);
const VERDICTS = Object.keys(rubric.verdicts);
const batches = (args.batches ? String(args.batches).split(",").map(n => `batch-${n}.json`)
  : readdirSync(join(A, "inputs")).filter(f => /^batch-\d+\.json$/.test(f)).sort((a, b) => a.localeCompare(b, undefined, { numeric: true })));

const unit = { type: "number", minimum: 0, maximum: 1 };
const schema = {
  type: "object",
  additionalProperties: false,
  required: ["claim_id", "scores", "verdict", "confidence", "operationalization", "candidate_datasets", "obstacles", "rationale"],
  properties: {
    claim_id: { type: "string" },
    scores: { type: "object", additionalProperties: false, required: DIMS, properties: Object.fromEntries(DIMS.map(d => [d, unit])) },
    verdict: { type: "string", enum: VERDICTS },
    confidence: unit,
    operationalization: { type: "string" },
    candidate_datasets: {
      type: "array", maxItems: 3,
      items: { type: "object", additionalProperties: false, required: ["name", "url", "role"], properties: { name: { type: "string" }, url: { type: "string" }, role: { type: "string" } } },
    },
    obstacles: { type: "array", maxItems: 3, items: { type: "string" } },
    rationale: { type: "string" },
  },
};

const system = `${instructions}

## How you are being run

You are the assessor "${assessor}" (model ${model}), called through an API with one claim per
request. You have no file access: the rubric is included below, and the instructions' references
to reading or writing files do not apply. Return only the JSON object for the one claim you are
given (not an array), following the output format above exactly. Do not include reasoning
outside the JSON.

## Rubric (assessment/rubric.json)

${JSON.stringify(rubric, null, 2)}`;

async function assess(claim) {
  const body = {
    model,
    temperature: 0.2,
    max_tokens: maxTokens,
    messages: [
      { role: "system", content: system },
      { role: "user", content: `Assess this claim:\n\n${JSON.stringify(claim, null, 2)}` },
    ],
    response_format: { type: "json_schema", json_schema: { name: "assessment", strict: true, schema } },
    chat_template_kwargs: { enable_thinking: false },
  };
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const r = await fetch(`${baseUrl}/chat/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...(process.env.OPENAI_API_KEY ? { Authorization: `Bearer ${process.env.OPENAI_API_KEY}` } : {}) },
        body: JSON.stringify(body),
        signal: AbortSignal.timeout(600000),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}: ${(await r.text()).slice(0, 300)}`);
      const j = await r.json();
      const out = JSON.parse(j.choices[0].message.content);
      out.claim_id = claim.id;
      for (const d of DIMS) out.scores[d] = Math.round(out.scores[d] * 100) / 100;
      out.confidence = Math.round(out.confidence * 100) / 100;
      return { out, usage: j.usage };
    } catch (e) {
      if (attempt === 3) throw e;
      console.error(`  ${claim.id}: ${e.message} (retry ${attempt})`);
    }
  }
}

const outDir = join(A, "raw", assessor);
mkdirSync(outDir, { recursive: true });
let done = 0, tokens = 0;
const t0 = Date.now();
for (const b of batches) {
  const input = JSON.parse(readFileSync(join(A, "inputs", b), "utf8"));
  const path = join(outDir, b);
  const prior = !args.force && existsSync(path) ? new Map(JSON.parse(readFileSync(path, "utf8")).map(r => [r.claim_id, r])) : new Map();
  const results = new Map(prior);
  const todo = input.filter(c => !results.has(c.id)).slice(0, Math.max(0, limit - done));
  console.log(`${b}: ${input.length} claims, ${prior.size} already done, ${todo.length} to run`);
  const save = () => writeFileSync(path, JSON.stringify(input.filter(c => results.has(c.id)).map(c => results.get(c.id)), null, 2) + "\n");
  let i = 0;
  await Promise.all(Array.from({ length: Math.min(concurrency, todo.length) }, async () => {
    while (i < todo.length) {
      const claim = todo[i++];
      try {
        const { out, usage } = await assess(claim);
        results.set(claim.id, out);
        tokens += usage?.total_tokens ?? 0;
        done++;
        if (done % 5 === 0) save();
        console.log(`  ${claim.id}: ${out.verdict} (${((Date.now() - t0) / 1000).toFixed(0)}s, ${done} done)`);
      } catch (e) {
        console.error(`  ${claim.id}: FAILED ${e.message}`);
      }
    }
  }));
  save();
  const missing = input.filter(c => !results.has(c.id)).length;
  console.log(`${b}: wrote ${results.size}/${input.length}${missing ? ` (${missing} missing; rerun to fill)` : ""}`);
  if (done >= limit) break;
}
console.log(`${done} assessments in ${((Date.now() - t0) / 60000).toFixed(1)} min, ${tokens} tokens`);
