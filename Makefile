SHELL := /bin/bash
SEED ?= 42
SCALE ?= medium
COMPOSE := docker compose --env-file .env -f deploy/compose/docker-compose.yml
GEN_DIR := data/generated

.PHONY: setup env up up-all down migrate seed lint test fmt

env:
	@test -f .env || { cp .env.example .env; echo "created .env from .env.example"; }

setup: env
	uv sync --all-packages
	uv run pre-commit install
	@echo "pnpm install: no-op until M7 (gateway)"

up: env
	$(COMPOSE) --profile core up -d --wait

up-all: env
	$(COMPOSE) --profile core --profile search up -d --wait

down:
	$(COMPOSE) --profile core --profile search --profile dashboards down

migrate:
	uv run alembic -c packages/mineops-data/alembic.ini upgrade head

seed:
	uv run mineops-data generate --seed $(SEED) --scale $(SCALE) --out $(GEN_DIR)/
	uv run mineops-data load --from $(GEN_DIR)/

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy
	@echo "eslint: no-op until M7 (gateway)"

test:
	uv run pytest
	@echo "jest: no-op until M7 (gateway)"

fmt:
	uv run ruff check --fix .
	uv run ruff format .
