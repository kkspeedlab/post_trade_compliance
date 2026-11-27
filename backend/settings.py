"""Approved RM-204 processing policy."""
from datetime import date

INITIAL_ORDER_DATE = date(2026, 11, 1)

def eligible_order_date(order_date: date, as_of: date) -> bool:
    """Inclusive order-date boundary; bank reporting dates are independent."""
    return INITIAL_ORDER_DATE <= order_date <= as_of
