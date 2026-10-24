from __future__ import annotations

from decimal import Decimal

from .models import AddOn, CreditEntry, Customer, Invoice, Plan, Subscription


def default_plans() -> dict[str, Plan]:
    return {
        "starter": Plan("starter", "Starter", Decimal("18.00")),
        "daily": Plan("daily", "Daily Grind", Decimal("33.00")),
        "connoisseur": Plan("connoisseur", "Connoisseur", Decimal("55.00")),
    }


def default_addons() -> dict[str, AddOn]:
    return {
        "extra_bag": AddOn("extra_bag", "Extra bag of beans", Decimal("7.00")),
        "grinder": AddOn("grinder", "Grinder rental", Decimal("5.00")),
        "priority": AddOn("priority", "Priority shipping", Decimal("4.00")),
    }


class InMemoryRepository:
    """Deliberately small storage layer. The assessment is about billing rules,
    not about databases.
    """

    def __init__(self) -> None:
        self.plans = default_plans()
        self.addons = default_addons()
        self.customers: dict[str, Customer] = {}
        self.subscriptions: dict[str, Subscription] = {}
        self.invoices: dict[str, Invoice] = {}
        self.credits: dict[str, CreditEntry] = {}
        self._sequences: dict[str, int] = {}

    def next_id(self, prefix: str) -> str:
        value = self._sequences.get(prefix, 0) + 1
        self._sequences[prefix] = value
        return f"{prefix}-{value:04d}"

    def customer_by_referral_code(self, referral_code: str) -> Customer | None:
        for customer in self.customers.values():
            if customer.referral_code == referral_code:
                return customer
        return None

    def invoices_for_customer(self, customer_id: str) -> list[Invoice]:
        return [inv for inv in self.invoices.values() if inv.customer_id == customer_id]

    def invoices_for_subscription(self, subscription_id: str) -> list[Invoice]:
        return [inv for inv in self.invoices.values() if inv.subscription_id == subscription_id]
