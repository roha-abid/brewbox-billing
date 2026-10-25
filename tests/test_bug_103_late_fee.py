"""BUG-103: the late fee starts on due date + 6 (five full grace days)."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from brewbox.models import InvoiceStatus, LineKind


@pytest.fixture
def invoice(service, starter_sub):
    return service.issue_invoice(starter_sub["id"], 2025, 1, issued_on=date(2025, 1, 1))


def _fee_lines(invoice):
    return [line for line in invoice.lines if line.kind == LineKind.LATE_FEE]


def test_due_date_is_fourteen_days_after_issue(invoice):
    assert invoice.due_on == date(2025, 1, 15)


@pytest.mark.parametrize("as_of", [date(2025, 1, 10), date(2025, 1, 15), date(2025, 1, 19), date(2025, 1, 20)])
def test_no_fee_up_to_and_including_due_date_plus_five(service, invoice, as_of):
    service.apply_late_fee(invoice.id, as_of=as_of)
    assert invoice.late_fee == Decimal("0.00")
    assert _fee_lines(invoice) == []
    assert invoice.total == Decimal("27.06")


@pytest.mark.parametrize("as_of", [date(2025, 1, 21), date(2025, 1, 22), date(2025, 3, 1)])
def test_fee_applies_from_due_date_plus_six(service, invoice, as_of):
    service.apply_late_fee(invoice.id, as_of=as_of)
    assert invoice.late_fee == Decimal("10.00")
    assert len(_fee_lines(invoice)) == 1


def test_fee_is_idempotent(service, invoice):
    for day in (date(2025, 1, 21), date(2025, 1, 21), date(2025, 2, 15)):
        service.apply_late_fee(invoice.id, as_of=day)
    assert len(_fee_lines(invoice)) == 1
    assert invoice.total == Decimal("37.06")


def test_fee_is_untaxed_and_raises_total_and_amount_due_by_ten(service, invoice):
    tax_before = invoice.tax_total
    due_before = invoice.amount_due
    service.apply_late_fee(invoice.id, as_of=date(2025, 1, 21))
    assert invoice.tax_total == tax_before
    assert invoice.amount_due == due_before + Decimal("10.00")
    assert invoice.subtotal == Decimal("25.00")  # fee is not part of the subtotal


def test_paid_invoice_never_gets_a_fee(service, invoice):
    service.record_payment(invoice.id, paid_on=date(2025, 1, 10))
    service.apply_late_fee(invoice.id, as_of=date(2025, 2, 1))
    assert invoice.late_fee == Decimal("0.00")
    assert _fee_lines(invoice) == []


def test_invoice_paid_after_fee_does_not_get_a_second_fee(service, invoice):
    service.apply_late_fee(invoice.id, as_of=date(2025, 1, 21))
    service.record_payment(invoice.id, paid_on=date(2025, 1, 22))
    assert invoice.status == InvoiceStatus.PAID
    service.apply_late_fee(invoice.id, as_of=date(2025, 3, 1))
    assert len(_fee_lines(invoice)) == 1
    assert invoice.total == Decimal("37.06")


def test_partial_payment_still_allows_fee_once_grace_has_passed(service, invoice):
    service.record_payment(invoice.id, amount="10.00", paid_on=date(2025, 1, 5))
    assert invoice.status == InvoiceStatus.ISSUED
    service.apply_late_fee(invoice.id, as_of=date(2025, 1, 20))
    assert invoice.late_fee == Decimal("0.00")
    service.apply_late_fee(invoice.id, as_of=date(2025, 1, 21))
    assert invoice.late_fee == Decimal("10.00")
    assert invoice.amount_due == Decimal("27.06") - Decimal("10.00") + Decimal("10.00")


def test_default_as_of_uses_service_today(service, invoice):
    # fixture "today" is 2025-03-01, well past the grace window
    service.apply_late_fee(invoice.id)
    assert invoice.late_fee == Decimal("10.00")
