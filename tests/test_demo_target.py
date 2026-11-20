import pytest
from demo_target.discount_calculator import calculate_discounted_price, calculate_bulk_order_total

def test_discount_calculation():
    """
    Verifies that discount subtraction behaves accurately:
    A $100 item discounted at 20% must equal $80.00.
    With the unpatched bug, this produces $120.00 and fails.
    """
    result = calculate_discounted_price(100.0, 20.0)
    assert result == 80.0, f"Expected $80.00, got ${result} (formula added instead of subtracted)"

def test_bulk_order_discount():
    items = [
        {"price": 50.0, "discount_percent": 10.0}, # should be 45.0
        {"price": 100.0, "discount_percent": 30.0} # should be 70.0
    ]
    # Total should be 115.0
    assert calculate_bulk_order_total(items) == 115.0
