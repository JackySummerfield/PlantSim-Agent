# Evaluation Suites

> **Status:** v0.1 — 20 QA-recall + 10 citation-recall fixtures, 30/30 currently green against the bundled `kb_minimal/` corpus.

This directory contains slow, opt-in evaluation suites that verify the
*underlying tools* without putting an LLM in the loop:

- **QA recall** ([`qa_questions.yaml`](qa_questions.yaml)) — for each
  hand-written question, calls the relevant MCP tool (`search_help` /
  `get_api`) directly against an index built from `kb_minimal/` and
  asserts the expected file (and, optionally, section substring)
  appears in the top-K hits. This measures **retrieval recall**, not
  the agent's phrasing.
- **Citation recall** ([`citation_recall.yaml`](citation_recall.yaml)) —
  feeds fixture response bodies through a pure-Python port of the
  [`citation-reviewer`](../../agents/citation-reviewer.agent.md) regex
  contract and asserts each fixture earns the expected verdict
  (`ok` / `missing_citations` / `suspicious_citations` /
  `malformed_refusal`). This measures the **reviewer's recall** of
  citation defects, independent of the LLM that emits responses.

Neither suite calls a language model — they are deterministic regression
tests for the parts of the system we control.

## Running

```powershell
# Direct script (verbose progress + final summary):
python tests/eval/run_eval.py

# Or via pytest, with the opt-in flag:
pytest tests/eval --run-eval -v
```

Without `--run-eval` the pytest wrapper skips both tests so the eval
suite never blocks the main `pytest mcp/` unit-test run.

## Adding fixtures

- **QA**: append an entry to `qa_questions.yaml` with a unique `id`. Use
  `args.query` terms that actually appear in the indexed *body* text
  (the v0.1 FTS indexer does not include section titles in the
  searchable column — that's a [v0.2 vector-retrieval roadmap item](../../docs/roadmap.md)). Probe candidates with:

  ```powershell
  python -c "from plantsim_mcp.config import load; from plantsim_mcp.tools.search_help import search_help; cfg=load(); print(search_help('your query', config=cfg))"
  ```

- **Citation**: append an entry with a unique `id`, the `workflow`
  (`W1` / `W2` / `W3`), the `expected.status`, and the full markdown
  `body` to audit. The reviewer port lives in `run_eval.py::review()`.

## What it doesn't cover

- End-to-end LLM behaviour (intent routing, prompt-following, refusal
  discipline) — that needs human-in-the-loop testing against a real
  Copilot session.
- Real PTS Help indexing — the bundled `kb_minimal/` is intentionally
  small. Run your own evaluations against a private corpus from
  `kb_local/` if you need scale validation.
