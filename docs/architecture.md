# Architecture — PlantSim-Agent

**Status:** Draft v0.1 · Last updated: 2026-06-29

This document describes **how** PlantSim-Agent is built. For **what** it does and **why**, see [`spec.md`](./spec.md). For release planning, see [`roadmap.md`](./roadmap.md).

---

## 1. High-level component diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│ VS Code  ─  GitHub Copilot Chat                                          │
│                                                                          │
│   user  →  /plantsim-copilot <query>                                     │
│              │                                                           │
│              ▼                                                           │
│   ┌─────────────────────────────────────────────┐                        │
│   │  plantsim-copilot.agent.md  (orchestrator)  │                        │
│   │  tools: read, edit, search, agent,          │                        │
│   │         plantsim-mcp/*                      │                        │
│   └────────┬────────────────────────────────────┘                        │
│            │ intent classification                                       │
│   ┌────────┴────────────┬──────────────────────┬─────────────────────┐  │
│   ▼ W1                  ▼ W2                   ▼ W3                  │  │
│  kb-qa skill        code-author skill     project-analyst skill      │  │
│  (load on demand)   (load on demand)      (load on demand)           │  │
│   │                  │                     │                          │  │
│   │                  └─────────┬───────────┘                          │  │
│   │                            ▼                                      │  │
│   │                  ┌──────────────────────┐                         │  │
│   │                  │ citation-reviewer    │   ← subagent            │  │
│   │                  │   .agent.md          │   (W1, W2, W3)          │  │
│   │                  │ tools: read          │                         │  │
│   │                  └──────────────────────┘                         │  │
│   │                                                                   │  │
│   └────────────────────────────┬──────────────────────────────────────┘  │
│                                ▼                                         │
│           ┌──────────────────────────────────────────┐                   │
│           │  plantsim-mcp  (Python + FastMCP)        │                   │
│           │                                          │                   │
│           │  Tools:                                  │                   │
│           │   • search_help(query, top_k)            │                   │
│           │   • get_api(object, method?)             │                   │
│           │   • find_method(name)                    │                   │
│           │   • find_callers(name)                   │                   │
│           │   • get_object_graph(scope)              │                   │
│           │   • search_code(pattern, scope?)         │                   │
│           │   • validate_simtalk(code)               │                   │
│           └──────────────┬───────────────────────────┘                   │
│                          ▼                                               │
│           ┌──────────────────────────────────────────┐                   │
│           │  storage layer                           │                   │
│           │   • SQLite + FTS5  (v0.1)                │                   │
│           │   • Index abstract base class            │                   │
│           │     ← VectorIndex implementation v0.2    │                   │
│           └──────────────┬───────────────────────────┘                   │
│                          ▼                                               │
│           ┌──────────────┐    ┌─────────────────────────┐                │
│           │ user's local │    │ user's `.psfm` project  │                │
│           │ PTS Help KB  │    │ folder                  │                │
│           │ (markdown)   │    │ (yaml files)            │                │
│           └──────────────┘    └─────────────────────────┘                │
└──────────────────────────────────────────────────────────────────────────┘
```

## 2. Components

### 2.1 Main agent — `plantsim-copilot.agent.md`

- **Role:** orchestrator. Classifies the user query into W1 / W2 / W3 and loads the matching skill.
- **Tools:** `[read, edit, search, agent, plantsim-mcp/*]`
- **Why it's an agent, not just a skill:** it needs `agent` tool access to invoke the citation reviewer as a subagent. Skills cannot dispatch subagents.
- **Behaviour contract** (excerpt; full text in the file):
  1. Identify intent.
  2. Load the matching skill (`plantsim-kb-qa`, `plantsim-code-author`, or `plantsim-project-analyst`).
  3. Use MCP tools per the skill's procedure.
  4. Emit a response that includes citation anchors:
     - W1 → `**Sources:**` (Help markdown path + section)
     - W2 → `**API Evidence Table**` (every non-syntax symbol → source)
     - W3 → `**File References:**` (project file path + line excerpt); from v0.2 write-back also requires `**API Evidence Table**` for any newly authored SimTalk
  5. Invoke `citation-reviewer` subagent on every response. If it returns `missing_citations`, re-generate.

### 2.2 Citation reviewer — `citation-reviewer.agent.md`

- **Role:** lightweight gate that ensures every workflow response carries verifiable source citations.
- **Tools:** `[read]` only. Minimal surface area.
- **`user-invocable: false`** — never appears in the agent picker; only callable as a subagent.
- **Algorithm (v0.1):**
  1. Receive `{workflow: W1|W2|W3, body: str}` as input.
  2. Run a **regex-level check** for the workflow's required anchor:
     - W1 → `**Sources:**` followed by ≥ 1 bullet pointing to a path under the configured KB root
     - W2 → a `| Symbol | Kind | Source |` table with ≥ 1 row and no empty `Source` cells
     - W3 → `**File References:**` followed by ≥ 1 entry of form `<path>:<line>` (or `<path> §<section>`) under a `.psfm` root; for v0.2+ write-back, additionally require the W2 anchor
  3. If anchor missing → output `{status: "missing_citations", advice: "..."}` (no LLM reasoning needed).
  4. If anchor present but suspicious (citations look like "common knowledge", "obvious", or are empty) → fall back to LLM judgement.
- **Why lightweight:** keeps latency low and reduces false positives. Reviewer runs on every response, so it must be fast.
- **Why W3 is also reviewed:** in v0.1 W3 responses already reference user-project files; the anchor check makes that grounding explicit and prevents the agent from paraphrasing without naming the file. From v0.2 (`.psfm` write-back), any generated SimTalk must carry the W2-style API Evidence Table — same reviewer, same contract, no architecture change needed.

### 2.3 Skills

| Skill | Purpose | Key procedure | Citation anchor |
|-------|---------|---------------|-----------------|
| **`plantsim-kb-qa`** | Documentation Q&A | search_help → format answer → append `**Sources:**` list | `**Sources:**` |
| **`plantsim-code-author`** | SimTalk authoring & review | Symbol Lookup Cascade → write code → emit `API Evidence Table` | `**API Evidence Table**` |
| **`plantsim-project-analyst`** | `.psfm` project queries | classify question (locate / trace / summarise) → call appropriate MCP tools | `**File References:**` (v0.2 write-back adds `**API Evidence Table**`) |

Skills are loaded by the agent only when its intent matches, keeping context cost predictable.

### 2.4 MCP server — `plantsim-mcp`

- **Stack:** Python ≥ 3.10, FastMCP, SQLite (stdlib), PyYAML, optional `markitdown` / `docling` for PDF → MD conversion.
- **Entry point:** `python -m plantsim_mcp.server` or `uvx plantsim-copilot-mcp`.
- **Configuration:** `plantsim_mcp/config.py` reads paths from `~/.plantsim-agent/config.toml` (created by `build_kb.py`). Defaults to dev path `../knowledge_base/markdown/pts_help_2504/` so contributors can debug without copying KB into the repo.

#### Tool contracts (v0.1 draft)

> Schemas are illustrative; final JSON-schema definitions live in `mcp/plantsim_mcp/tools/*.py`.

| Tool | Input | Output |
|------|-------|--------|
| `search_help(query: str, top_k: int = 5)` | natural-language query | list of `{file_path, section, snippet, score}` |
| `get_api(object: str, method?: str)` | object name (e.g. `Buffer`), optional method | structured `{object, methods: [{name, signature, summary, source}]}` |
| `find_method(name: str, scope?: str)` | method name, optional sub-path of project | list of `{file_path, parent_object, signature}` |
| `find_callers(name: str)` | method name | list of `{caller_file, caller_object, line_excerpt}` |
| `get_object_graph(scope?: str)` | optional sub-path | list of `{object, type, connections: [...]}` |
| `search_code(pattern: str, regex: bool = false, scope?: str)` | pattern, optional regex flag | list of `{file_path, line_no, snippet}` |
| `validate_simtalk(code: str)` | SimTalk source | list of `{rule_id, line, severity, message}` |

### 2.5 Storage layer

- **`storage/base.py`** defines an `Index` abstract base class with `add_doc`, `search(query, top_k)`, `delete`, `rebuild`. This abstraction is the seam for swapping FTS5 → vector store in v0.2.
- **`storage/sqlite.py`** is the v0.1 implementation: a single SQLite file with three virtual FTS5 tables (`docs`, `code_units`) plus relational tables for the `.psfm` call graph (`callers(caller_id, callee_id, kind)`).
- **DB location:** `~/.plantsim-agent/indices/{help.db, project.db}` (path configurable).

### 2.6 Indexers

| Indexer | Job |
|---------|-----|
| `indexers/help_pdf_to_md.py` | Convert a Help PDF/CHM to markdown using `markitdown` (fast, CPU-only) or `docling` (better tables) |
| `indexers/help_md_to_fts.py` | Walk markdown tree, split on `## / ###` headers, write into FTS5 |
| `indexers/psfm_parser.py` | Parse a `.psfm` folder. For each YAML, extract `Name`, `InternalClassType`, `Program` field, attribute references, and method call sites |
| `indexers/psfm_indexer.py` | Take the parser AST → populate `code_units` FTS5 + caller graph table |

## 3. Data flow examples

### W1 — Documentation Q&A

```
user: "How does Buffer.numMU behave on a blocked station?"
   │
   ▼ orchestrator → kb-qa skill procedure
   │
   ▼ MCP: search_help("Buffer numMU blocked")
   │     → [{file: ".../Buffer.md", section: "Attributes", snippet: "..."}]
   │
   ▼ agent formulates answer + appends:
       **Sources:**
       - knowledge_base/.../Buffer.md → §Attributes (numMU)
   │
   ▼ citation-reviewer subagent
   │     ├─ anchor `**Sources:**` present?  ✓
   │     ├─ at least one source line?       ✓
   │     └─ status: "ok"
   │
   ▼ response shown to user
```

### W2 — Code authoring with reviewer

```
user: "Write a method that logs MU throughput per shift to a DataTable."
   │
   ▼ orchestrator → code-author skill
   │
   ▼ Symbol Lookup Cascade for: DataTable.append, MU, currentShift, ...
   │     → all hit in API index (Tier 1) or via MCP search_help
   │
   ▼ emit SimTalk code + API Evidence Table
   │
   ▼ citation-reviewer
   │     ├─ Evidence table present?    ✓
   │     ├─ every Source non-empty?    ✓
   │     └─ status: "ok"
   │
   ▼ response shown to user
```

### W3 — Project query (reviewer checks file-ref anchor)

```
user: "find all callers of InitFleet in the open .psfm project"
   │
   ▼ orchestrator → project-analyst skill
   │
   ▼ MCP: find_callers("InitFleet")
   │     → [{caller_file: "Init.yaml", caller_object: "Init", line_excerpt: "&InitFleet.executeIn(0)"}]
   │
   ▼ agent formulates answer + appends:
       **File References:**
       - Init.yaml:42 — `&InitFleet.executeIn(0)`
   │
   ▼ citation-reviewer subagent
   │     ├─ anchor `**File References:**` present?  ✓
   │     ├─ at least one entry under the .psfm root? ✓
   │     └─ status: "ok"
   │
   ▼ response shown to user

  (v0.2 write-back path will additionally emit an API Evidence Table
   for any newly generated SimTalk — same reviewer covers it.)
```

## 4. Cross-cutting concerns

### 4.1 Configuration

- A single TOML file at `~/.plantsim-agent/config.toml`:
  ```toml
  [paths]
  help_kb_root      = "C:/.../my-pts-help/markdown"
  index_dir         = "C:/Users/.../.plantsim-agent/indices"
  default_project   = ""   # optional; otherwise MCP tools require explicit project_path
  
  [features]
  retrieval         = "fts5"  # v0.2: "fts5" | "vector" | "hybrid"
  ```
- The MCP server reads this at startup; the install script writes it on first run.

### 4.2 Logging

- MCP server uses `logging` module → file at `~/.plantsim-agent/logs/server.log`, rotated daily.
- No telemetry; nothing leaves the user's machine.

### 4.3 Testing

- `mcp/tests/` — `pytest` suite, fixture indices under `mcp/tests/fixtures/`.
- `tests/` (repo root) — integration tests that exercise the full agent → MCP → storage path against a tiny fixture KB and a stub `.psfm` project.

### 4.4 Packaging & install

- The MCP server is a regular Python package; `mcp/pyproject.toml` exposes a `plantsim-copilot-mcp` console-script entry point so `uvx plantsim-copilot-mcp` works directly.
- `scripts/install.ps1` and `install.sh` create symbolic links from this repo's `agents/` and `skills/` into `~/.copilot/agents/` and `~/.copilot/skills/`. Symbolic links (not copies) so that `git pull` in the repo immediately updates the installed customisations.

## 5. Decisions log

The following decisions are settled for v0.1; revisiting them requires a documented rationale.

| # | Decision | Rationale |
|---|----------|-----------|
| D1 | Custom **Agent**, not just Skill | Skills cannot invoke subagents; reviewer must run after generation |
| D2 | **Citation-only** reviewer (not full code review) | Avoids LLM-on-LLM cascade; cheap and high signal |
| D3 | **SQLite FTS5** for v0.1, abstract `Index` interface for v0.2 vector store | Zero external deps now; clean upgrade path |
| D4 | **Python** for MCP server | Aligned with simulation community; rich markdown/yaml/sqlite tooling |
| D5 | Ship **no** Siemens content | Strict Siemens IP terms |
| D6 | **MIT** license | Maximally permissive; helps commercial Plant Sim users adopt |
| D7 | Symbolic-link install | Repo updates apply instantly without re-running installer |
| D8 | `.psfm` is **read-only** in v0.1 | Write-back needs more safety design (git/backup gating) |
| D9 | No telemetry | Open-source community sensitivity; keeps trust low-friction |

## 6. Open implementation questions

These are not blockers for Phase 1 but should be settled during Phase 2:

- **Markdown chunking granularity for FTS5** — by `##`, by `###`, or sliding-window? Affects recall vs precision.
- **`.psfm` Program field SimTalk extraction** — full lexer too heavy for v0.1; use regex to extract method references (e.g. `&methodName.executeIn` patterns) plus identifier scan? Acceptable false-positive rate?
- **Citation-reviewer fallback to LLM** — what trigger? Currently "anchor missing OR source text matches one of {common knowledge, obvious, ...}" — needs a small false-positive eval set.
- **uvx availability in restricted corporate networks** — first-install behaviour to confirm; fall back to `pip install -e .` instructions if blocked.
