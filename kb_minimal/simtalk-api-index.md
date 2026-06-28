# SimTalk 2.0 API Index

A self-authored quick-reference index of the Plant Simulation objects most often touched in SimTalk methods. Each entry lists attribute and method **names** with one-line summaries — it is not a substitute for the official Plant Simulation Help, which the AI agent will retrieve for behavioural detail.

## EventController

**Purpose:** sim clock, start/stop/reset, time control.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Time` | time RO | current sim time |
| `AbsSimTime` | datetime | StartDate + Time |
| `StartDate` | datetime | base date |
| `EndTime` | time | stop time |
| `StartStat` | time | warm-up end |
| `Realtime` | bool | realtime mode |
| `RealtimeScale` | real | realtime factor |
| `ExperimentManager` | obj | active EM (void if none) |

| Method | Signature | Description |
|--------|-----------|-------------|
| `start` | `() → bool` | start sim |
| `stop` | `() → bool` | stop sim |
| `reset` | `() → void` | reset model |

**Callbacks:** `init`, `reset`, `endSim` (any method named `endSim` auto-called)

---

## Station

**Purpose:** single-MU processing place.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Name` | string | object name |
| `ProcessingTime` | time/dist | processing time |
| `SetupTime` | time/dist | setup on MU type change |
| `RecoveryTime` | time/dist | recovery after failure |
| `Pause` | bool | pause station |
| `NumMU` | int RO | MU count (0 or 1) |
| `MU` | obj RO | current MU (void if empty) |
| `Occupied`/`empty` | bool RO | occupancy flags (inverses) |
| `failed`/`operational` | bool RO | failure flags (inverses) |

| Method | Signature | Description |
|--------|-----------|-------------|
| `MU(n)` | `(n:int) → obj` | nth MU |
| `startPause`/`stopPause` | `→ void` | pause/resume |
| `startFailure`/`stopFailure` | `→ void` | trigger/end failure |

**Sensor Controls:** `entranceControl`, `exitControl`, `setupControl`, `failureControl`, `pullControl`

**Notes:** capacity 1; blocks if successor blocked (unless exit strategy configured).

---

## Buffer

**Purpose:** FIFO/LIFO MU storage.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Capacity` | int | max MUs (-1 = inf) |
| `BufferType` | string | `Queue` (FIFO) \| `Stack` (LIFO) |
| `NumMU` | int RO | current count |
| `empty`/`full` | bool RO | state flags |
| `ProcTime` | time | min dwell time |

| Method | Signature | Description |
|--------|-----------|-------------|
| `MU(n)` | `(n:int) → obj` | nth MU |
| `Cont` | `→ container` | container ops |

**Sensor Controls:** `entranceControl`, `exitControl`, `pullControl`

**Notes:** flat capacity (no indexed places); dwell time not extended by failures/pauses.

---

## Conveyor

**Purpose:** continuous MU transport at constant speed.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Length` | length | total length |
| `Speed` | velocity | speed (-1 = inf) |
| `Capacity` | int | max MUs (-1 = inf) |
| `Accumulating` | bool | bunching when blocked |
| `Backwards` | bool | reverse direction |
| `MUDistance` | length | gap/pitch between MUs |
| `MUDistanceType` | string | `Gap` \| `Pitch` \| `MinGap` \| `MinPitch` |
| `NumMU` / `OccupiedLength` | RO | count / used length |

| Method | Signature | Description |
|--------|-----------|-------------|
| `MU(n)` | `(n:int) → obj` | nth MU |
| `start`/`stop` | `→ void` | start/stop conveyor |

**Sensor Controls:** `entranceControl`, `exitControl`, `rearControl`, `pullControl`

**Notes:** non-accumulating blocks ALL MUs on any blockage; accumulating only blocks the affected MU.

---

## Source

**Purpose:** MU creation and dispatch.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Interval` | time/dist | between creations |
| `Start` / `Stop` | time | first / last creation |
| `Amount` | int | total MUs to create |
| `MU` | obj/path | MU class to create |
| `Blocking` | bool | remember planned time when blocked |

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `(muClass:obj) → obj` | programmatic creation |

**Sensor Controls:** `exitControl`

**Notes:** MU selection modes: Constant, Sequence, Cyclical, Random, Percentage, Order Controlled.

---

## Drain

**Purpose:** MU removal and throughput measurement.

| Attribute | Type | Description |
|-----------|------|-------------|
| `NumMU` | int RO | total MUs through |
| `StatThroughputPerHour` | real RO | throughput rate |

| Method | Signature | Description |
|--------|-----------|-------------|
| `typeStatistics` | `(table) → bool` | per-type stats |
| `typeStatisticsCumulated` | `(table) → bool` | cumulated stats |

**Sensor Controls:** `entranceControl` only (no exitControl — MUs are deleted).

---

## Store

**Purpose:** 3D grid storage with (X,Y,Z) placement.

| Attribute | Type | Description |
|-----------|------|-------------|
| `XDim` / `YDim` / `ZDim` | int | capacity per axis |
| `Capacity` | int RO | XDim × YDim × ZDim |
| `NumMU` | int RO | current count |

| Method | Signature | Description |
|--------|-----------|-------------|
| `MU(x,y,z)` | `(x,y,z:int) → obj` | MU at coord |
| `findFreePlace` | `() → place` | next free slot |
| `findFreePlaceInRange` | `(range) → place` | free slot in range |

**Sensor Controls:** `entranceControl` (sets storage coord), `exitControl`

**Notes:** without entranceControl uses ascending first-free; supermarket mode auto-reorders when stock ≤ MinStock.

---

## Connector

**Purpose:** unidirectional material flow connection.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Width` | real | thickness (0=1px, -1=invisible) |
| `Color` | color | line color |
| `PredInterface` / `SuccInterface` | obj RO | endpoints |

| Method | Signature | Description |
|--------|-----------|-------------|
| `connect` | `(start, end) → connector` | create connection |

**Notes:** only one Connector per object pair. Dynamic: `.UserObjects.Connector.connect(a, b)`.

---

## Track

**Purpose:** length-oriented path for AGVs/Transporters.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Length` | length | track length |
| `Capacity` | int | max transporters (-1 = inf) |
| `FwDestList` / `BwDestList` | list | routing destinations |

| Method | Signature | Description |
|--------|-----------|-------------|
| `getRouteLength` | `(target) → length` | shortest route (-1 if unreachable) |

**Sensor Controls:** `entranceControl`, `exitControl`, sensors (waypoint logic)

**Routing priority (low→high):** round-robin → Driving Control → Dest Lists → Exit Control. Transporters keep FIFO; cannot pass.

---

## AGVPool

**Purpose:** AGV fleet manager.

| Attribute | Type | Description |
|-----------|------|-------------|
| `AGV` | class | template vehicle |
| `Amount` | int | AGVs at init |
| `NumIdleAGVs` | int RO | idle count |

| Method | Signature | Description |
|--------|-----------|-------------|
| `getIdleAGV` | `() → obj` | next idle AGV (void if none); sets IsIdle=false |
| `getAssignedAGV` | `(n:int) → obj` | by index |
| `getAssignedAGVsTable` | `() → table` | all AGVs |

**Notes:** caller must reset `IsIdle := true` when AGV returns.

---

## Marker

**Purpose:** waypoint for AGV free-movement routing.

| Attribute | Type | Description |
|-----------|------|-------------|
| `UseRotationOfMarker` | bool | directional (true) vs omnidirectional |

| Method | Signature | Description |
|--------|-----------|-------------|
| `getRouteLength` | `(toMarker) → length` | route length (-1 if unreachable) |

**Sensor Controls:** `ArrivalCtrl` (fires on arrival)

**Notes:** omnidirectional = AGV turns before marker; directional = AGV crosses through.

---

## Worker

**Purpose:** resource that walks/beams to Workplaces to perform services.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Priority` | int | assignment priority (higher = preferred) |
| `Efficiency` | % | speed factor (100% = normal; 50% → 2× time) |
| `Speed` | velocity | walking speed |
| `Services` | list | service names + optional priority/efficiency override |

| Method | Signature | Description |
|--------|-----------|-------------|
| `teleportTo` | `(workplace) → void` | instant travel |
| `teleportToHome` / `teleportToPool` | `() → void` | return home / pool |

**Notes:** created by WorkerPool, managed by Broker. Travel modes: `MoveFreelyWithinArea` \| `WalkAlongFootpaths` \| `BeamToWorkplace`.

---

## DataTable

**Purpose:** typed multi-column tables.

| Attribute | Type | Description |
|-----------|------|-------------|
| `XDim` / `YDim` | int RO | column / row count |

**Access:** `table["ColName", row]` (read/write). `table[colIdx, row]` by number (avoid in production).

| Method | Signature | Description |
|--------|-----------|-------------|
| `getColumnNo` | `(name) → int` | col number by name |
| `getDataType` / `setDataType` | `(col[, type])` | get/set col type |
| `insertRow` / `cutRow` | `([row]) → bool` | add/remove row |
| `insertColumn` / `cutColumn` | `([col]) → bool` | add/remove column |
| `getColumnYDim` | `(col) → int` | last filled row in col |
| `getColumnUniqueValues` | `(col) → array` | unique values |
| `sort` | `(col[, ascending])` | sort by column |

**Notes:** types: string, int, real, bool, date, datetime, time, money, length, speed, object, table. Use FastAccessColumnIndex / FastAccessRowIndex for large tables; SQLite for joins.

---

## MU (Mobile Unit) Operations

MU = any moving object (Part, Container, Transporter).

| Operation | Syntax | Description |
|-----------|--------|-------------|
| Move | `mu.move(dest) → bool` | returns false if failed |
| Move to coord | `mu.move(store, x, y, z)` | to store coordinate |
| Create | `muClass.create(dest) → obj` | new instance |
| Delete | `mu.delete` | destroy |
| Container | `mu.cont → obj` | object holding this MU |
| Contents | `station.MU(n) → obj` | nth MU inside |
| Class | `mu.MUClass → obj` | class reference |
| User attr | `mu.AttrName` | read/write |

**Critical:** always check `move` result — silent failure if blocked.
```simtalk
if mu.move(target) = false
    -- handle blocked
end
```

---

## ParallelStation

**Purpose:** multi-place processing (2D grid).

| Attribute | Type | Description |
|-----------|------|-------------|
| `XDim` / `YDim` | int | places per axis |
| `Capacity` | int RO | XDim × YDim |
| `ProcessingTime` / `SetupTime` | time/dist | process / setup time |
| `StartProcessingWhenFull` | bool | wait until full to process |
| `NumMU` / `Pause` | RO/bool | count / pause |

| Method | Signature | Description |
|--------|-----------|-------------|
| `pe` | `(x,y:int) → any` | access place at coord |
| `findPart` | `(partType:string) → obj` | find MU by type |
| `startProcessing` | `→ void` | start without waiting |

**Sensor Controls:** `entranceControl`, `exitControl`, `setupControl`, `pullControl`

**Notes:** supports type-dependent and place-dependent processing times.

---

## AssemblyStation

**Purpose:** assemble mounting parts onto a main part (or delete them).

| Attribute | Type | Description |
|-----------|------|-------------|
| `AssemblyTable` | obj | defines parts to assemble/delete |
| `AssemblyTableMode` | string | `None` \| `Predecessors` \| `MU Types` \| `Depends on Main MU` \| `Fill up Main MU` |
| `AssemblyMode` | string | `Attach MUs` \| `Delete MUs` |
| `MainMU` | int | predecessor number for main part |
| `ExitingMU` | string | `Main MU` \| `New MU` |
| `SequentialDelivery` | bool | one-at-a-time delivery |
| `ProcessingTime` | time/dist | per assembly |

| Method | Signature | Description |
|--------|-----------|-------------|
| `musToBeDeleted` | `→ container` | MUs scheduled for deletion |
| `NumMUsToBeDeleted` | `→ int` | count |

**Sensor Controls:** `entranceControl`, `exitControl`, `setupControl`, `pullControl`

**Notes:** parts can't enter via SimTalk move — physical connectors required.

---

## WorkerPool

**Purpose:** creates and houses Worker resources.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Broker` | obj | broker managing assignments |
| `ShiftCalendar` | obj | shift schedule |
| `PartsBuffer` | obj | undelivered-parts buffer |
| `WorkersTravelMode` | string | `Move freely` \| `Walk along footpaths` \| `Beam to workplace` |
| `GetJobOrdersAtHomeOnly` | bool | accept jobs only at home/pool |
| `ChooseNearestWorker` | bool | broker picks nearest |

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `(workerClass:obj) → obj` | programmatic create |
| `getWorkersToCreateTable` | `→ table` | worker creation table |
| `setWorkersToCreateTable` | `(table) → void` | replace table |

**Notes:** workers auto-created from "Workers to Create" table at init.

---

## Broker

**Purpose:** mediates service requests between importers (workplaces) and exporters (workers).

| Attribute | Type | Description |
|-----------|------|-------------|
| `ChooseNearestWorker` | bool | prefer shortest travel |
| `ImpRequestCtrl` / `ExpRequestCtrl` | method | importer / exporter callbacks |
| `OpenRequests` / `SatisfiedRequests` | int RO | pending / completed |
| `MediatedCapacity` | int RO | currently brokered |

| Method | Signature | Description |
|--------|-----------|-------------|
| `engage` | `(importer, exporter, amount:int) → void` | manual assignment |

**Notes:** non-optimizing & order-sensitive — request specific services before general. Hierarchical: passes to successor brokers if local exporters insufficient.

---

## Trigger

**Purpose:** time-based driver that changes attributes and invokes methods.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Active` | bool | enable/disable |
| `Absolute` | bool | absolute vs. relative time |
| `StartTime` / `StartDate` | time/datetime | start (relative / absolute) |
| `ActiveInterval` | time | duration trigger stays active |
| `Periodic` / `PeriodLength` | bool/time | repetition |
| `CurrentValue` | any RO | current value |

| Method | Signature | Description |
|--------|-----------|-------------|
| `compute` | `→ void` | recompute combination values |
| `insertTriggeredAttr` / `deleteTriggeredAttr` | `(obj, attr:string)` | add/remove controlled attr |
| `insertTriggeredMeth` / `deleteTriggeredMeth` | `(method)` | add/remove triggered method |

**Notes:** types: Input (single TimeSequence) or Combination (formula AND/OR/NOT or +,-,*,/).

---

## Generator

**Purpose:** periodic interval-based method activation.

| Attribute | Type | Description |
|-----------|------|-------------|
| `Active` | bool | enable/disable |
| `Start` / `Stop` | time/dist | first / stop time (0 = unlimited) |
| `Interval` / `Duration` | time/dist | interval / gap between ctrl calls |
| `IntervalCtrl` / `DurationCtrl` | method | called at interval / after duration |

**Notes:** Interval and Duration always paired; supports any distribution.

---

## ExperimentManager

**Purpose:** parametric studies, optimization, statistical analysis.

| Attribute | Type | Description |
|-----------|------|-------------|
| `ExperimentTable` | table | input values per experiment |
| `InputTable` / `OutputTable` | table | input vars / output vars |
| `ObservationsPerExperiment` | int | replications (stochastic) |
| `ResultsPrecision` | int | decimal places (1-14, -1=max) |
| `DecimalSeparator` | string | `.` or `,` |
| `MaxNumExpForDetailedReport` | int | threshold for detailed stats (default 1000) |

| Method | Signature | Description |
|--------|-----------|-------------|
| `startExp` | `([generateReport:bool]) → void` | start study |
| `endOfExperiment` | `→ void` | end current early |
| `restoreParam` | `→ void` | restore original inputs |
| `getBestParameter` | `(table, outputName:string, maximize:bool) → table` | optimal params |

**Notes:** designs: Multi-level, Random, Two-level. Skip UI during runs by checking `EventController.ExperimentManager /= void`.

---

## Common Sensor Control Signatures

```simtalk
-- Entrance/Exit control (most material flow objects)
param mu : object → void

-- Routing exit control (returns target)
param mu : object → object

-- Init control (called at sim start)
→ void

-- EndSim (any method named "endSim" auto-called at sim end)
→ void
```

---

## Common Shared Methods (All Material Flow Objects)

| Method | Description |
|--------|-------------|
| `.succ(n)` | Get nth successor |
| `.pred(n)` | Get nth predecessor |
| `.numSucc` | Number of successors |
| `.numPred` | Number of predecessors |
| `.succConnector` | Connector to successor |
| `.predConnector` | Connector from predecessor |

---

## Object Navigation

| Expression | Meaning |
|------------|---------|
| `self` | Current method's owner object |
| `self.~` | Parent frame |
| `root` | Model root |
| `?.` | Current MU (in sensor controls) |
| `@.` | Predecessor object (in entrance/exit) |
| `current` | The object where the MU currently is |
