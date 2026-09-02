.DEFAULT_GOAL := help
PY ?= python3

# Every target below must appear here. `docs/`, `scripts/`, and `tools/` exist as
# directories, so an undeclared target sharing one of those names makes make print
# "up to date" and skip the recipe entirely — a gate that reports success without
# running. scripts/tests/test_makefile_phony.py fails when a target is missing.
.PHONY: help lint i18n-check switcher-check ja-markers switcher-write audit links links-external anchors pr-verify all \
        frontmatter markdown headings python format-python new-note stats drift test secrets clean \
        diagrams diagrams-check

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

lint: frontmatter markdown headings python ## Frontmatter schema + Markdown lint + heading style + Python lint

RUFF_PINNED := $(shell sed -n 's/^ruff==//p' requirements-dev.txt)

# Prefer a project-local virtual environment over whatever is on PATH. Without this,
# resolution depends on PATH order, and a package-manager copy installed for something
# else silently wins: an 0.15.20 from Homebrew sat ahead of the pinned version here and
# `make python` was linting with the wrong rule set. A .venv is gitignored, so this costs
# nothing when there isn't one.
RUFF := $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,$(shell command -v ruff 2>/dev/null))

# The install line has to be one that works. `pip` is not always on PATH, and on a
# Homebrew Python `pip install --user` is refused outright by PEP 668, so the instruction
# this file used to print was a dead end on the machine it was written on. Both forms
# below install exactly the pinned version.
define TOOLCHAIN_HELP
	echo "       Install the pinned version, either way:"; \
	echo "         python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt"; \
	echo "         pipx uninstall ruff; pipx install 'ruff==$(RUFF_PINNED)'"; \
	echo "       A .venv is preferred and is used automatically when present."
endef

python: ## Lint and format-check tools/ and scripts/ (fails when ruff is absent or unpinned)
	@test -n "$(RUFF)" || { \
		echo "error: ruff is not installed, so this gate would check nothing."; \
		echo "       It used to fall back to py_compile and report success, which is a"; \
		echo "       weaker check wearing the same name: every finding CI reports would"; \
		echo "       still be there, just discovered later."; \
		$(TOOLCHAIN_HELP); \
		exit 1; \
	}
	@reported=$$($(RUFF) --version 2>/dev/null) || { \
		echo "error: $(RUFF) is present but does not run."; \
		echo "       Its exit status was discarded here until a sibling repository pointed"; \
		echo "       out that a pipeline reports the last command's status, so a broken"; \
		echo "       install was misread as a version mismatch and sent you to the wrong fix."; \
		$(TOOLCHAIN_HELP); \
		exit 1; \
	}; \
	installed=$${reported##* }; \
	if [ "$$installed" != "$(RUFF_PINNED)" ]; then \
		echo "error: $(RUFF) is $$installed, but CI pins $(RUFF_PINNED)."; \
		echo "       Rule sets differ between releases, so a local pass here does not"; \
		echo "       mean CI passes -- and this used to be a warning that was easy to"; \
		echo "       walk past, which is the same silent divergence it warned about."; \
		$(TOOLCHAIN_HELP); \
		exit 1; \
	fi
	@$(RUFF) check $(PY_PATHS) && $(RUFF) format --check $(PY_PATHS)

format-python: ## Apply ruff formatting to tools/ and scripts/
	@$(RUFF) format $(PY_PATHS) && $(RUFF) check --fix $(PY_PATHS)

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

ja-markers: ## Check that English links into Japanese-only pages are labelled
	@$(PY) tools/check_ja_only_markers.py --selftest >/dev/null
	@$(PY) tools/check_ja_only_markers.py

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

headings: ## Check that Japanese section headings are noun phrases
	@$(PY) tools/check_heading_style.py --selftest >/dev/null
	@$(PY) tools/check_heading_style.py

anchors: ## Check that externally cited section anchors have not been renamed
	@$(PY) tools/check_anchor_contract.py

pr-verify: ## Confirm CI passed for the commit a PR will merge (PR=<number>)
	@test -n "$(PR)" || { echo "usage: make pr-verify PR=<number>" >&2; exit 2; }
	@$(PY) scripts/verify_pr_checks.py $(PR)

links-external: ## Check internal + external links (network required)
	@$(PY) tools/check_links.py --external

all: lint i18n-check switcher-check ja-markers audit secrets links anchors drift test ## Run every check (commit gate)
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
# Not part of `all`: both need the AWS Architecture Icons package, which is never committed. The
# generated .drawio files and the exported images are the committed artefacts, so a contributor
# without the package can still run the gate.
diagrams: ## Regenerate the .drawio sources and export SVG + PNG (needs the AWS icon package)
	@$(PY) tools/build_diagrams.py --write --export
diagrams-check: ## Verify the committed diagrams still match the spec (needs the AWS icon package)
	@$(PY) tools/build_diagrams.py --check

clean: ## Remove local caches and previews
	@rm -rf .ruff_cache .pytest_cache __pycache__ tools/__pycache__ tmp-previews
	@find . -name '.DS_Store' -delete
	@echo "Cleaned."
