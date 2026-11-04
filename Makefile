PYTHON ?= python

.PHONY: install init-db seed report all test

install:
	$(PYTHON) -m pip install -r requirements.txt -c constraints.txt
	$(PYTHON) -m pip install -e .

init-db:
	$(PYTHON) -m aurora init-db

seed:
	$(PYTHON) -m aurora seed

report:
	$(PYTHON) -m aurora report

all:
	$(PYTHON) -m aurora all

test:
	$(PYTHON) -m pytest -q
