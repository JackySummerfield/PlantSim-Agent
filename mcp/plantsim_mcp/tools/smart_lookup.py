"""``smart_lookup`` MCP tool — one-shot intelligent help lookup.

Replaces the multi-step cascade that the LLM used to drive manually
(``get_api`` → retry with ``did_you_mean`` → ``search_help``). Now
the server does the entire cascade in a single tool call, cutting
round-trips from 5–10 down to 1.

Strategy priority:

1. **Exact** — if the query looks like an identifier (single token,
   CamelCase / snake_case), try ``find_by_section`` first.
2. **Suggestion retry** — if exact match fails but ``did_you_mean``
   has candidates, retry with the best suggestion automatically.
3. **FTS fallback** — free-text search across the entire help corpus.

The response always reports which strategy succeeded so the agent can
frame the answer correctly (exact match vs approximate).
"""

from __future__ import annotations

import re
from typing import Any

from ..config import Config, load
from ..storage.sqlite import SQLiteFTSIndex


_IDENTIFIER_RE = re.compile(r"^[\w_][\w\d_]*$")


def _looks_like_identifier(query: str) -> bool:
    """Heuristic: single token that looks like a SimTalk identifier."""
    tokens = query.strip().split()
    if len(tokens) == 1 and _IDENTIFIER_RE.match(tokens[0]):
        return True
    # Also match underscored names like str_to_dateTime
    if len(tokens) == 1:
        return bool(_IDENTIFIER_RE.match(tokens[0].replace("\\", "")))
    return False


def smart_lookup(
    query: str,
    top_k: int = 10,
    config: Config | None = None,
) -> dict[str, Any]:
    """One-shot intelligent lookup with automatic cascade.

    Parameters
    ----------
    query:
        Either a SimTalk identifier (``"SimTime"``, ``"str_to_dateTime"``)
        or a natural-language question (``"how to get model time as
        dateTime"``). The tool auto-detects which strategy to use.
    top_k:
        Maximum number of results (default 10).
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    dict
        ``{"query", "strategy", "hits", "did_you_mean"}``.

        * ``strategy`` — one of ``"exact"``, ``"suggestion"``, ``"fts"``,
          ``"none"``. Tells the caller how the hits were found.
        * ``hits`` — list of ``{"file_path", "section", "snippet"}``.
        * ``did_you_mean`` — populated only when strategy is ``"none"``
          (nothing found at all); gives the agent a last-resort retry
          option.

    Raises
    ------
    FileNotFoundError
        If the help index has not been built.
    """
    cfg = config or load()
    db_path = cfg.paths.help_db
    if not db_path.exists():
        raise FileNotFoundError(
            f"Help index not found at {db_path}. "
            "Run `plantsim-copilot-mcp build-kb` to create it."
        )

    clean_query = query.strip()
    if not clean_query:
        return {"query": query, "strategy": "none", "hits": [], "did_you_mean": []}

    with SQLiteFTSIndex(db_path) as idx:
        # ---- Stage 1: exact name lookup (if it looks like an identifier) ----
        if _looks_like_identifier(clean_query):
            hits = idx.find_by_section(clean_query, top_k=top_k)
            if hits:
                return {
                    "query": query,
                    "strategy": "exact",
                    "hits": [_hit_to_dict(h) for h in hits],
                    "did_you_mean": [],
                }

            # ---- Stage 2: suggestion retry ----
            suggestions = idx.suggest_entry_names(clean_query, limit=5)
            if suggestions:
                # Try the top suggestion
                retry_hits = idx.find_by_section(suggestions[0], top_k=top_k)
                if retry_hits:
                    return {
                        "query": query,
                        "strategy": "suggestion",
                        "suggested_name": suggestions[0],
                        "hits": [_hit_to_dict(h) for h in retry_hits],
                        "did_you_mean": suggestions[1:],
                    }

        # ---- Stage 3: FTS fallback ----
        fts_hits = idx.search(clean_query, top_k=top_k)
        if fts_hits:
            return {
                "query": query,
                "strategy": "fts",
                "hits": [_hit_to_dict(h) for h in fts_hits],
                "did_you_mean": [],
            }

        # ---- Nothing found ----
        # Last resort: try to suggest names even for multi-word queries
        # by extracting potential identifiers
        suggestions: list[str] = []
        tokens = clean_query.split()
        for token in tokens:
            if _IDENTIFIER_RE.match(token) and len(token) > 2:
                s = idx.suggest_entry_names(token, limit=3)
                suggestions.extend(s)
        # Deduplicate while preserving order
        seen: set[str] = set()
        unique_suggestions: list[str] = []
        for s in suggestions:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique_suggestions.append(s)
                if len(unique_suggestions) >= 5:
                    break

        return {
            "query": query,
            "strategy": "none",
            "hits": [],
            "did_you_mean": unique_suggestions,
        }


def _hit_to_dict(h: Any) -> dict[str, str]:
    return {
        "file_path": h.file_path,
        "section": h.section,
        "snippet": h.snippet or "",
    }
