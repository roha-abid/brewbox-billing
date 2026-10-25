"""FEAT-202: referral credit ledger."""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from brewbox.models import InvoiceStatus, LineKind, Plan


@pytest.fixture
def referrer(ana):
    return ana  # referral code ANA-123


@pytest.fixture
def referee(service, referrer):
    return service.create_customer("Bob Jones", "bob@example.com", "BOB-456", referred_by="ANA-123")


def _sub(service, customer, plan="starter", addons=("extra_bag",), start=date(2025, 1, 1), discount=0):
    return service.create_subscription(
        customer["id"], plan, list(addons), start_date=start, discount_percent=discount
    )


def _first_invoice_paid(service, customer, paid_on=date(2025, 1, 10), **kwargs):
    sub = _sub(service, customer, **kwargs)
    invoice = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    service.record_payment(invoice.id, paid_on=paid_on)
    return sub, invoice


# ---- customer creation ---------------------------------------------------
def test_unknown_referral_code_is_rejected(service):
    with pytest.raises(ValueError):
        service.create_customer("Bob", "bob@example.com", "BOB-1", referred_by="NOPE-1")
    assert service.repo.customer_by_referral_code("BOB-1") is None


def test_self_referral_is_rejected(service):
    with pytest.raises(ValueError):
        service.create_customer("Bob", "bob@example.com", "BOB-1", referred_by="BOB-1")
    assert service.repo.customers == {}


def test_self_referral_is_rejected_case_insensitively(service):
    with pytest.raises(ValueError):
        service.create_customer("Bob", "bob@example.com", "bob-1", referred_by=" Bob-1 ")


def test_referral_code_lookup_is_normalised(service, referrer):
    bob = service.create_customer("Bob", "bob@example.com", "BOB-1", referred_by=" ana-123 ")
    assert bob["referred_by"] == "ANA-123"


def test_customer_without_referral_is_still_allowed(service):
    bob = service.create_customer("Bob", "bob@example.com", "BOB-1")
    assert bob["referred_by"] is None


# ---- awarding ------------------------------------------------------------
def test_first_paid_invoice_creates_ten_percent_credit_including_addons(service, referrer, referee):
    _, invoice = _first_invoice_paid(service, referee)
    credits = service.list_credits(referrer["id"])
    assert len(credits) == 1
    credit = credits[0]
    assert credit.amount == Decimal("2.50")  # 10% of 18.00 + 7.00, tax excluded
    assert credit.remaining == Decimal("2.50")
    assert credit.customer_id == referrer["id"]
    assert credit.source_customer_id == referee["id"]
    assert credit.source_invoice_id == invoice.id
    assert credit.issued_on == date(2025, 1, 10)
    assert credit.expires_on == date(2025, 1, 10) + timedelta(days=365)
    assert service.credit_balance(referrer["id"], as_of=date(2025, 1, 11)) == Decimal("2.50")


def test_credit_base_is_after_discount(service, referrer, referee):
    _first_invoice_paid(service, referee, addons=(), discount=10)
    assert service.list_credits(referrer["id"])[0].amount == Decimal("1.62")  # not 1.80


def test_credit_base_includes_discount_with_addons(service, referrer, referee):
    _first_invoice_paid(service, referee, discount=20)
    # (25.00 - 3.60) * 10% = 2.14
    assert service.list_credits(referrer["id"])[0].amount == Decimal("2.14")


def test_credit_excludes_tax_and_late_fee(service, referrer, referee):
    sub = _sub(service, referee)
    invoice = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    service.apply_late_fee(invoice.id, as_of=date(2025, 2, 1))
    service.record_payment(invoice.id, paid_on=date(2025, 2, 2))
    assert service.list_credits(referrer["id"])[0].amount == Decimal("2.50")


def test_no_credit_when_invoice_is_only_issued(service, referrer, referee):
    service.issue_invoice(_sub(service, referee)["id"], 2025, 1)
    assert service.list_credits(referrer["id"]) == []


def test_no_credit_for_partial_payment_then_credit_on_final_payment(service, referrer, referee):
    invoice = service.issue_invoice(_sub(service, referee)["id"], 2025, 1, issued_on=date(2025, 1, 1))
    service.record_payment(invoice.id, amount="10.00", paid_on=date(2025, 1, 5))
    assert service.list_credits(referrer["id"]) == []
    service.record_payment(invoice.id, paid_on=date(2025, 1, 20))
    credits = service.list_credits(referrer["id"])
    assert len(credits) == 1
    assert credits[0].issued_on == date(2025, 1, 20)


def test_customer_without_referrer_creates_no_credit(service, ana):
    _first_invoice_paid(service, ana)
    assert service.repo.credits == {}


def test_one_credit_per_referee(service, referrer, referee):
    sub, _ = _first_invoice_paid(service, referee)
    second = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    service.record_payment(second.id, paid_on=date(2025, 2, 5))
    assert len(service.list_credits(referrer["id"])) == 1


def test_paying_a_later_invoice_first_does_not_earn_a_credit(service, referrer, referee):
    sub = _sub(service, referee)
    first = service.issue_invoice(sub["id"], 2025, 1, issued_on=date(2025, 1, 1))
    second = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    service.record_payment(second.id, paid_on=date(2025, 2, 5))
    assert service.list_credits(referrer["id"]) == []
    service.record_payment(first.id, paid_on=date(2025, 2, 6))
    assert len(service.list_credits(referrer["id"])) == 1


def test_each_referee_earns_their_own_credit(service, referrer, referee):
    carol = service.create_customer("Carol", "carol@example.com", "CAR-1", referred_by="ANA-123")
    _first_invoice_paid(service, referee)
    _first_invoice_paid(service, carol, paid_on=date(2025, 1, 12))
    assert len(service.list_credits(referrer["id"])) == 2
    assert service.credit_balance(referrer["id"], as_of=date(2025, 1, 15)) == Decimal("5.00")


# ---- cap and rounding ---------------------------------------------------
def _expensive_plan(service, price):
    service.repo.plans["gold"] = Plan("gold", "Gold", Decimal(price))


@pytest.mark.parametrize(
    "price, expected",
    [("499.90", "49.99"), ("500.00", "50.00"), ("500.10", "50.00"), ("2000.00", "50.00")],
)
def test_credit_is_capped_at_fifty_dollars(service, referrer, referee, price, expected):
    _expensive_plan(service, price)
    _first_invoice_paid(service, referee, plan="gold", addons=())
    assert service.list_credits(referrer["id"])[0].amount == Decimal(expected)


def test_credit_rounds_half_up(service, referrer, referee):
    _expensive_plan(service, "10.05")  # 10% = 1.005
    _first_invoice_paid(service, referee, plan="gold", addons=())
    assert service.list_credits(referrer["id"])[0].amount == Decimal("1.01")


# ---- expiry --------------------------------------------------------------
def test_credit_expires_after_365_days(service, referrer, referee):
    _first_invoice_paid(service, referee)  # issued 2025-01-10, expires 2026-01-10
    assert service.credit_balance(referrer["id"], as_of=date(2026, 1, 9)) == Decimal("2.50")
    assert service.credit_balance(referrer["id"], as_of=date(2026, 1, 10)) == Decimal("0.00")
    assert service.credit_balance(referrer["id"], as_of=date(2026, 6, 1)) == Decimal("0.00")


def test_credit_is_not_applied_on_expiry_date(service, referrer, referee):
    _first_invoice_paid(service, referee)
    sub = _sub(service, referrer, start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2026, 1, issued_on=date(2026, 1, 10))
    assert invoice.credit_applied == Decimal("0.00")
    assert service.list_credits(referrer["id"])[0].remaining == Decimal("2.50")


def test_credit_is_applied_the_day_before_expiry(service, referrer, referee):
    _first_invoice_paid(service, referee)
    sub = _sub(service, referrer, start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2026, 1, issued_on=date(2026, 1, 9))
    assert invoice.credit_applied == Decimal("2.50")


# ---- applying ------------------------------------------------------------
def test_credit_is_applied_after_tax_on_the_referrers_next_invoice(service, referrer, referee):
    _first_invoice_paid(service, referee)
    sub = _sub(service, referrer, start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    assert invoice.tax_total == Decimal("2.06")  # tax on the full 25.00, credit is not a discount
    assert invoice.total == Decimal("27.06")
    assert invoice.discount_total == Decimal("0.00")
    assert invoice.credit_applied == Decimal("2.50")
    assert invoice.amount_due == Decimal("24.56")
    assert invoice.status == InvoiceStatus.ISSUED
    assert all(line.kind != LineKind.DISCOUNT for line in invoice.lines)
    ledger = service.list_credits(referrer["id"])[0]
    assert ledger.remaining == Decimal("0.00")
    assert ledger.amount == Decimal("2.50")


def test_credit_is_never_applied_to_the_invoice_that_generated_it(service, referrer, referee):
    _, invoice = _first_invoice_paid(service, referee)
    assert invoice.credit_applied == Decimal("0.00")
    assert invoice.customer_id == referee["id"]


def test_credit_does_not_apply_to_other_customers(service, referrer, referee):
    _first_invoice_paid(service, referee)
    dave = service.create_customer("Dave", "dave@example.com", "DAV-1")
    invoice = service.issue_invoice(_sub(service, dave, start=date(2025, 2, 1))["id"], 2025, 2)
    assert invoice.credit_applied == Decimal("0.00")
    assert service.credit_balance(referrer["id"], as_of=date(2025, 2, 1)) == Decimal("2.50")


def test_credit_larger_than_invoice_leaves_zero_due_and_keeps_remainder(service, referrer, referee):
    _expensive_plan(service, "600.00")
    _first_invoice_paid(service, referee, plan="gold", addons=())  # credit 50.00
    sub = _sub(service, referrer, addons=(), start=date(2025, 2, 1))
    small = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    assert small.total == Decimal("19.49")  # 18.00 + 1.49 tax
    assert small.credit_applied == Decimal("19.49")
    assert small.amount_due == Decimal("0.00")
    assert small.status == InvoiceStatus.ISSUED  # not auto-paid
    assert service.list_credits(referrer["id"])[0].remaining == Decimal("30.51")  # partial use
    assert service.credit_balance(referrer["id"], as_of=date(2025, 2, 2)) == Decimal("30.51")

    nxt = service.issue_invoice(sub["id"], 2025, 3, issued_on=date(2025, 3, 1))
    assert nxt.credit_applied == Decimal("19.49")
    assert service.credit_balance(referrer["id"], as_of=date(2025, 3, 2)) == Decimal("11.02")


def test_amount_due_never_goes_negative(service, referrer, referee):
    _expensive_plan(service, "600.00")
    _first_invoice_paid(service, referee, plan="gold", addons=())
    sub = _sub(service, referrer, addons=(), start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2025, 2)
    assert invoice.amount_due == Decimal("0.00")
    assert invoice.total - invoice.credit_applied >= 0


def test_credit_stays_on_account_when_referrer_has_no_invoice(service, referrer, referee):
    _first_invoice_paid(service, referee)
    assert service.credit_balance(referrer["id"], as_of=date(2025, 1, 11)) == Decimal("2.50")
    assert len(service.list_credits(referrer["id"])) == 1


def test_oldest_expiring_credit_is_used_first(service, referrer, referee):
    carol = service.create_customer("Carol", "carol@example.com", "CAR-1", referred_by="ANA-123")
    # Carol pays first -> expires first; Bob pays later.
    _first_invoice_paid(service, carol, paid_on=date(2025, 1, 5), addons=())  # 1.80
    _first_invoice_paid(service, referee, paid_on=date(2025, 1, 20), addons=())  # 1.80
    # make amounts distinguishable
    credits = sorted(service.repo.credits.values(), key=lambda c: c.expires_on)
    credits[0].amount = credits[0].remaining = Decimal("1.00")
    credits[1].amount = credits[1].remaining = Decimal("3.00")

    sub = _sub(service, referrer, addons=(), start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    assert invoice.credit_applied == Decimal("4.00")
    assert all(c.remaining == Decimal("0.00") for c in credits)


def test_older_credit_is_drained_before_newer_one_is_touched(service, referrer, referee):
    carol = service.create_customer("Carol", "carol@example.com", "CAR-1", referred_by="ANA-123")
    _expensive_plan(service, "600.00")
    _first_invoice_paid(service, carol, paid_on=date(2025, 1, 5), plan="gold", addons=())  # 50.00
    _first_invoice_paid(service, referee, paid_on=date(2025, 1, 20), plan="gold", addons=())  # 50.00
    older, newer = sorted(service.repo.credits.values(), key=lambda c: c.expires_on)
    sub = _sub(service, referrer, addons=(), start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    assert invoice.credit_applied == Decimal("19.49")
    assert older.remaining == Decimal("30.51")
    assert newer.remaining == Decimal("50.00")


def test_expired_credit_is_skipped_but_valid_one_is_used(service, referrer, referee):
    carol = service.create_customer("Carol", "carol@example.com", "CAR-1", referred_by="ANA-123")
    _first_invoice_paid(service, carol, paid_on=date(2025, 1, 5))  # expires 2026-01-05
    _first_invoice_paid(service, referee, paid_on=date(2025, 3, 1))  # expires 2026-03-01
    sub = _sub(service, referrer, start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2026, 2, issued_on=date(2026, 2, 1))
    assert invoice.credit_applied == Decimal("2.50")
    expired, valid = sorted(service.repo.credits.values(), key=lambda c: c.expires_on)
    assert expired.remaining == Decimal("2.50")
    assert valid.remaining == Decimal("0.00")


def test_invoice_with_credit_applied_is_idempotent(service, referrer, referee):
    _first_invoice_paid(service, referee)
    sub = _sub(service, referrer, start=date(2025, 2, 1))
    first = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    again = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 9))
    assert first is again
    assert first.credit_applied == Decimal("2.50")


def test_remaining_balance_after_credit_can_be_paid_in_cash(service, referrer, referee):
    _first_invoice_paid(service, referee)
    sub = _sub(service, referrer, start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    service.record_payment(invoice.id, paid_on=date(2025, 2, 3))
    assert invoice.status == InvoiceStatus.PAID
    assert invoice.amount_due == Decimal("0.00")
    assert invoice.amount_paid == Decimal("24.56")


def test_zero_due_invoice_is_not_charged_a_late_fee(service, referrer, referee):
    _expensive_plan(service, "600.00")
    _first_invoice_paid(service, referee, plan="gold", addons=())
    sub = _sub(service, referrer, addons=(), start=date(2025, 2, 1))
    invoice = service.issue_invoice(sub["id"], 2025, 2, issued_on=date(2025, 2, 1))
    service.apply_late_fee(invoice.id, as_of=date(2025, 3, 30))
    assert invoice.late_fee == Decimal("0.00")


# ---- ledger --------------------------------------------------------------
def test_ledger_entry_exposes_required_fields(service, referrer, referee):
    _, invoice = _first_invoice_paid(service, referee)
    entry = service.list_credits(referrer["id"])[0]
    assert entry.id
    assert (entry.amount, entry.remaining) == (Decimal("2.50"), Decimal("2.50"))
    assert entry.source_invoice_id == invoice.id
    assert entry.issued_on == date(2025, 1, 10)
    assert entry.expires_on == date(2026, 1, 10)


def test_ledger_keeps_fully_used_entries(service, referrer, referee):
    _first_invoice_paid(service, referee)
    service.issue_invoice(_sub(service, referrer, start=date(2025, 2, 1))["id"], 2025, 2)
    entries = service.list_credits(referrer["id"])
    assert len(entries) == 1
    assert entries[0].remaining == Decimal("0.00")


def test_list_credits_is_empty_for_customer_without_credits(service, ana):
    assert service.list_credits(ana["id"]) == []
    assert service.credit_balance(ana["id"]) == Decimal("0.00")


def test_credit_balance_defaults_to_service_today(service, referrer, referee):
    _first_invoice_paid(service, referee, paid_on=date(2025, 2, 20))  # today fixture is 2025-03-01
    assert service.credit_balance(referrer["id"]) == Decimal("2.50")
