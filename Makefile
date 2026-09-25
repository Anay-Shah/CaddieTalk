.PHONY: install test lint fmt serve app import plot clean

install:
	python3 -m venv .venv
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -e ".[dev]"
	cd apps/mobile && npm install

test:
	.venv/bin/pytest

lint:
	.venv/bin/ruff check .
	.venv/bin/black --check .

fmt:
	.venv/bin/ruff check --fix .
	.venv/bin/black .

# The API the mobile app talks to. Binds to every interface so a phone on the same
# wifi can reach it — the app finds this host automatically via Expo.
serve:
	.venv/bin/uvicorn caddie_api:app --host 0.0.0.0 --port 8000 --reload

app:
	cd apps/mobile && npx expo start

# Import a course from OpenStreetMap. Example:
#   make import ARGS="--name 'Braeben' --near 43.606,-79.687"
import:
	.venv/bin/python -m course_import import $(ARGS)

# Render each hole of an imported course for visual verification. Example:
#   make plot ARGS="data/courses/braeben/course.json"
plot:
	.venv/bin/python -m course_import plot $(ARGS)

clean:
	rm -rf .pytest_cache .ruff_cache **/__pycache__
