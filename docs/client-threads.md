# Client conversations

These four threads are part of the requirements. Read all of them before
changing code. Dates, names, and small operational details are intentionally
realistic; the **business rules** are what matter.

---

## Thread 1 — "Discount is leaking onto add-ons"

**From:** Priya Raman, Billing Operations  
**To:** Marco Silva, Engineering  
**Cc:** Dana Okafor, Finance  
**Date:** Mon, 3 Mar 2025 09:14  
**Subject:** Discount is leaking onto add-ons

> Marco,
>
> A customer on the Starter plan with the extra-bag add-on used a 20% promo and
> the invoice discounted the add-on too. Add-ons are already low margin. The
> promo is for the coffee plan only.
>
> Can you make sure the discount line is calculated from the plan fee only?
> Also, someone typed 45% into the admin screen last week. We never discount
> more than 30%. Please reject anything above 30% rather than silently clamping
> it, so ops sees the mistake.
>
> Tax should be calculated after the discount. Rounding to cents needs to be
> commercial rounding (half-up), not truncation. The plan can be prorated on the
> first invoice; apply the discount to the prorated plan amount, not the full
> list price.
>
> Thanks,
> Priya

**From:** Marco Silva  
**To:** Priya Raman  
**Date:** Mon, 3 Mar 2025 09:41  
**Subject:** RE: Discount is leaking onto add-ons

> A few clarifications so I do not guess:
>
> 1. Is 30% allowed, or is 30% already too high?
> 2. Do we reject a discount of exactly 30.0? What about 30.01?
> 3. Should the cap apply to the percentage entered, or to the resulting dollar
>    amount?
> 4. Are add-ons ever discountable under a different promo?

**From:** Priya Raman  
**Date:** Mon, 3 Mar 2025 10:02  
**Subject:** RE: Discount is leaking onto add-ons

> 30% is allowed. Anything strictly greater than 30% is rejected with a clear
> validation error. The cap is on the percentage, not the dollar amount.
>
> Add-ons are never discounted. Not under this promo and not under any current
> promo. If that changes, we will write a separate ticket.
>
> One more thing: the discount is a percentage and can have one decimal place
> (12.5% is valid). The tax rate stays 8.25%.

**Decision:** Plan fee only. `0 <= percent <= 30`; above 30 is a validation
error, not a clamp. Tax after discount. Round half-up.

---

## Thread 2 — "First invoice is wrong for mid-month sign-ups"

**From:** Dana Okafor, Finance  
**To:** Marco Silva, Engineering  
**Date:** Tue, 4 Mar 2025 14:20  
**Subject:** First invoice is wrong for mid-month sign-ups

> Hi Marco,
>
> Finance reconciliation found a problem with subscriptions that start mid-month.
> A Starter customer who activated on 15 March was billed 16/30 of the plan.
> March has 31 days and they should be billed for 17 days: the 15th through the
> 31st, inclusive. The add-on was also charged in full even though it was only
> active for part of the month.
>
> Please use the actual number of days in the calendar month, count the
> activation day, and prorate add-ons the same way as the plan. February in a
> leap year must use 29 days. A subscription active for the whole month should
> simply be billed the full monthly price, with no rounding drift.
>
> Round each line to cents half-up before tax. Do not use a 30-day convention.
>
> Separately, the late fee is being applied on day 5. Our terms give five full
> calendar days of grace after the due date. If the due date is 15 January, a
> payment on 20 January is on time and should not attract a fee; a fee starts on
> 21 January. The fee is $10, once per invoice, and is not taxed.
>
> Invoice due date remains 14 days after the issue date.
>
> Dana

**From:** Marco Silva  
**Date:** Tue, 4 Mar 2025 15:03  
**Subject:** RE: First invoice is wrong for mid-month sign-ups

> Two edge cases:
>
> - If a month has no billable days (for example, a subscription starts after
>   the month ends), should we issue a zero invoice?
> - If a late fee is applied and then the invoice is paid, do we add another fee
>   on the next run?

**From:** Dana Okafor  
**Date:** Tue, 4 Mar 2025 15:19  
**Subject:** RE: First invoice is wrong for mid-month sign-ups

> No billable days means no invoice at all. Do not create zero-dollar invoices;
> they confuse reconciliation.
>
> One fee per invoice, ever. If the invoice is already paid, no fee. If a fee
> was already added, later runs must be idempotent.
>
> All dates are local calendar dates in America/New_York. There is no
> time-of-day billing logic in this service, so just use the date fields.

**Decision:** Proration = active calendar days / actual days in month, start day
included, add-ons included, each line rounded half-up, tax after. No invoice for
zero billable days. Late fee starts on due date + 6, once, untaxed. Payment made
inside the grace window removes no fee that was already applied; it just means a
paid invoice never receives another one.

---

## Thread 3 — "Pause for holidays"

**From:** Nia Patel, Product  
**To:** Marco Silva, Engineering  
**Date:** Wed, 5 Mar 2025 11:05  
**Subject:** Pause feature for holiday customers

> We keep losing customers who go away for a month. They want to pause instead
> of cancelling. Here is the product rule:
>
> - Minimum 7 days, maximum 90 days, inclusive of both start and end dates.
> - A pause can be scheduled to start today or in the future.
> - Pause dates are inclusive. A pause from 10 January through 19 January is
>   10 paused days and billing resumes on 20 January.
> - Pauses cannot overlap, cannot start before the subscription start date, and
>   a fully paused month produces **no invoice** rather than a $0 invoice.
> - A partially paused month bills only the active days, using the same proration
>   rules as a mid-month start.
> - Customers can resume early, but the shortened pause still has to be at least
>   7 days. When they resume on a date, that date is active again.
> - We need to list a subscription's pause periods for support/audit.
>
> One guardrail from finance: a subscription with an overdue unpaid invoice must
> be settled before it can be paused. Overdue means the due date has passed and
> there is a positive balance.
>
> Existing invoices are not recalculated retroactively. If the customer already
> received an invoice for the current month, pausing does not credit it back.
>
> Nia

**From:** Marco Silva  
**Date:** Wed, 5 Mar 2025 11:48  
**Subject:** RE: Pause feature for holiday customers

> What should happen if someone tries a 6-day pause or a 91-day pause? And is
> the overdue check based on the pause start date or today?

**From:** Nia Patel  
**Date:** Wed, 5 Mar 2025 11:59  
**Subject:** RE: Pause feature for holiday customers

> Reject invalid lengths with a validation error; do not clamp them.
>
> The overdue check uses today's date at the moment the pause is requested, not
> the future pause start. A customer with an overdue invoice today cannot
> schedule a pause for next month.
>
> Also, a pause that crosses a month boundary must prorate both months. For
> example, 28 January through 6 February: the January invoice loses those
> January days, and the February invoice loses the paused February days.

**Decision:** Implement pause as stored, non-overlapping windows; validate
7–90 days, ordering, subscription start, overlap, and overdue balance. Billing
subtracts paused days; full pause => no invoice. Resume early shortens the
window and must leave at least 7 days.

---

## Thread 4 — "Referral credits"

**From:** Omar Haddad, Growth  
**To:** Marco Silva, Engineering  
**Date:** Thu, 6 Mar 2025 16:32  
**Subject:** Referral credits — final rules

> Marco, we are launching referrals next month. The rules we agreed with finance:
>
> - A referrer earns **10% of the referee's first paid invoice**, calculated on
>   the pre-tax amount after any discount. That includes plan and add-ons.
>   Exclude tax, late fees, and anything paid with an existing credit.
> - Cap the credit at **$50** per referee. Round half-up to cents.
> - The credit is created only when the referee's first invoice is **fully
>   paid**, not when it is issued. If the referee never pays, nobody gets a
>   credit.
> - One credit per referee. Paying a second invoice must not create another.
> - The credit belongs to the referrer and is applied automatically to the
>   referrer's next issued invoice, **after tax**. Treat it as a payment, not a
>   discount: tax is always calculated on the full taxable amount first.
> - If the credit is larger than the invoice, the amount due becomes zero and
>   the remainder stays on the referrer's balance. No cash payouts, no negative
>   invoices.
> - Credits expire **12 months after issue** (365 days). Do not use an expired
>   credit. Apply the oldest-expiring credit first.
> - Self-referral and unknown referral codes are rejected when the customer is
>   created.
>
> A ledger entry with the original amount, remaining amount, source invoice, and
> expiry is enough. We do not need a UI.
>
> Omar

**From:** Marco Silva  
**Date:** Thu, 6 Mar 2025 17:10  
**Subject:** RE: Referral credits — final rules

> If the referee's first invoice is discounted, is the 10% based on the amount
> after discount or before?
>
> And if a credit covers the whole next invoice, do we mark that invoice paid or
> leave it issued with zero due?

**From:** Omar Haddad  
**Date:** Thu, 6 Mar 2025 17:26  
**Subject:** RE: Referral credits — final rules

> After discount. The base is the pre-tax subtotal minus the discount; add-ons
> are included. So a $18 plan with a 10% discount gets a $1.62 credit, not
> $1.80.
>
> For the referrer's invoice, leave status as issued with $0 due; the existing
> service does not auto-pay invoices. Finance will treat zero-due issued
> invoices as settled. What matters is that `amount_due` stops at zero and the
> unused credit remains.
>
> Also, do not apply a credit to the invoice that generated it. It goes to the
> referrer, so this should fall out naturally, but tests should show it.

**Decision:** Award on first fully-paid invoice; base = subtotal − discount
(plan + prorated add-ons, pre-tax); 10%, cap $50, half-up. One per referee.
Credit ledger expires after 365 days, applies after tax, oldest expiry first,
remainder carries, no negative due.
