.PHONY: setup run clean install

VENV = venv
PYTHON = $(VENV)/bin/python
STREAMLIT = $(VENV)/bin/streamlit

setup: $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

install: setup

$(VENV):
	python3 -m venv $(VENV)

run: $(VENV)
	$(STREAMLIT) run app.py

clean:
	rm -rf $(VENV)

