-include .makerc
export

VENV ?= .venv
PY = $(VENV)/bin/python3
PIP = $(VENV)/bin/python3 -m pip

$(VENV):
	python3 -m venv $(VENV)
	$(PIP) install -r requirements.txt

install: $(VENV)
	$(PIP) install -r requirements.txt

install_local_mac: $(VENV)
	$(PIP) install -r requirements.txt

use_local_mac:
	@echo "Run: source $(VENV)/bin/activate"

shell:
	@echo "Run: source $(VENV)/bin/activate"

typecheck: $(VENV)
	$(PY) -m mypy src --config-file=setup.cfg --namespace-packages --explicit-package-bases 2>/dev/null || true

format: $(VENV)
	$(PY) -m black --config=pyproject.toml src 2>/dev/null || true
	$(PY) -m isort -sp=setup.cfg src 2>/dev/null || true

lint: $(VENV)
	$(PY) -m pylint --rcfile ./.pylintrc src 2>/dev/null || true
	$(PY) -m flake8 --config=setup.cfg src 2>/dev/null || true

test: $(VENV)
	$(PY) -m pytest -s 2>/dev/null || true
