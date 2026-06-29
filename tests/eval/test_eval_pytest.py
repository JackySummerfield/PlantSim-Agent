"""Pytest wrapper for the slow evaluation suites.

Skipped by default; run explicitly with::

    pytest tests/eval --run-eval

The actual logic lives in :mod:`tests.eval.run_eval` so both ``python
tests/eval/run_eval.py`` and pytest exercise the same code. The
``--run-eval`` flag is registered in this directory's ``conftest.py``.
"""

from __future__ import annotations

import pytest

from . import run_eval


def _requires_eval_flag(request: pytest.FixtureRequest) -> None:
    if not request.config.getoption("--run-eval"):
        pytest.skip("eval suite is opt-in; rerun with --run-eval")


def test_qa_recall(request: pytest.FixtureRequest) -> None:
    _requires_eval_flag(request)
    result = run_eval.run_qa_suite(verbose=False)
    assert result.ok, (
        f"QA recall {result.passed}/{result.total}\n"
        + "\n".join(f"  - {f}" for f in result.failures)
    )


def test_citation_recall(request: pytest.FixtureRequest) -> None:
    _requires_eval_flag(request)
    result = run_eval.run_citation_suite(verbose=False)
    assert result.ok, (
        f"Citation recall {result.passed}/{result.total}\n"
        + "\n".join(f"  - {f}" for f in result.failures)
    )

