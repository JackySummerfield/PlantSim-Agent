"""Tests for ProjectStore + indexer + project tools."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.config import Config, Paths
from plantsim_mcp.indexers.psfm_indexer import build_project_index
from plantsim_mcp.storage.project import (
    CodeUnit,
    FlowEdge,
    ObjectRow,
    ProjectStore,
)
from plantsim_mcp.tools import (
    find_callers,
    find_method,
    get_object_graph,
    search_code,
)


# ---------------------------------------------------------------------------
# ProjectStore unit tests
# ---------------------------------------------------------------------------


def test_store_roundtrip_objects(tmp_path: Path) -> None:
    with ProjectStore(tmp_path / "p.db") as store:
        store.add_objects(
            [
                ObjectRow(
                    uuid="u1", name="A", class_type="Method",
                    origin_uuid=None, file_path="a.yaml",
                ),
                ObjectRow(
                    uuid="u2", name="A", class_type="Method",
                    origin_uuid="u1", file_path="b.yaml", has_body=True,
                ),
            ]
        )
        assert store.count_objects() == 2
        hits = store.find_by_name("A", class_type="Method")
        assert {h.uuid for h in hits} == {"u1", "u2"}
        children = store.children_of("u1")
        assert [c.uuid for c in children] == ["u2"]


def test_store_get_by_uuid_and_many(tmp_path: Path) -> None:
    with ProjectStore(tmp_path / "p.db") as store:
        store.add_objects(
            [
                ObjectRow(uuid="u1", name="x", class_type="Method",
                          origin_uuid=None, file_path="a.yaml"),
                ObjectRow(uuid="u2", name="y", class_type="Variable",
                          origin_uuid=None, file_path="b.yaml"),
            ]
        )
        assert store.get_by_uuid("u1").name == "x"
        assert store.get_by_uuid("missing") is None
        many = store.get_many_by_uuid(["u1", "u2", "missing"])
        assert {m.uuid for m in many} == {"u1", "u2"}


def test_store_code_search(tmp_path: Path) -> None:
    with ProjectStore(tmp_path / "p.db") as store:
        store.add_objects(
            [
                ObjectRow(uuid="m1", name="Init", class_type="Method",
                          origin_uuid=None, file_path="m1.yaml", has_body=True),
                ObjectRow(uuid="m2", name="Step", class_type="Method",
                          origin_uuid=None, file_path="m2.yaml", has_body=True),
            ]
        )
        store.add_code_units(
            [
                CodeUnit(uuid="m1", name="Init", body="PalletJackResults.append(x)"),
                CodeUnit(uuid="m2", name="Step", body="local i := 0"),
            ]
        )
        hits = store.search_code("PalletJackResults")
        assert len(hits) == 1
        obj, snippet, score = hits[0]
        assert obj.uuid == "m1"
        assert "[[PalletJackResults]]" in snippet
        assert score > 0


def test_store_edges(tmp_path: Path) -> None:
    with ProjectStore(tmp_path / "p.db") as store:
        store.add_edges(
            [
                FlowEdge("a", "b", "successor"),
                FlowEdge("c", "b", "predecessor"),
            ]
        )
        assert store.predecessors_of("b") == ["c"]
        assert store.successors_of("a") == ["b"]


def test_store_rebuild_clears_data(tmp_path: Path) -> None:
    db = tmp_path / "p.db"
    with ProjectStore(db) as store:
        store.add_objects(
            [ObjectRow(uuid="u1", name="x", class_type="Method",
                       origin_uuid=None, file_path="a.yaml")]
        )
        assert store.count_objects() == 1
        store.rebuild()
        assert store.count_objects() == 0


# ---------------------------------------------------------------------------
# End-to-end: indexer + tools on sample_psfm fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def indexed_project(tmp_path: Path, sample_psfm: Path) -> Config:
    """Build the project index and return a Config pointing at it."""
    index_dir = tmp_path / "indices"
    index_dir.mkdir()
    paths = Paths(index_dir=index_dir)
    cfg = Config(paths=paths)

    with ProjectStore(cfg.paths.project_db) as store:
        result = build_project_index(sample_psfm, store)
    assert len(result.objects) > 0
    return cfg


def test_find_method_returns_definition_and_overrides(indexed_project: Config) -> None:
    hits = find_method.find_method("Init", config=indexed_project)
    by_role = {h["role"]: h for h in hits}
    # Definition (the parent Method)
    assert by_role["definition"]["uuid"] == "33333333-3333-3333-3333-333333333333"
    assert by_role["definition"]["file_path"] == "Models/Station/Init.yaml"
    # Override (instance method)
    override = [h for h in hits if h["role"] == "override"]
    assert len(override) == 1
    assert override[0]["uuid"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert override[0]["parent_uuid"] == "33333333-3333-3333-3333-333333333333"


def test_find_method_without_overrides(indexed_project: Config) -> None:
    hits = find_method.find_method(
        "Init", include_overrides=False, config=indexed_project
    )
    assert len(hits) == 1
    assert hits[0]["role"] == "definition"


def test_find_method_unknown_returns_empty(indexed_project: Config) -> None:
    assert find_method.find_method("Nope", config=indexed_project) == []


def test_find_callers_finds_references(indexed_project: Config) -> None:
    # Init body mentions "InitPalletJackFleet"; the method itself is excluded.
    hits = find_callers.find_callers("InitPalletJackFleet", config=indexed_project)
    assert len(hits) == 1
    assert hits[0]["uuid"] == "33333333-3333-3333-3333-333333333333"
    assert "[[InitPalletJackFleet]]" in hits[0]["snippet"]


def test_find_callers_rejects_non_identifier(indexed_project: Config) -> None:
    assert find_callers.find_callers("not a name", config=indexed_project) == []
    assert find_callers.find_callers("with-dash", config=indexed_project) == []
    assert find_callers.find_callers("", config=indexed_project) == []


def test_search_code_full_text(indexed_project: Config) -> None:
    hits = search_code.search_code("PalletCapacity", config=indexed_project)
    # Parent Init body + override body both write to PalletCapacity.
    uuids = {h["uuid"] for h in hits}
    assert "33333333-3333-3333-3333-333333333333" in uuids
    assert "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa" in uuids


def test_search_code_empty_query(indexed_project: Config) -> None:
    assert search_code.search_code("   ", config=indexed_project) == []


def test_get_object_graph_by_name(indexed_project: Config) -> None:
    graph = get_object_graph.get_object_graph(name="Init", config=indexed_project)
    assert graph["object"]["uuid"] == "33333333-3333-3333-3333-333333333333"
    # Children = the instance override
    assert {c["uuid"] for c in graph["children"]} == {
        "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    }
    # No parent (this is a top-level Method)
    assert graph["parent"] is None


def test_get_object_graph_by_uuid_with_external_predecessor(
    indexed_project: Config,
) -> None:
    # The Station Buffer has a $Predecessors entry pointing at 99999999...
    # which is NOT in our project — should surface as <external>.
    graph = get_object_graph.get_object_graph(
        uuid="44444444-4444-4444-4444-444444444444", config=indexed_project
    )
    preds = graph["predecessors"]
    assert len(preds) == 1
    assert preds[0]["class_type"] == "<external>"
    assert preds[0]["uuid"] == "99999999-9999-9999-9999-999999999999"


def test_get_object_graph_unknown_centre(indexed_project: Config) -> None:
    graph = get_object_graph.get_object_graph(uuid="zzz", config=indexed_project)
    assert graph["object"] is None
    assert graph["parent"] is None
    assert graph["children"] == []


def test_get_object_graph_requires_name_or_uuid(indexed_project: Config) -> None:
    with pytest.raises(ValueError):
        get_object_graph.get_object_graph(config=indexed_project)


# ---------------------------------------------------------------------------
# Missing-DB error path (shared by all project tools)
# ---------------------------------------------------------------------------


def test_tools_raise_when_db_missing(tmp_path: Path) -> None:
    paths = Paths(index_dir=tmp_path / "nope")
    cfg = Config(paths=paths)
    with pytest.raises(FileNotFoundError):
        find_method.find_method("X", config=cfg)
    with pytest.raises(FileNotFoundError):
        find_callers.find_callers("X", config=cfg)
    with pytest.raises(FileNotFoundError):
        search_code.search_code("X", config=cfg)
    with pytest.raises(FileNotFoundError):
        get_object_graph.get_object_graph(name="X", config=cfg)
