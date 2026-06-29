"""Shared pytest fixtures for plantsim-mcp."""

from __future__ import annotations

from pathlib import Path

import pytest


SAMPLE_BUFFER_MD = """\
# Buffer

Buffers are passive material-flow objects.

## Attributes

### numMU

`numMU` returns the current number of MUs in the buffer.

The value is updated synchronously as MUs enter and leave.

### capacity

`capacity` is the maximum number of MUs the buffer can hold.

## Methods

### move

`move(target)` moves the front MU to the target object.
"""

SAMPLE_FLOWCONTROL_MD = """\
# FlowControl

A FlowControl distributes MUs to its successors according to a rule.

## Strategy

The default strategy is cyclic.
"""


@pytest.fixture
def sample_kb(tmp_path: Path) -> Path:
    """Create a tiny markdown KB on disk and return its root."""
    root = tmp_path / "kb"
    root.mkdir()
    (root / "Buffer.md").write_text(SAMPLE_BUFFER_MD, encoding="utf-8")
    sub = root / "FlowControl"
    sub.mkdir()
    (sub / "FlowControl.md").write_text(SAMPLE_FLOWCONTROL_MD, encoding="utf-8")
    return root
