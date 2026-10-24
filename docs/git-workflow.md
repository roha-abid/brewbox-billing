# Git and pull-request workflow

The assessment is not only about code. We review how you structure the change.

## Branch model

Use `main` as the integration branch. Create one short-lived branch per ticket,
from the latest `main`, and open one pull request per branch.

```
main
 ├── bugfix/BUG-101-discount-scope
 ├── bugfix/BUG-102-calendar-proration
 ├── bugfix/BUG-103-late-fee-grace
 ├── feature/FEAT-201-pause-resume
 └── feature/FEAT-202-referral-credits
```

Rules:

- Lowercase, hyphenated, with the ticket id.
- Do not commit directly to `main`.
- Rebase or merge `main` in as needed; do not rewrite branches that already have
  review comments.
- Keep unrelated refactors out of ticket branches. If you find cleanup worth
  doing, raise a separate `chore/...` branch and PR, or leave a note.

## Commit style

Use Conventional Commits, in the imperative mood:

```
fix(billing): apply discount to plan line only

- discount is calculated from the prorated plan amount
- reject discounts greater than 30 percent
- keep add-ons undiscounted and tax after discount

Refs: BUG-101
```

Guidelines:

- A commit should build and pass tests. Avoid "wip" commits in the final PR.
- Separate the failing/reproduction test from the fix when it helps the reviewer:
  `test(billing): reproduce discount applied to add-ons`, then
  `fix(billing): apply discount to plan only`.
- Reference the ticket in the body (`Refs: BUG-101`), not only in the title.
- Do not mix ticket work in one commit. A reviewer should be able to revert one
  ticket without touching another.
- No generated/vendor files, virtual environments, `.pytest_cache`, or secrets.

Suggested minimum history:

```
chore: assessment starter
test(billing): reproduce BUG-101 discount scope
fix(billing): restrict discount to plan and cap at 30%
test(billing): reproduce BUG-102 proration error
fix(billing): prorate by actual calendar days
...
feat(billing): add pause and resume windows
feat(billing): add referral credit ledger
docs: add submission notes
```

## Pull requests

For every ticket:

1. Push the branch to your remote.
2. Open a PR into `main` using `.github/pull_request_template.md`.
3. Fill in the ticket, what changed, how it was tested, and the AI disclosure.
4. Link the PR in `SUBMISSION.md`.
5. Include the command and output summary of `pytest`.

We do not require an approval, but the PR description must let a reviewer verify
the acceptance criteria without reading the whole diff first.

## Submission

Complete `SUBMISSION.md` and include:

- the remote URL,
- branch names,
- PR links,
- commit hashes per ticket,
- test command/result,
- a short design note per ticket,
- an honest AI-usage note.

If you cannot push to a remote, deliver the repository as a bundle plus a text
file containing the same information, and create local branches/commits. PR
links are strongly preferred.
