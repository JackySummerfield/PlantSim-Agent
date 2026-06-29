"""Pytest config for the slow evaluation suites.

Adds the ``--run-eval`` opt-in flag.
"""

from __future__ import annotations


def pytest_addoption(parser):  # type: ignore[no-untyped-def]
    parser.addoption(
        "--run-eval",
        action="store_true",
        default=False,
        help="Run the slow PlantSim-Agent evaluation suites.",
    )
