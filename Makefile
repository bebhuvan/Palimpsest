.PHONY: bootstrap config-check schemas lint typecheck test test-browser audit check restate restate-seshat restate-verify acquire-whg acquire-whg-western-ghats build-smoke build-browser-pilot build-dossier-pilot build-cedula-dossier-pilot build-1543-dossier-pilots build-release verify-release install-tippecanoe publish-r2

PIPELINE_CONFIG ?= config/research-overlay.yml

bootstrap:
	uv sync --extra dev

config-check:
	uv run history-data config-check --config "$(PIPELINE_CONFIG)"

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

restate:
	uv run history-data restate-dossiers \
		--dossiers data/staged/canonical/dossiers.ndjson \
		--output data/editorial/restatements.ndjson \
		--provider "$${RESTATE_PROVIDER:-deepseek}" \
		--model "$${RESTATE_MODEL:-deepseek-v4-flash}" \
		--limit "$${RESTATE_LIMIT:-25}"

restate-seshat:
	uv run history-data restate-assertions \
		--assertions data/staged/canonical/evidence-assertions.ndjson \
		--output data/editorial/seshat-restatements.ndjson \
		--provider "$${RESTATE_PROVIDER:-deepseek}" \
		--model "$${RESTATE_MODEL:-deepseek-v4-flash}" \
		--limit "$${RESTATE_LIMIT:-25}"

restate-verify:
	uv run history-data restate-verify \
		--dossiers data/staged/canonical/dossiers.ndjson \
		--restatements data/editorial/restatements.ndjson

acquire-whg:
	uv run history-data acquire-whg \
		--features data/staged/canonical/features.ndjson \
		--output data/editorial/whg/reconciliation-pilot.json \
		--limit "$${WHG_LIMIT:-25}" \
		--candidates "$${WHG_CANDIDATES:-5}"

acquire-whg-western-ghats:
	uv run history-data acquire-whg-dataset \
		--dataset-id 693 \
		--output data/editorial/whg/western-ghats-preview.json \
		--limit "$${WHG_DATASET_LIMIT:-10}"

build-smoke:
	uv run history-data build --config "$(PIPELINE_CONFIG)" --limit 25 --no-advance-latest

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
	uv run history-data build --config "$(PIPELINE_CONFIG)" --enrich --tiles --advance-latest
	uv run history-data verify-build --require-tiles

verify-release:
	uv run history-data verify-build --require-tiles

publish-r2:
	uv run history-data publish-r2 --bucket "$${R2_BUCKET}"
