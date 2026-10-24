# BrewBox subscription billing — internship assessment

You are joining the small engineering team at **BrewBox**, a coffee subscription
company. The billing engine already creates customers, subscriptions, monthly
invoices, and payments. Operations has reported three defects, and product has
asked for two new capabilities.

Your job is to work through the tickets in `docs/user-stories.md` using the
clarifications in `docs/client-threads.md`, then submit the work as a clean Git
history with feature branches and pull requests.

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

The starter suite contains four tests that fail on purpose. They are the
reported defects; the requested features do not have candidate-facing tests yet.
You are expected to add tests for every ticket.

Run a small demo:

```bash
python -m brewbox
```

## Repository layout

```
src/brewbox/
  models.py       dataclasses, money helpers, business constants
  repository.py   in-memory plans, customers, subscriptions, invoices, credits
  billing.py      BillingService: the public API you will change
  cli.py          small manual demo
tests/            starter and reported-bug tests
docs/
  assignment.md       task brief and definition of done
  client-threads.md   four client conversations — source of truth
  user-stories.md     tickets, user stories, acceptance criteria
  git-workflow.md     required branch / commit / PR workflow
scripts/
  fingerprint.py      prints SHA-256 of the integrity-bubble files
```

## What you must deliver

1. **BUG-101** discount scope, cap, and rounding.
2. **BUG-102** calendar-correct proration.
3. **BUG-103** late-fee grace period.
4. **FEAT-201** pause and resume billing.
5. **FEAT-202** referral credit ledger.
6. Tests that cover normal cases, boundaries, and regressions.
7. A short `SUBMISSION.md` with:
   - branch names and PR links,
   - commit hashes for each ticket,
   - test command and final result,
   - a short explanation of each business rule and trade-off,
   - an honest note describing how you used AI, if at all.

## Using AI

AI tools are allowed for targeted help such as explaining a traceback, reviewing
a function, or suggesting edge cases. They are **not** allowed to do the whole
assessment for you.

Pasting the entire repository into an AI tool is explicitly out of bounds. The
test and documentation files contain small bubble notes that mark this
assessment. Do not remove or rewrite them; `tests/test_integrity_bubble.py`
checks that they remain. A submission with the bubbles removed, or one that
cannot explain its own code in the follow-up interview, will be rejected.

If you use AI, disclose it in `SUBMISSION.md` and in the pull request template.
You remain responsible for every line you submit.

## Timebox

The task is sized for roughly **4–6 focused hours**. Do not gold-plate. A small,
correct, well-tested change is better than a large speculative rewrite.
