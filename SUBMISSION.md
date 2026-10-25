# Submission

## Repository

- Remote URL: <!-- TODO: add your public GitHub repository URL -->
- Default branch: `main`

## Pull requests

| Ticket | Branch | PR link | Key commits |
|---|---|---|---|
| BUG-101 | `bugfix/BUG-101-discount-scope` | <!-- TODO --> | `ac6d622` test, `162de50` fix |
| BUG-102 | `bugfix/BUG-102-calendar-proration` | <!-- TODO --> | `3632e9e` test, `6d2fefe` fix |
| BUG-103 | `bugfix/BUG-103-late-fee-grace` | <!-- TODO --> | `3dce90d` test, `bfbd4f3` fix |
| FEAT-201 | `feature/FEAT-201-pause-resume` | <!-- TODO --> | `fce0198` test, `9f3211e` feat |
| FEAT-202 | `feature/FEAT-202-referral-credits` | <!-- TODO --> | `deaeb78` test, `9b46d26` feat |

Each branch was cut from the `main` that already contained the previous ticket
(101 -> 102 -> 103 -> 201 -> 202), because the later tickets build on earlier
ones (pause uses the BUG-102 proration; referral credits use the BUG-101
discount fields).

## Test evidence

- Command: `pytest`
- Result: `137 passed`
- Tests added: 123 new tests (the 14 starter tests are untouched), in
  `tests/test_bug_101_discount.py`, `tests/test_bug_102_proration.py`,
  `tests/test_bug_103_late_fee.py`, `tests/test_feat_201_pause_resume.py` and
  `tests/test_feat_202_referral_credits.py`. The assessment bubble files and
  existing tests were not edited.

## Design notes

### BUG-101 — discount scope

The discount is `plan_amount * percent / 100`, where `plan_amount` is the
already-prorated, already-rounded plan line. Add-ons are never discounted. Tax
is `(plan - discount + add-ons) * 8.25%`, computed after the discount.
`create_subscription` rejects `percent < 0` and `percent > 30` (and
non-numeric values) with `ValueError`; it never clamps, so ops sees the
mistake. 30 is allowed, 30.01 is not.

### BUG-102 — proration

Billable days = days from `max(start_date, first of month)` through the last
day of the month, inclusive, divided by the real number of days in that month.
Each line (plan and every add-on) is `price * days / days_in_month` rounded
half-up, then tax is taken on the sum of the rounded lines. Multiplying before
dividing means a full month is exactly the list price. No billable days returns
`None`; the invoice period still covers the whole calendar month.

### BUG-103 — late fee

The fee applies when `as_of > due_on + 5 days` (i.e. from due date + 6). It is
a separate untaxed $10 line, added once per invoice, never to paid invoices.
The grace period is the constant `LATE_FEE_GRACE_DAYS`.

### FEAT-201 — pause/resume

Pauses are stored as inclusive, non-overlapping `PausePeriod` windows on the
subscription. Validation: 7-90 days, start <= end, not before the subscription
start, no overlap, not cancelled, and no overdue invoice for the customer
(due date strictly before the *request* date, status issued, balance > 0).
`_active_days` subtracts paused days from the billable window, so BUG-102
proration handles partial pauses and pauses that cross a month boundary; a
fully paused month returns `None`. Existing invoices are never recalculated.
`resume_subscription` sets the pause end to the day before the resume date and
requires the shortened pause to still be at least 7 days.
Trade-off: I did not reject pauses that start in the past, because the
acceptance criteria only list the rules above; the overdue check uses
`as_of` (default: today).

### FEAT-202 — referral credits

`create_customer` rejects unknown and self referral codes. When a referee's
*first* invoice becomes fully paid, the referrer gets a `CreditEntry` for
`10% * (subtotal - discount_total)`, capped at $50, rounded half-up, valid for
365 days from the payment date. Only the referee's first invoice (earliest
period) can earn it, and only one credit per referee. Credits are applied in
`issue_invoice` after tax, oldest expiry first, never past the invoice total;
the remainder stays in the ledger and the invoice stays `issued` (not
auto-paid). A credit is usable while `as_of < expires_on`.
Trade-off: if a referee pays a later invoice before their first one, no credit
is created until the first invoice itself is paid.

## AI assistance

- Tools used: Claude (Anthropic).
- What I used them for: Claude implemented the five tickets, wrote the tests
  and drafted these notes from the repository documents.
- What I verified and can explain without assistance: <!-- TODO: edit this honestly after you have read and understood the code -->
- I confirm I did not paste the entire repository or assignment into an AI tool:
  <!-- TODO: yes/no - answer honestly -->
