.PHONY: setup test dry-run static adaptive tables plots
PYTHON ?= python
setup:
	$(PYTHON) -m pip install -r research/requirements.txt
test:
	$(PYTHON) -m pytest -q tests research/test_validate_results.py
dry-run:
	$(PYTHON) scripts/run_static.py --mock
static:
	$(PYTHON) scripts/run_static.py
adaptive:
	$(PYTHON) scripts/run_adaptive.py
tables:
	$(PYTHON) scripts/make_tables.py
plots:
	$(PYTHON) scripts/make_plots.py
