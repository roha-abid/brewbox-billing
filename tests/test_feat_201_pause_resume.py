"""FEAT-201: pause and resume subscriptions."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from brewbox.models import LineKind, PausePeriod, SubscriptionStatus

REQUEST_DAY = date(2025, 1, 2)  # "today" when a pause is requested in most tests


@pytest.fixture
def sub(service, ana):
    return service.create_subscription(
        ana["id"],
        plan_code="starter",
        addon_codes=["extra_bag"],
        start_date=date(2025, 1, 1),
    )


def _pause(service, sub, start, days, as_of=REQUEST_DAY):
    return service.pause_subscription(
        sub["id"], start, start + timedelta(days=days - 1), as_of=as_of
    )


def _plan(invoice):
    return next(line.amount for line in invoice.lines if line.kind == LineKind.PLAN)


def _addon(invoice):
    return next(line.amount for line in invoice.lines if line.kind == LineKind.ADDON)


# ---- length boundaries ---------------------------------------------------
def test_seven_day_pause_is_accepted(service, sub):
    pause = _pause(service, sub, date(2025, 1, 10), 7)
    assert pause == PausePeriod(date(2025, 1, 10), date(2025, 1, 16))
    assert pause.days == 7


def test_six_day_pause_is_rejected(service, sub):
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 1, 10), 6)
    assert service.list_pauses(sub["id"]) == []


def test_ninety_day_pause_is_accepted(service, sub):
    assert _pause(service, sub, date(2025, 1, 10), 90).days == 90


def test_ninety_one_day_pause_is_rejected(service, sub):
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 1, 10), 91)


def test_start_after_end_is_rejected(service, sub):
    with pytest.raises(ValueError):
        service.pause_subscription(sub["id"], date(2025, 1, 20), date(2025, 1, 10), as_of=REQUEST_DAY)


def test_pause_before_subscription_start_is_rejected(service, ana):
    sub = service.create_subscription(ana["id"], "starter", start_date=date(2025, 2, 1))
    with pytest.raises(ValueError):
        service.pause_subscription(sub["id"], date(2025, 1, 25), date(2025, 2, 5), as_of=REQUEST_DAY)


def test_pause_starting_on_subscription_start_is_allowed(service, sub):
    assert _pause(service, sub, date(2025, 1, 1), 7).start == date(2025, 1, 1)


def test_unknown_subscription_is_rejected(service):
    with pytest.raises(ValueError):
        service.pause_subscription("sub-9999", date(2025, 1, 10), date(2025, 1, 20), as_of=REQUEST_DAY)


def test_cancelled_subscription_cannot_be_paused(service, sub):
    service.repo.subscriptions[sub["id"]].cancelled_on = date(2025, 1, 5)
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 1, 10), 7)


# ---- overlaps -----------------------------------------------------------
def test_overlapping_pause_is_rejected(service, sub):
    _pause(service, sub, date(2025, 1, 10), 10)  # 10..19
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 1, 19), 7)  # shares 19 Jan
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 1, 5), 7)  # 5..11 shares 10, 11
    assert len(service.list_pauses(sub["id"])) == 1


def test_adjacent_pause_is_allowed(service, sub):
    _pause(service, sub, date(2025, 1, 10), 10)  # 10..19
    second = _pause(service, sub, date(2025, 1, 20), 7)  # starts the next day
    assert second.start == date(2025, 1, 20)
    assert [p.start for p in service.list_pauses(sub["id"])] == [date(2025, 1, 10), date(2025, 1, 20)]


# ---- billing ------------------------------------------------------------
def test_inclusive_dates_ten_day_pause_resumes_on_the_twentieth(service, sub):
    pause = service.pause_subscription(sub["id"], date(2025, 1, 10), date(2025, 1, 19), as_of=REQUEST_DAY)
    assert pause.days == 10
    subscription = service.repo.subscriptions[sub["id"]]
    assert subscription.status_on(date(2025, 1, 19)) == SubscriptionStatus.PAUSED
    assert subscription.status_on(date(2025, 1, 20)) == SubscriptionStatus.ACTIVE
    invoice = service.issue_invoice(sub["id"], 2025, 1)
    # 31 - 10 = 21 active days
    assert _plan(invoice) == Decimal("12.19")  # 18.00 * 21/31 = 12.1935
    assert _addon(invoice) == Decimal("4.74")  # 7.00 * 21/31 = 4.7419


def test_paused_days_are_removed_from_plan_and_every_addon(service, ana):
    sub = service.create_subscription(ana["id"], "starter", ["extra_bag", "grinder"], date(2025, 1, 1))
    _pause(service, sub, date(2025, 1, 10), 10)
    invoice = service.issue_invoice(sub["id"], 2025, 1)
    addons = [line.amount for line in invoice.lines if line.kind == LineKind.ADDON]
    assert addons == [Decimal("4.74"), Decimal("3.39")]  # 7*21/31, 5*21/31


def test_pause_across_month_boundary_prorates_both_months(service, sub):
    # 28 Jan .. 6 Feb: January loses 4 days, February loses 6 days
    service.pause_subscription(sub["id"], date(2025, 1, 28), date(2025, 2, 6), as_of=REQUEST_DAY)
    jan = service.issue_invoice(sub["id"], 2025, 1)
    feb = service.issue_invoice(sub["id"], 2025, 2)
    assert _plan(jan) == Decimal("15.68")  # 18.00 * 27/31 = 15.6774
    assert _plan(feb) == Decimal("14.14")  # 18.00 * 22/28 = 14.1428
    assert _addon(feb) == Decimal("5.50")  # 7.00 * 22/28


def test_fully_paused_month_has_no_invoice(service, sub):
    service.pause_subscription(sub["id"], date(2025, 2, 1), date(2025, 2, 28), as_of=REQUEST_DAY)
    assert service.issue_invoice(sub["id"], 2025, 2) is None
    assert service.repo.invoices_for_subscription(sub["id"]) == []
    assert service.issue_invoice(sub["id"], 2025, 3) is not None  # billing resumes


def test_pause_longer_than_a_month_skips_the_whole_middle_month(service, sub):
    service.pause_subscription(sub["id"], date(2025, 1, 20), date(2025, 3, 10), as_of=REQUEST_DAY)  # 50 days
    assert service.issue_invoice(sub["id"], 2025, 2) is None
    jan = service.issue_invoice(sub["id"], 2025, 1)
    mar = service.issue_invoice(sub["id"], 2025, 3)
    assert _plan(jan) == Decimal("11.03")  # 19 active days (1-19 Jan): 18.00 * 19/31
    assert _plan(mar) == Decimal("12.19")  # 21 of 31 days: 18.00 * 21/31


def test_pause_combined_with_mid_month_start(service, ana):
    sub = service.create_subscription(ana["id"], "starter", [], date(2025, 3, 15))
    service.pause_subscription(sub["id"], date(2025, 3, 20), date(2025, 3, 26), as_of=date(2025, 3, 15))
    invoice = service.issue_invoice(sub["id"], 2025, 3)
    # 15..31 = 17 days, minus 7 paused = 10 active; 18.00 * 10/31 = 5.806 -> 5.81
    assert _plan(invoice) == Decimal("5.81")


def test_discount_applies_to_the_reduced_plan_amount(service, ana):
    sub = service.create_subscription(ana["id"], "starter", ["extra_bag"], date(2025, 1, 1), discount_percent=10)
    _pause(service, sub, date(2025, 1, 10), 10)
    invoice = service.issue_invoice(sub["id"], 2025, 1)
    assert _plan(invoice) == Decimal("12.19")
    assert invoice.discount_total == Decimal("1.22")  # 12.19 * 10% = 1.219


def test_unpaused_month_is_unchanged(service, sub):
    _pause(service, sub, date(2025, 2, 10), 7)
    invoice = service.issue_invoice(sub["id"], 2025, 1)
    assert invoice.subtotal == Decimal("25.00")


def test_pause_after_invoice_does_not_change_existing_invoice(service, sub):
    invoice = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    before = (invoice.subtotal, invoice.total, len(invoice.lines), invoice.credit_applied)
    _pause(service, sub, date(2025, 1, 10), 10, as_of=date(2025, 1, 5))
    assert (invoice.subtotal, invoice.total, len(invoice.lines), invoice.credit_applied) == before
    assert service.issue_invoice(sub["id"], 2025, 1) is invoice  # idempotent, not re-rated


# ---- overdue guardrail ---------------------------------------------------
def test_pause_blocked_by_overdue_unpaid_invoice(service, sub):
    service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))  # due 15 Jan
    with pytest.raises(ValueError):
        service.pause_subscription(sub["id"], date(2025, 3, 1), date(2025, 3, 10), as_of=date(2025, 1, 16))
    assert service.list_pauses(sub["id"]) == []


def test_overdue_check_uses_request_date_not_pause_start(service, sub):
    service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    # requested on the due date: not yet overdue, even though the pause starts much later
    pause = service.pause_subscription(sub["id"], date(2025, 3, 1), date(2025, 3, 10), as_of=date(2025, 1, 15))
    assert pause.start == date(2025, 3, 1)


def test_invoice_due_today_is_not_overdue_but_tomorrow_is(service, sub):
    service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 1, 15))
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 4, 1), 7, as_of=date(2025, 1, 16))


def test_paid_invoice_does_not_block_a_pause(service, sub):
    invoice = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    service.record_payment(invoice.id, paid_on=date(2025, 1, 5))
    assert _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 2, 20)).days == 7


def test_settled_overdue_invoice_unblocks_pause(service, sub):
    invoice = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 1, 20))
    service.record_payment(invoice.id, paid_on=date(2025, 1, 21))
    assert _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 1, 22)).days == 7


def test_partially_paid_overdue_invoice_still_blocks(service, sub):
    invoice = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    service.record_payment(invoice.id, amount="5.00", paid_on=date(2025, 1, 5))
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 1, 20))


def test_overdue_invoice_on_another_subscription_of_same_customer_blocks(service, ana, sub):
    other = service.create_subscription(ana["id"], "daily", start_date=date(2025, 1, 1))
    service.issue_invoice(other["id"], 2025, 1, issued_on=date(2025, 1, 1))
    with pytest.raises(ValueError):
        _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 1, 20))


def test_overdue_invoice_of_a_different_customer_does_not_block(service, sub):
    bob = service.create_customer("Bob", "bob@example.com", "BOB-1")
    other = service.create_subscription(bob["id"], "daily", start_date=date(2025, 1, 1))
    service.issue_invoice(other["id"], 2025, 1, issued_on=date(2025, 1, 1))
    assert _pause(service, sub, date(2025, 3, 1), 7, as_of=date(2025, 1, 20)).days == 7


# ---- resume --------------------------------------------------------------
def test_early_resume_shortens_the_pause_and_resume_day_is_active(service, sub):
    _pause(service, sub, date(2025, 1, 10), 20)  # 10..29
    pause = service.resume_subscription(sub["id"], date(2025, 1, 20))
    assert pause == PausePeriod(date(2025, 1, 10), date(2025, 1, 19))
    subscription = service.repo.subscriptions[sub["id"]]
    assert subscription.status_on(date(2025, 1, 19)) == SubscriptionStatus.PAUSED
    assert subscription.status_on(date(2025, 1, 20)) == SubscriptionStatus.ACTIVE
    invoice = service.issue_invoice(sub["id"], 2025, 1)
    assert _plan(invoice) == Decimal("12.19")  # 10 paused days removed


def test_resume_that_leaves_six_days_is_rejected(service, sub):
    _pause(service, sub, date(2025, 1, 10), 20)  # 10..29
    with pytest.raises(ValueError):
        service.resume_subscription(sub["id"], date(2025, 1, 16))  # would leave 10..15 = 6 days
    assert service.list_pauses(sub["id"])[0].end == date(2025, 1, 29)


def test_resume_that_leaves_exactly_seven_days_is_accepted(service, sub):
    _pause(service, sub, date(2025, 1, 10), 20)
    pause = service.resume_subscription(sub["id"], date(2025, 1, 17))  # 10..16 = 7 days
    assert pause.days == 7


def test_resume_on_or_before_pause_start_is_rejected(service, sub):
    _pause(service, sub, date(2025, 1, 10), 20)
    with pytest.raises(ValueError):
        service.resume_subscription(sub["id"], date(2025, 1, 10))
    with pytest.raises(ValueError):
        service.resume_subscription(sub["id"], date(2025, 1, 5))


def test_resume_without_a_pause_covering_the_date_is_rejected(service, sub):
    with pytest.raises(ValueError):
        service.resume_subscription(sub["id"], date(2025, 1, 20))
    _pause(service, sub, date(2025, 1, 10), 10)  # 10..19
    with pytest.raises(ValueError):
        service.resume_subscription(sub["id"], date(2025, 1, 20))  # pause already over


def test_resume_picks_the_right_pause_when_several_exist(service, sub):
    _pause(service, sub, date(2025, 1, 10), 7)  # 10..16
    _pause(service, sub, date(2025, 2, 1), 20)  # 1..20 Feb
    service.resume_subscription(sub["id"], date(2025, 2, 11))
    pauses = service.list_pauses(sub["id"])
    assert pauses[0] == PausePeriod(date(2025, 1, 10), date(2025, 1, 16))
    assert pauses[1] == PausePeriod(date(2025, 2, 1), date(2025, 2, 10))


def test_resume_unknown_subscription_is_rejected(service):
    with pytest.raises(ValueError):
        service.resume_subscription("sub-9999", date(2025, 1, 20))


# ---- listing -------------------------------------------------------------
def test_list_pauses_is_chronological_and_returns_a_copy(service, sub):
    _pause(service, sub, date(2025, 3, 1), 7)
    _pause(service, sub, date(2025, 1, 10), 7)
    pauses = service.list_pauses(sub["id"])
    assert [p.start for p in pauses] == [date(2025, 1, 10), date(2025, 3, 1)]
    pauses.clear()
    assert len(service.list_pauses(sub["id"])) == 2


def test_list_pauses_unknown_subscription_is_rejected(service):
    with pytest.raises(ValueError):
        service.list_pauses("sub-9999")
