# Self-documenting Makefile — run `make help` for available targets.
.DEFAULT_GOAL := help

ARGS ?=

# ── Quality ───────────────────────────────────────────────────────────
.PHONY: preflight test lint help

preflight: ## Run fast preflight checks (conflict markers, YAML, ruff)
	python3 scripts/preflight.py $(ARGS)

test: ## Run pytest suite
	python3 -m pytest tests/ -x -q

lint: ## Run ruff linter
	ruff check .

# ── Utilities ─────────────────────────────────────────────────────────
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
