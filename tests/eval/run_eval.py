"""PlantSim-Agent evaluation runner (Phase 4 #2).

Two independent suites:

1. **QA recall** (``qa_questions.yaml``) — calls each MCP tool directly
   against an index built from ``kb_minimal/`` and asserts the expected
   ``file_path`` / ``section`` substrings appear in the top-K hits.
   Tests the *underlying retrieval*, not the LLM.

2. **Citation recall** (``citation_recall.yaml``) — exercises a pure
   Python port of the citation-reviewer's regex contract against fixture
   response bodies and asserts the verdict matches ``expected.status``.
   Tests the *reviewer's recall*, not the LLM either.

Run manually::

    python tests/eval/run_eval.py

Or as a separate pytest job (slow, opt-in)::

    pytest tests/eval -v

The runner is intentionally pytest-friendly when imported: each suite
exposes a ``run_*_suite()`` function returning a ``Result`` namedtuple
so a thin test file can ``assert`` on the score.
"""

from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Allow `python tests/eval/run_eval.py` from a fresh clone.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_MCP_SRC = _REPO_ROOT / "mcp"
if str(_MCP_SRC) not in sys.path:
    sys.path.insert(0, str(_MCP_SRC))

import yaml  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
QA_YAML = EVAL_DIR / "qa_questions.yaml"
CITATION_YAML = EVAL_DIR / "citation_recall.yaml"
KB_MINIMAL = _REPO_ROOT / "kb_minimal"


# ---------------------------------------------------------------------------
# Citation-reviewer regex port
# ---------------------------------------------------------------------------

# Forbidden phrases drawn verbatim from agents/citation-reviewer.agent.md
# (Check 2 — source-text quality).
_FORBIDDEN_PHRASES = [
    "common knowledge",
    "obvious",
    "general oop",
    "simtalk standard",
    "general simtalk",
    "standard library",
    "from training data",
    "well known",
    "by analogy",
]

# W1: bullet under **Sources:** whose link target contains a '/'
_W1_SOURCES_HEADER = re.compile(r"\*\*Sources:\*\*", re.MULTILINE)
_W1_BULLET = re.compile(r"^\s*[-*]\s*\[[^\]]+\]\(([^)]+)\)", re.MULTILINE)

# W2: markdown table header containing all three columns (case-sensitive
# per spec — using exact substring match on header row).
_MD_TABLE_ROW = re.compile(r"^\s*\|.+\|\s*$", re.MULTILINE)

# W3: any inline markdown link with a path-like target that's NOT
# an http/https/mailto URL.
_W3_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")

# Refusal discipline
_REFUSAL = re.compile(r"❌\s*Cannot verify:", re.MULTILINE)
_CASCADE_OR_SEARCHED = re.compile(r"^(Cascade results:|Searched:)", re.MULTILINE)


@dataclass
class ReviewerVerdict:
    status: str  # ok | missing_citations | suspicious_citations | malformed_refusal
    workflow: str
    detail: str | None = None
    offenders: list[dict[str, str]] = field(default_factory=list)


def review(body: str, workflow: str) -> ReviewerVerdict:
    """Pure-Python implementation of the citation-reviewer's contract."""
    workflow = workflow.upper()

    # Check 1 — anchor presence
    sources: list[str] = []  # the strings we will quality-scan in Check 2
    if workflow == "W1":
        if not _W1_SOURCES_HEADER.search(body):
            return ReviewerVerdict("missing_citations", workflow,
                                   "no '**Sources:**' header")
        # Grab text after the FIRST Sources: header
        tail = body[_W1_SOURCES_HEADER.search(body).end():]
        bullets = [m.group(1) for m in _W1_BULLET.finditer(tail)
                   if "/" in m.group(1)]
        if not bullets:
            return ReviewerVerdict(
                "missing_citations", workflow,
                "'**Sources:**' header present but no bullet with a path link",
            )
        sources = bullets

    elif workflow == "W2":
        table_match = _find_w2_table(body)
        if table_match is None:
            return ReviewerVerdict(
                "missing_citations", workflow,
                "no 'Symbol | Kind | Source' table found",
            )
        rows = table_match
        if not rows:
            return ReviewerVerdict(
                "missing_citations", workflow,
                "evidence table has no data rows",
            )
        for r in rows:
            if not r["source"]:
                return ReviewerVerdict(
                    "missing_citations", workflow,
                    f"row {r['symbol']!r} has empty Source cell",
                )
        sources = [r["source"] for r in rows]

    elif workflow == "W3":
        path_links = [m.group(2) for m in _W3_LINK.finditer(body)
                      if "/" in m.group(2)
                      and not m.group(2).lower().startswith(("http:", "https:", "mailto:"))]
        if not path_links:
            return ReviewerVerdict(
                "missing_citations", workflow,
                "no inline [text](path) link with a slashed path",
            )
        sources = path_links
    else:
        raise ValueError(f"unknown workflow: {workflow!r}")

    # Check 2 — source-text quality
    offenders: list[dict[str, str]] = []
    for s in sources:
        lower = s.lower()
        for ph in _FORBIDDEN_PHRASES:
            if ph in lower:
                offenders.append({"source": s, "phrase": ph})
                break
    if offenders:
        return ReviewerVerdict(
            "suspicious_citations", workflow,
            f"{len(offenders)} forbidden phrase(s) in Source cells/links",
            offenders=offenders,
        )

    # Check 3 — refusal discipline
    for m in _REFUSAL.finditer(body):
        # Look in the 10 lines after the refusal for a Cascade/Searched block.
        after = body[m.end():]
        next_10_lines = "\n".join(after.splitlines()[:10])
        if not _CASCADE_OR_SEARCHED.search(next_10_lines):
            return ReviewerVerdict(
                "malformed_refusal", workflow,
                "❌ Cannot verify without Cascade results/Searched within 10 lines",
            )

    return ReviewerVerdict("ok", workflow)


def _find_w2_table(body: str) -> list[dict[str, str]] | None:
    """Return parsed rows of the first table whose header has Symbol|Kind|Source."""
    lines = body.splitlines()
    for i, line in enumerate(lines):
        if "|" not in line:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if {"Symbol", "Kind", "Source"}.issubset(set(cells)):
            # Found header. Skip the separator row (i+1), parse data rows.
            try:
                hdr = cells
                sym_i, kind_i, src_i = (hdr.index("Symbol"),
                                        hdr.index("Kind"),
                                        hdr.index("Source"))
            except ValueError:
                continue
            rows: list[dict[str, str]] = []
            for j in range(i + 2, len(lines)):
                raw = lines[j].strip()
                if not raw.startswith("|"):
                    break
                cells_j = [c.strip() for c in raw.strip("|").split("|")]
                if len(cells_j) <= max(sym_i, kind_i, src_i):
                    continue
                rows.append({
                    "symbol": cells_j[sym_i],
                    "kind": cells_j[kind_i],
                    "source": cells_j[src_i],
                })
            return rows
    return None


# ---------------------------------------------------------------------------
# Suite runners
# ---------------------------------------------------------------------------

@dataclass
class Result:
    name: str
    total: int
    passed: int
    failures: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.passed == self.total


def _build_isolated_help_index() -> Path:
    """Build a help.db from kb_minimal/ in a temp dir and return its path."""
    from plantsim_mcp.config import load
    from plantsim_mcp.indexers.help_md_to_fts import build
    from plantsim_mcp.storage.sqlite import SQLiteFTSIndex

    tmp = Path(tempfile.mkdtemp(prefix="psim_eval_"))
    os.environ["PLANTSIM_AGENT_HOME"] = str(tmp)
    # Write a minimal config so load() returns the right roots
    cfg_text = (
        "[paths]\n"
        f'index_dir = "{tmp.as_posix()}/indices"\n'
        f'help_kb_roots = ["{KB_MINIMAL.as_posix()}"]\n'
    )
    (tmp / "config.toml").write_text(cfg_text, encoding="utf-8")
    cfg = load()
    db_path = cfg.paths.index_dir / "help.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with SQLiteFTSIndex(db_path) as idx:
        build(cfg.paths.help_kb_roots, idx)
    return db_path


def run_qa_suite(verbose: bool = True) -> Result:
    from plantsim_mcp.config import load
    from plantsim_mcp.tools import get_api as get_api_tool
    from plantsim_mcp.tools import search_help as search_help_tool

    _build_isolated_help_index()
    cfg = load()

    cases: list[dict[str, Any]] = yaml.safe_load(QA_YAML.read_text(encoding="utf-8"))
    result = Result(name="QA recall", total=len(cases), passed=0)

    for case in cases:
        tool = case["tool"]
        args = case.get("args", {})
        top_k = case.get("top_k", 5)
        expected = case["expected"]
        min_match = case.get("min_match", len(expected))

        if tool == "search_help":
            hits = search_help_tool.search_help(
                query=args["query"], top_k=top_k, config=cfg
            )
        elif tool == "get_api":
            ret = get_api_tool.get_api(
                name=args["name"], top_k=top_k, config=cfg
            )
            hits = ret.get("hits", [])
        else:
            result.failures.append(f"{case['id']}: unknown tool {tool!r}")
            continue

        matched = _count_matches(hits, expected)
        if matched >= min_match:
            result.passed += 1
            if verbose:
                print(f"  PASS {case['id']}  ({matched}/{len(expected)} expected hits)")
        else:
            msg = f"{case['id']}: matched {matched}/{min_match} (got: {[h.get('file_path','') for h in hits]})"
            result.failures.append(msg)
            if verbose:
                print(f"  FAIL {msg}")

    return result


def _count_matches(hits: list[dict[str, Any]], expected: list[dict[str, str]]) -> int:
    n = 0
    for exp in expected:
        fc = exp["file_contains"]
        sc = exp.get("section_contains")
        for h in hits:
            fp = h.get("file_path", "")
            sec = h.get("section", "")
            if fc in fp and (sc is None or sc in sec):
                n += 1
                break
    return n


def run_citation_suite(verbose: bool = True) -> Result:
    cases: list[dict[str, Any]] = yaml.safe_load(
        CITATION_YAML.read_text(encoding="utf-8")
    )
    result = Result(name="Citation recall", total=len(cases), passed=0)
    for case in cases:
        verdict = review(case["body"], case["workflow"])
        want = case["expected"]["status"]
        if verdict.status == want:
            result.passed += 1
            if verbose:
                print(f"  PASS {case['id']}  (verdict={verdict.status})")
        else:
            msg = f"{case['id']}: expected {want!r}, got {verdict.status!r} ({verdict.detail})"
            result.failures.append(msg)
            if verbose:
                print(f"  FAIL {msg}")
    return result


def main() -> int:
    print("=" * 60)
    print("PlantSim-Agent evaluation")
    print("=" * 60)
    qa = run_qa_suite()
    print(f"\n[QA recall]       {qa.passed}/{qa.total} passed")
    cit = run_citation_suite()
    print(f"[Citation recall] {cit.passed}/{cit.total} passed")
    failures = qa.failures + cit.failures
    if failures:
        print("\nFailures:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nAll suites green.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
