# `kb_local/` — Your Private Knowledge Base

**Everything in this folder is gitignored** (except this `README.md` and the `.gitkeep` placeholder). It is the home for content that **must not** be pushed to GitHub:

- Markdown built from **Siemens Plant Simulation Help** (copyrighted — see [LICENSE notice](../LICENSE) and [README §Trademark](../README.md#trademark-notice))
- Company-internal modeling standards, naming conventions, project templates
- Notes, PDFs, scratch material you only want available to your own agent

The MCP server can read `kb_local/` together with the public `kb_minimal/` (and any other directory you list) when building indexes, so anything you drop here becomes searchable by the agent on your machine — but stays off the public repository.

## Suggested Layout

```
kb_local/
├── pts_help_2504/             # markdown converted from Plant Simulation 2504 Help
│   ├── 00_Overview/
│   ├── 01_Reference/
│   └── ...
├── pts_help_2404/             # multiple versions can co-exist (Phase v0.3)
├── modeling-standards/        # your team's internal modeling rules
├── project-templates/         # `.psfm` snippets, frame patterns
└── notes/                     # personal scratch
```

You can use any structure you like — the indexer walks the tree recursively and discovers Markdown files automatically. The [`docs/kb-build-guide.md`](../docs/kb-build-guide.md) walks through converting PTS Help into the recommended layout.

## Wiring It Up

Add the directories you want indexed to `~/.plantsim-agent/config.toml`:

```toml
[paths]
help_kb_roots = [
    "C:/Users/me/.copilot/plantsim-agent/kb_minimal",
    "C:/Users/me/.copilot/plantsim-agent/kb_local/pts_help_2504",
    "C:/Users/me/some-other-folder/extra-notes",
]
index_dir = "C:/Users/me/.plantsim-agent/indices"
```

The indexer aggregates all listed roots into a single `help.db`. Each root contributes its basename as a label so identical filenames across roots never collide. Missing directories are silently skipped, so listing `kb_local/...` before you've populated it is harmless.

## Refreshing After Re-conversion

If you re-convert PTS Help (e.g. a new release) in a separate workspace, [`scripts/sync-help-from-workspace.ps1`](../scripts/sync-help-from-workspace.ps1) mirrors that output into `kb_local/pts_help_<version>/`:

```powershell
# additive sync (default source = author workspace; override with -Source)
.\scripts\sync-help-from-workspace.ps1

# new version, true mirror
.\scripts\sync-help-from-workspace.ps1 -Version 2604 -Source "C:/work/pts_help_2604_md" -Mirror
```

Rebuild the index afterwards (a proper `build-kb` CLI is on the v0.1 roadmap).

## Why Not `~/.plantsim-agent/`?

Earlier drafts placed user KB outside the repo entirely. We moved it **inside** the repo (gitignored) so that:

- One project folder owns everything: code + private data
- Backups are simpler (copy the whole folder)
- The indexer doesn't need to handle two separate roots

Nothing in `kb_local/` will ever be committed — the [.gitignore](../.gitignore) rule `kb_local/*` ensures that.

## Verifying

After dropping files here, confirm git ignores them:

```powershell
cd ~/.copilot/plantsim-agent
git status
# Should NOT list anything new under kb_local/
git check-ignore -v kb_local/pts_help_2504/something.md
# Should print the matching ignore rule
```
