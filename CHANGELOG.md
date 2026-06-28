# Changelog

All notable changes to this project will be documented in this file.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Project scaffolding: directory structure, `.gitignore`, `.gitattributes`, MIT `LICENSE`
- `README.md` with project overview, trademark notice, and roadmap pointer
- Specification documents: `docs/spec.md`, `docs/architecture.md`, `docs/roadmap.md`
- KB build guide stub: `docs/kb-build-guide.md`
- Self-authored sample knowledge base in `kb_minimal/`
- `kb_local/` placeholder + `kb_local/README.md` for user-private KB (gitignored)
- `scripts/install.ps1` and `scripts/uninstall.ps1` to symlink agents/skills into `~/.copilot/`

### Changed
- Repository relocated out of OneDrive to `~/.copilot/plantsim-agent/` to avoid cloud-sync corruption of `.git/`
- `.gitignore` rewritten: removed stale `pts_ai/` references; added `kb_local/*` rule

[Unreleased]: https://github.com/JackySummerfield/plantsim-agent/compare/HEAD
