# AGENTS.md

<!-- audit-file-allow: naming,neutrality,pii -->
<!-- This document defines the naming, neutrality, and public-output rules, so it necessarily
     quotes the patterns it forbids. The file-level allowance above exempts it from the audit
     that enforces those rules elsewhere. Do not copy this declaration into content files. -->

> Project-specific instructions for AI coding agents working in this repository.
> This file is committed and travels with the repo. Kiro steering under `.kiro/` is local-only  <!-- gitleaks:allow -->
> (gitignored), so anything an agent must know to work correctly belongs **here**.

## Project Overview

A **documentation-first** knowledge base for Amazon FSx for NetApp ONTAP adoption: migration cases
and best practices across design, build, and operations. There is no application to deploy — the
deliverable is the documentation itself, plus small validation tools under `tools/`.

**Every localizable document lives under `docs/<lang>/`.** Japanese is the reference language and the
only complete tree. The one exception is the root `README.md`, which *is* the Japanese hub — so
`docs/ja/README.md` does not exist.

Two navigation axes, mirrored in each language:

- `docs/<lang>/playbooks/` — lifecycle: `01-assess` → `02-design` → `03-migrate` → `04-build` → `05-operate` → `06-optimize`
- `docs/<lang>/domains/` — cross-cutting topics: `data-protection`, `data-utilization`, `security-governance`, `performance`, `cost`, `multiprotocol-identity`

Plus `docs/<lang>/case-studies/` (anonymized field findings) and `docs/ja/reference/` (decision
trees, comparisons, limits, glossary — currently bilingual single files, see Localization).

## Core Commands

### Set up the pinned toolchain first

```bash
python3 -m venv .venv                                          # preferred
.venv/bin/python -m pip install -r requirements-dev.txt        # ruff, exact-pinned
npm install -g markdownlint-cli2                               # not pip-installable
brew install gitleaks                                          # not pip-installable
```

**`make python` uses `.venv/bin/ruff` when it exists, before anything on `PATH`.** That removes the
failure this instruction used to produce: resolution by `PATH` order means a copy installed for
something else can win silently, and a Homebrew `ruff` at 0.15.20 was in fact shadowing the pinned
version here, so the gate linted with the wrong rule set while reporting success.

A virtual environment is not required. Without one, install the pin globally and keep it matched:

```bash
pipx uninstall ruff && pipx install "ruff==$(sed -n 's/^ruff==//p' requirements-dev.txt)"
```

`pip install --user` is refused outright on a Homebrew Python (PEP 668), and plain `pip` is often
not on `PATH` at all — so the older instruction was a dead end on the machine it was written on.
That mattered once the gate stopped accepting a mismatch.

**Install all three. Every gate now fails when its tool is missing, rather than skipping.** Three
of them used to degrade quietly — `make markdown` printed "skipping", `make audit` printed
"skipping secret scan", and `make python` fell back to `py_compile` under the same name. A check
whose tool is absent is indistinguishable from a check that passed, and the gitleaks half of
`make audit` was in exactly that state inside CI on every run.

**`make python` fails when the `ruff` first on `PATH` is not the pinned version.** Rule sets widen
between releases, so a newer `ruff` reports findings on code that has not changed and an older one
stays silent on code CI will reject. This used to be a warning, which was easy to walk past — the
same silent divergence it was warning about. If it fires after installing the pin, check for a second
binary earlier on `PATH` with `which -a ruff`; a package-manager copy shadowing the pinned one is the
usual cause.

```bash
make help          # List all targets
make lint            # markdownlint + frontmatter schema validation
make i18n-check      # Tier 1 cross-language section parity
make switcher-check  # Language switcher blocks match what exists on disk
make ja-markers      # English links into Japanese-only pages carry (日本語)
make audit           # Pre-publication audit (naming / neutrality / PII / internal IDs)
make secrets         # gitleaks scan of the worktree (full history: gitleaks workflow)
make links           # Broken link check (internal links offline, external opt-in)
make anchors         # Externally cited section anchors have not been renamed
make pr-verify PR=n  # CI passed for the commit this PR will merge, keyed on its head SHA
make drift           # AGENTS.md size budget, steering loader thinness, index reachability
make test            # Guardrail tests: guard contract, .PHONY, one break per doc gate
make all             # everything above (commit gate)

# Individual validators (also callable directly)
python3 tools/validate_frontmatter.py            # Schema + evidence-tier rules
python3 tools/check_i18n_parity.py               # Section structure/count across languages
python3 tools/audit_public_output.py             # Naming, neutrality, PII, internal IDs
python3 tools/check_links.py                     # Internal link resolution
python3 tools/check_links.py --external          # Include external URLs (network required)
python3 tools/sync_lang_switcher.py              # Verify switcher blocks + cross-language links
python3 tools/sync_lang_switcher.py --write      # Regenerate switcher blocks
python3 tools/new_note.py --module domains/performance --slug my-slug   # Scaffold a note
python3 scripts/guard_irreversible_ops.py --selftest   # block / ask / allow, both directions
```

CI calls these Makefile targets rather than repeating the commands, and the linted path list lives
once in the Makefile's `PY_PATHS`. Test directories live in `TEST_DIRS` for the same reason: a
`tests/` directory that is not listed there runs nowhere, and `make test` fails when one exists
outside the list.

`make all` is the gate. Run it before every commit — and specifically **after the last edit**, not before it.

The pre-commit hook is not a substitute. It scans for secrets only, so a commit can pass the hook and
still fail `markdown lint` in CI. The failure mode this produces is narrow and easy to walk into: run
the gate, then touch one more file (a CHANGELOG entry is the usual candidate), then commit. Re-run the
gate after that last edit.

## Repository Layout

```text
├── README.md                       # JA hub. The other 7 hubs live at docs/<lang>/README.md
├── AGENTS.md                       # This file
├── llms.txt                        # LLM-facing repository map (llmstxt.org)
├── CONTRIBUTING.md                 # Authoring conventions
├── Makefile
├── docs/
│   ├── i18n-manifest.txt           # Which Tier 1 guide requires which languages
│   ├── _assets/
│   │   ├── diagrams/               # .drawio sources
│   │   └── images/  images/png/    # Exported svg / png@2x
│   ├── ja/                         # Reference language, only complete tree
│   │   ├── navigation.md  evidence-policy.md
│   │   ├── playbooks/               # Lifecycle axis
│   │   │   ├── 01-assess/ … 06-optimize/
│   │   │   │   ├── README.md
│   │   │   │   ├── notes/<slug>.md  # 1 file = 1 concern, YAML frontmatter required
│   │   │   │   └── checklists/<slug>.md
│   │   │   └── _template/           # Copy this to add a module
│   │   ├── domains/                 # Topic axis (same internal shape)
│   │   │   ├── data-protection/ … multiprotocol-identity/
│   │   │   └── _template/
│   │   ├── case-studies/
│   │   │   ├── _template/case-study.md   # Anonymization-enforcing template
│   │   │   └── README.md
│   │   └── reference/
│   │       ├── decision-trees/      # Mermaid flowcharts
│   │       ├── comparison/          # Option matrices (symmetric trade-offs)
│   │       ├── limits/              # Limits + source + verified_on
│   │       └── glossary/
│   ├── en/                          # Same shape, only the files that are translated
│   │   ├── README.md  navigation.md  evidence-policy.md
│   │   ├── playbooks/<module>/README.md
│   │   ├── domains/<module>/README.md
│   │   └── case-studies/README.md
│   └── ko/ zh-CN/ zh-TW/ fr/ de/ es/     # README.md hubs for now
├── tools/                          # Validation + scaffolding scripts (Python 3.12+, stdlib only)
├── scripts/                        # Maintenance helpers
├── .kiro/                          # Kiro steering + MCP (gitignored, local only)  <!-- gitleaks:allow -->
└── .private/                       # Non-public source notes (gitignored, never committed)  <!-- gitleaks:allow -->
```

A language directory holds only what has actually been translated. Nothing is stubbed out to make
the tree look symmetric — `make switcher-check` derives the language switcher from what exists, so a
missing translation is simply absent from the switcher rather than a broken link.

## Content Model

### Note frontmatter (required on every file under `notes/`)

```yaml
---
title: <one-line statement of the concern, not a topic label>
lifecycle: [assess|design|migrate|build|operate|optimize]   # ≥1
domains: [data-protection|data-utilization|security-governance|performance|cost|multiprotocol-identity]  # ≥1
evidence: verified | documented | field-observation | hypothesis
verified_on: YYYY-MM-DD        # required iff evidence == verified
region: ap-northeast-1         # required iff evidence == verified
source: <URL or "vendor documentation">  # required iff evidence == documented
ontap_version: 9.17.1P7D1      # optional; required for version-specific behavior
lang: ja
---
```

Case studies additionally carry `industry` and `scale_band` (see `docs/ja/case-studies/_template/`).
**No other key is accepted.** An unrecognized key is an error, not an extension: a misspelled
`regoin:` leaves the value plainly visible to a reviewer while every gate ignores it, which is worse
than the key being absent. `region` is required on `verified` because a reader cannot judge whether
their environment differs without knowing where the result came from — if the environment cannot be
named, the tier is wrong rather than the field optional.

### Evidence tiers — the central discipline of this repository

| Tier | Meaning | Requirement |
|------|---------|-------------|
| `verified` | Reproduced in a named environment by the author | `verified_on` + environment (version / region / config) stated inline |
| `documented` | Stated in vendor or AWS documentation | `source` URL; quote ≤ 30 consecutive words; paraphrase preferred |
| `field-observation` | Observed once in the field, not reproduced | Must say so explicitly in the body; no generalization |
| `hypothesis` | Reasoned expectation, untested | Must be labeled as untested in the body |

Never promote a tier without adding the corresponding evidence. Downgrading is always allowed.

A tier records **where a claim comes from**, not how far it was chased. So `documented` carries no claim
that anyone reproduced it, and "we searched and found nothing stated" is not a tier at all — it is a
statement about the documentation, so write it in the body with the date and scope of the search.
Reaching for `hypothesis` there asserts reasoning the note does not have. See
[`docs/ja/evidence-policy.md`](docs/ja/evidence-policy.md).

**Distinctions that must never blur** (repeat them inline where relevant):

- "sample run" vs "production estimate"
- "this test environment" vs "general service limit"
- "design consideration" vs "legal / compliance / regulatory judgment"
- "AI assistive signal" vs "final decision"

## Naming (authoritative — applies to every file, diagram, comment, and commit)

- First mention: **Amazon FSx for NetApp ONTAP**. Thereafter: **FSx for ONTAP**. These are the only accepted forms.
- Forbidden, always correct to "FSx for ONTAP": `FSxN`, bare `FSx`, `FSx ONTAP`, `FSx NetApp`.
- S3 Access Point in this context: write **FSx for ONTAP S3 AP** (not bare `S3 AP` when the FSx for ONTAP context matters).
- **Do not propose these products anywhere**: NetApp Workload Factory, NetApp Console, BlueXP. Reframe to the native equivalent (Amazon CloudWatch, ONTAP REST API, FabricPool, AWS DataSync, Snapshot / FlexClone / SnapMirror).
- Exception: verbatim external citation titles that literally contain a forbidden form. Mark the line with `<!-- allow:naming -->`.
- Repository and directory names (`fsxn-adoption-playbook`) are identifiers, not prose, and are exempt. Prose referring to them needs `<!-- allow:naming -->`.

## Vendor Neutrality (right-tool-for-the-job)

As an AWS Community Builder / AWS Ambassador, framing matters as much as accuracy.

Forbidden: `best`, `beats X`, `X is inferior`, `competing tools`, `競合ツール`, `X より優れている`, `優位性`, `game-changer`, and any vendor-versus positioning.

| Avoid | Prefer |
|---|---|
| "competing tools" / 競合ツール | "alternative options" / 選択肢 |
| "X is better than Y" | "X suits A; Y suits B" / 用途に応じて選択 |
| "Y's weakness is…" | "Y's trade-off is…" — stated **symmetrically**, including for the recommended option |

Every comparison must include a neutral "how to choose" section and list the recommended option's own constraints.

## Public-Output Safety

This is a public repository. Git history is permanent and search-indexed.

**Never commit**: personal names (colleagues, reviewers, customers — JA or EN), email addresses, phone numbers, addresses, identity-linked social handles, employee IDs, AWS account IDs, internal IPs or hostnames, support case numbers, vendor-internal ticket or product IDs, customer or organization names, unmasked screenshots.

| Do NOT use | Use instead |
|---|---|
| A named reviewer | Role-based reference ("storage operations perspective") |
| `name@example.com` | "(internal reviewer)" |
| Internal ticket `XX-I-12345` | "an internal product request (tracked)" |
| Support case `#123456` | "filed with the vendor (no number)" |
| Real account ID | `123456789012` |
| Real IP | `10.0.x.x` or `<management-ip>` |
| Real file system ID | `fs-0123456789abcdef0` <!-- gitleaks:allow --> |
| `/Users/<name>/…` | Relative path or `${PROJECT_DIR}` |

Names are acceptable in `.private/` and `.kiro/` (both gitignored). Never in tracked files.  <!-- gitleaks:allow -->

### Branch names and commit messages are public output too

They are indexed, quoted in release notes, and effectively permanent. The existing rules cover their
*form*; these cover their *content*.

**Branch names** — `<type>/<what>`, kebab-case ASCII, ≤ 40 characters.

| Rule | Why |
|---|---|
| Name what the branch **adds or changes**, never what was wrong before | A name is visible on the pull request page forever and reads as a verdict on earlier work. `docs/readme-honest-coverage` judges the past; `docs/module-status-accuracy` describes the change |
| Noun phrase, not a sentence | `docs/lang-directory-layout`, not `docs/move-all-docs-under-lang` |
| One concern per branch | When the name stops describing the contents, split the branch. Do not rename it to something vaguer |
| No dates, ticket IDs, person names, or tooling/session references | `docs/phase3-20260806`, `docs/agent-session-2` leak process and rot immediately |

**Commit subjects** — `<type>(<scope>): <what changed>`, ≤ 72 characters, imperative, no trailing period.

State the effect, not the activity: `docs: add environment-first entry`, not `docs: update navigation.md`. The diff already lists files; the subject is for the reader scanning `git log --oneline`.

**Commit bodies** — wrap at 72. Lead with **why**: the problem the change addresses, since the diff already shows what. Say what was deliberately left undone and which constraints were accepted. Corrections to an earlier commit are stated plainly, without apology.

**Never in a branch name, subject, body, or PR text**: persona names, review rounds or counts, customer or organization names, support case numbers, vendor-internal IDs, real account IDs or IPs, personal paths, and vendor-versus phrasing. Process metadata is banned here for the same reason it is banned in published docs — it is noise for readers and it dates the work.

**Merge strategy affects how long a branch name lives.** A squash merge keeps the pull request title and number in `main`; the branch name survives only on the pull request page. A merge commit embeds the branch name in `main` permanently. Squash is the default here — the pull request body carries the detail, and `main` stays readable.

**Before merging, run `make pr-verify PR=<number>` rather than reading `gh pr checks`.** That command reports the latest results, not results for the current head, so pushing one more commit and re-reading it returns the previous commit's verdict with nothing marking it stale. A pull request here was merged over a failing gate, and the next one nearly consumed a stale result the same way. `make pr-verify` keys every lookup on the head SHA and treats a workflow that has not started as a failure.

### Do not invent role-labeled review notes

Do **not** write inline callouts labeled with a job title or persona name (`> **AppSec lens**:`,
`> **FinOps Engineer lens**:`, `> **… の視点**:`) unless a real person in that role actually reviewed
the content. Such a label implies an interview or expert review took place.

Use **neutral, topic-based labels** instead — the finding is unchanged, only the label differs:

```markdown
> **Security note**: …
> **Cost note**: …
> **セキュリティに関する補足**: …
> **DR runbook sequencing note**: …
```

Pre-commit check: `grep -rnoE '^> \*\*[^*]+(lens|の視点)[^*]*\*\*' <changed-files>` must return nothing.

### No process metadata in published docs

Do not add "Persona Review Summary" sections, review rounds, review dates, lens counts, or
`R1/F2/EXT/Round` tags. They are noise for humans and inflate token cost and hallucination risk for
crawlers. Review provenance belongs in `.private/`.  <!-- gitleaks:allow -->

## Immutability (WORM) features: never enable one on your own judgement

**This is the hardest rule in this file. It exists because it was broken.**

On 2026-08-06 an agent working in this repository created an FSx for ONTAP SnapLock audit log volume to
verify a documented claim. It did not ask which retention period to use, and it read the warning that
governs the operation only *after* the operation would not reverse. One 128 MiB volume made the volume,
its SVM, and **the entire file system** undeletable for six months. The agent had already set privileged
delete to `PERMANENTLY_DISABLED`, closing the last escape route. The verification produced no usable
finding. A support case was opened; the constraint is documented and working as designed.

The lesson generalizes past SnapLock:

> **A feature whose purpose is to remove your ability to delete data must never be enabled by an agent
> acting on its own judgement.** When such a feature works correctly it is indistinguishable from an
> outage you caused. There is no rollback, and the blast radius is routinely wider than the resource
> named in the call.

### Operations that require an explicit human instruction naming the retention value

| Service | Operation or parameter |
|---|---|
| FSx for ONTAP — SnapLock | `SnaplockConfiguration`, `SnaplockType`, `AuditLogVolume`, `PrivilegedDelete`, `RetentionPeriod`, `VolumeAppendModeEnabled`, ONTAP `snaplock` / `audit-logs` endpoints |
| FSx for ONTAP — **snapshot locking (Tamperproof Snapshot)** | `-snapshot-locking-enabled`, `-snaplock-expiry-time`, `volume snapshot modify-snaplock-expiry-time`, `volume snapshot policy create -retention-period`, `snapmirror policy add-rule -retention-period`. **Applies to volumes that are not SnapLock volumes, and has no AWS API parameter — so "we do not use SnapLock" is not protection, and no IAM condition key or console warning can gate it** |
| Amazon S3 | Object Lock configuration, `put-object-retention`, `put-object-legal-hold` |
| S3 Glacier | `initiate-vault-lock`, `complete-vault-lock` |
| AWS Backup | Vault Lock (`put-backup-vault-lock-configuration`), compliance mode |
| Amazon EBS | `lock-snapshot` |
| Anywhere | any value literally named `PERMANENTLY_DISABLED`, `COMPLIANCE`, or an equivalent terminal state |

### The gate

1. **Identify which parameter actually sets the lock, and check whether the API you are using can set it
   at all.** Do not stop at "use the minimum". A service can expose several retention parameters, and the
   one that binds may not be the one you set. Here the volume's `RetentionPeriod` was already `0 YEARS`
   while a *different* parameter — the audit log configuration's retention — did the locking, and
   `CreateSnaplockConfiguration` has **no field for it**, so the default applied silently. When your API
   cannot set a value, the fact that a default will be applied is itself the thing to get approved.
2. **State the widest scope before acting**: volume, SVM, file system, bucket, vault, account. Name the
   period, and the cost of holding that scope for its whole duration.
3. **Say plainly whether any documented path reverses it early.** For a SnapLock audit log volume there is
   none short of closing the account.
4. **Read the delete/teardown page before the create page.** Reversibility is a property of the exit, and
   the exit is documented separately from the entry. Here the governing text was a warning on
   [Deleting SnapLock volumes](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snaplock-delete-volume.html),
   not on the page describing how to turn the feature on.
5. **Verification is not an exemption.** Use a disposable, dedicated file system or account. The incident
   above *was* verification work.
6. **Do not combine irreversible operations without re-asking.** Ordering narrows the exits: privileged
   delete was disabled first, so the WORM log files could not be removed later.

`scripts/guard_irreversible_ops.py` enforces this mechanically — it blocks a matching mutating command and
allows read-only inspection. Wire it to a `PreToolUse` hook. **If it blocks you, do not look for a call
that evades it.** It is stdlib-only and project-agnostic; copy it into other repositories — that file
alone, nothing else. Verify it with
`python3 scripts/guard_irreversible_ops.py --selftest`, which covers all three verdicts — block
(exit 2), ask (exit 0 plus a `permissionDecision` payload), and allow (exit 0, silent). Proving it
blocks is not enough on its own: a guard that also stops ordinary work gets switched off.

**The hook must point at this tracked file.** A copy under `.kiro/` or `$HOME` is invisible to
collaborators and to CI, and it drifts. That is not hypothetical here — the wired copy once covered
none of S3 Object Lock, Glacier Vault Lock, Backup Vault Lock, or EBS snapshot lock while this file
listed all four, so ten documented block cases were silently permitted.
`scripts/tests/test_hook_wiring.py` fails when no hook runs the tracked script, and
`scripts/tests/test_guard_irreversible_ops.py` fails when a listed feature area has no block case.

The cases live inside the script deliberately. Once the hook is active, **passing a sample locking command
on the command line gets the verification run itself blocked** — which happened during development. Keeping
them internal means checking the guard never requires a matching string to cross the shell.

## Task-specific references (not loaded every turn)

This file is read on every turn, so material that only matters during one kind of work
lives in tracked documents instead. They are public, versioned, and reviewed like any
other doc — `.kiro/` only records when to read them.

| Document | Read it when |
|---|---|
| [`docs/agent/localization.md`](docs/agent/localization.md) | adding, translating, or restructuring a document under `docs/<lang>/` |
| [`docs/agent/architecture-diagrams.md`](docs/agent/architecture-diagrams.md) | creating, editing, regenerating, or exporting a diagram |
| [`docs/agent/pitfalls.md`](docs/agent/pitfalls.md) | a gate fails and the cause is not obvious, or before finalizing a change |
| [`docs/agent/domain-knowledge.md`](docs/agent/domain-knowledge.md) | writing a technical claim about AD integration, S3 Access Points, or documented constraints |
| [`docs/agent/documentation-design.md`](docs/agent/documentation-design.md) | creating or restructuring a README, a module hub, or a technical reference document. **A README that carries detail inline instead of linking out is the failure it prevents** |

### Tools other repositories copy

Three tools are portable. **The copy set for each lives in `COPY_SETS` in
[`scripts/tests/test_copyability_claims.py`](scripts/tests/test_copyability_claims.py)**, which stages
it outside the repository and imports it there. Recorded where it is enforced, not repeated here.

## Authoring Conventions

- Markdown, ATX headings (`##`), no trailing whitespace, one sentence per line is **not** required.
- Tables over bullet lists for anything with 2+ attributes per item.
- Mermaid for flowcharts and sequence diagrams; draw.io for architecture diagrams.
- **Every diagram carries the same information in prose or a table.** A mermaid block is a summary of something stated elsewhere in the document, never the only place a fact appears. Mermaid does not render in every context, is not reliably reachable by a screen reader, and is not extractable by a crawler — so a decision that exists only inside a diagram is a decision some readers cannot access.
- Code blocks always carry a language tag.
- Internal links are relative paths. Blog-facing images use absolute `raw.githubusercontent.com` URLs.
- Japanese is the primary authoring language; code, identifiers, and commit messages are English.
- **Japanese section headings (`##` and deeper) are noun phrases.** `自環境での確認手順`, not `自分の環境で確かめる`; `この区分が必要な理由`, not `なぜこの区分が必要か`. Nominalizing must keep the assertion — suffix it (`片方の穴の存在`) rather than drop it. The H1 and frontmatter `title` are exempt, being a one-line claim by convention. Table and procedure: `docs/agent/documentation-design.md`.
- Commit messages: conventional commits (`docs:`, `feat:`, `fix:`, `chore:`, `refactor:`, `ci:`), under 72 chars.
- PR titles: `<type>: <description>`, under 70 chars. Enforced by `.github/workflows/pr-title-check.yml`.

## Verification Checklist

Before submitting changes:

1. `make lint` — markdownlint clean, all frontmatter valid
2. `make audit` — zero naming, neutrality, PII, or internal-ID hits
3. `make i18n-check` — Tier 1 parity holds
4. `make switcher-check` — switcher blocks match the languages on disk
5. `make links` and `make anchors` — no broken internal links, no renamed external anchor
6. Merging → `make pr-verify PR=<number>` passed for the **current** head SHA
7. New note → frontmatter complete, `evidence` tier honest, environment stated for any number
8. New case study → anonymization table in `docs/ja/case-studies/_template/` fully applied
9. Changed a Tier 1 doc → every language the manifest names updated in the same commit
10. Added a translation → `sync_lang_switcher.py --write`, never a hand-edited switcher line
11. Renamed a heading in a document another repository cites → tell them, note it in `CHANGELOG.md`,
    then `check_anchor_contract.py --write`. GitHub answers an unknown fragment with the top of the
    page, so the citing side never observes a broken link
12. Changed a diagram → light and dark regenerated, PNG visually confirmed

## Self-Review (4-Axis Check)

Run before the checklist above. Automated checks catch syntax; these catch design-level issues.

1. **Implementation gaps** — anything in scope still missing? (Note added but not linked from the module README? Tier 1 changed in only one language? Decision tree updated but the comparison matrix left stale?)
2. **Oddities** — anything strange in the diff? (Leftover placeholder text, a frontmatter `evidence: verified` with no `verified_on`, headings that no longer match the body, half-applied renames.)
3. **Polish opportunities** — small in-scope improvements noticed and dismissed? Include them if they touch the same files with no risk.
4. **Regression risk** — did a link target move? Does another doc cite a number you just changed? Did a glossary term change meaning?

Surface findings explicitly and fix before finalizing.

## External Dependencies

- Primary region for verification: `ap-northeast-1` (Tokyo)
- ONTAP baseline for carried-over findings: 9.17.1P7D1
- Tooling: Python 3.12 or later (stdlib only for `tools/`; CI runs 3.14), `ruff` exact-pinned in `requirements-dev.txt`, `markdownlint-cli2`, `gitleaks`. CI installs `ruff` from the pinned file rather than resolving the latest release, so the lint verdict does not depend on the day it runs
- A CI interpreter bump is a documentation change too: the version appears in prose in `AGENTS.md` and `CONTRIBUTING.md`, and a dependency bot cannot update prose. State the supported floor as a range and the CI version separately, so a later bump touches one line instead of three
- No application runtime, no AWS deployment from this repository
