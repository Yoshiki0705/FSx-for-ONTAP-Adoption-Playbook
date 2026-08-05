.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help lint i18n-check switcher-check switcher-write audit links links-external all \
        frontmatter markdown python format-python new-note stats clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

lint: frontmatter markdown python ## Frontmatter schema + Markdown lint + Python lint

RUFF_PINNED := $(shell sed -n 's/^ruff==//p' requirements-dev.txt)

python: ## Lint and format-check tools/ and scripts/ (skipped when ruff is absent)
	@if command -v ruff >/dev/null 2>&1; then \
		installed=$$(ruff --version | awk '{print $$2}'); \
		if [ "$$installed" != "$(RUFF_PINNED)" ]; then \
			echo "warning: ruff $$installed installed, CI pins $(RUFF_PINNED)."; \
			echo "         Rule sets differ between versions, so a local pass does not"; \
			echo "         mean CI passes. Install the pinned version:"; \
			echo "         pip install -r requirements-dev.txt"; \
		fi; \
		ruff check tools scripts && ruff format --check tools scripts; \
	else \
		echo "ruff not installed - falling back to a syntax check"; \
		echo "  install the pinned version: pip install -r requirements-dev.txt"; \
		$(PY) -m py_compile tools/*.py scripts/*.py && echo "python: all modules compile"; \
	fi

format-python: ## Apply ruff formatting to tools/ and scripts/
	@ruff format tools scripts && ruff check --fix tools scripts

frontmatter: ## Validate YAML frontmatter on all notes
	@$(PY) tools/validate_frontmatter.py

markdown: ## Run markdownlint if available (skipped when not installed)
	@if command -v markdownlint-cli2 >/dev/null 2>&1; then \
		markdownlint-cli2 "**/*.md" "#node_modules" "#.private"; \
	else \
		echo "markdownlint-cli2 not installed - skipping (npm i -g markdownlint-cli2)"; \
	fi

i18n-check: ## Check Tier 1 cross-language section parity
	@$(PY) tools/check_i18n_parity.py

switcher-check: ## Verify language switchers, and that no page links to the wrong language
	@$(PY) tools/sync_lang_switcher.py

switcher-write: ## Regenerate language switcher blocks from what exists on disk
	@$(PY) tools/sync_lang_switcher.py --write

audit: ## Pre-publication audit (naming / neutrality / PII / internal IDs)
	@$(PY) tools/audit_public_output.py
	@if command -v gitleaks >/dev/null 2>&1; then \
		gitleaks detect --no-git --source . --redact --exit-code 1; \
	else \
		echo "gitleaks not installed - skipping secret scan"; \
	fi

links: ## Check internal link resolution
	@$(PY) tools/check_links.py

links-external: ## Check internal + external links (network required)
	@$(PY) tools/check_links.py --external

all: lint i18n-check switcher-check audit links ## Run every check (commit gate)
	@echo "All checks passed."

new-note: ## Scaffold a note. Usage: make new-note MODULE=domains/performance SLUG=my-slug
	@test -n "$(MODULE)" || (echo "MODULE is required (e.g. MODULE=domains/performance)"; exit 1)
	@test -n "$(SLUG)"   || (echo "SLUG is required (e.g. SLUG=snapmirror-initial-sync)"; exit 1)
	@$(PY) tools/new_note.py --module "$(MODULE)" --slug "$(SLUG)"

stats: ## Count notes by evidence tier
	@$(PY) tools/validate_frontmatter.py --stats

clean: ## Remove local caches and previews
	@rm -rf .ruff_cache .pytest_cache __pycache__ tools/__pycache__ tmp-previews
	@find . -name '.DS_Store' -delete
	@echo "Cleaned."
