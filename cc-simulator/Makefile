# Makefile for managing the cc-simulator project

.PHONY: install run test clean docker-build docker-run all

# Default port: 5001 to avoid macOS ControlCenter on 5000
PORT ?= 5001

install:
    pip install -e .

run:
    PORT=$(PORT) python scripts/serve.py

test:
    python -m pytest -q

docker-build:
    docker build -t cc-simulator .

docker-run:
    docker run --rm -p $(PORT):5000 -e PORT=5000 cc-simulator

all: install test

clean:
    find . -type d -name "__pycache__" -exec rm -r {} +
    find . -type f -name "*.pyc" -exec rm -f {} +