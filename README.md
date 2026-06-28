<a id="readme-top"></a>

<div align="center">

# PlantSim-Agent

**An open-source GitHub Copilot agent for Siemens Plant Simulation / SimTalk developers.**

Bring AI assistance into the closed Plant Simulation ecosystem — knowledge-base Q&A, SimTalk code generation & review, and `.psfm` project analysis, all grounded in your own licensed documentation.

[Spec](./docs/spec.md) · [Architecture](./docs/architecture.md) · [Roadmap](./docs/roadmap.md) · [KB Build Guide](./docs/kb-build-guide.md)

</div>

---

## Table of Contents

- [PlantSim-Agent](#plantsim-agent)
  - [Table of Contents](#table-of-contents)
  - [About The Project](#about-the-project)
  - [Why](#why)
  - [Features](#features)
  - [Getting Started](#getting-started)
    - [Prerequisites](#prerequisites)
    - [Installation](#installation)
    - [Building Your Local Knowledge Base](#building-your-local-knowledge-base)
  - [Usage](#usage)
  - [Architecture Overview](#architecture-overview)
  - [Roadmap](#roadmap)
  - [Contributing](#contributing)
  - [License](#license)
  - [Acknowledgments](#acknowledgments)
  - [Trademark Notice](#trademark-notice)

---

## About The Project

Siemens Plant Simulation is a powerful discrete-event simulation tool, but its ecosystem is closed: documentation, modelling conventions, and the SimTalk 2.0 scripting language are not part of any mainstream AI training corpus. As a result, general-purpose AI assistants either refuse to help, hallucinate APIs, or produce SimTalk 1.0 syntax that no longer compiles.

**PlantSim-Agent** closes that gap. It is a GitHub Copilot agent + MCP server combination that gives Plant Simulation developers an AI pair-programmer **grounded in real documentation** and **aware of their actual `.psfm` project**.

## Why

| Pain point | How this project addresses it |
|---|---|
| LLMs fabricate Plant Simulation APIs | Every answer cites a concrete documentation source; a `citation-reviewer` subagent rejects responses that lack citations |
| SimTalk 2.0 vs 1.0 confusion | Hard-coded rule set + validator catches legacy syntax |
| Long chat sessions drift away from standards | Code-author skill re-injects modelling standards on every turn |
| `.psfm` projects are folders of hundreds of YAML files | MCP server pre-indexes the project so the agent can do `find_method`, `find_callers`, `search_code` instantly |
| Siemens documentation is copyrighted and cannot be redistributed | Users build their **own** local knowledge base from their **own** licensed Help; this repository ships only conversion tools and a small self-authored sample KB |

## Features

PlantSim-Agent provides three task-oriented capabilities, exposed as a single Copilot agent that routes by intent:

1. **Knowledge-Base Q&A** — Ask about Plant Simulation features, object APIs, SimTalk syntax. Answers cite the exact Help section.
2. **SimTalk Code Assistant** — Generate, refactor, debug, or review SimTalk 2.0 snippets. Every API used is listed with its source.
3. **`.psfm` Project Analyst** — Point the agent at a Plant Simulation model folder; ask "where is method X called?", "summarise this object", or "show the call graph".

All three flows are gated by a lightweight `citation-reviewer` subagent that re-runs the response if required citations are missing.

## Getting Started

> ⚠️ **Status: pre-alpha (v0.1 in progress).** Phase 1 — repository scaffolding — is complete; agents, skills, and the MCP server are being built. Use the [Roadmap](./docs/roadmap.md) to track progress.

### Prerequisites

- **VS Code** with the **GitHub Copilot Chat** extension installed and signed in
- **Python ≥ 3.10** (for the MCP server)
- **Git**
- A licensed installation of **Siemens Tecnomatix Plant Simulation** (for SimTalk authoring) and access to its Help documentation (PDF or CHM) — *required only if you want full KB Q&A; a small sample KB is bundled for evaluation*

### Installation

1. **Enable Windows Developer Mode** (one-time, no admin needed):
   `Settings` → `Privacy & Security` → `For developers` → `Developer Mode: On`. This lets non-admin users create symbolic links.

2. **Clone into the recommended location.** Any path works, but `~/.copilot/plantsim-agent/` keeps everything Copilot-related under one home:

   ```powershell
   git clone https://github.com/JackySummerfield/plantsim-agent.git $HOME/.copilot/plantsim-agent
   cd $HOME/.copilot/plantsim-agent
   ```

   > ⚠️ **Do not clone into a OneDrive / Dropbox / iCloud / Google Drive folder.** Cloud sync corrupts `.git/objects/`. Your remote is GitHub — that is your only sync.

3. **Run the installer** (creates symlinks under `~/.copilot/agents/` and `~/.copilot/skills/` so VS Code Copilot picks them up):

   ```powershell
   .\scripts\install.ps1
   ```

   The installer is idempotent — rerun it any time you `git pull` new agents or skills. Use `.\scripts\uninstall.ps1` to remove just the symlinks (the repo itself is untouched).

4. **Register the MCP server in your Copilot `mcp.json`** — instructions will land with Phase 2 ([`docs/roadmap.md`](./docs/roadmap.md)).

5. **Reload VS Code** (`Ctrl+Shift+P` → `Developer: Reload Window`). The `PlantSim-Agent` agent should appear in the agent picker.

### Building Your Local Knowledge Base

The repository ships with two knowledge-base directories side by side, with very different visibility:

| Folder | Tracked in git? | Contents |
|---|---|---|
| [`kb_minimal/`](./kb_minimal/) | ✅ yes | Self-authored sample KB: SimTalk syntax cheat sheet, API index of public method names, modelling-standards template. Ships with the repo so anyone can evaluate the agent immediately. **Contains no Siemens content.** |
| [`kb_local/`](./kb_local/) | ❌ no — fully gitignored | **Your private KB.** Drop markdown converted from your licensed Plant Simulation Help, plus any company-internal modelling standards, project templates, or notes. The MCP server indexes both folders together but `kb_local/` never leaves your machine. |

For the full Help-to-markdown conversion workflow, see [`docs/kb-build-guide.md`](./docs/kb-build-guide.md).

## Usage

Once installed, in any VS Code workspace open Copilot Chat and select **PlantSim-Agent** from the agent picker (or type `/plantsim-copilot`).

```text
/plantsim-copilot How do I make a Worker ignore service requests during a break?
```

```text
/plantsim-copilot Write a SimTalk method that logs MU throughput per shift to a DataTable.
```

```text
/plantsim-copilot In this .psfm project, find every method that calls InitPalletJackFleet.
```

## Architecture Overview

```
VS Code Copilot Chat
   ↓
[plantsim-copilot.agent.md]    ← main orchestrator
   ↓ intent routing
   ├→ kb-qa skill        → MCP: search_help / get_api
   ├→ code-author skill  → MCP: search_help / get_api / validate_simtalk
   └→ project-analyst skill → MCP: find_method / find_callers / search_code / get_object_graph
                              ↓
                   plantsim-mcp server (Python + FastMCP)
                              ↓
                   SQLite FTS5 indices  ←  user-built local KB + .psfm project
```

The optional `citation-reviewer` subagent inspects KB Q&A and code-authoring responses to ensure each one carries verifiable source citations. See [`docs/architecture.md`](./docs/architecture.md) for the full design.

## Roadmap

- **v0.1** — KB Q&A · SimTalk code authoring · `.psfm` read-only project queries · citation reviewer
- **v0.2** — Vector search for KB · richer `validate_simtalk` (lexer/parser) · `.psfm` write-back with safety checks
- **v0.3+** — Call-graph visualisation · custom model providers · VS Code extension packaging

Full detail in [`docs/roadmap.md`](./docs/roadmap.md).

## Contributing

Contributions are very welcome — this project benefits enormously from anyone who knows Plant Simulation well. Guidelines will be added in `docs/contributing.md` (Phase 4).

In the meantime:

- Open an issue to discuss before sending a PR
- Do **not** submit any content extracted from Siemens documentation (text, screenshots, table excerpts) — see [Trademark Notice](#trademark-notice)
- All self-authored KB material in `kb_minimal/` must be your own summary, not a paste from Help

## License

Distributed under the MIT License. See [`LICENSE`](./LICENSE) for full text.

## Acknowledgments

- The Plant Simulation community on the SCC Forum, LinkedIn, and PSWiki for years of public knowledge sharing
- Steffen Bangsow's books for shaping the modelling vocabulary of an entire generation of users
- [GitHub Copilot Custom Agents](https://code.visualstudio.com/docs/copilot/customization/custom-agents) and [Agent Skills](https://code.visualstudio.com/docs/copilot/customization/agent-skills) for making this pattern possible
- [Model Context Protocol](https://modelcontextprotocol.io/) for the tool-server architecture

## Trademark Notice

This project is **not affiliated with, endorsed by, or sponsored by Siemens AG or Siemens Industry Software Inc.** "Siemens", "Plant Simulation", "Tecnomatix", and "SimTalk" are trademarks of Siemens or its affiliates and are used here only for nominative reference.

This repository does **not** redistribute Siemens documentation, the Plant Simulation Help, model libraries, or any other proprietary Siemens material. Knowledge-base content used by the agent must be built locally by each user from their own licensed copy of the Help.

<p align="right">(<a href="#readme-top">back to top</a>)</p>
