"""One-shot smoke test against a real ``.psfm`` project on disk.

Not a pytest test — invoke manually with the path to a ``.psfm``
folder and (optionally) a Method / identifier to probe::

    # Powershell
    $env:PLANTSIM_SMOKE_PROJECT = 'D:\\models\\MyProject.psfm'
    python scripts/smoke_psfm.py

    # Or pass on the CLI
    python scripts/smoke_psfm.py D:\\models\\MyProject.psfm --method Init --ident Results

It builds the project index and runs each tool with a representative
query, printing a summary so you can sanity-check the parser on real
data before declaring a slice done.
"""

from __future__ import annotations

import argparse
import os
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


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=(
            "Run a smoke test against a real .psfm project. "
            "Override the project path via PLANTSIM_SMOKE_PROJECT "
            "or pass it as the first positional argument."
        )
    )
    p.add_argument(
        "project",
        nargs="?",
        default=os.environ.get("PLANTSIM_SMOKE_PROJECT"),
        help="Path to a .psfm folder. Falls back to $PLANTSIM_SMOKE_PROJECT.",
    )
    p.add_argument(
        "--method",
        default=os.environ.get("PLANTSIM_SMOKE_METHOD", "Init"),
        help="Method name to look up with find_method / validate_simtalk.",
    )
    p.add_argument(
        "--ident",
        default=os.environ.get("PLANTSIM_SMOKE_IDENT", "str_to_obj"),
        help="Identifier to probe with find_callers / search_code.",
    )
    p.add_argument(
        "--centre",
        default=os.environ.get("PLANTSIM_SMOKE_CENTRE", "Init"),
        help="Object name to centre get_object_graph on.",
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.project:
        print(
            "ERROR: pass a .psfm path or set $PLANTSIM_SMOKE_PROJECT",
            file=sys.stderr,
        )
        return 2

    project = Path(args.project)
    if not project.is_dir():
        print(f"PROJECT not found: {project}", file=sys.stderr)
        return 2

    index_dir = Path(tempfile.mkdtemp(prefix="plantsim_smoke_"))
    paths = Paths(index_dir=index_dir)
    cfg = Config(paths=paths)

    print(f"=== indexing {project.name} ...")
    with ProjectStore(cfg.paths.project_db) as store:
        result = build_project_index(project, store)
    print(
        f"files={result.files_scanned}  docs={result.docs_scanned}  "
        f"objects={len(result.objects)}  code_units={len(result.code_units)}  "
        f"edges={len(result.edges)}  skipped={len(result.skipped)}"
    )
    if result.skipped:
        for path, err in result.skipped[:5]:
            print(f"  skipped: {path}  ({err})")

    print(f"\n=== find_method({args.method!r})")
    fm = find_method(args.method, config=cfg)
    if fm["hits"]:
        for h in fm["hits"][:6]:
            print(f"  [{h['role']:<10}] {h['uuid'][:8]}  {h['file_path']}")
    else:
        print(f"  no hits — did_you_mean: {fm['did_you_mean']}")

    print(f"\n=== find_callers({args.ident!r})")
    for h in find_callers(args.ident, top_k=5, config=cfg):
        print(f"  {h['name']!r:<28} {h['file_path']}  -- {h['snippet'][:80]}")

    print(f"\n=== search_code({args.ident!r})")
    for h in search_code(args.ident, top_k=5, config=cfg):
        print(f"  {h['name']!r:<28} {h['file_path']}  -- {h['snippet'][:80]}")

    print(f"\n=== get_object_graph(name={args.centre!r})")
    g = get_object_graph(name=args.centre, config=cfg)
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

    print(f"\n=== validate_simtalk(name={args.method!r})")
    init_result = find_method(args.method, config=cfg)
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
