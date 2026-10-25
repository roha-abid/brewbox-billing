"""BUG-101: discount applies to the plan line only and is capped at 30%."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from brewbox.models import LineKind


def _sub(service, customer, discount, addons=("extra_bag",), start=date(2025, 1, 1)):
    return service.create_subscription(
        customer["id"],
        plan_code="starter",
        addon_codes=list(addons),
        start_date=start,
        discount_percent=discount,
    )


def _line(invoice, kind):
    return next(line for line in invoice.lines if line.kind == kind)


def test_zero_percent_discount_creates_no_discount_line(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, 0)["id"], 2025, 1)
    assert invoice.discount_total == Decimal("0.00")
    assert all(line.kind != LineKind.DISCOUNT for line in invoice.lines)
    assert invoice.total == Decimal("27.06")


def test_discount_is_calculated_from_plan_only(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, 20)["id"], 2025, 1)
    assert invoice.subtotal == Decimal("25.00")
    assert invoice.discount_total == Decimal("3.60")  # 20% of 18.00, not of 25.00
    assert _line(invoice, LineKind.ADDON).amount == Decimal("7.00")
    assert _line(invoice, LineKind.DISCOUNT).amount == Decimal("-3.60")
    assert invoice.tax_total == Decimal("1.77")
    assert invoice.total == Decimal("23.17")


def test_exactly_thirty_percent_is_accepted(service, ana):
    sub = _sub(service, ana, 30)
    assert sub["discount_percent"] == Decimal("30")
    invoice = service.issue_invoice(sub["id"], 2025, 1)
    assert invoice.discount_total == Decimal("5.40")
    # (18.00 - 5.40 + 7.00) * 8.25% = 1.6170 -> 1.62
    assert invoice.tax_total == Decimal("1.62")
    assert invoice.total == Decimal("21.22")


@pytest.mark.parametrize("bad", [31, "30.01", Decimal("30.1"), 45, 100])
def test_discount_above_thirty_is_rejected_not_clamped(service, ana, bad):
    with pytest.raises(ValueError):
        _sub(service, ana, bad)
    assert service.repo.subscriptions == {}


@pytest.mark.parametrize("bad", [-1, "-0.01"])
def test_negative_discount_is_rejected(service, ana, bad):
    with pytest.raises(ValueError):
        _sub(service, ana, bad)
    assert service.repo.subscriptions == {}


def test_non_numeric_discount_is_a_value_error(service, ana):
    with pytest.raises(ValueError):
        _sub(service, ana, "abc")


def test_one_decimal_discount_is_valid(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, "12.5")["id"], 2025, 1)
    assert invoice.discount_total == Decimal("2.25")  # 18.00 * 12.5%
    assert _line(invoice, LineKind.DISCOUNT).description == "Discount 12.5%"


def test_discount_rounds_half_up_before_tax(service, ana):
    # 18.00 * 12.25% = 2.205 -> 2.21 (half-up), not 2.20
    invoice = service.issue_invoice(_sub(service, ana, "12.25", addons=())["id"], 2025, 1)
    assert invoice.discount_total == Decimal("2.21")
    # tax on 18.00 - 2.21 = 15.79 -> 1.302675 -> 1.30
    assert invoice.tax_total == Decimal("1.30")
    assert invoice.total == Decimal("17.09")


def test_discount_line_is_negative_and_total_adds_up(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, 10)["id"], 2025, 1)
    discount = _line(invoice, LineKind.DISCOUNT)
    assert discount.amount < 0
    assert invoice.total == invoice.subtotal - invoice.discount_total + invoice.tax_total


def test_discount_without_addons_matches_plan_only_math(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, 10, addons=())["id"], 2025, 1)
    assert invoice.discount_total == Decimal("1.80")
    assert invoice.total == Decimal("17.54")  # 16.20 + 1.34 (1.3365)
