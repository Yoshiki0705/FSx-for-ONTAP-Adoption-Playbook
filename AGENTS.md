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

```bash
make help          # List all targets
make lint            # markdownlint + frontmatter schema validation
make i18n-check      # Tier 1 cross-language section parity
make switcher-check  # Language switcher blocks match what exists on disk
make audit           # Pre-publication audit (naming / neutrality / PII / internal IDs)
make links           # Broken link check (internal links offline, external opt-in)
make all             # lint + i18n-check + switcher-check + audit + links

# Individual validators (also callable directly)
python3 tools/validate_frontmatter.py            # Schema + evidence-tier rules
python3 tools/check_i18n_parity.py               # Section structure/count across languages
python3 tools/audit_public_output.py             # Naming, neutrality, PII, internal IDs
python3 tools/check_links.py                     # Internal link resolution
python3 tools/check_links.py --external          # Include external URLs (network required)
python3 tools/sync_lang_switcher.py              # Verify switcher blocks
python3 tools/sync_lang_switcher.py --write      # Regenerate switcher blocks
python3 tools/sync_lang_switcher.py --verify-parity   # JA/EN links must match modulo <lang>
python3 tools/new_note.py --module domains/performance --slug my-slug   # Scaffold a note
```

`make all` is the gate. Run it before every commit.

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
├── tools/                          # Validation + scaffolding scripts (Python 3.12, stdlib only)
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
source: <URL or "vendor documentation">  # required iff evidence == documented
ontap_version: 9.17.1P7D1      # optional; required for version-specific behavior
region: ap-northeast-1         # optional; required for measured numbers
lang: ja
---
```

### Evidence tiers — the central discipline of this repository

| Tier | Meaning | Requirement |
|------|---------|-------------|
| `verified` | Reproduced in a named environment by the author | `verified_on` + environment (version / region / config) stated inline |
| `documented` | Stated in vendor or AWS documentation | `source` URL; quote ≤ 30 consecutive words; paraphrase preferred |
| `field-observation` | Observed once in the field, not reproduced | Must say so explicitly in the body; no generalization |
| `hypothesis` | Reasoned expectation, untested | Must be labeled as untested in the body |

Never promote a tier without adding the corresponding evidence. Downgrading is always allowed.

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

## Documentation Design Principles

### Hub & Spoke

- `README.md` is a hub: it links out, it does not contain details inline.
- Each `docs/` file answers **one** question in depth.
- Max visible content in a README before `<details>` expansion: ~150 lines.

### Progressive disclosure

- Wrap anything not needed on first read in `<details><summary>`.
- First-time reader needs: what is this / how do I start / where are the details.
- Returning reader needs: what changed / where is the specific doc.

### Action-first headings

- Use "はじめる" / "Get Started", not "前提条件" / "Prerequisites".
- The first visible section is a Get Started table with time estimates.

### 7±2 rule

- No more than 7 items visible at one navigation level. More than 7 rows → collapse into `<details>`.

### No dead weight

- Development history → `CHANGELOG.md`, not README.
- If content will never be updated again, it does not belong in a README.

### Technical reference docs must include

Executive-summary conclusion up front, FAQ / common misconceptions, a selection flowchart (mermaid is
fine), OT/IT security considerations where applicable, phased adoption steps, and a Related Documents
section with back-links.

## Localization

### Path model

A document's language is its directory, never a filename suffix. `README.en.md` and friends do not
exist; the counterpart of `docs/ja/domains/cost/README.md` is `docs/en/domains/cost/README.md`.

Because the two files sit at the same depth, **a translation is a copy plus text replacement — every
relative link stays byte-identical**. If you find yourself adjusting `../` counts while translating,
something is in the wrong place. `make switcher-check --verify-parity` enforces this: it compares the
Japanese and English link target sets and fails on any difference beyond the language segment.

One exception: root `README.md` is the Japanese hub, so `docs/ja/README.md` does not exist and the
"home" link resolves to a different depth per language. That link is generated, so it costs nothing.

### Tiers

Three tiers, enforced by `make i18n-check`:

| Tier | Scope | Languages |
|---|---|---|
| 1 | Root `README.md` + `docs/<lang>/README.md`, and the guides listed in `docs/i18n-manifest.txt` | per manifest; default all 8 |
| 2 | Module `README` under `docs/<lang>/{playbooks,domains}/` | ja, en |
| 3 | `notes/`, `checklists/` | ja (en optional) |

Tier 1 requires matching section structure and count across the languages the manifest names for that
file. When you change one language, change all of them in the same commit.

`docs/ja/reference/**` is currently written as **bilingual single files** (Japanese and English prose
sharing the same tables). It is therefore not split per language yet, and English pages link into
`docs/ja/reference/`. When adding to `reference/`, follow the existing bilingual style rather than
creating a partial `docs/en/reference/` tree.

### Language switcher

Never hand-write or hand-edit a switcher line. Each localized file carries a generated block:

```markdown
<!-- lang-switcher:start -->
🌐 [日本語](…) | [English](…) | [🏠 リポジトリトップ](…)
<!-- lang-switcher:end -->
```

`python3 tools/sync_lang_switcher.py --write` fills it from the filesystem, listing only languages
that actually exist. The tool does not insert the marker pair — placement is a layout decision, so a
new file needs the markers added once, after the H1 and at the end of the file.

**Never translate**: file paths, commands, badge URLs, anchor IDs, product and technical terms
(ONTAP, SnapMirror, FlexCache, FlexClone, SnapLock, FabricPool, S3 Access Point, SVM, LIF).

## Authoring Conventions

- Markdown, ATX headings (`##`), no trailing whitespace, one sentence per line is **not** required.
- Tables over bullet lists for anything with 2+ attributes per item.
- Mermaid for flowcharts and sequence diagrams; draw.io for architecture diagrams.
- **Every diagram carries the same information in prose or a table.** A mermaid block is a summary of something stated elsewhere in the document, never the only place a fact appears. Mermaid does not render in every context, is not reliably reachable by a screen reader, and is not extractable by a crawler — so a decision that exists only inside a diagram is a decision some readers cannot access.
- Code blocks always carry a language tag.
- Internal links are relative paths. Blog-facing images use absolute `raw.githubusercontent.com` URLs.
- Japanese is the primary authoring language; code, identifiers, and commit messages are English.
- Commit messages: conventional commits (`docs:`, `feat:`, `fix:`, `chore:`, `refactor:`, `ci:`), under 72 chars.
- PR titles: `<type>: <description>`, under 70 chars. Enforced by `.github/workflows/pr-title-check.yml`.

## Architecture Diagrams

Follow the same standard as sibling repositories:

- Official AWS Architecture Icons, current quarterly Asset Package only. Do **not** use draw.io's bundled `mxgraph.aws4` (2019 generation).
- Service icons 80×80 (`Arch_*_64.svg` native), resource icons 48×48 (`Res_*_48.svg`). No rescaling, no mixing.
- Labels use official service names with the `Amazon`/`AWS` prefix. No abbreviations (`ALB` → `Elastic Load Balancing`). Non-AWS elements (`NFS クライアント`, `Windows ファイルサーバー`) need no prefix.
- Arrows: single-color preset open arrow only (`endArrow=open;endFill=0;strokeColor=#232F3E`). No color-coding or dashed-line semantics.
- Sources live in `docs/_assets/diagrams/`, exports in `docs/_assets/images/` and `docs/_assets/images/png/`. Diagrams are language-neutral; the underscore marks the directory as not-content, which is also why the validators skip it.
- Ship **both themes**: light is the default and what docs display; dark is generated from light with `Res_*_48_Dark` icon substitution and linked alongside.
- Never commit the icon asset package itself — only diagrams with icons already embedded.
- `ET.parse()` passing is not verification. **Render the PNG and look at it**, per language.
- `@2x` exports exceed the 2000px read limit; downscale to a preview before reading.

## Verification Checklist

Before submitting changes:

1. `make lint` — markdownlint clean, all frontmatter valid
2. `make audit` — zero naming, neutrality, PII, or internal-ID hits
3. `make i18n-check` — Tier 1 parity holds
4. `make switcher-check` — switcher blocks match the languages on disk
5. `make links` — no broken internal links
6. New note → frontmatter complete, `evidence` tier honest, environment stated for any number
7. New case study → anonymization table in `docs/ja/case-studies/_template/` fully applied
8. Changed a Tier 1 doc → every language the manifest names updated in the same commit
9. Added a translation → `sync_lang_switcher.py --write`, never a hand-edited switcher line
10. Changed a diagram → light and dark regenerated, PNG visually confirmed

## Self-Review (4-Axis Check)

Run before the checklist above. Automated checks catch syntax; these catch design-level issues.

1. **Implementation gaps** — anything in scope still missing? (Note added but not linked from the module README? Tier 1 changed in only one language? Decision tree updated but the comparison matrix left stale?)
2. **Oddities** — anything strange in the diff? (Leftover placeholder text, a frontmatter `evidence: verified` with no `verified_on`, headings that no longer match the body, half-applied renames.)
3. **Polish opportunities** — small in-scope improvements noticed and dismissed? Include them if they touch the same files with no risk.
4. **Regression risk** — did a link target move? Does another doc cite a number you just changed? Did a glossary term change meaning?

Surface findings explicitly and fix before finalizing.

## Common Pitfalls

| Pitfall | Solution |
|---|---|
| `evidence: verified` without `verified_on` | `make lint` fails. Either add the date or downgrade the tier |
| A measured number with no environment stated | Always state ONTAP version, region, and configuration next to the number |
| Tier 1 doc updated in Japanese only | `make i18n-check` fails. Update every language the manifest names, in the same commit |
| Adjusting `../` counts while translating a file | The counterpart belongs at the same depth under `docs/<lang>/`. Only the language segment may differ |
| Hand-editing a switcher line, or adding a language to it manually | `make switcher-check` fails. Run `sync_lang_switcher.py --write` |
| A link that resolves but sends the reader into another language | `make links` cannot see this. `sync_lang_switcher.py --verify-parity` can |
| Creating `docs/en/reference/` for one file | `reference/` is bilingual single files today. Follow that style or split the whole tree deliberately |
| Bare `FSx` or `FSxN` slipping into prose | `make audit` fails. Only "Amazon FSx for NetApp ONTAP" / "FSx for ONTAP" |
| Suggesting BlueXP / Workload Factory / NetApp Console | Reframe to CloudWatch / ONTAP REST API / FabricPool / DataSync / Snapshot-FlexClone-SnapMirror |
| Vendor-versus phrasing in a comparison | State trade-offs symmetrically and add a "how to choose" section |
| Invented `**X Engineer lens**` callout | Relabel to a neutral topic note (`**Security note**`) |
| Case study with a recognizable configuration | Abstract to industry + scale band; drop anything identifying |
| Personal path `/Users/<name>/` in an example | Use `${PROJECT_DIR}` or a relative path |
| Dark diagram not regenerated after a light edit | Regenerate; the light/dark pair must stay in sync |
| Reading a `@2x` PNG directly | Exceeds the 2000px limit. Downscale to a preview first |
| Citing another repo's finding without a link | Always link the source repository and doc |

## FSx for ONTAP Domain Knowledge (carry-over)

These are established findings from sibling repositories. Do not re-derive them; cite and link instead.

### AD integration

- AWS Managed Microsoft AD inserts an intermediate OU: `OU=Computers,OU=<ShortName>,DC=…`. Omitting it causes silent failures. Self-managed AD has no intermediate OU.
- `FileSystemAdministratorsGroup` must be `Domain Admins`. `AWS Delegated FSx Administrators` has insufficient permissions for SVM join (verified failure → `MISCONFIGURED`).
- SVM NetBIOS name: ≤15 chars, must differ from the domain ShortName, unique per AD domain. Never reuse a name after a failed join — AD retains the orphaned computer account.
- Windows EC2 domain join: use a separate `AWS::SSM::Association` with the AWS-managed `AWS-JoinDirectoryServiceDomain` document. Never `SsmAssociations` on the instance, never a custom `aws:domainJoin` document.

### S3 Access Points

- IAM ARN must be access-point style: `arn:aws:s3:<region>:<account>:accesspoint/<name>` (and `/object/*`). Bucket-style ARNs do not work.
- Dual-layer authorization: AWS side (IAM + AP policy) **and** ONTAP side (file system identity) must both allow.
- `NetworkOrigin` is immutable after creation. `Internet` origin is not reachable via an S3 Gateway VPC Endpoint.
- Size limits are **binary** despite docs saying "GB": single `PutObject` and per-`UploadPart` 5 GiB; whole object 50 GiB. The whole-object limit is checked only at `CompleteMultipartUpload`, after the full payload transfers — validate client-side first.
- On an AD-joined SVM, **every** data operation requires AD DC reachability. `HeadBucket` succeeds even when AD is unreachable (false positive) — always verify with a data operation.

### Documented constraints

- No S3 Event Notifications → use EventBridge Scheduler polling or FPolicy.
- SnapLock / tamperproof snapshot enablement is **irreversible**. Enabling the feature is not the same as auto-locking; a retention period on the policy is what triggers locking.
- Volume names allow only alphanumerics and underscores.

## External Dependencies

- Primary region for verification: `ap-northeast-1` (Tokyo)
- ONTAP baseline for carried-over findings: 9.17.1P7D1
- Tooling: Python 3.12 (stdlib only for `tools/`), `markdownlint-cli2`, `gitleaks`
- No application runtime, no AWS deployment from this repository
