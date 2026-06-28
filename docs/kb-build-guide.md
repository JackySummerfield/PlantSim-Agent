# Building Your Local Knowledge Base

> **Status:** stub for v0.1 Phase 1. The indexer scripts referenced here will land in Phase 2 (see [`roadmap.md`](./roadmap.md)). This page documents the **intended** workflow so users and contributors understand the contract.

## Why you need to build the KB locally

Siemens Plant Simulation's Help is copyrighted and may not be redistributed by anyone other than Siemens (see the [trademark notice](../README.md#trademark-notice)). This project therefore **does not ship the Help**. Instead, you supply your own licensed copy and the indexer turns it into a local searchable knowledge base that the MCP server queries.

Your KB never leaves your machine.

## What you need

1. A licensed installation of **Tecnomatix Plant Simulation** (any 2024+ release).
2. Either:
   - the Plant Simulation **Help PDF** (typically downloadable from the Siemens Support Center), or
   - the **CHM** file shipped with your install (`Plant Simulation X.chm` in the install directory).
3. Python ≥ 3.10 with the project's MCP server installed (see [`installation.md`](./installation.md)).
4. ~500 MB of free disk space (the markdown KB plus the SQLite index).

## Workflow (v0.1 target)

### Option A — interactive wizard (recommended)

```powershell
plantsim-copilot-mcp build-kb
```

The wizard will:

1. Ask where your Help PDF / CHM lives.
2. Convert it to markdown with [`markitdown`](https://github.com/microsoft/markitdown) (CPU-only, no GPU needed).
3. Split the markdown by `##` / `###` headings.
4. Load it into a SQLite FTS5 index at `~/.plantsim-agent/indices/help.db`.
5. Write the resulting paths into `~/.plantsim-agent/config.toml` so the MCP server picks them up.

Expected duration on a typical laptop: 2–5 minutes for a full Help PDF (~5000 pages).

### Option B — manual

If you prefer to control each step, run the indexers individually:

```powershell
# 1. PDF → markdown
python -m plantsim_mcp.indexers.help_pdf_to_md `
    --input  "C:/path/to/PlantSimulationHelp.pdf" `
    --output "C:/path/to/help_md"

# 2. markdown → FTS5
python -m plantsim_mcp.indexers.help_md_to_fts `
    --input  "C:/path/to/help_md" `
    --db     "$HOME/.plantsim-agent/indices/help.db"

# 3. Tell the server where everything lives
plantsim-copilot-mcp config set paths.help_kb_root "C:/path/to/help_md"
plantsim-copilot-mcp config set paths.index_dir   "$HOME/.plantsim-agent/indices"
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
