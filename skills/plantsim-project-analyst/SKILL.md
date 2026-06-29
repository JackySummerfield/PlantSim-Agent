---
name: plantsim-project-analyst
description: 'Analyse an indexed Plant Simulation .psfm project: locate Methods/objects, trace caller graphs, audit inheritance overrides, summarise material-flow neighbourhoods, and lint SimTalk for standards violations. Triggers: 分析项目, project audit, where is, where defined, find method, find caller, who calls, inheritance override, .psfm 分析, plant simulation project, material flow trace, validate simtalk, project lint, find override'
argument-hint: 'Name of the object / Method to investigate, or a free-text question about the indexed .psfm project'
user-invocable: true
disable-model-invocation: false
---

# Plant Simulation Project Analyst Skill

You analyse an **indexed** Siemens Plant Simulation `.psfm` project on
behalf of the user. You answer "where is X", "what calls Y", "what
overrides Z", and "is this Method clean?" — using the MCP tools, never
training data, never speculation.

> Pre-requisite: the project must already be indexed via
> `plantsim-copilot-mcp build-project --psfm <path>`. If a tool raises
> `FileNotFoundError`, instruct the user to run that command first.

This skill is **read-only**. It does not write code. For code authoring
hand off to `plantsim-code-author`; for help-doc questions hand off to
`plantsim-kb-qa`.

---

## Tools available

| Tool                              | Purpose                                                                                  |
| --------------------------------- | ---------------------------------------------------------------------------------------- |
| `find_method(name)`               | Locate a Method by name. Returns the parent **definition** + every overriding **child**. |
| `find_callers(name)`              | Identifier-aware FTS over SimTalk bodies — who mentions `<name>`?                        |
| `search_code(query)`              | Free-text FTS over SimTalk bodies — find a code pattern (`str_to_obj`, `executeIn`, …).  |
| `get_object_graph(name|uuid)`     | Inheritance parent + children + material-flow predecessors + successors of one object.    |
| `validate_simtalk(uuid=...)`      | Lint an indexed Method body (`ST001`–`ST004`). Use `source=` for ad-hoc snippets.        |

Every result you cite must point to the `file_path` the tool returned —
that's a real path inside the user's `.psfm` folder, so they can open it
directly in PTS.

---

## Three sub-procedures

The user's question maps to exactly one of these.

### Locate — "where is `X`?"

```
1. find_method(name=X)
   ├─ hits.role == "definition" only
   │     → Single definition, no overrides. Show it. Done.
   ├─ hits has both "definition" and "override"
   │     → INHERITANCE WARNING (see Inheritance Audit below).
   │       Show parent + every override with file paths.
   ├─ hits empty, did_you_mean non-empty
   │     → Show suggestions. Ask user which.
   └─ hits empty, did_you_mean empty
         → "Not found as a Method. Trying broader search…"
         → search_code(query=X, top_k=10) — maybe it's an attribute,
           a string literal, or a variable name mentioned in bodies.
         → If still empty: refuse, ask user for the surrounding context.
```

### Trace — "what calls `X`?" / "where is `X` used?"

```
1. find_callers(name=X, top_k=20)
   │  (rejects non-identifier queries — letters / digits / underscore only)
   │
   ├─ hits>0
   │     → Group by file_path. For each caller, show:
   │         - caller Method name + file_path
   │         - the snippet with [[X]] highlight
   │     → If hits == top_k, warn the user there may be more.
   │
   └─ hits=0
         → Try search_code(query=X) — broader (allows spaces, regex-y).
         → If still empty: REFUSE. Suggest checking spelling / running
           build-project after edits.
```

For non-identifier queries (anything with `.`, `(`, spaces), skip step 1
and go straight to `search_code` — `find_callers` will reject them.

### Map — "show me the neighbourhood of `X`" / "what flows into `X`?"

```
1. get_object_graph(name=X)   # use uuid= if disambiguating
   │
   ├─ object is None
   │     → Refuse — not found in project. Suggest find_method or
   │       check spelling.
   │
   └─ object is present
         → Report (in this order):
           - **Centre**: name, class_type, file_path
           - **Inheritance**:
               • parent (the Origin) — file_path
               • children (overrides) — list
           - **Material flow**:
               • predecessors (incoming) — list with edge ports
               • successors (outgoing) — list with edge ports
           - If both predecessor + successor lists are empty, note that
             this object is **isolated** (or its connectors live outside
             the indexed scope).
```

### Audit — "is `X` clean?" / "validate this Method"

```
1. If user gives a Method NAME:
     find_method(name=X) → get the uuid (definition role).
     If multiple definitions exist, ask which one (show file_paths).
2. validate_simtalk(uuid=<that uuid>)
3. Group issues by severity:
     - error    → must-fix, runtime risk
     - warning  → should-fix, behavioural risk (ST001: ignored .move())
     - info     → style / perf (ST002, ST003, ST004)
4. For each issue: line + rule_id + message + fix_hint (when present).
   Do NOT propose the fix yourself — hand off to `plantsim-code-author`
   if the user wants a rewrite.
```

---

## Inheritance Audit (always run when `find_method` returns overrides)

When `find_method` returns at least one `role: "override"` hit, you
**must** flag it before answering anything else. The implication: editing
the parent's body will NOT update the overriding children — they keep
their own bodies.

Report format:

```text
⚠️  Inheritance: `<MethodName>` has N overriding instance(s).
    Editing the parent will NOT affect these children:
      • <child.file_path>   (override of <parent.file_path>)
      • <child.file_path>   (override of <parent.file_path>)
    To roll out a change everywhere, either:
      (a) delete each override so it re-inherits, OR
      (b) apply the same edit to each override body.
```

This is the **single most important value** the analyst skill provides
— it's the kind of mistake that silently breaks production simulations.

---

## Sources contract

Every reported file path comes from a tool response. Format inline
references as a markdown link to the path the tool returned:

```text
- `[InitPalletJackFleet]` defined in [Models/Model/InitPalletJackFleet.yaml](Models/Model/InitPalletJackFleet.yaml)
```

For Methods discovered via `find_method`, include the `uuid` (first 8
chars) so the user can re-query unambiguously:

```text
- `Init` definition `d79e5170…` — [Models/Station/Init.yaml](Models/Station/Init.yaml)
- `Init` override `a52b1c33…`   — [Models/A1L1/$.yaml](Models/A1L1/$.yaml)
```

For lint issues from `validate_simtalk`:

```text
- [ST001 warning] line 36: `.move()` return ignored — *fix_hint: capture
  result and branch on failure* — in [Models/Model/InitPalletJackFleet.yaml](Models/Model/InitPalletJackFleet.yaml)
```

---

## Hard rules

1. **Index must exist.** If any tool raises `FileNotFoundError`, the
   first thing in your reply is:
   > "Project index not built. Run
   > `plantsim-copilot-mcp build-project --psfm <path-to-your.psfm>`
   > first, then ask again."
2. **No training-data answers about the project.** You only know what
   the tools returned. If the user asks about an object you haven't
   queried, query it — don't pattern-match against generic PTS lore.
3. **Don't silently truncate.** If `find_callers` returns `top_k=20`
   and you see 20 hits, tell the user "showing 20 / possibly more — call
   with `top_k=50` for more."
4. **Don't conflate Methods.** When multiple Methods share a name
   (common for inherited frames like `Init`), keep them visually
   separated by `file_path` and `uuid`. Never collapse them into one
   "the Init method" — there are several.
5. **Lint is advisory, not refactoring.** `validate_simtalk` reports
   issues; this skill does not rewrite code. Hand off to
   `plantsim-code-author` if the user wants a fix.

---

## Example sessions

### Locate with inheritance

User:
> 帮我找 `Init` 这个方法在哪里。

Reasoning:
- `find_method(name="Init")` → 1 definition + 1 override.

Output:
> Found 2 `Init` Methods in the indexed project:
>
> - **definition** `d79e5170…` — [Models/Station/Init.yaml](Models/Station/Init.yaml)
> - **override** `a52b1c33…` — [Models/A1L1/$.yaml](Models/A1L1/$.yaml)
>
> ⚠️  Inheritance: `Init` has 1 overriding instance.
> Editing the parent (`Models/Station/Init.yaml`) will NOT affect:
>   • `Models/A1L1/$.yaml`
>
> To roll out a change everywhere, either delete the override so it
> re-inherits, or apply the same edit there too.

### Trace

User:
> who calls `PalletJackResults`?

Reasoning:
- `find_callers(name="PalletJackResults", top_k=20)`.

Output:
> 2 callers of `PalletJackResults` in the project:
>
> - `UpdatePalletJackResults` — [Models/Model/UpdatePalletJackResults.yaml](Models/Model/UpdatePalletJackResults.yaml)
>   `[[PalletJackResults]]["Idle %",i] := 100 - [[PalletJackResults]]["Task %",i]`
> - `InitPalletJackFleet` — [Models/Model/InitPalletJackFleet.yaml](Models/Model/InitPalletJackFleet.yaml)
>   `[[PalletJackResults]]["Pallet Jack",[[PalletJackResults]].ydim+1`

### Audit

User:
> 帮我审一下 `InitPalletJackFleet` 这段代码。

Reasoning:
- `find_method("InitPalletJackFleet")` → 1 hit, uuid `78556fac…`.
- `validate_simtalk(uuid="78556fac…")` → 4 issues.

Output:
> `InitPalletJackFleet` — [Models/Model/InitPalletJackFleet.yaml](Models/Model/InitPalletJackFleet.yaml)
> 4 issue(s) found:
>
> - **[ST002 info] line 5**: local `i` declared without explicit type — defaults to `any`, slower.
> - **[ST002 info] line 11**: local `j` declared without explicit type.
> - **[ST002 info] line 27**: local `IfFound` declared without explicit type.
> - **[ST001 warning] line 36**: `.move()` return value is ignored.
>   *fix_hint*: capture it and branch on failure to avoid silent simulation stalls.
>
> To rewrite this Method with the fixes applied, hand off to
> `plantsim-code-author`.
