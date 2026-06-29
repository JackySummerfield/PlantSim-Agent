"""Tests for the .psfm parser."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.indexers.psfm_parser import parse_project


def test_parse_discovers_all_objects(sample_psfm: Path) -> None:
    result = parse_project(sample_psfm)
    # 4 parent files (Station: $, PalletCapacity, Init, Buffer)
    # + 2 model-level (Model $, InitPalletJackFleet)
    # + 4 instance docs (Frame, Variable, Init override, Buffer)
    # + 1 synthetic inline Method (Buffer.OnEntrance via $CustomAttributes)
    assert len(result.objects) == 11
    assert result.docs_scanned == 10
    assert result.files_scanned == 7


def test_parse_links_origin_for_instances(sample_psfm: Path) -> None:
    result = parse_project(sample_psfm)
    by_uuid = {o.uuid: o for o in result.objects}

    # Parent class has no Origin
    station = by_uuid["11111111-1111-1111-1111-111111111111"]
    assert station.origin_uuid is None
    assert station.class_type == "Frame"

    # Instance Frame inherits from Station
    instance = by_uuid["77777777-7777-7777-7777-777777777777"]
    assert instance.origin_uuid == "11111111-1111-1111-1111-111111111111"

    # Pure-inheritance child (Variable, just an Origin link, no body)
    variable = by_uuid["88888888-8888-8888-8888-888888888888"]
    assert variable.origin_uuid == "22222222-2222-2222-2222-222222222222"
    assert variable.has_body is False

    # Override Method (has its own Program) → has_body True
    override = by_uuid["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]
    assert override.origin_uuid == "33333333-3333-3333-3333-333333333333"
    assert override.has_body is True


def test_parse_harvests_program_bodies(sample_psfm: Path) -> None:
    result = parse_project(sample_psfm)
    by_uuid_body = {c.uuid: c.body for c in result.code_units}

    # Parent Method has body
    assert "InitPalletJackFleet" in by_uuid_body["33333333-3333-3333-3333-333333333333"]

    # Top-level Model method has body
    assert "FleetNum" in by_uuid_body["55555555-5555-5555-5555-555555555555"]

    # Instance override has its own body (different from parent)
    assert ":= 50" in by_uuid_body["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]


def test_parse_extracts_inline_custom_attribute_methods(sample_psfm: Path) -> None:
    result = parse_project(sample_psfm)
    # Buffer has an inline OnEntrance method via $CustomAttributes
    inline_uuid = "44444444-4444-4444-4444-444444444444::OnEntrance"
    bodies = {c.uuid: c.body for c in result.code_units}
    assert inline_uuid in bodies
    assert "_RunMethod.execute(AMR)" in bodies[inline_uuid]

    inline_objs = [o for o in result.objects if o.uuid == inline_uuid]
    assert len(inline_objs) == 1
    assert inline_objs[0].name == "OnEntrance"
    assert inline_objs[0].class_type == "Method"
    # Parent host is the Buffer
    assert inline_objs[0].origin_uuid == "44444444-4444-4444-4444-444444444444"


def test_parse_emits_flow_edges(sample_psfm: Path) -> None:
    result = parse_project(sample_psfm)
    # Buffer has $Predecessors: [99999999...]  →  edge from 9999.. to Buffer
    edges = [(e.src_uuid, e.dst_uuid, e.kind) for e in result.edges]
    assert (
        "99999999-9999-9999-9999-999999999999",
        "44444444-4444-4444-4444-444444444444",
        "predecessor",
    ) in edges


def test_parse_skips_doc_without_internal_class_type(tmp_path: Path) -> None:
    project = tmp_path / "Empty.psfm"
    project.mkdir()
    (project / "junk.yaml").write_text("foo: bar\n", encoding="utf-8")
    result = parse_project(project)
    assert result.files_scanned == 1
    assert result.docs_scanned == 0
    assert result.objects == []


def test_parse_handles_malformed_yaml(tmp_path: Path) -> None:
    project = tmp_path / "Broken.psfm"
    project.mkdir()
    (project / "ok.yaml").write_text(
        "InternalClassType: Frame\nName: Ok\nUUID: deadbeef\n", encoding="utf-8"
    )
    (project / "bad.yaml").write_text("foo: [bar, : :\n", encoding="utf-8")
    result = parse_project(project)
    # The malformed file silently yields no docs; the good file still parses.
    assert len(result.objects) == 1
    assert result.objects[0].name == "Ok"


def test_parse_missing_project_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        parse_project(tmp_path / "does-not-exist.psfm")
