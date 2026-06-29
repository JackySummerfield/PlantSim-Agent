"""One-shot smoke test against the real KongMing .psfm project.

Not a pytest test — invoke manually:
    python scripts/smoke_psfm_kongming.py

It builds the project index and runs each tool with a representative
query, printing a summary so we can sanity-check the parser on real
data before declaring the slice done.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.indexers.psfm_indexer import build_project_index
from plantsim_mcp.storage.project import ProjectStore
from plantsim_mcp.tools.find_callers import find_callers
from plantsim_mcp.tools.find_method import find_method
from plantsim_mcp.tools.get_object_graph import get_object_graph
from plantsim_mcp.tools.search_code import search_code
from plantsim_mcp.tools.validate_simtalk import validate_simtalk


PROJECT = Path(
    r"C:\Users\tao.j.10\Procter and Gamble"
    r"\GC PD Modeling & Simulation - 文档"
    r"\5_kongming_2C\3_simulation_model\TCDC"
    r"\TCDC_KongMing_PS2504.psfm"
)


def main() -> int:
    if not PROJECT.is_dir():
        print(f"PROJECT not found: {PROJECT}", file=sys.stderr)
        return 2

    here = Path(__file__).resolve().parent.parent
    index_dir = Path(tempfile.mkdtemp(prefix="plantsim_smoke_"))
    paths = Paths(index_dir=index_dir)
    cfg = Config(paths=paths)

    print(f"=== indexing {PROJECT.name} ...")
    with ProjectStore(cfg.paths.project_db) as store:
        result = build_project_index(PROJECT, store)
    print(
        f"files={result.files_scanned}  docs={result.docs_scanned}  "
        f"objects={len(result.objects)}  code_units={len(result.code_units)}  "
        f"edges={len(result.edges)}  skipped={len(result.skipped)}"
    )
    if result.skipped:
        for path, err in result.skipped[:5]:
            print(f"  skipped: {path}  ({err})")

    print("\n=== find_method('InitPalletJackFleet')")
    fm = find_method("InitPalletJackFleet", config=cfg)
    if fm["hits"]:
        for h in fm["hits"][:6]:
            print(f"  [{h['role']:<10}] {h['uuid'][:8]}  {h['file_path']}")
    else:
        print(f"  no hits — did_you_mean: {fm['did_you_mean']}")

    print("\n=== find_callers('PalletJackResults')")
    for h in find_callers("PalletJackResults", top_k=5, config=cfg):
        print(f"  {h['name']!r:<28} {h['file_path']}  -- {h['snippet'][:80]}")

    print("\n=== search_code('str_to_obj')")
    for h in search_code("str_to_obj", top_k=5, config=cfg):
        print(f"  {h['name']!r:<28} {h['file_path']}  -- {h['snippet'][:80]}")

    print("\n=== get_object_graph(name='Init')")
    g = get_object_graph(name="Init", config=cfg)
    if g["object"]:
        print(
            f"  centre: {g['object']['name']} ({g['object']['class_type']}) "
            f"{g['object']['file_path']}"
        )
        print(f"  parent: {g['parent']}")
        print(f"  children: {len(g['children'])}")
        print(f"  predecessors: {len(g['predecessors'])}  successors: {len(g['successors'])}")
    else:
        print("  not found")

    print("\n=== validate_simtalk(uuid=InitPalletJackFleet)")
    init_result = find_method("InitPalletJackFleet", config=cfg)
    init_hits = init_result["hits"]
    if init_hits:
        init_uuid = init_hits[0]["uuid"]
        try:
            issues = validate_simtalk(uuid=init_uuid, config=cfg)
        except KeyError as exc:
            print(f"  no body: {exc}")
        else:
            print(f"  {len(issues)} issue(s) found")
            for it in issues[:5]:
                print(
                    f"    [{it['rule_id']} {it['severity']}] "
                    f"line {it['line']}: {it['message'][:100]}"
                )

    return 0


if __name__ == "__main__":
    sys.exit(main())
