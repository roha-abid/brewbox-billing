# User stories and acceptance criteria

The client threads in `docs/client-threads.md` are the source of truth. This
file turns them into testable tickets. "Given / When / Then" criteria are
contractual; use them to design both implementation and tests.

---

## BUG-101 — Discount must apply to the plan only, with a 30% cap

**Source:** client thread 1  
**Type:** business-logic defect

**User story**  
As a billing operator, I want a promo discount to reduce only the plan fee, so
that low-margin add-ons are not sold below cost and tax is calculated correctly.

**Acceptance criteria**

1. Given a subscription with a plan and add-ons, when an invoice is issued with
   a discount, then the discount is calculated from the plan line only.
2. Given a prorated first invoice, when a discount applies, then the discount is
   calculated from the prorated plan amount, not the full list price.
3. Given a discount of `30`, when a subscription is created, then it is
   accepted.
4. Given a discount greater than `30` (for example `30.01` or `45`), when a
   subscription is created, then a `ValueError` is raised and the subscription
   is not created.
5. Given a negative discount, then a `ValueError` is raised.
6. Given a valid discount, when the invoice is issued, then tax is calculated on
   `(plan after discount + add-ons)` at 8.25%.
7. Given a monetary component, then it is rounded to cents with `ROUND_HALF_UP`
   before tax is calculated.
8. Given an invoice, then the discount line is negative and the invoice total is
   `subtotal - discount + tax` (plus any late fee).

**Example:** Starter ($18.00) + extra bag ($7.00), 20% discount, full month:

| Line | Amount |
|---|---:|
| Plan | 18.00 |
| Add-on | 7.00 |
| Discount 20% | −3.60 |
| Tax 8.25% | 1.77 |
| **Total** | **23.17** |

**Out of scope:** add-on-specific promotions; discount codes; stacking.

---

## BUG-102 — Calendar-correct proration for mid-month starts

**Source:** client thread 2  
**Type:** calculation bug

**User story**  
As a finance analyst, I want first invoices prorated by real calendar days so
that revenue reconciles and customers are not over- or under-charged.

**Acceptance criteria**

1. Given a subscription that starts mid-month, then the number of billable days
   is the count of active calendar days from the start date through the last day
   of the month, inclusive.
2. Given a month with `N` days, then the proration factor is
   `billable_days / N`, using the actual `N` (28, 29, 30, or 31).
3. Given 15 March 2025, then billable days are 17 of 31 (15th–31st inclusive).
4. Given a subscription active for the entire month, then the full monthly price
   is billed with no proration rounding drift.
5. Given a leap-year February, then the denominator is 29.
6. Given add-ons, then each add-on is prorated with the same factor as the plan.
7. Given zero billable days for a month (for example, the subscription starts
   after the month ends), then no invoice is created (`None`), not a zero-dollar
   invoice.
8. Given multiple prorated lines, then each line is rounded to cents with
   `ROUND_HALF_UP`, then tax is calculated on the rounded amounts.
9. Given a mid-month start, then the invoice's `period_start` / `period_end`
   still describe the full calendar month being billed.

**Example:** Starter ($18.00) + extra bag ($7.00), start 15 March 2025, no
discount:

| Line | Calculation | Amount |
|---|---|---:|
| Plan | 18.00 × 17/31 | 9.87 |
| Add-on | 7.00 × 17/31 | 3.84 |
| Tax | 13.71 × 8.25% | 1.13 |
| **Total** | | **14.84** |

**Out of scope:** annual plans; time-of-day billing; retroactive re-rating of
already-issued invoices.

---

## BUG-103 — Late fee grace period is five full days

**Source:** client thread 2  
**Type:** off-by-one bug

**User story**  
As a finance analyst, I want the $10 late fee to start only after the five-day
grace period, so that customers paying inside the grace window are not
penalized.

**Acceptance criteria**

1. Given an invoice issued on 1 January, then its due date is 15 January
   (issue + 14 days).
2. Given an unpaid invoice and an as-of date on or before due date + 5 days,
   then no late fee is added.
3. Given an unpaid invoice and an as-of date on due date + 6 days or later, then
   exactly one $10 late-fee line is added.
4. Given the late fee has already been applied, then repeated calls are
   idempotent: one fee per invoice, forever.
5. Given an invoice that is already paid, then no late fee is added.
6. Given the late fee, then it is a separate line, is not taxed, and increases
   the invoice total and amount due by $10.
7. Given a partial payment, then the invoice remains unpaid and the fee can
   still be applied once the grace period has passed.

**Example:** due 15 January. As-of 20 January -> no fee. As-of 21 January ->
$10 fee.

**Out of scope:** compounding fees, interest, fee waivers, dunning.

---

## FEAT-201 — Pause and resume a subscription

**Source:** client thread 3  
**Type:** new feature

**User story**  
As a subscription customer going on holiday, I want to pause my deliveries and
billing for 7–90 days, so that I do not pay for coffee I cannot receive.

**Acceptance criteria**

1. Given an active subscription, when a pause of 7 days is requested, then it is
   accepted. A pause of 6 days is rejected with `ValueError`.
2. Given a pause of 90 days, then it is accepted. A pause of 91 days is
   rejected with `ValueError`.
3. Given `start > end`, then the pause is rejected.
4. Given a pause start before the subscription start date, then it is rejected.
5. Given two pause windows that share any day, then the second is rejected.
6. Given a pause start/end, then both dates are inclusive: a 10–19 January pause
   has 10 paused days, and billing resumes on 20 January.
7. Given a partial-month pause, then the invoice bills only active days using
   the same proration as BUG-102. Paused days are excluded from both the plan and
   every add-on.
8. Given a month that is fully paused, then `issue_invoice` returns `None` and
   no invoice is stored.
9. Given a pause that crosses a month boundary, then both months exclude their
   respective paused days.
10. Given a customer with an overdue unpaid invoice (due date strictly before
    the request date and positive amount due), when a pause is requested, then
    it is rejected.
11. Given an existing invoice, when a pause is created later, then that invoice
    is not recalculated or credited.
12. Given an early resume, then the pause end becomes the day before the resume
    date, the shortened pause must still be at least 7 days, and the resume date
    is active.
13. Given a subscription, then its pause windows can be listed for audit.
14. Given a cancelled subscription, then it cannot be paused. (Cancellation is
    not implemented as a feature; do not build it.)

**Out of scope:** automatic resume notifications, extending paid periods,
pausing individual add-ons, prorating already-issued invoices.

---

## FEAT-202 — Referral credits

**Source:** client thread 4  
**Type:** new feature

**User story**  
As a referrer, I want a credit on my account when someone I referred pays their
first invoice, so that I am rewarded without the company issuing cash.

**Acceptance criteria**

1. Given a new customer with a `referred_by` code, then the code must belong to
   an existing customer; unknown codes are rejected with `ValueError`.
2. Given a customer tries to refer themselves, then customer creation is
   rejected with `ValueError`.
3. Given a referee's first invoice becomes fully paid, then a credit is created
   for the referrer equal to 10% of `(invoice.subtotal − invoice.discount_total)`,
   capped at $50.00, rounded `ROUND_HALF_UP`.
4. Given the referee's first invoice includes add-ons, then add-ons are included
   in the credit base. Tax, late fees, and prior credits are excluded.
5. Given the referee's first invoice has a discount, then the base is after the
   discount. (Example: $18.00 plan, 10% discount -> $1.62 credit, not $1.80.)
6. Given the referee's first invoice is not fully paid, then no credit exists.
7. Given a referee with an existing referral credit, then paying another invoice
   does not create a second credit. One credit per referee.
8. Given a credit was issued on a date, then it expires 365 days later and is
   not applied on or after the expiry date.
9. Given a referrer with available credits, when their next invoice is issued,
   then credits are applied automatically after tax, oldest expiry first, before
   calculating amount due.
10. Given the credit is larger than the invoice total, then `amount_due` is
    zero and the unused remainder stays available until expiry.
11. Given a referrer has no other invoice, then the credit remains on the
    account; it is not paid out in cash.
12. Given an invoice has a credit applied, then its status remains `issued`
    unless a real payment later settles any remaining balance; a zero amount due
    is not automatically marked paid.
13. Given a credit ledger, then each entry exposes original amount, remaining
    amount, source invoice, issued date, and expiry date.
14. Given a credit is applied, then the total tax is calculated before the
    credit is applied. A credit is a payment, not a discount.

**Out of scope:** referral links/UI, payout, multi-level referrals, promo
stacking, credit transfers between customers.

---

## Cross-cutting regression criteria

1. `pytest` passes.
2. Existing public methods keep their signatures unless a client thread
   explicitly changes them.
3. Invoice idempotency is preserved: issuing the same subscription/month twice
   returns the same invoice.
4. All money remains `Decimal`; no float arithmetic.
5. Every new rule has at least one positive test and one boundary/negative test.
6. Assessment bubble comments remain intact.
