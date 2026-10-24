from __future__ import annotations

from datetime import date

from .billing import BillingService


def main() -> None:
    service = BillingService(today=lambda: date(2025, 3, 1))
    ana = service.create_customer("Ana Silva", "ana@example.com", "ANA-123")
    sub = service.create_subscription(
        ana["id"],
        plan_code="starter",
        addon_codes=["extra_bag"],
        start_date=date(2025, 3, 15),
    )
    invoice = service.issue_invoice(sub["id"], 2025, 3)
    if invoice is None:
        print("No invoice for this period.")
        return

    print(f"Invoice {invoice.id} for {invoice.period_start} to {invoice.period_end}")
    for line in invoice.lines:
        print(f"  {line.description:<32} {line.amount:>8}")
    print(f"  {'Total':<32} {invoice.total:>8}")


if __name__ == "__main__":
    main()
