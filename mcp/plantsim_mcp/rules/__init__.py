"""SimTalk-validation rules engine.

Each rule is a tiny callable that consumes a list of source lines and
yields :class:`Issue` records. Rules are intentionally regex-level and
**stateless** — SimTalk has no public parser we can lean on, so we
look for syntactic patterns the P&G Modeling Standards explicitly
call out:

* SimTalk 1.0 → 2.0 outdated identifiers (per
  ``12_SimTalk_Reference/05_Outdated_SimTalk_Names`` in the PTS Help).
* Bare ``.move()`` calls whose return value is dropped.
* ``var x := ...`` declarations without an explicit type annotation.
* SimTalk 1.0 declaration syntax markers (``is var``, ``is real``).

The rule registry is exposed so the MCP tool can selectively disable
rules via an ``ignore_rules`` parameter.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Issue record
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    rule_id: str
    severity: str  # "error" | "warning" | "info"
    line: int  # 1-based
    column: int  # 1-based; 0 if N/A
    message: str
    snippet: str
    fix_hint: str | None = None


# ---------------------------------------------------------------------------
# Outdated SimTalk identifier blacklist
# ---------------------------------------------------------------------------

# Curated subset from kb_local/pts_help_2504/12_SimTalk_Reference/
# 05_Outdated_SimTalk_Names.md. We keep the list small but high-signal;
# the full table has 400+ entries and is reachable via search_help when
# the user wants exhaustive coverage. Values are the 2.0 replacement.
OUTDATED_NAMES: dict[str, str] = {
    "__checkForLicense": "checkForLicense",
    "__setRandomSeedCounter": "setRandomSeedCounter",
    "Active": "ServerSocket (Socket) or IsShown (Chart)",
    "animIcon": "animation",
    "animMU": "animation",
    "AttributType": "AttributeType",
    "BarMode": "DisplayType",
    "blockingPercentage": "StatBlockingPortion",
    "BreakCtrl": "PauseCtrl",
    "BumpCtrl": "CollisionCtrl",
    "Bumped": "Collided",
    "commonFormat": "setCommonFormat",
    "createAttribute": "createAttr",
    "createBuildingBlock": "derive / duplicate",
    "createObject": "derive / duplicate",
    "deleteAttribute": "deleteAttr",
    "deleteBuildingBlock": "deleteObject",
    "DestList": "FwDestList",
    "DisplayMode": "DisplayType",
    "DistanceIsBelowLimit": "DistanceObjectBelowLimit",
    "emptyPercentage": "StatEmptyPortion",
    "entryOpen": "EntranceOpen",
    "executeSilentOld": "executeSilent",
    "ExitForNextEnteringMU": "ExitForMU",
    "exitSimple": "exitApplication",
    "failPercentage": "StatFailPortion",
    "FailImporterActive": "FailImp.Active",
    "freeEntry": "EntranceFree",
    "generationTable": "creationTable",
    "GenerationTableActive": "creationTable",
    "getAttributList": "getAttributeList",
    "BatChargeCnt": "StatBatChargeCount",
    "BatChargeStat": "StatBatChargePortion",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_COMMENT_RE = re.compile(r"(--|//).*$")
_BLOCK_COMMENT_OPEN = re.compile(r"/\*")
_BLOCK_COMMENT_CLOSE = re.compile(r"\*/")
_STRING_RE = re.compile(r'"([^"\\]|\\.)*"')


def _strip_noise(line: str) -> str:
    """Drop string literals and line comments so identifier scans don't match them."""
    no_strings = _STRING_RE.sub('""', line)
    no_comments = _COMMENT_RE.sub("", no_strings)
    return no_comments


def _enumerate_code_lines(source: str) -> Iterator[tuple[int, str, str]]:
    """Yield ``(line_no_1based, raw_line, code_only_line)`` skipping block comments.

    Block comments ``/* ... */`` may span multiple lines; lines inside
    a block comment are yielded with an empty ``code_only_line``.
    """
    in_block = False
    for i, raw in enumerate(source.splitlines(), start=1):
        line = raw
        out = ""
        # Walk char-by-char to handle "/*" and "*/" on the same line.
        cursor = 0
        while cursor < len(line):
            if in_block:
                close = line.find("*/", cursor)
                if close == -1:
                    cursor = len(line)
                else:
                    cursor = close + 2
                    in_block = False
            else:
                open_ = line.find("/*", cursor)
                if open_ == -1:
                    out += line[cursor:]
                    cursor = len(line)
                else:
                    out += line[cursor:open_]
                    cursor = open_ + 2
                    in_block = True
        yield i, raw, _strip_noise(out)


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------


def rule_outdated_names(source: str) -> Iterator[Issue]:
    """R001: Flag SimTalk 1.0 names that have a 2.0 replacement."""
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in OUTDATED_NAMES) + r")\b"
    )
    for line_no, raw, code in _enumerate_code_lines(source):
        for match in pattern.finditer(code):
            name = match.group(1)
            yield Issue(
                rule_id="ST001",
                severity="warning",
                line=line_no,
                column=match.start() + 1,
                message=f"Outdated SimTalk identifier {name!r} — use {OUTDATED_NAMES[name]!r} instead.",
                snippet=raw.rstrip(),
                fix_hint=f"Replace {name} → {OUTDATED_NAMES[name]}",
            )


# Match `.move(...)` not preceded by an assignment operator, an if/while/
# stopuntil/waituntil keyword, or `return`.
_MOVE_CALL_RE = re.compile(r"\.move\s*\(")
_MOVE_OK_PREFIX_RE = re.compile(
    r"(:=|==|=|>|<|/=|!=|\breturn\b|\bif\b|\bwhile\b|\belseif\b|"
    r"\bwaituntil\b|\bstopuntil\b)\s*[^=]*$"
)


def rule_move_return_ignored(source: str) -> Iterator[Issue]:
    """R002: Flag ``X.move(Y)`` whose Boolean result is dropped."""
    for line_no, raw, code in _enumerate_code_lines(source):
        for match in _MOVE_CALL_RE.finditer(code):
            prefix = code[: match.start()]
            if _MOVE_OK_PREFIX_RE.search(prefix):
                continue
            # `mu.move` could also be a column / attribute name in a table
            # access. Skip if the next token is `[` (attribute access).
            tail = code[match.end():].lstrip()
            if tail.startswith("["):
                continue
            yield Issue(
                rule_id="ST002",
                severity="warning",
                line=line_no,
                column=match.start() + 1,
                message=".move() return value is ignored. Capture it and "
                "branch on failure to avoid silent simulation stalls.",
                snippet=raw.rstrip(),
                fix_hint=(
                    "var ok : boolean := X.move(Y)\nif not ok\n    debug\nend"
                ),
            )


# `var name := value` without `: type` between name and `:=`.
# Excludes `var name : type := value` and `var name : type`.
_VAR_UNTYPED_RE = re.compile(
    r"\bvar\s+([A-Za-z_][A-Za-z0-9_]*(?:\s*,\s*[A-Za-z_][A-Za-z0-9_]*)*)\s*:="
)


def rule_var_untyped(source: str) -> Iterator[Issue]:
    """R003: Flag ``var x := ...`` declarations without an explicit type."""
    for line_no, raw, code in _enumerate_code_lines(source):
        for match in _VAR_UNTYPED_RE.finditer(code):
            names = match.group(1)
            yield Issue(
                rule_id="ST003",
                severity="info",
                line=line_no,
                column=match.start() + 1,
                message=f"Local variable(s) {names!r} declared without an explicit type — "
                "defaults to 'any' and runs slower.",
                snippet=raw.rstrip(),
                fix_hint=f"var {names} : <type> := ...",
            )


# SimTalk 1.0 declaration form: `is var <name> : <type>` or `is <type>`.
_SIMTALK_1_DECL_RE = re.compile(r"\bis\s+(var\b|real\b|integer\b|boolean\b|string\b|object\b)")


def rule_simtalk_1_decl(source: str) -> Iterator[Issue]:
    """R004: Flag SimTalk 1.0 ``is var`` / ``is <type>`` declarations."""
    for line_no, raw, code in _enumerate_code_lines(source):
        for match in _SIMTALK_1_DECL_RE.finditer(code):
            yield Issue(
                rule_id="ST004",
                severity="warning",
                line=line_no,
                column=match.start() + 1,
                message="SimTalk 1.0 declaration syntax detected. "
                "Convert to SimTalk 2.0 (`var name : type`).",
                snippet=raw.rstrip(),
                fix_hint=(
                    "Use the IDE command 'Convert all Methods to New Syntax' "
                    "(right-click Basis with Shift held) or rewrite the line "
                    "as `var name : type := value`."
                ),
            )


# ---------------------------------------------------------------------------
# Registry + entry point
# ---------------------------------------------------------------------------


RULES: dict[str, Callable[[str], Iterator[Issue]]] = {
    "ST001": rule_outdated_names,
    "ST002": rule_move_return_ignored,
    "ST003": rule_var_untyped,
    "ST004": rule_simtalk_1_decl,
}


def validate(source: str, ignore_rules: list[str] | None = None) -> list[Issue]:
    """Run every enabled rule against ``source`` and return all issues.

    Issues are sorted by ``(line, column, rule_id)`` for stable output.
    """
    skip = set(ignore_rules or [])
    issues: list[Issue] = []
    for rule_id, fn in RULES.items():
        if rule_id in skip:
            continue
        issues.extend(fn(source))
    issues.sort(key=lambda i: (i.line, i.column, i.rule_id))
    return issues
