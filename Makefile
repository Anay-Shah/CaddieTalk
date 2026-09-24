.PHONY: install test lint fmt import plot clean

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/black --check .

fmt:
	.venv/bin/ruff check --fix .
	.venv/bin/black .

# Import a course from OpenStreetMap. Example:
#   make import ARGS="--name 'Glen Abbey' --near 43.44,-79.72"
import:
	.venv/bin/python -m course_import import $(ARGS)

# Render each hole of an imported course for visual verification. Example:
#   make plot ARGS="data/courses/glen-abbey/course.json"
plot:
	.venv/bin/python -m course_import plot $(ARGS)

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__
