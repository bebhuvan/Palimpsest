.PHONY: bootstrap config-check schemas lint typecheck test test-browser audit check build-smoke build-browser-pilot build-dossier-pilot build-cedula-dossier-pilot build-1543-dossier-pilots build-release verify-release install-tippecanoe publish-r2

bootstrap:
	uv sync --extra dev

config-check:
	uv run history-data config-check

schemas:
	uv run history-data schemas

lint:
	uv run ruff check .

typecheck:
	uv run mypy

test:
	uv run pytest --cov=history_pipeline --cov-report=term-missing --cov-fail-under=80

test-browser:
	npm run test:browser

audit:
	uv audit --frozen
	npm audit --audit-level=high

check: config-check lint typecheck test

build-smoke:
	uv run history-data build --limit 25 --no-advance-latest

build-browser-pilot: install-tippecanoe
	uv run python scripts/build-browser-pilot.py

build-dossier-pilot:
	uv run python scripts/build-dossier-pilot.py

build-cedula-dossier-pilot:
	uv run python scripts/build-cedula-dossier-pilot.py

build-1543-dossier-pilots: build-dossier-pilot build-cedula-dossier-pilot

install-tippecanoe:
	bash scripts/install-tippecanoe.sh

build-release: install-tippecanoe check
	uv run history-data build --enrich --tiles
	uv run history-data verify-build --require-tiles

verify-release:
	uv run history-data verify-build --require-tiles

publish-r2:
	uv run history-data publish-r2 --bucket "$${R2_BUCKET}"
