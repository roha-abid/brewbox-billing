from __future__ import annotations

import hashlib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FILES = [
    "tests/conftest.py",
    "tests/test_basic_billing.py",
    "tests/test_reported_bugs.py",
    "tests/test_integrity_bubble.py",
    "docs/assignment.md",
]


def main() -> None:
    print("SHA-256 of assessment integrity files")
    print("Compare these with evaluator/original_hashes.sha256.\n")
    for relative in FILES:
        path = REPO_ROOT / relative
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{digest}  {relative}")


if __name__ == "__main__":
    main()
