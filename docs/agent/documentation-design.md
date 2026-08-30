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

- Name what the reader does, not what the document contains: "Get Started" / `はじめかた`, not
  "Prerequisites" / `前提条件`.
- The first visible section is a Get Started table with time estimates.
- Action-first is about the *subject* of the heading. In Japanese it does not license a verb form —
  `はじめかた`, not `はじめる`. See below.

## Japanese headings are noun phrases

Applies to every section heading at `##` and deeper in a Japanese document. A verb form, a question
form, or a full predicate reads as a sentence fragment where a Japanese reader expects a label.

| Form | Avoid | Use |
|---|---|---|
| Verb (dictionary form) | `自分の環境で確かめる` | `自環境での確認手順` |
| Verb (dictionary form) | `構築後の検証を自動化する` | `構築後検証の自動化` |
| Question | `なぜこの区分が必要か` | `この区分が必要な理由` |
| Question | `責務をどう分けるか` | `責務の分割` |
| Predicate (`〜ます` / `〜です`) | `記録されない読み取りがあります` | `記録されない読み取りの存在` |
| Predicate (plain) | `クロスアカウントのデータアクセスは成立する` | `クロスアカウントデータアクセスの成立` |

**Nominalizing must not drop the assertion.** A heading in this repository often carries the finding
itself, so `監査は 2 つの面に分かれ、片方に穴があります` → `監査の 2 つの面と片方の穴` loses the claim:
"there is a hole" degrades to the noun "hole". Carry it with a suffix or a modifier instead —
`監査の 2 つの面と片方の穴の存在`. The usable suffixes are `〜の存在`, `〜の不在`, `〜の成立`,
`〜の不成立`, `〜の必要`, `〜の不可`, `〜の相互作用`, `〜の差`, `〜の上限`, plus prefixes and modifiers
(`未対応の〜`, `既定で無効な〜`). **If no suffix preserves the claim, the heading is carrying a whole
sentence and belongs in the body.**

**Exempt: the H1 and the frontmatter `title`.** Those are a one-line claim by a separate convention
in `AGENTS.md`, so `課金は「確保した量」と「使った量」に分かれる` is correct as a title and would be
wrong as a section heading.

English headings are unaffected — `Deleting a volume` and `How to choose` are both fine.

**Renaming a heading renames its anchor.** Update inbound links, and follow the external-anchor
procedure in `AGENTS.md` when the heading is listed in `docs/agent/external-anchor-contract.txt`.

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
