"""``validate_simtalk`` MCP tool — lint a SimTalk source block.

Either pass raw ``source`` to validate it directly, or pass ``uuid``
to validate a Method body already indexed in the project DB. The
latter lets the agent run: ``find_method('Init') → validate_simtalk(uuid=...)``
without having to read the YAML again.
"""

from __future__ import annotations

from typing import Any

from ..config import Config
from ..rules import Issue, validate
from ._project_common import open_project_store


def _issue_to_dict(i: Issue) -> dict[str, Any]:
    return {
        "rule_id": i.rule_id,
        "severity": i.severity,
        "line": i.line,
        "column": i.column,
        "message": i.message,
        "snippet": i.snippet,
        "fix_hint": i.fix_hint,
    }


def validate_simtalk(
    source: str | None = None,
    uuid: str | None = None,
    ignore_rules: list[str] | None = None,
    config: Config | None = None,
) -> list[dict[str, Any]]:
    """Validate a SimTalk method body.

    Parameters
    ----------
    source:
        Raw SimTalk source. When supplied, ``uuid`` is ignored.
    uuid:
        UUID of an indexed Method. The tool reads ``code_units.body``
        from the project DB. Requires ``build-project`` to have run.
    ignore_rules:
        Rule IDs to skip (e.g. ``["ST003"]`` to silence the untyped-var
        suggestion). Default: run every rule.
    config:
        Optional pre-loaded :class:`~plantsim_mcp.config.Config`.

    Returns
    -------
    list of dict
        One entry per issue, sorted by ``(line, column, rule_id)``.

    Raises
    ------
    ValueError
        If neither ``source`` nor ``uuid`` was supplied.
    KeyError
        If ``uuid`` was supplied but no body exists for it in the index.
    FileNotFoundError
        If ``uuid`` was supplied but the project index has not been built.
    """
    if source is None and uuid is None:
        raise ValueError("validate_simtalk requires either 'source' or 'uuid'")

    if source is None:
        assert uuid is not None  # for mypy
        with open_project_store(config) as store:
            body = store.get_body(uuid)
        if body is None:
            raise KeyError(
                f"No SimTalk body indexed for uuid={uuid!r}. "
                "Use find_method to locate a Method with `has_body=true`."
            )
        source = body

    issues = validate(source, ignore_rules=ignore_rules)
    return [_issue_to_dict(i) for i in issues]
