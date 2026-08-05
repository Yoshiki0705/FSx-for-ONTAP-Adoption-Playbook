.DEFAULT_GOAL := help
PY ?= python3

.PHONY: help lint i18n-check audit links links-external all frontmatter markdown python \
        format-python new-note stats clean

help: ## Show available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

lint: frontmatter markdown python ## Frontmatter schema + Markdown lint + Python lint

python: ## Lint and format-check tools/ and scripts/ (skipped when ruff is absent)
	@if command -v ruff >/dev/null 2>&1; then \
		ruff check tools scripts && ruff format --check tools scripts; \
	else \
		echo "ruff not installed - falling back to a syntax check"; \
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

all: lint i18n-check audit links ## Run every check (commit gate)
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
