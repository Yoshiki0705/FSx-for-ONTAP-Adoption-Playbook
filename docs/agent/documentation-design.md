# Documentation design principles

> Moved out of [`AGENTS.md`](../../AGENTS.md) so it is not read on every turn. Read this before
> creating or restructuring a README, a module hub, or a technical reference document.
>
> `AGENTS.md` remains authoritative on any disagreement.

These rules decide layout, not content. The evidence discipline that decides what a document may
claim is in [`docs/ja/evidence-policy.md`](../ja/evidence-policy.md).

## Hub and spoke

- `README.md` is a hub: it links out, it does not carry details inline.
- Each `docs/` file answers **one** question in depth.
- Maximum visible content in a README before `<details>` expansion: about 150 lines.

## Progressive disclosure

- Wrap anything not needed on a first read in `<details><summary>`.
- A first-time reader needs: what this is, how to start, where the details are.
- A returning reader needs: what changed, and where the specific document is.

## Action-first headings

- Use "はじめる" / "Get Started", not "前提条件" / "Prerequisites".
- The first visible section is a Get Started table with time estimates.

## The 7±2 rule

No more than 7 items visible at one navigation level. More than 7 rows collapse into `<details>`.

## No dead weight

- Development history belongs in `CHANGELOG.md`, not in a README.
- Content that will never be updated again does not belong in a README.

## What a technical reference document must include

An executive-summary conclusion up front, an FAQ or common-misconceptions section, a selection
flowchart (mermaid is fine), OT/IT security considerations where they apply, phased adoption steps,
and a Related Documents section with back-links.

**A mermaid diagram never carries a fact on its own.** It summarizes something the document also
states in prose or a table, because mermaid does not render everywhere, is not reliably reachable by
a screen reader, and is not extractable by a crawler.

## Related documents

- [`AGENTS.md`](../../AGENTS.md) — authoritative on every rule
- [`localization.md`](localization.md) — adding or restructuring a document under `docs/<lang>/`
- [`architecture-diagrams.md`](architecture-diagrams.md) — creating or exporting a diagram
- [`docs/ja/evidence-policy.md`](../ja/evidence-policy.md) — what a document may claim
