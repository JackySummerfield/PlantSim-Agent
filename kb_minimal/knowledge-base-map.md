# Knowledge Base Map (Template)

This file documents the **expected layout** of a fully-built Plant Simulation knowledge base on a user's machine. The MCP server uses this layout to resolve "go-deeper" lookups when the [API Index](./simtalk-api-index.md) or [Syntax Quick Reference](./simtalk-syntax-quick-ref.md) do not carry enough detail.

> **You do not need to edit this file.** The build wizard (`plantsim-copilot-mcp build-kb`) writes the actual resolved paths into `~/.plantsim-agent/config.toml`. This document explains the **shape** so contributors and advanced users know what the indexer is producing.

## Expected directory shape

```
{help_kb_root}/                            # configured in config.toml
├── 09_Plant_Simulation_Program_Window/
├── 10_Step-by-Step_Help/
├── 11_Objects_Reference_Help/
│   ├── 02_Material_Flow_Objects/
│   ├── 04_Resource_Objects/
│   ├── 05_Information_Flow_Objects/
│   ├── 06_User_Interface_Objects/
│   ├── 07_Mobile_Objects/
│   └── 08_Tools/
├── 12_SimTalk_Reference/
│   └── 04_General_Access_to_SimTalk/
│       └── 11_Predefined_Functions/
├── 13_3D_Reference_Help/
├── 14_Quick_Reference.md
└── 15_Add-Ins_Reference_Help/
```

The Siemens documentation pipeline (`markitdown` or `docling`) produces this layout when you point it at a recent Plant Simulation Help PDF or CHM. If your version differs, the indexer flattens deviations automatically.

## Where each topic lives

When the agent needs deeper detail than the sample KB provides, it looks under `{help_kb_root}/` as follows:

### Material flow objects
EventController, Source, Drain, Station, ParallelStation, AssemblyStation, DismantleStation, PickAndPlace_Robot, Buffer, PlaceBuffer, Conveyor, Store, Connector, Frame, FlowControl, Sorter, Turntable, Track, TwoLaneTrack — all under `11_Objects_Reference_Help/02_Material_Flow_Objects/`.

### Resource objects
AGVPool, Marker, Worker, WorkerPool, Broker, Workplace, ShiftCalendar — under `11_Objects_Reference_Help/04_Resource_Objects/`.

### Information flow objects
DataTable, Method, Trigger, Generator, AttributeExplorer — under `11_Objects_Reference_Help/05_Information_Flow_Objects/`.

### Mobile objects
Mobile Units (MU), Container, Transporter — under `11_Objects_Reference_Help/07_Mobile_Objects/`.

### SimTalk language
Variables, parameters, data types, operators, control flow, predefined functions (math / date / string / debug / output) — under `12_SimTalk_Reference/`.

### Shared properties
Cross-cutting properties (processing times, failures, exit strategies, statistics, sensors, blocking behaviour) shared by all material-flow objects live under `11_Objects_Reference_Help/02_Material_Flow_Objects/02_Shared_Properties/`.

### Tools and add-ins
ExperimentManager, BottleneckAnalyzer, GanttChart — under `11_Objects_Reference_Help/08_Tools/` and `06_User_Interface_Objects/`.
3D reference under `13_3D_Reference_Help/`. Database interfaces under `15_Add-Ins_Reference_Help/`.

## How the agent uses this map

1. The agent reads a user query.
2. If the answer is in [API Index](./simtalk-api-index.md), it answers directly with a citation.
3. If not, the agent calls `search_help(query)` on the MCP server, which performs a BM25 search across the full indexed Help.
4. The result includes the path of the source markdown file — the agent quotes that path in its `**Sources:**` block.

For installation and configuration of the actual KB, see [`kb-build-guide.md`](../docs/kb-build-guide.md).
