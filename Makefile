PYTHON ?= python3
.PHONY: test check
test:
	$(PYTHON) -m unittest discover -s tests -v
check: test
	$(PYTHON) scripts/release_check.py
