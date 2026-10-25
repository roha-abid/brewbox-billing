"""BUG-102: calendar-correct proration (active days / real days in month)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from brewbox.models import LineKind


def _sub(service, customer, start, addons=("extra_bag",), discount=0, plan="starter"):
    return service.create_subscription(
        customer["id"],
        plan_code=plan,
        addon_codes=list(addons),
        start_date=start,
        discount_percent=discount,
    )


def _amount(invoice, kind):
    return next(line.amount for line in invoice.lines if line.kind == kind)


def test_march_15_start_bills_17_of_31_days(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, date(2025, 3, 15))["id"], 2025, 3)
    assert _amount(invoice, LineKind.PLAN) == Decimal("9.87")  # 18.00 * 17/31
    assert _amount(invoice, LineKind.ADDON) == Decimal("3.84")  # 7.00 * 17/31
    assert invoice.subtotal == Decimal("13.71")
    assert invoice.tax_total == Decimal("1.13")
    assert invoice.total == Decimal("14.84")


def test_period_dates_still_cover_the_full_month(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, date(2025, 3, 15))["id"], 2025, 3)
    assert invoice.period_start == date(2025, 3, 1)
    assert invoice.period_end == date(2025, 3, 31)


def test_start_on_first_of_month_is_a_full_month(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, date(2025, 3, 1))["id"], 2025, 3)
    assert _amount(invoice, LineKind.PLAN) == Decimal("18.00")
    assert _amount(invoice, LineKind.ADDON) == Decimal("7.00")


def test_start_before_the_month_is_a_full_month(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, date(2025, 1, 20))["id"], 2025, 3)
    assert invoice.subtotal == Decimal("25.00")


def test_start_on_last_day_bills_one_day(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, date(2025, 3, 31))["id"], 2025, 3)
    assert _amount(invoice, LineKind.PLAN) == Decimal("0.58")  # 18.00 / 31 = 0.5806
    assert _amount(invoice, LineKind.ADDON) == Decimal("0.23")  # 7.00 / 31 = 0.2258


@pytest.mark.parametrize(
    "year, month, days_in_month",
    [(2025, 2, 28), (2024, 2, 29), (2025, 4, 30), (2025, 1, 31)],
)
def test_denominator_is_actual_days_in_month(service, ana, year, month, days_in_month):
    start = date(year, month, 11)
    invoice = service.issue_invoice(_sub(service, ana, start, addons=())["id"], year, month)
    active = days_in_month - 11 + 1
    expected = (Decimal("18.00") * active / days_in_month).quantize(Decimal("0.01"), "ROUND_HALF_UP")
    assert _amount(invoice, LineKind.PLAN) == expected


def test_leap_february_uses_29_days(service, ana):
    sub = _sub(service, ana, date(2024, 2, 15), addons=())
    invoice = service.issue_invoice(sub["id"], 2024, 2)
    # 15th..29th inclusive = 15 days; 18.00 * 15/29 = 9.3103 -> 9.31
    assert _amount(invoice, LineKind.PLAN) == Decimal("9.31")


def test_non_leap_february_uses_28_days(service, ana):
    sub = _sub(service, ana, date(2025, 2, 15), addons=())
    invoice = service.issue_invoice(sub["id"], 2025, 2)
    # 15th..28th inclusive = 14 days; 18.00 * 14/28 = 9.00
    assert _amount(invoice, LineKind.PLAN) == Decimal("9.00")


def test_full_month_has_no_rounding_drift_for_any_month_length(service, ana):
    sub = _sub(service, ana, date(2024, 1, 1), addons=("extra_bag", "grinder"), plan="connoisseur")
    for month in range(1, 13):
        invoice = service.issue_invoice(sub["id"], 2024, month)
        assert invoice.subtotal == Decimal("67.00")  # 55 + 7 + 5


def test_every_addon_is_prorated_with_the_same_factor(service, ana):
    sub = _sub(service, ana, date(2025, 3, 15), addons=("extra_bag", "grinder", "priority"))
    invoice = service.issue_invoice(sub["id"], 2025, 3)
    addons = [line.amount for line in invoice.lines if line.kind == LineKind.ADDON]
    assert addons == [Decimal("3.84"), Decimal("2.74"), Decimal("2.19")]


def test_each_line_is_rounded_before_tax(service, ana):
    invoice = service.issue_invoice(_sub(service, ana, date(2025, 3, 15))["id"], 2025, 3)
    # tax is on the sum of rounded lines (13.71), not on unrounded 13.7097...
    assert invoice.subtotal == _amount(invoice, LineKind.PLAN) + _amount(invoice, LineKind.ADDON)
    assert invoice.tax_total == Decimal("1.13")


def test_discount_is_taken_from_prorated_plan_amount(service, ana):
    sub = _sub(service, ana, date(2025, 3, 15), discount=20)
    invoice = service.issue_invoice(sub["id"], 2025, 3)
    assert _amount(invoice, LineKind.PLAN) == Decimal("9.87")
    assert invoice.discount_total == Decimal("1.97")  # 9.87 * 20% = 1.974
    # taxable = 9.87 - 1.97 + 3.84 = 11.74 -> 0.96855 -> 0.97
    assert invoice.tax_total == Decimal("0.97")
    assert invoice.total == Decimal("12.71")


def test_subscription_starting_after_the_month_has_no_invoice(service, ana):
    sub = _sub(service, ana, date(2025, 4, 1))
    assert service.issue_invoice(sub["id"], 2025, 3) is None
    assert service.repo.invoices == {}


def test_month_before_start_returns_none_not_a_zero_invoice(service, ana):
    sub = _sub(service, ana, date(2025, 3, 15))
    assert service.issue_invoice(sub["id"], 2025, 2) is None
    assert service.issue_invoice(sub["id"], 2025, 3) is not None
    assert len(service.repo.invoices) == 1


def test_prorated_invoice_is_still_idempotent(service, ana):
    sub = _sub(service, ana, date(2025, 3, 15))
    first = service.issue_invoice(sub["id"], 2025, 3)
    assert service.issue_invoice(sub["id"], 2025, 3) is first
    assert len(service.repo.invoices) == 1
