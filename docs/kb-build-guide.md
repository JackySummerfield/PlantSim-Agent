# Building Your Local Knowledge Base

This guide walks you through the complete flow: **download the official Help PDF → convert to markdown → index into the MCP server's searchable database**. The whole process takes ~10 minutes.

## Why you need to build it locally

Siemens Plant Simulation Help is copyrighted. This project **does not ship the Help content** — instead you supply your own licensed copy and the indexer builds a local search database that never leaves your machine.

## Prerequisites

| Item | Notes |
|------|-------|
| **Siemens account** | To download the Help PDF |
| **Python ≥ 3.10** | With the MCP server installed (`pip install -e mcp/`) |
| **markitdown** | `pip install markitdown[all]` (included if you did `pip install -e "mcp/[indexers]"`) |
| **~500 MB disk** | For the markdown + SQLite index |

## Step-by-step

### 1. Download the Plant Simulation Help PDF

1. Open [Plant Simulation Help](https://docs.sw.siemens.com/zh-CN/doc/297028302/PL20250108338137660.PlantSimulation/Help_Start_Page) (or the English version)
2. Log in with your Siemens account
3. Click **"参考文档 PDF"** (upper right corner) / **"Reference Documentation PDF"**
4. Save the PDF somewhere (e.g. `~/Downloads/PlantSimulation_Help.pdf`)

### 2. Convert the PDF to indexed-ready markdown

```powershell
python scripts/convert_help_pdf.py ~/Downloads/PlantSimulation_Help.pdf -o ~/pts_help_md
```

This runs 3 steps automatically:
1. **markitdown** — converts the entire PDF to markdown (~5–10 min, CPU-only)
2. **Clean** — strips page headers/footers, copyright preamble, image placeholders
3. **Code-tag** — wraps SimTalk snippets in ` ```simtalk ` fenced blocks

Output: `~/pts_help_md/_code_tagged.md` (~7–9 MB)

### 3. Index into the knowledge base

```powershell
plantsim-copilot-mcp build-kb --fullmd-src ~/pts_help_md/_code_tagged.md --chapters 11,12,13,15
```

This builds `help.db` (~30 MB) with ~4000 searchable entries covering:
- **Ch 11**: Objects Reference (all Material Flow / Resource / Information Flow objects)
- **Ch 12**: SimTalk Reference (all functions, operators, types)
- **Ch 13**: 3D Reference
- **Ch 15**: Add-Ins Reference

### 4. Verify

```text
/plantsim-copilot 怎么让 Buffer 设置有限容量？
```

The agent should answer with a `**Sources:**` block citing specific Help sections.

## One-shot (for CI / scripting)

If you want to do everything in one go after download:

```powershell
# Convert
python scripts/convert_help_pdf.py ./PlantSimulation_Help.pdf -o ./pts_help_md

# Init config (non-interactive) + build index
plantsim-copilot-mcp init --non-interactive `
    --fullmd-src ./pts_help_md/_code_tagged.md `
    --chapters 11,12,13,15 `
    --kb-root ./kb_minimal `
    --build
```

## Adding other documents

The same pattern works for any document you want in the KB:

1. Convert to markdown (any tool: markitdown, docling, manual…)
2. Place it in `kb_local/` (gitignored, stays on your machine)
3. Either add the directory to `~/.plantsim-agent/config.toml` under `help_kb_roots`, or rerun `plantsim-copilot-mcp init`

Example — adding your team's modeling standards:

```powershell
# Place documents
mkdir kb_local/modeling-standards
cp my_standards.md kb_local/modeling-standards/

# Re-index
plantsim-copilot-mcp build-kb --root kb_local/modeling-standards --root kb_minimal
```

## Higher-quality conversion (optional)

If you need better table rendering (e.g. for reference chapters with complex property tables), use [docling](https://github.com/DS4SD/docling) instead of markitdown:

```powershell
pip install docling PyMuPDF
python scripts/convert_docling_batch.py PlantSimulation_Help.pdf -o ./pts_help_docling -b 100
```

> ⚠️ **docling is heavy**: requires ~3 GB model download, benefits greatly from GPU, and takes ~1 hour on CPU for the full Help PDF. For most users markitdown is sufficient.

For the full docling-based pipeline with batch processing, resume support, and advanced post-processing, see the companion project [everything-to-md](https://github.com/JackySummerfield/everything-to-md) (if available).

## Updating after a Plant Simulation upgrade

When Siemens releases a new PTS version (e.g. 2504 → 2604):

1. Download the new PDF from the same link above
2. Rerun the same conversion command (output goes to a new directory)
3. Rebuild the index pointing at the new markdown

```powershell
python scripts/convert_help_pdf.py ./PlantSimulation_Help_2604.pdf -o ~/pts_help_2604
plantsim-copilot-mcp build-kb --fullmd-src ~/pts_help_2604/_code_tagged.md --chapters 11,12,13,15
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `markitdown` errors on the PDF | PDF might be password-protected or very old | Re-download from Siemens Support Center |
| Very slow markitdown (~20+ min) | Normal for a 5000-page PDF on slow machines | Be patient; or use the batch docling approach for resume support |
| `search_help` returns no results | Index not built or config paths wrong | Check `~/.plantsim-agent/config.toml` has the correct `fullmd_src` |
| SimTalk code blocks not formatted | The code-tag heuristic missed some blocks | Run with `--skip-code-tag` and manually review; file a GitHub issue with examples |
| Chapter content missing | markitdown headings differ from expected `# 11.` pattern | Open `_code_tagged.md` and search for `^# 1` to verify heading structure |

For unresolved issues, open a GitHub issue.
