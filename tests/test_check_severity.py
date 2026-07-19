"""Regression coverage for the Check severity taxonomy (GH-153).

Every Check carries a severity in {notice, warning, error}. These pin the
dataclass contract the panel bucketing relies on.
"""

import pytest

from rebalance.doctor import (
    ERROR,
    FAIL,
    NOTICE,
    OK,
    WARN,
    WARNING,
    Check,
)


def test_default_severity_is_warning() -> None:
    assert Check("x", WARN, "d").severity == WARNING


def test_explicit_severity_preserved() -> None:
    assert Check("x", OK, "d", severity=NOTICE).severity == NOTICE
    assert Check("x", WARN, "d", severity=ERROR).severity == ERROR


def test_invalid_severity_rejected() -> None:
    with pytest.raises(ValueError):
        Check("x", WARN, "d", severity="critical")  # type: ignore[arg-type]


def test_fail_status_upgrades_warning_to_error() -> None:
    """Legacy FAIL emitters that never set a severity land in the error bucket."""
    assert Check("database", FAIL, "missing").severity == ERROR


def test_fail_status_keeps_explicit_notice() -> None:
    """A deliberate non-warning severity is not overridden by the FAIL upgrade."""
    assert Check("x", FAIL, "d", severity=NOTICE).severity == NOTICE
