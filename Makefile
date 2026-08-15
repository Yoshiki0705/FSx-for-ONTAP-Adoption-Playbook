.DEFAULT_GOAL := help
PY ?= python3

# Every target below must appear here. `docs/`, `scripts/`, and `tools/` exist as
# directories, so an undeclared target sharing one of those names makes make print
# "up to date" and skip the recipe entirely — a gate that reports success without
# running. scripts/tests/test_makefile_phony.py fails when a target is missing.
.PHONY: help lint i18n-check switcher-check switcher-write audit links links-external all \
        frontmatter markdown python format-python new-note stats drift test secrets clean

# Single definition of what gets linted and formatted. CI calls these targets rather
# than repeating the list, so local and CI cannot end up inspecting different trees.
PY_PATHS := tools scripts

# Every directory holding tests. A tests/ directory that is not listed here runs
# nowhere: not locally, not in CI, and only when someone remembers a command from a
# README. scripts/tests/test_test_discovery.py fails when one is missing.
TEST_DIRS := scripts/tests

help: ## Show available targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

lint: frontmatter markdown python ## Frontmatter schema + Markdown lint + Python lint

RUFF_PINNED := $(shell sed -n 's/^ruff==//p' requirements-dev.txt)

python: ## Lint and format-check tools/ and scripts/ (fails when ruff is absent or unpinned)
	@command -v ruff >/dev/null 2>&1 || { \
		echo "error: ruff is not installed, so this gate would check nothing."; \
		echo "       It used to fall back to py_compile and report success, which is a"; \
		echo "       weaker check wearing the same name: every finding CI reports would"; \
		echo "       still be there, just discovered later."; \
		echo "       Install the pinned version:  pip install -r requirements-dev.txt"; \
		exit 1; \
	}
	@installed=$$(ruff --version | awk '{print $$2}'); \
	if [ "$$installed" != "$(RUFF_PINNED)" ]; then \
		echo "error: ruff $$installed is first on PATH, but CI pins $(RUFF_PINNED)."; \
		echo "       Rule sets differ between releases, so a local pass here does not"; \
		echo "       mean CI passes -- and this used to be a warning that was easy to"; \
		echo "       walk past, which is the same silent divergence it warned about."; \
		echo "       Install the pinned version:  pip install -r requirements-dev.txt"; \
		echo "       Then check for a second binary earlier on PATH:  which -a ruff"; \
		exit 1; \
	fi
	@ruff check $(PY_PATHS) && ruff format --check $(PY_PATHS)

format-python: ## Apply ruff formatting to tools/ and scripts/
	@ruff format $(PY_PATHS) && ruff check --fix $(PY_PATHS)

frontmatter: ## Validate YAML frontmatter on all notes
	@$(PY) tools/validate_frontmatter.py

# Single definition of the lint scope. Ignores live in .markdownlint-cli2.jsonc so the
# CI action and this target apply the same exclusions; scripts/tests/test_gate_integrity.py
# checks that the workflow's globs still match this list.
# The `#` must be escaped: make starts a comment at an unescaped `#` even inside a
# variable assignment, which truncated this list mid-quote and handed /bin/sh an
# unterminated string. markdownlint-cli2 uses a leading `#` to mean "exclude".
MD_GLOBS := "**/*.md" "\#node_modules" "\#.private"

markdown: ## Run markdownlint (fails when it is not installed)
	@command -v markdownlint-cli2 >/dev/null 2>&1 || { \
		echo "error: markdownlint-cli2 is not installed, so this gate would check nothing."; \
		echo "       A skipped lint that reports success is the failure this target had:"; \
		echo "       CI runs markdownlint regardless, so skipping locally only moves the"; \
		echo "       finding to a red pull request."; \
		echo "       Install it:  npm install -g markdownlint-cli2"; \
		exit 1; \
	}
	@markdownlint-cli2 $(MD_GLOBS)

i18n-check: ## Check Tier 1 cross-language section parity
	@$(PY) tools/check_i18n_parity.py

switcher-check: ## Verify language switchers, and that no page links to the wrong language
	@$(PY) tools/sync_lang_switcher.py

switcher-write: ## Regenerate language switcher blocks from what exists on disk
	@$(PY) tools/sync_lang_switcher.py --write

# Split from `audit` deliberately. The two answer different questions, and bundling them
# hid that only one was running: in CI's docs-quality job gitleaks is not installed, so
# `make audit` printed "skipping secret scan" and passed. Secret scanning there is covered
# by .github/workflows/gitleaks.yml, which scans full history rather than the worktree.
audit: ## Pre-publication audit (naming / neutrality / PII / internal IDs)
	@$(PY) tools/audit_public_output.py

secrets: ## Secret scan of the worktree (fails when gitleaks is not installed)
	@command -v gitleaks >/dev/null 2>&1 || { \
		echo "error: gitleaks is not installed, so this scan would check nothing."; \
		echo "       A security gate that skips silently is worse than no gate: it"; \
		echo "       reports success. Install it:  brew install gitleaks"; \
		echo "       (CI scans full history in .github/workflows/gitleaks.yml.)"; \
		exit 1; \
	}
	@gitleaks detect --no-git --source . --redact --exit-code 1

links: ## Check internal link resolution
	@$(PY) tools/check_links.py

links-external: ## Check internal + external links (network required)
	@$(PY) tools/check_links.py --external

all: lint i18n-check switcher-check audit secrets links drift test ## Run every check (commit gate)
	@echo "All checks passed."

drift: ## Check AGENTS.md size budget and steering/AGENTS authority relationship
	@$(PY) scripts/check_agent_context_budget.py

test: ## Run the guardrail and gate tests (stdlib unittest, no dependencies)
	@for dir in $(TEST_DIRS); do $(PY) -m unittest discover -s $$dir -t . -q || exit 1; done

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

docs: ## TEMPORARY deliberate break to prove CI can fail
	@echo "this recipe never runs"
