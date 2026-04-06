"""Unit tests for the order state machine -- no database required."""

import pytest

from app.services.order_service import validate_transition
from app.models.order import ORDER_TRANSITIONS


# -- Valid transitions ---------------------------------------------------------

VALID_TRANSITIONS = [
    ("created", "payment_recorded"),
    ("payment_recorded", "accepted"),
    ("accepted", "dispatched"),
    ("dispatched", "arrived"),
    ("arrived", "in_service"),
    ("in_service", "completed"),
    ("completed", "after_sales_credit"),
]


@pytest.mark.parametrize("from_status,to_status", VALID_TRANSITIONS)
def test_valid_transition(from_status, to_status):
    assert validate_transition(from_status, to_status) is True, (
        f"Expected transition {from_status} -> {to_status} to be valid"
    )


# -- Invalid transitions -------------------------------------------------------

INVALID_TRANSITIONS = [
    ("created", "dispatched"),
    ("created", "completed"),
    ("payment_recorded", "dispatched"),
]


@pytest.mark.parametrize("from_status,to_status", INVALID_TRANSITIONS)
def test_invalid_transition(from_status, to_status):
    assert validate_transition(from_status, to_status) is False, (
        f"Expected transition {from_status} -> {to_status} to be invalid"
    )


# -- Terminal state ------------------------------------------------------------

def test_after_sales_credit_is_terminal():
    next_states = ORDER_TRANSITIONS.get("after_sales_credit", [])
    assert next_states == [], (
        f"after_sales_credit should be terminal with no valid next states, got: {next_states}"
    )
