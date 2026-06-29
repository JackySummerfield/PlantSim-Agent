"""Tests for the chapter-aware PTS Help fullmd indexer."""

from __future__ import annotations

from pathlib import Path

import pytest

from plantsim_mcp.indexers.pts_help_fullmd_indexer import (
    DEFAULT_CHAPTERS,
    _extract_entry_name,
    _is_categorical,
    build_fullmd,
    iter_fullmd_docs,
)
from plantsim_mcp.storage.sqlite import SQLiteFTSIndex


# A miniature fullmd file that mirrors the real structure:
#   H1 chapter banner
#   H2/H3/H4 grouping (kept as ancestors only)
#   H5/H6 reference entries (indexed)
#   \_ categorical groupings (skipped)
#   "See also" body label promoted to H6 (skipped)
SAMPLE_FULLMD = """\
# 10. Step-by-Step Help

## Step-by-step

### Connecting Stations

Some prose that should NOT be indexed because chapter 10 isn't requested.

##### Stop [SimTalk] - Source (in ch10 — should be ignored)

This body should be skipped.

# 11. Objects Reference Help

## Material Flow Objects

### Source

#### Attributes

##### Stop [SimTalk] - Source

Sets the simulation time at which the Source stops producing MUs.

Remarks

A Stop time of zero indicates infinite production.

Syntax

```simtalk
<Path>.Stop:time
```

##### Start [SimTalk] - Source

Sets the simulation time at which the Source starts producing MUs.

Example

```simtalk
MySource.Start := 3600
```

##### Capacity [text box] - Source

Sets the buffer capacity exposed in the dialog.

##### \\_Attributes of the Controls

(categorical heading — entries below, no body)

###### ConnectCtrl [SimTalk]

Hooks the OnEntrance control.

###### See also

(a body label leaked to a heading — should be skipped)

# 12. SimTalk Reference

## Built-in Functions

### Array helpers

##### appendArray [SimTalk]

Appends one array onto another.

Example

```simtalk
a.appendArray(b)
```

# 14. Quick Reference

## Cards

##### Shortcut Card

This entry is in chapter 14 and should NOT be indexed by default.
"""


@pytest.fixture
def fullmd_file(tmp_path: Path) -> Path:
    src = tmp_path / "pts_help_2504_fullmd" / "_full_docling_code_tagged.md"
    src.parent.mkdir(parents=True)
    src.write_text(SAMPLE_FULLMD, encoding="utf-8")
    return src


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_extract_entry_name_with_bracket() -> None:
    assert _extract_entry_name("Stop [SimTalk] - Source") == "Stop"
    assert _extract_entry_name("Capacity [text box] - Exporter") == "Capacity"
    assert _extract_entry_name("Material Active [check box] - MUs") == "Material Active"


def test_extract_entry_name_without_bracket() -> None:
    assert _extract_entry_name("Predefined Names") == "Predefined Names"


def test_extract_entry_name_strips_underscore_prefix() -> None:
    assert _extract_entry_name(r"\_Attributes of the Controls") == "Attributes of the Controls"
    assert _extract_entry_name("_Methods for Accessing Lists") == "Methods for Accessing Lists"


def test_is_categorical_underscore() -> None:
    assert _is_categorical(r"\_Attributes of the Controls")
    assert _is_categorical("_Methods for Accessing Lists")
    assert not _is_categorical("Stop [SimTalk] - Source")


def test_is_categorical_body_label() -> None:
    assert _is_categorical("See also")
    assert _is_categorical("Remarks")
    assert _is_categorical("Example")
    assert not _is_categorical("appendArray [SimTalk]")


def test_default_chapters() -> None:
    assert DEFAULT_CHAPTERS == (11, 12, 13, 15)


# ---------------------------------------------------------------------------
# iter_fullmd_docs
# ---------------------------------------------------------------------------


def test_iter_fullmd_docs_indexes_only_target_chapters(fullmd_file: Path) -> None:
    docs = list(iter_fullmd_docs(fullmd_file))
    sections = [d.section for d in docs]
    # Should pick up ch11 H5/H6 + ch12, drop ch10 entry and ch14 entry,
    # drop the \_ categorical and the stray "See also"
    assert "Stop [SimTalk] - Source" in sections
    assert "Start [SimTalk] - Source" in sections
    assert "Capacity [text box] - Source" in sections
    assert "ConnectCtrl [SimTalk]" in sections
    assert "appendArray [SimTalk]" in sections
    # Skipped:
    assert not any("ch10" in s for s in sections)
    assert "Shortcut Card" not in sections
    assert not any("Attributes of the Controls" in s for s in sections)
    assert "See also" not in sections


def test_iter_fullmd_docs_populates_entry_name(fullmd_file: Path) -> None:
    by_section = {d.section: d for d in iter_fullmd_docs(fullmd_file)}
    assert by_section["Stop [SimTalk] - Source"].entry_name == "Stop"
    assert by_section["Capacity [text box] - Source"].entry_name == "Capacity"
    assert by_section["appendArray [SimTalk]"].entry_name == "appendArray"


def test_iter_fullmd_docs_body_stops_at_next_sibling(fullmd_file: Path) -> None:
    stop_doc = next(
        d for d in iter_fullmd_docs(fullmd_file) if d.section == "Stop [SimTalk] - Source"
    )
    # Body of Stop should include its prose and code block...
    assert "stops producing MUs" in stop_doc.content
    assert "<Path>.Stop:time" in stop_doc.content
    # ...but must NOT bleed into the next entry "Start"
    assert "Start [SimTalk] - Source" not in stop_doc.content
    assert "MySource.Start" not in stop_doc.content


def test_iter_fullmd_docs_h6_under_h5_categorical(fullmd_file: Path) -> None:
    """Verify the H6 ``ConnectCtrl`` survives even though its H5 parent
    was a ``\\_`` categorical that we skipped."""
    docs = list(iter_fullmd_docs(fullmd_file))
    sections = [d.section for d in docs]
    assert "ConnectCtrl [SimTalk]" in sections


def test_iter_fullmd_docs_custom_chapters(fullmd_file: Path) -> None:
    docs = list(iter_fullmd_docs(fullmd_file, chapters=[12]))
    sections = [d.section for d in docs]
    assert sections == ["appendArray [SimTalk]"]


def test_iter_fullmd_docs_missing_file(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        list(iter_fullmd_docs(tmp_path / "nope.md"))


def test_iter_fullmd_docs_doc_ids_are_unique(fullmd_file: Path) -> None:
    ids = [d.doc_id for d in iter_fullmd_docs(fullmd_file)]
    assert len(ids) == len(set(ids))


def test_iter_fullmd_docs_file_path_uses_label(fullmd_file: Path) -> None:
    docs = list(iter_fullmd_docs(fullmd_file))
    assert all(d.file_path.startswith("pts_help_2504_fullmd/") for d in docs)


# ---------------------------------------------------------------------------
# build_fullmd + storage integration (entry_name lookup)
# ---------------------------------------------------------------------------


def test_build_fullmd_into_index(fullmd_file: Path, tmp_path: Path) -> None:
    db_path = tmp_path / "help.db"
    with SQLiteFTSIndex(db_path) as idx:
        written = build_fullmd(fullmd_file, idx)
    assert written >= 5  # 4 in ch11 + 1 in ch12 at minimum

    # find_by_section should now use the entry_name fast path
    with SQLiteFTSIndex(db_path) as idx:
        hits = idx.find_by_section("Stop", top_k=5)
        sections = [h.section for h in hits]
        assert "Stop [SimTalk] - Source" in sections


def test_build_fullmd_finds_ui_control_by_entry_name(
    fullmd_file: Path, tmp_path: Path
) -> None:
    """The whole point of entry_name: get_api('Capacity') should return
    the [text box] UI control even though the LIKE pattern targets [SimTalk]."""
    db_path = tmp_path / "help.db"
    with SQLiteFTSIndex(db_path) as idx:
        build_fullmd(fullmd_file, idx)
        hits = idx.find_by_section("Capacity", top_k=5)
    sections = [h.section for h in hits]
    assert "Capacity [text box] - Source" in sections
