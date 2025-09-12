# Makefile

# Makefile for managing the cc-simulator project

.PHONY: install run test clean

install:
    pip install -r requirements.txt

run:
    python scripts/serve.py

test:
    pytest tests/

clean:
    find . -type d -name "__pycache__" -exec rm -r {} +
    find . -type f -name "*.pyc" -exec rm -f {} +