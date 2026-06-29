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


# ---------------------------------------------------------------------------
# .psfm fixture — mirrors a realistic .psfm layout in miniature
# ---------------------------------------------------------------------------

# Parent Frame definition for a "Station" class. No Origin → root.
_STATION_FRAME_YAML = """\
InternalClassType: Frame
Name: Station
UUID: 11111111-1111-1111-1111-111111111111
$SequenceNumber: 2
"""

# A Variable on the Station parent. No Origin → root.
_STATION_PALLET_CAPACITY_YAML = """\
InternalClassType: Variable
Name: FleetCapacity
DataType: integer
UUID: 22222222-2222-2222-2222-222222222222
$SequenceNumber: 40
Value: 10
"""

# A Method on the Station parent. Has Program body.
_STATION_INIT_METHOD_YAML = """\
InternalClassType: Method
Name: Init
UUID: 33333333-3333-3333-3333-333333333333
$SequenceNumber: 3
Program: |+1
 root.FleetCapacity := 20
 InitFleet.executeIn(0)
"""

# A Buffer with $Predecessors and an inline $CustomAttributes method.
_STATION_BUFFER_YAML = """\
InternalClassType: Buffer
Name: Buffer
UUID: 44444444-4444-4444-4444-444444444444
$SequenceNumber: 1
$Predecessors:
- 99999999-9999-9999-9999-999999999999
$CustomAttributes:
-
 Name: OnEntrance
 DataType: method
 Value: |+1
  local AMR := @
  if ?._RunMethod /= void
  \t?._RunMethod.execute(AMR)
  end
"""

# Top-level Method directly in the Model frame.
_MODEL_INIT_FLEET_YAML = """\
InternalClassType: Method
Name: InitFleet
UUID: 55555555-5555-5555-5555-555555555555
$SequenceNumber: 10
Program: |+1
 local FleetNum : integer
 for var i:=1 to FleetInput.ydim
 \tFleetNum := str_to_obj("FleetNumZ").value
 end
"""

# Model frame ($.yaml).
_MODEL_FRAME_YAML = """\
InternalClassType: Frame
Name: Model
UUID: 66666666-6666-6666-6666-666666666666
$SequenceNumber: 1
"""

# An instance folder under the Model — multi-doc YAML.
# First doc = the instance Frame (Origin -> Station parent).
# Subsequent docs = pure-inheritance children with no body.
# One doc overrides the Init method (has its own Program body).
_INSTANCE_MULTI_DOC_YAML = """\
---
InternalClassType: Frame
Origin: 11111111-1111-1111-1111-111111111111
UUID: 77777777-7777-7777-7777-777777777777
$SequenceNumber: 100
---
$ObjectName: FleetCapacity
InternalClassType: Variable
Origin: 22222222-2222-2222-2222-222222222222
UUID: 88888888-8888-8888-8888-888888888888
$SequenceNumber: 1
$DataType: integer
Value: 99
---
$ObjectName: Init
InternalClassType: Method
Origin: 33333333-3333-3333-3333-333333333333
UUID: aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa
$SequenceNumber: 2
Program: |+1
 root.FleetCapacity := 50
---
$ObjectName: Buffer
InternalClassType: Buffer
Origin: 44444444-4444-4444-4444-444444444444
UUID: bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb
$SequenceNumber: 3
"""


@pytest.fixture
def sample_psfm(tmp_path: Path) -> Path:
    """Create a miniature ``.psfm`` folder mirroring a realistic layout.

    Structure:
        Sample.psfm/
            Models/
                Station/
                    $.yaml                  (parent Frame)
                    FleetCapacity.yaml      (parent Variable)
                    Init.yaml               (parent Method w/ Program)
                    Buffer.yaml             (parent Buffer w/ inline method + $Predecessors)
                Model/
                    $.yaml                  (scene Frame)
                    InitFleet.yaml          (Method directly in Model)
                    Station_Instance1/
                        $.yaml              (multi-doc: instance + pure-inh children + override)
    """
    project = tmp_path / "Sample.psfm"
    station = project / "Models" / "Station"
    model = project / "Models" / "Model"
    instance = model / "Station_Instance1"
    station.mkdir(parents=True)
    instance.mkdir(parents=True)

    (station / "$.yaml").write_text(_STATION_FRAME_YAML, encoding="utf-8")
    (station / "FleetCapacity.yaml").write_text(
        _STATION_PALLET_CAPACITY_YAML, encoding="utf-8"
    )
    (station / "Init.yaml").write_text(_STATION_INIT_METHOD_YAML, encoding="utf-8")
    (station / "Buffer.yaml").write_text(_STATION_BUFFER_YAML, encoding="utf-8")
    (model / "$.yaml").write_text(_MODEL_FRAME_YAML, encoding="utf-8")
    (model / "InitFleet.yaml").write_text(
        _MODEL_INIT_FLEET_YAML, encoding="utf-8"
    )
    (instance / "$.yaml").write_text(_INSTANCE_MULTI_DOC_YAML, encoding="utf-8")

    return project
