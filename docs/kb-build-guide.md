# Building Your Local Knowledge Base

> **Status:** v0.1 — the interactive wizard (Option A) is implemented and tested. The PDF/CHM → markdown converter pipeline (Option B step 1) is still on the roadmap; for now, point the wizard at a markdown KB you already have on disk (see [`kb_minimal/`](../kb_minimal/) for the expected shape).

## Why you need to build the KB locally

Siemens Plant Simulation's Help is copyrighted and may not be redistributed by anyone other than Siemens (see the [trademark notice](../README.md#trademark-notice)). This project therefore **does not ship the Help**. Instead, you supply your own licensed copy and the indexer turns it into a local searchable knowledge base that the MCP server queries.

Your KB never leaves your machine.

## What you need

1. A licensed installation of **Tecnomatix Plant Simulation** (any 2024+ release) — only required if you want to index the official Help. The bundled `kb_minimal/` works without one.
2. A **markdown** copy of whatever you want indexed. The wizard does **not** yet convert PDF/CHM for you; produce markdown using your preferred tool (`markitdown`, `marker`, etc. — see [`/memories/doc-conversion-lessons.md`](https://github.com/JackySummerfield/plantsim-agent/blob/main/docs/doc-conversion-lessons.md) for tips) or use the optional single-file **fullmd** path if you already have one.
3. Python ≥ 3.10 with the project's MCP server installed (see [`installation.md`](./installation.md)).
4. ~500 MB of free disk space (the markdown KB plus the SQLite index).

## Workflow

### Option A — interactive wizard (recommended)

```powershell
# Console-script (after `pip install -e mcp/`):
plantsim-copilot-mcp init

# Or from a fresh clone, no install required:
python scripts\build_kb.py
```

The wizard will:

1. Ask for one or more **markdown KB roots** (defaults to the bundled `kb_minimal/` if it can find it next to the package).
2. Optionally ask for a **PTS Help fullmd source** (single `.md`) and which chapters to slice — defaults to `[11, 12, 13, 15]`.
3. Optionally ask for a default **`.psfm` project folder** so `find_method` / `find_callers` / `get_object_graph` work out of the box.
4. Pick an **index output directory** (default: `$PLANTSIM_AGENT_HOME/indices`, normally `~/.plantsim-agent/indices`).
5. Write the resulting paths into `~/.plantsim-agent/config.toml`.
6. Offer to run the indexers right away — produces `help.db` and (if a project was given) `project.db`.

Expected duration on a typical laptop: under a minute for `kb_minimal/`; ~1–3 minutes for a full chapter-sliced fullmd.

### Option A (non-interactive) — for CI, cold installs, automation

Every prompt has a matching flag, so the same wizard drives unattended setup:

```powershell
plantsim-copilot-mcp init `
    --non-interactive `
    --kb-root .\kb_minimal `
    --kb-root C:\path\to\my_other_kb `
    --fullmd-src C:\path\to\PTS_Help.md `
    --chapters 11,12,13,15 `
    --project C:\path\to\Model.psfm `
    --index-dir $HOME\.plantsim-agent\indices `
    --build
```

Add `--force` to overwrite an existing `config.toml` without the confirmation prompt, or `--config <path>` to write somewhere other than `$PLANTSIM_AGENT_HOME/config.toml`.

### Option B — manual indexer invocation

If you prefer to control each step (e.g. re-indexing without touching `config.toml`), run the indexers individually:

```powershell
# markdown → FTS5
python -m plantsim_mcp.indexers.help_md_to_fts `
    --input  "C:/path/to/help_md" `
    --db     "$HOME/.plantsim-agent/indices/help.db"
```

## What if I do not have the Help yet?

The repository ships a tiny **sample KB** in [`kb_minimal/`](../kb_minimal/) — self-authored summaries of the most common Plant Simulation objects and SimTalk syntax. With sample KB alone you can:

- Try the agent's user interface
- Run the test suite
- Validate that the install scripts work

You **cannot** expect full answers from sample KB alone — it covers maybe 5 % of the surface area of the real Help. Build your local KB as soon as you can.

## Updating after a Plant Simulation upgrade

When you upgrade Plant Simulation (for example from `2504` to `2604`), rebuild the KB:

```powershell
plantsim-copilot-mcp build-kb --rebuild
```

The wizard re-converts the new Help and re-creates the index in place. Old indices are kept under `~/.plantsim-agent/indices/archive/` so you can roll back.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `markitdown` errors converting CHM | CHM extraction unreliable | Use the PDF source instead |
| Very slow conversion of a large PDF | Single-threaded markitdown | Be patient (5–10 min for 5000 pages); upgrading to `docling` (Phase 2) will help |
| `search_help` returns no results | Index not built or `config.toml` paths wrong | Run `plantsim-copilot-mcp config show` and verify paths |
| Garbled text in markdown output | Source PDF uses non-Unicode fonts | Re-export PDF from Siemens Support Center; older PDFs sometimes fail |

For unresolved issues, open a GitHub issue with the output of `plantsim-copilot-mcp diagnose`.
