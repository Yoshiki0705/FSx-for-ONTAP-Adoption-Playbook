# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Added

- Repository scaffold: two-axis content model (`playbooks/` lifecycle × `domains/` topic)
- Evidence-tier discipline (`verified` / `documented` / `field-observation` / `hypothesis`) with
  frontmatter enforcement in `tools/validate_frontmatter.py`
- Validation tooling, standard library only: frontmatter schema, cross-language parity,
  public-output audit, internal link resolution
- Three-tier localization policy with `docs/i18n-manifest.txt` gating promotion to 8 languages
- Root `README` in 8 languages; `docs/ja|en/navigation.md` and `evidence-policy.md`
- Anonymization policy and template for `case-studies/`
- `reference/`: migration-method decision tree, comparison and limits conventions, glossary
- `llms.txt` and `AGENTS.md` for AI agent and crawler consumption
- CI: docs quality gate, markdown lint, PR title check, gitleaks secret scan

### Changed

- **Localized content moved under `docs/<lang>/`.** A document's language is now its directory
  rather than a filename suffix; `README.<lang>.md` no longer exists anywhere. The root `README.md`
  stays as the Japanese hub, so `docs/ja/README.md` deliberately does not exist. Because every
  language now sits at the same depth, a translation is a copy plus text replacement — relative
  links are identical across languages.
  - `playbooks/`, `domains/`, `case-studies/` → `docs/ja/…`, with English module READMEs at `docs/en/…`
  - `reference/` → `docs/ja/reference/` (bilingual single files, not split per language yet)
  - Diagram and image assets → `docs/_assets/{diagrams,images}`
- Language switchers are generated from what exists on disk by `tools/sync_lang_switcher.py`
  instead of being hand-maintained, so a missing translation is an absent link rather than a
  broken one. Enforced by `make switcher-check`.
- `tools/check_links.py` now also checks `llms.txt`, which was silently exempt because it is not
  a `.md` file — the one entry point crawlers read first.
- `tools/new_note.py` accepts both `domains/performance` and `docs/ja/domains/performance`.

### Corrected

- Nothing yet.
