.PHONY: install test demo fingerprint

install:
	python3 -m pip install -e ".[dev]"

test:
	python3 -m pytest

demo:
	PYTHONPATH=src python3 -m brewbox

fingerprint:
	python3 scripts/fingerprint.py
