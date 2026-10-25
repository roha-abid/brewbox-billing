from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

CENT = Decimal("0.01")
TAX_RATE = Decimal("0.0825")
LATE_FEE = Decimal("10.00")
LATE_FEE_GRACE_DAYS = 5
MIN_PAUSE_DAYS = 7
MAX_PAUSE_DAYS = 90
MAX_DISCOUNT_PERCENT = Decimal("30")
REFERRAL_RATE = Decimal("0.10")
MAX_REFERRAL_CREDIT = Decimal("50.00")
CREDIT_VALID_DAYS = 365


def money(value: Decimal | int | str) -> Decimal:
    """Round a monetary value to cents using commercial (half-up) rounding."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


class SubscriptionStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class InvoiceStatus(str, Enum):
    ISSUED = "issued"
    PAID = "paid"
    VOID = "void"


class LineKind(str, Enum):
    PLAN = "plan"
    ADDON = "addon"
    DISCOUNT = "discount"
    TAX = "tax"
    LATE_FEE = "late_fee"


@dataclass(frozen=True)
class Plan:
    code: str
    name: str
    monthly_price: Decimal


@dataclass(frozen=True)
class AddOn:
    code: str
    name: str
    monthly_price: Decimal


@dataclass
class Customer:
    id: str
    name: str
    email: str
    referral_code: str
    referred_by: str | None = None


@dataclass(frozen=True)
class PausePeriod:
    start: date
    end: date

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    def overlaps(self, other: "PausePeriod") -> bool:
        return self.start <= other.end and other.start <= self.end


@dataclass
class Subscription:
    id: str
    customer_id: str
    plan_code: str
    addon_codes: tuple[str, ...]
    start_date: date
    discount_percent: Decimal = Decimal("0")
    pauses: list[PausePeriod] = field(default_factory=list)
    cancelled_on: date | None = None

    def status_on(self, day: date) -> SubscriptionStatus:
        if self.cancelled_on is not None and day >= self.cancelled_on:
            return SubscriptionStatus.CANCELLED
        if any(pause.start <= day <= pause.end for pause in self.pauses):
            return SubscriptionStatus.PAUSED
        return SubscriptionStatus.ACTIVE


@dataclass
class LineItem:
    description: str
    amount: Decimal
    kind: LineKind


@dataclass
class Invoice:
    id: str
    customer_id: str
    subscription_id: str
    period_start: date
    period_end: date
    issued_on: date
    due_on: date
    lines: list[LineItem] = field(default_factory=list)
    status: InvoiceStatus = InvoiceStatus.ISSUED
    subtotal: Decimal = Decimal("0.00")
    discount_total: Decimal = Decimal("0.00")
    tax_total: Decimal = Decimal("0.00")
    credit_applied: Decimal = Decimal("0.00")
    late_fee: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    amount_paid: Decimal = Decimal("0.00")
    paid_on: date | None = None

    @property
    def amount_due(self) -> Decimal:
        return money(self.total - self.credit_applied - self.amount_paid)

    def add_line(self, description: str, amount: Decimal, kind: LineKind) -> None:
        self.lines.append(LineItem(description=description, amount=money(amount), kind=kind))


@dataclass
class CreditEntry:
    id: str
    customer_id: str
    source_customer_id: str
    source_invoice_id: str
    amount: Decimal
    remaining: Decimal
    issued_on: date
    expires_on: date
    reason: str
