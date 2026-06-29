# Product Specification — PlantSim-Agent

**Status:** Draft v0.1 · Last updated: 2026-06-29
**Owner:** Jacky Tao ([@JackySummerfield](https://github.com/JackySummerfield))
**Audience:** Contributors, early adopters, anyone evaluating whether the project fits their needs.

---

## 1. Problem

Siemens Tecnomatix Plant Simulation is the most common platform for discrete-event simulation in manufacturing and logistics, but its ecosystem is closed in three painful ways:

1. **Documentation is Proprietary.** The Help is not on the public web; it ships with the licensed install and is covered by Siemens IP terms.
2. **SimTalk 2.0 is niche.** General-purpose LLMs were trained on very little SimTalk and routinely produce SimTalk 1.0 syntax (which no longer compiles) or invent APIs.
3. **`.psfm` projects are folders of hundreds of YAML files.** Even if an LLM knew SimTalk, navigating a real project to answer "where is `AGVFleet` called?" requires structured indexing.

The result: Plant Simulation developers cannot benefit from the modern AI workflow that other developers take for granted.

## 2. Goal

Deliver an open-source GitHub Copilot agent that gives Plant Simulation developers a trustworthy AI assistant for three workflows:

| # | Workflow | Why it matters |
|---|----------|----------------|
| W1 | **Documentation Q&A** | Look up an API, behaviour, or setup step without leaving the editor |
| W2 | **SimTalk code authoring & review** | Generate, refactor, debug, and review snippets — without hallucinated APIs |
| W3 | **`.psfm` project analysis** | Understand and navigate an existing model without opening Plant Simulation |

Trustworthiness is non-negotiable: **every answer must carry a verifiable citation** — Help section for W1, API source row for W2, project file/line for W3. The agent rejects its own output when citations are missing.

## 3. Non-Goals

- Replacing Plant Simulation's GUI or runtime
- Hosting a SaaS Q&A service (this project is local-first)
- Bundling or redistributing Siemens documentation
- Supporting SimTalk 1.0 generation (only conversion *from* 1.0 *to* 2.0)
- Multi-user / cloud collaboration (out of scope for v0.x)
- Visual `.psfm` editing (we do not modify YAML in v0.1)

## 4. Target Users

| Persona | Skill level | Primary need |
|---------|-------------|--------------|
| **PlantSim Engineer** | Intermediate SimTalk; deep modelling | W1, W2 — fewer Help lookups, faster snippet writing |
| **New Plant Sim User** | Beginner | W1 — explain concepts, point to right Help section |
| **Senior Modeller / Architect** | Expert | W3 — review and refactor inherited projects |
| **External developer / consultant** | Variable | W2, W3 — onboard quickly to a customer's existing model |

## 5. User Stories

### W1 — Documentation Q&A
- *As an engineer*, when I forget the exact signature of `Buffer.numMU`, I want to ask the agent and get the signature plus a link to the Help section, so I can verify without losing flow.
- *As a beginner*, when I read about "FlowControl", I want a plain-language explanation of what it does and when to use it, with a pointer to the Help.

### W2 — SimTalk Code Authoring & Review
- *As an engineer*, when I describe a task ("log MU throughput every shift to a DataTable"), I want the agent to produce paste-ready SimTalk 2.0 code that follows our standards, listing every API used and its source.
- *As a reviewer*, when I paste a colleague's SimTalk method, I want the agent to flag SimTalk 1.0 leftovers, unchecked `.move()` calls, and hard-coded magic numbers, citing the standards rule for each issue.

### W3 — `.psfm` Project Analysis
- *As a senior modeller* inheriting a model, I want to ask "where is method X called from?" and get a list of caller methods with file paths.
- *As an engineer* debugging a deadlock, I want to ask "show me every method that touches the `AGVPool`" and get a focused subset, not the whole project dumped.
- *As an architect*, I want a one-paragraph summary of the model's structure: top-level frames, key resource pools, main control methods.

## 6. Scope by Release

### v0.1 (current target)

**In scope:**
- W1 KB Q&A backed by user-built FTS5 index of their own PTS Help
- W2 SimTalk code authoring, review, debugging — read-only on user files
- W3 `.psfm` read-only queries: `find_method`, `find_callers`, `search_code`, `get_object_graph`
- Citation reviewer (lightweight, format-anchor-first) — runs on **all three workflows** with workflow-specific anchors (W1: `**Sources:**`; W2: `**API Evidence Table**`; W3: `**File References:**`)
- Installation scripts (Windows + POSIX)
- Self-authored sample KB (`kb_minimal/`) so the agent is usable without a full Help build

**Out of scope (deferred):**
- `.psfm` write-back / refactor
- Vector retrieval (BM25 / FTS5 only)
- Deep SimTalk lexer/parser
- Call-graph visualisation
- Non-Copilot model backends
- VS Code extension packaging

See [`docs/roadmap.md`](./roadmap.md) for v0.2 and beyond.

## 7. Success Criteria

| Criterion | Measure | Target |
|-----------|---------|--------|
| **KB Q&A accuracy** | 20-question hand-graded benchmark | ≥ 80 % correct & cited |
| **Citation reviewer recall** | 10 deliberately uncited responses | 10/10 flagged |
| **Indexing speed** | KongMing `.psfm` (~1000+ YAML files) | < 2 minutes cold build |
| **Hallucinated-API rate** | 10 representative coding tasks, human review | 0 fabricated APIs in cited code |
| **Cold-install time** | Fresh VS Code profile → working agent | ≤ 5 minutes |

## 8. Constraints

- **Legal:** No Siemens Help content, screenshots, or model libraries may be redistributed. Users bring their own Help.
- **Privacy:** Local-first; the agent must not transmit user `.psfm` content anywhere beyond the Copilot inference path the user already trusts.
- **Operating system:** Windows is the primary target (Plant Simulation runs on Windows). macOS and Linux are supported for the MCP server and docs, but agent invocation requires VS Code Copilot which is cross-platform.
- **Python:** ≥ 3.10 (FastMCP requirement and modern type-hint syntax).
- **No telemetry:** The project does not collect any usage data.

## 9. Glossary

| Term | Meaning |
|------|---------|
| **`.psfm`** | A Plant Simulation model saved in the modern "folder" format: a directory containing one YAML per object, instead of a single binary file. |
| **SimTalk** | Plant Simulation's embedded scripting language. SimTalk 2.0 is the current version; 1.0 syntax is legacy and no longer compiles. |
| **MCP** | [Model Context Protocol](https://modelcontextprotocol.io/) — a standard for connecting LLMs to local tools and data sources. |
| **Custom Agent** | A `.agent.md` file that defines a Copilot persona with specific tools, instructions, and behaviour. |
| **Skill** | A `SKILL.md`-rooted folder of procedural knowledge that an agent loads on demand. |
| **Subagent** | A custom agent invoked by another agent for a focused task (e.g. citation review) with isolated context. |
| **FTS5** | SQLite's full-text search extension; provides BM25 ranking out of the box without external dependencies. |
| **API Evidence Table** | A markdown table the code-author skill emits alongside every code block, listing each non-syntax symbol and its documentation source. |
