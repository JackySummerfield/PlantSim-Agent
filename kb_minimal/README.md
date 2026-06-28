# `kb_minimal/` — Self-Authored Sample Knowledge Base

This folder contains a **small, self-authored** knowledge base shipped with the project. It is intentionally limited and is **not** a substitute for the full Plant Simulation Help.

## Why it exists

1. **Out-of-the-box usability.** A new user can try the agent without first running the Help-build pipeline.
2. **Reference for `kb-qa` and `code-author` skills.** The Tier 1 entries (always loaded into agent context) live here.
3. **Legal cleanliness.** Everything in this folder is written by the project's contributors. It contains no excerpted Siemens text.

## Files

| File | Role |
|------|------|
| [`simtalk-syntax-quick-ref.md`](./simtalk-syntax-quick-ref.md) | SimTalk 2.0 language cheat sheet (Tier 1, always loaded) |
| [`simtalk-api-index.md`](./simtalk-api-index.md) | One-line summaries of attributes/methods on the most common objects (Tier 1) |
| [`modeling-standards.md`](./modeling-standards.md) | General-purpose SimTalk / DataTable / naming / performance standards (Tier 2, loaded on demand) |
| [`knowledge-base-map.md`](./knowledge-base-map.md) | Template describing the layout the full user-built KB is expected to follow (used by the agent for "go-deeper" cascades) |
| `object-summary/` | Self-written one-page summaries of individual Plant Simulation objects (populated incrementally in v0.1 Phase 3) |

## What goes here vs what does **not** go here

✅ **Acceptable:**
- Original prose summarising publicly known Plant Simulation concepts (object purposes, modelling patterns)
- Listings of API **names** (attributes, methods) — names alone are not copyrightable
- Code patterns and best-practices written by the contributor
- Diagrams and tables created by the contributor

❌ **Not acceptable:**
- Verbatim or near-verbatim text from the Plant Simulation Help, manuals, training material, or any Siemens publication
- Screenshots or images from Siemens documentation
- Worked-example code that originates from Siemens samples, libraries, or tutorials
- Translated copies of Siemens content — translation does not strip copyright

If you are unsure whether material is acceptable, ask before adding it (open a draft PR or an issue).
