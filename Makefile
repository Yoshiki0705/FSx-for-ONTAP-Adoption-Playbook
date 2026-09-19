.DEFAULT_GOAL := help
PY ?= python3

# Every target below must appear here. `docs/`, `scripts/`, and `tools/` exist as
# directories, so an undeclared target sharing one of those names makes make print
# "up to date" and skip the recipe entirely — a gate that reports success without
# running. scripts/tests/test_makefile_phony.py fails when a target is missing.
.PHONY: sweep-probes entry-points allow-budget workflow-observability help lint i18n-status i18n-check switcher-check ja-markers switcher-write audit links links-external anchors pr-verify hooks all \
        frontmatter markdown headings python powershell format-python new-note stats drift test secrets clean \
        diagrams diagrams-check diagram-fonts diagram-flow cfn shell cross-repo cross-repo-external \
        inbound-probes inbound-probes-refresh gate editorial-report sentence-report glossary-report \
        structure-report mermaid-report frontmatter-report vocabulary-report

# Single definition of what gets linted and formatted. CI calls these targets rather
# than repeating the list, so local and CI cannot end up inspecting different trees.
PY_PATHS := tools scripts
# Trees that may contain shell scripts and CloudFormation templates. Listed once for the
# same reason as PY_PATHS: a workflow carrying its own copy is a second list to keep in
# step. `find` is used rather than a fixed file list so a script added later is covered
# without editing this file — the failure mode being avoided is a detector whose scan
# range silently excludes the new thing.
SH_PATHS := examples scripts tools
CFN_PATHS := examples
# Trees that may contain PowerShell. Separate from SH_PATHS because `find -name '*.sh'` never
# matched a .ps1, which is how examples/multiprotocol-ad/set-test-acls.ps1 stayed unlinted while
# sitting inside a directory the shell gate already walked.
PS_PATHS := examples scripts tools

# Every directory holding tests. A tests/ directory that is not listed here runs
# nowhere: not locally, not in CI, and only when someone remembers a command from a
# README. scripts/tests/test_test_discovery.py fails when one is missing.
TEST_DIRS := scripts/tests

help: ## Show available targets
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN{FS=":.*?## "}{printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

lint: frontmatter markdown headings python shell powershell cfn ## Frontmatter schema + Markdown lint + heading style + Python, shell, PowerShell and CloudFormation lint

RUFF_PINNED := $(shell sed -n 's/^ruff==//p' requirements-dev.txt)

# Prefer a project-local virtual environment over whatever is on PATH. Without this,
# resolution depends on PATH order, and a package-manager copy installed for something
# else silently wins: an 0.15.20 from Homebrew sat ahead of the pinned version here and
# `make python` was linting with the wrong rule set. A .venv is gitignored, so this costs
# nothing when there isn't one.
RUFF := $(if $(wildcard .venv/bin/ruff),.venv/bin/ruff,$(shell command -v ruff 2>/dev/null))
# Same precedence for PSScriptAnalyzer's wrapper, for the same reason: resolution by PATH order lets
# a copy installed for something else win silently.
PSA := .venv/bin/py-psscriptanalyzer
PSA_CMD := $(if $(wildcard .venv/bin/py-psscriptanalyzer),.venv/bin/py-psscriptanalyzer,py-psscriptanalyzer)

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

# --severity=style lowers the reporting threshold to the bottom of the default check set. It is
# set deliberately: shellcheck reports different findings between releases -- CI's copy raised
# SC2015 at info level on code a newer local copy passed -- which is the same "verdict depends
# on the day it runs" problem the pinned ruff exists to avoid. Pinning the binary across macOS,
# Linux and CI is impractical, so the gate asks for findings at every severity instead. A script
# clean here is clean under any version's default threshold.
# --enable=all is deliberately NOT used: those checks are opt-in style preferences that vary
# more between releases, not correctness findings.
shell: ## Run shellcheck at style severity on every shell script (fails when it is not installed)
	@command -v shellcheck >/dev/null 2>&1 || { \
		echo "error: shellcheck is not installed, so this gate would check nothing."; \
		echo "       examples/ ships scripts that readers run against their own accounts,"; \
		echo "       so an unchecked quoting bug there is a defect delivered, not a lint"; \
		echo "       finding. Install it:  brew install shellcheck"; \
		exit 1; \
	}
	@set -e; files=$$(find $(SH_PATHS) -name '*.sh' -type f 2>/dev/null); \
	if [ -z "$$files" ]; then echo "shell: no scripts found"; else \
		shellcheck --severity=style $$files && \
		echo "shell: $$(echo $$files | wc -w | tr -d ' ') script(s) clean at style severity"; \
	fi
cfn: ## Run cfn-lint on every CloudFormation template (fails when it is not installed)
	@command -v cfn-lint >/dev/null 2>&1 || { \
		echo "error: cfn-lint is not installed, so this gate would check nothing."; \
		echo "       A template that only fails at CreateStack time wastes a reader's"; \
		echo "       seventeen-minute file-system creation to find it."; \
		echo "       Install it:  pip install -r requirements-dev.txt"; \
		exit 1; \
	}
	@set -e; files=$$(grep -rl '^AWSTemplateFormatVersion' $(CFN_PATHS) --include='*.yaml' --include='*.yml' 2>/dev/null || true); \
	if [ -z "$$files" ]; then echo "cfn: no templates found"; else \
		cfn-lint $$files && echo "cfn: $$(echo $$files | wc -w | tr -d ' ') template(s) clean"; \
	fi
# PSScriptAnalyzer, through the py-psscriptanalyzer wrapper so the same pinned invocation works on
# macOS, on Linux and in CI. Until this existed, every .ps1 in examples/ was linted by nothing:
# SH_PATHS matches *.sh only, so examples/multiprotocol-ad/set-test-acls.ps1 shipped unchecked for
# readers to run against their own accounts. A file that no gate looks at is indistinguishable from
# a file that passes.
powershell: ## Run PSScriptAnalyzer on every PowerShell script (fails when it is not installed)
	@files=$$(find $(PS_PATHS) -name '*.ps1' -type f 2>/dev/null); \
	if [ -z "$$files" ]; then echo "powershell: no scripts found"; exit 0; fi; \
	if [ ! -x "$(PSA)" ] && ! command -v py-psscriptanalyzer >/dev/null 2>&1; then \
		echo "error: py-psscriptanalyzer is not installed, so this gate would check nothing."; \
		echo "       Install it:  python3 -m venv .venv && .venv/bin/python -m pip install -r requirements-dev.txt"; \
		exit 1; \
	fi; \
	if ! command -v pwsh >/dev/null 2>&1 && ! command -v powershell >/dev/null 2>&1; then \
		echo "error: PSScriptAnalyzer needs a PowerShell host and none is on PATH, so this gate"; \
		echo "       would check nothing. It is NOT skipped: a .ps1 in examples/ is run by readers"; \
		echo "       against their own accounts, and CI checks it either way -- skipping locally"; \
		echo "       only moves the finding to a red pull request."; \
		echo "       macOS:  brew install powershell   (a formula, not a cask, and needs no sudo)"; \
		echo "       Linux:  https://learn.microsoft.com/powershell/scripting/install/installing-powershell-on-linux"; \
		echo "       GitHub-hosted runners already have it."; \
		exit 1; \
	fi; \
	set -e; \
	$(PSA_CMD) --severity Warning $$files && \
		echo "powershell: $$(echo $$files | wc -w | tr -d ' ') script(s) clean at Warning severity"
frontmatter: ## Validate YAML frontmatter on all notes
	@$(PY) tools/validate_frontmatter.py

frontmatter-report: ## Report missing future verified metadata (not a gate)
	@$(PY) tools/validate_frontmatter.py --report-missing-verified

sentence-report: ## Report Japanese sentence length migration findings (not a gate)
	@$(PY) tools/check_sentence_length.py

glossary-report: ## Report unlinked glossary first uses (not a gate)
	@$(PY) tools/check_glossary_first_use.py

structure-report: ## Report future note/checklist structure findings (not a gate)
	@$(PY) tools/check_document_structure.py

vocabulary-report: ## Report staged sales-vocabulary findings (not a gate)
	@$(PY) tools/audit_public_output.py --only sales-vocabulary --report

mermaid-report: ## Parse/render every Mermaid block with mmdc (not a gate; run npm ci first)
	@$(PY) tools/check_mermaid.py

editorial-report: frontmatter-report sentence-report glossary-report structure-report vocabulary-report mermaid-report ## Run all staged editorial reports (not a gate)

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

i18n-status: ## Report how much of each module is still Japanese-only (not a gate)
	@$(PY) tools/report_i18n_status.py

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
# Split offline from network for the same reason as links / links-external. The offline half
# answers "is every cross-repo citation registered"; the network half answers "does the cited
# file still say it". Both are needed: a citation nobody registered is unverifiable, and a
# registered citation whose claim was retracted reads exactly like one that still holds.
cross-repo: ## Check that sibling-repository citations are registered
	@$(PY) tools/check_cross_repo.py
cross-repo-external: ## Also fetch each cited file and confirm the probe string survives
	@$(PY) tools/check_cross_repo.py --external
# The mirror image of the two above, and the half that was missing. Those guard what this repository
# cites; this guards what other repositories cite *from* here. The offline direction is ours to
# check, because the pinned files are in this tree — so it belongs in the commit gate, unlike
# cross-repo-external. Discovery needs the network and is opt-in.
inbound-probes: ## Check that strings other repositories pin in our files still occur exactly once
	@$(PY) tools/check_inbound_probes.py
inbound-probes-refresh: ## Re-read each sibling's published contract and rewrite the artifact
	@$(PY) tools/check_inbound_probes.py --refresh

headings: ## Check that Japanese section headings are noun phrases
	@$(PY) tools/check_heading_style.py --selftest >/dev/null
	@$(PY) tools/check_heading_style.py

anchors: ## Check that externally cited section anchors have not been renamed
	@$(PY) tools/check_anchor_contract.py

workflow-observability: ## Check every workflow's triggers parse, and classify them
	@$(PY) scripts/check_workflow_observability.py --selftest

sweep-probes: ## Remove probe files a killed test run left in docs/ or examples/
	@$(PY) scripts/sweep_gate_probes.py

entry-points: ## Check that every module README routes the reader, not just lists notes
	@$(PY) tools/check_entry_points.py --selftest >/dev/null
	@$(PY) tools/check_entry_points.py

allow-budget: ## Check that the set of audit allow markers has not grown
	@$(PY) tools/check_allow_budget.py --selftest >/dev/null
	@$(PY) tools/check_allow_budget.py

pr-verify: ## Confirm CI passed for the commit a PR will merge (PR=<number>)
	@test -n "$(PR)" || { echo "usage: make pr-verify PR=<number>" >&2; exit 2; }
	@$(PY) scripts/verify_pr_checks.py $(PR)

links-external: ## Check internal + external links (network required)
	@$(PY) tools/check_links.py --external

# The guarded form of `all`, and what both hooks run. It asserts the gate did not change the git
# index — a check that writes to the real repository has left edits in the index and nowhere else.
# `all` cannot assert this about itself: a recipe runs after its prerequisites, so it cannot see the
# state before they ran.
gate: ## Run `all` and assert it did not change the git index (what the hooks run)
	@scripts/run_gate.sh /tmp/gate.log

all: sweep-probes lint entry-points i18n-check switcher-check ja-markers audit allow-budget workflow-observability secrets links cross-repo inbound-probes anchors diagram-fonts diagram-flow drift test ## Run every check (commit gate)
	@echo "All checks passed."

# In `all`, unlike `diagrams-check`: this reads the committed .drawio and .svg only, so it needs
# neither the AWS icon package nor the draw.io CLI.
diagram-fonts: ## Check that diagram labels clear the readability floor
	@$(PY) tools/check_diagram_fonts.py --selftest >/dev/null
	@$(PY) tools/check_diagram_fonts.py

diagram-flow: ## Check that diagrams read rightwards and downwards, with labels under icons
	@$(PY) tools/check_diagram_flow.py --selftest >/dev/null
	@$(PY) tools/check_diagram_flow.py

hooks: ## Activate the tracked pre-commit and pre-push hooks in this clone (idempotent)
	@current="$$(git config --local --get core.hooksPath || true)"; \
	if [ "$$current" = ".githooks" ]; then \
	    echo "hooks: already active in this clone (core.hooksPath=.githooks)"; \
	else \
	    git config --local core.hooksPath .githooks; \
	    echo "hooks: activated (core.hooksPath=.githooks)"; \
	fi; \
	globalpath="$$(git config --global --get core.hooksPath || true)"; \
	if [ -n "$$globalpath" ]; then \
	    echo "hooks: note: a global core.hooksPath is set ($$globalpath)."; \
	    echo "hooks:       the local setting above overrides it in THIS clone only."; \
	    echo "hooks:       any clone without it runs the global hook instead, and the"; \
	    echo "hooks:       tracked hook is then present, correct, and never runs."; \
	fi

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
