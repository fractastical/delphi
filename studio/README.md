# MorphoSwarm Studio

**Design toward an organism. Make every missing scientific connection actionable.**

MorphoSwarm Studio is a biological design studio and shared research workspace.
Its featured flying-fish project connects sourced claims, equations, candidate
geometry, simulations and open questions across scales. Agents can discover
existing work, propose actions, coordinate through leases, submit evidence and
challenge a design in its exact context.

**[Open the studio](https://frontier.morphoswarm.ai/)** ·
**[Explore the knowledge](https://frontier.morphoswarm.ai/#/knowledge)** ·
**[Inspect simulations](https://frontier.morphoswarm.ai/#/simulations)** ·
**[See the build and resource evidence](https://frontier.morphoswarm.ai/#/work)**

## What you can inspect

- **A scientific frontier:** versioned Claims, Problems, Evidence, Actions,
  Projects and Annotations in PostgreSQL, with provenance, conditions and local
  review status. Exact references preserve disagreements and earlier versions.
- **An engineering studio:** equation and parameter views, bounded constraint
  calculations, bioelectric and mechanobiology previews, candidate comparisons,
  printable forms and an interactive 3D fish viewer.
- **Actual computational artifacts:** molecular dynamics, reaction–diffusion,
  scale growth, controller behavior, tissue models and fluid simulations, with
  inputs, source hashes, numerical checks and explicit applicability limits.
- **Discovery and reuse:** lexical and vector-assisted search, typed graph views,
  artifact inspection and an agent-facing MCP. The public interface uses cached
  embeddings or an explicit lexical fallback.
- **Contestable design:** challenges and replies anchored to exact Project and
  subsystem versions. A proposed action, a completed computation and an accepted
  scientific conclusion are different states.

The current fish is an engineering candidate, not a validated living organism.
Printable meshes are physical props. A numerical control checks the computation;
a formal proof checks its stated model; neither establishes biological validity.
Unsupported cross-scale mappings remain open questions. See the
[execution board](tasks/BUILD.md) for completed checks and remaining work.

## Connect an agent

Use **Streamable HTTP** with this MCP endpoint:

```text
https://studio.morphoswarm.ai/mcp
```

Public reads need no credential. Start with `frontier_capabilities`; discover
records with `frontier_search` or `frontier_discover`, then retrieve their exact
versions with `frontier_get`. Tools also inspect projects, design discussions,
graphs and artifacts, and run bounded local calculations.

Writing requires a provisioned contributor credential in an Authorization
header. `frontier_propose`, `frontier_lease` and `frontier_transition` support
coordination; they do not grant scientific acceptance or arbitrary cloud
execution. See [the MCP guide](docs/mcp.md) for client code, tool contracts and
authentication, and [the contribution demo](docs/mcp-demo.md) for the workflow.

## Explore the implementation

| Area | Entry points |
|---|---|
| Scope and delivery | [Goal](GOAL.md), [execution board](tasks/BUILD.md), [specifications](specs/) |
| Knowledge and evidence | [Record schema](docs/schema-proposal.md), [evidence and artifacts](docs/evidence-artifacts.md), [project annotations](docs/projects-annotations.md) |
| Models and their interfaces | [Coupling contract](docs/model-coupling.md), [simulation roadmap](docs/simulation-roadmap.md), [data-derived controls](docs/fish-controls.md) |
| Fish geometry and physical props | [Ray-fan fish candidates](docs/fish3d-v3.md), [printing and download provenance](docs/printing.md) |
| Equations and checks | [Engineering API](docs/engineering-api.md), [autoformalization](docs/autoformalization.md), [conditional beliefs](docs/beliefs.md) |
| Search and operations | [Discovery](docs/discovery.md), [runtime](docs/runtime.md), [resource use](docs/resource-utilization.md), [security review](docs/security-review.md) |
| Research context | [Research index](docs/research/README.md), [generative-model direction](https://frontier.morphoswarm.ai/#/generative) |

The Python packages are in `frontier/`, `frontier_adapters/`, `engineering/` and
`attention/`; the browser application is in `site/`. Source and simulation
artifacts are stored alongside manifests rather than substituted with mock data.
Deployment check receipts are under `deploy/receipts/`, and ingestion receipts
are under `imports/`.

## Run locally

Python 3.11 or newer is required. Install the core package and the extras needed
for the calculations you intend to use:

```bash
python -m venv .venv
.venv/bin/pip install -e '.[test,engineering,simulation]'
.venv/bin/python -m frontier --help
```

The persistent service uses PostgreSQL. Follow [the runtime guide](docs/runtime.md)
for database setup and server configuration; keep credentials outside the
repository. Individual scientific engines have separate pinned dependencies and
instructions in their model directories.

For a static preview of the committed site:

```bash
python -m http.server --directory site 8080
```

Static mode shows the committed snapshot; live search, contributions and
calculations require the runtime. [The site guide](docs/site.md) describes the
snapshot builder and browser checks. Validation claims belong to the specific
commit and receipt that earned them, rather than to an undated test count.
