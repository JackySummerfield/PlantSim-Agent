# Plant Simulation Modeling Standards

Core code and data standards for Plant Simulation models. Focused on SimTalk authoring, DataTable usage, naming, and performance — not on organizational process.

---

## General Principles

- Plant Simulation is a **discrete-event** tool, NOT a physics engine. Don't build "visual digital twins"; build models that answer specific questions.
- **Minimize MUs** — more MUs = slower runtime. Destroy sub-parts after assembly.
- **All configuration in tables, never hardcoded** — enables scaling without code edits.
- Self-documenting code; add comments only when the WHY is non-obvious.
- Mark open items with `//TODO`.
- Remove debug `print` statements before delivery.
- Run the **Profiler** before accepting a model; focus on method runtime and call frequency.

---

## SimTalk Code Rules

### Syntax & types

- **SimTalk 2.0 only.** Convert any 1.0 syntax encountered.
- **Declare explicit data types** — `any` is slower than typed variables.
- **Declare loop variables locally**: `for var i := 1 to ...`
- **Use assignment operators**: `counter += 1`, `x -= y`, `x *= y`.

### Control flow

- **Use `switch` over cascading `if-elseif`** — better performance and readability.
- **Fail gracefully**: the `else` / `default` branch should call `debug` so unexpected paths are caught.
- Use `exitloop` as soon as a search finds its match.

### MU movement

- **Always check `.move()` success:**
  ```simtalk
  var success : boolean := Station1.MU.move(Station2)
  if success = false
      debug
  end
  ```

### waituntil

- Assign `.cont` (or the watched expression) to a local variable first, then `waituntil` on it.

### Init / endSim hygiene

- `clearConsole` at the top of init; `openConsole` only if messages are needed.
- Document observers in the frame init comments.
- Long-running methods (>5s): wrap with `InfoBox("Processing...", false)` … `InfoBox("", false)`.

---

## Inputs & Outputs

### Inputs

- **All inputs live in tables**, never directly inside object dialogs.
- Group input tables in one location (a dedicated frame is ideal).
- Each object has an `INIT` method that pulls its config from the setup table.
- Small models: one table is fine. Larger models: one table per object type (`ObjectType_Setup`).
- If a table is modified at runtime: **copy it in `INIT` and modify only the copy.**
- Model-level switches: store in a `ModelSettings` DataTable (string `Value` column, cast in code).
- **Colors must come from a table** via `getBackgroundColorCell`. Never call `makeRGBValue` inside methods.

### Outputs

- All outputs in tables, gathered in one location (root frame preferred).
- The user should never need to open an object to find results.
- Pick one consistent collection pattern (`endSim` on each object, OR a single frame `endSim` that aggregates).

### Logging

- Prefer **manual DataTable logging** over built-in statistics when validation matters.
- Use a **Gantt-compatible format** for all resource and transport movement.
- Logging must be **toggleable** behind an `if enabled` check for performance.
- Standard logger: one method that takes parameters and is wrapped in the enable check.

---

## DataTable Standards

- **Never combine inputs and outputs in one table.**
- **Access by column NAME**, never by column number — column numbers break on reorder.
- Column names: A–Z, 0–9, underscore only. No spaces. Must start with a letter.
- Use specific data types (`length`, `time`, `speed`) — not `string` / `real` for everything.
- Percentages: 0–100 `real`, not 0–1 decimals.
- Validate / cleanse data on import; do not assume callers passed clean values.
- **Close all DataTables in init** for performance.
- Don't change column layout after first release — downstream methods depend on it.
- For data-intensive models (joins, large lookups): use **SQLite** rather than chained DataTable searches.

---

## Naming

- Names should be descriptive but **not too long** — e.g. `PL01`, not `PackingLine01_FullName`.
- **Zero-pad numbers**: `PL01, PL02 … PL10` (never `PL1, PL10` — sorts break).
- Use the object **Name**, not Label.
- **Prefix user-defined attributes / variables with underscore**: `_PreviousTimeStamp`, `_BatchID`.

---

## Objects

- Derive every used object into a user class library folder (`Ctrl+click`-drag); never drop standard toolbox objects directly into a model.
- Group derived classes by type into sub-folders (conveyors, machines, MUs, …).
- **Standard state colors** (apply consistently across the model):
  - Blocked = Yellow
  - Failed = Red
  - Paused = Blue
  - Setting-Up = Brown
  - Unplanned = LightBlue

### Connector

- Dynamic connection: `.UserObjects.Connector.connect(oSource, oTarget)`
- Hide a connector: set its color to white / background color.
- Adjust width via `.succConnector.width := 5`.

### Buffer

- Enable **MU Animation** to avoid the visual "tower" stacking effect.

### Workers

- Workers move **freely** by default (Plant Simulation object avoidance handles it well).
- Workers do not carry a width property — Plant Simulation assumes 80 cm.
- Log every worker trip in the Gantt log table.
- Add a user-defined `_PreviousTimeStamp : datetime` on the worker class.
- Update `_PreviousTimeStamp` with `EventController.AbsSimTime` whenever a worker enters/leaves the pool.

---

## MUs

- All MUs derived into a user class folder (`Ctrl+Shift+drag`), organised by sub-folder.
- For many variants of similar parts: create one standard MU and set its attributes in the Source's **exit control**, rather than defining a separate class per variant.

### Transportation MUs

- Log all AGV / truck trips in the Gantt log table.
- **Track-based AGVs are the default** — they support automatic routing and Sankey diagrams.
- Track-less AGVs do **not** have collision avoidance; choose deliberately.

---

## Performance Checklist

- Minimum MU count for the question being answered.
- Tables / SQLite for lookups, not nested loops.
- Hot loops contain only essential work; use `exitloop` on first match.
- DataTables closed in init unless actively viewed.
- Logging behind an `if enabled` switch.
- `EventController.ExperimentManager /= void` check before any UI/animation updates during experiment runs.
- Profiler confirms methods are not dominating runtime — if they are <20% of runtime, focus next on reducing MU count.
