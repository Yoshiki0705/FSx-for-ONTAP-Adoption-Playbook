# Localization workflow

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this when adding, translating, or restructuring a document under `docs/<lang>/`.
>
> `AGENTS.md` remains authoritative on any disagreement.

## Path model

A document's language is its directory, never a filename suffix. `README.en.md` and friends do not
exist; the counterpart of `docs/ja/domains/cost/README.md` is `docs/en/domains/cost/README.md`.

Because the two files sit at the same depth, **a translation is a copy plus text replacement — every
relative link stays byte-identical**. If you find yourself adjusting `../` counts while translating,
something is in the wrong place. `make switcher-check` enforces the consequence: for every link it
resolves the target's language, and if the *source* file's own language has that same page, the link
must point there. A fallback into Japanese is allowed only while no counterpart exists.

One exception: root `README.md` is the Japanese hub, so `docs/ja/README.md` does not exist and the
"home" link resolves to a different depth per language. That link is generated, so it costs nothing.

## Tiers

Three tiers, enforced by `make i18n-check`:

| Tier | Scope | Languages |
|---|---|---|
| 1 | Root `README.md` + `docs/<lang>/README.md`, and the guides listed in `docs/i18n-manifest.txt` | per manifest; default all 8 |
| 2 | Module `README` under `docs/<lang>/{playbooks,domains}/` | ja, en |
| 3 | `notes/`, `checklists/`, `reference/` | ja; en optional per file, and gated once it exists |

## What English covers, and what it deliberately does not

**English is complete through Tier 2 and opt-in below it.** Every hub, guide, and module README
exists in English, so an English reader can navigate the whole repository and read every question a
module claims to answer. The answers themselves are Japanese unless a specific note has been
translated.

This is a deliberate stopping point, not a backlog:

| | English | Why |
|---|---|---|
| Hubs, `navigation.md`, `evidence-policy.md` | Required | A reader must be able to find their way and read the confidence signals |
| Module `README` (12 modules) | Required | The question list is the index. Without it, English readers cannot tell what is covered |
| `notes/`, `checklists/` | Optional | These carry numbers, thresholds, and irreversible operations. A mistranslation here does not announce itself |
| `reference/` | Not split | Written as bilingual single files; Japanese and English prose share the same tables |

**Do not translate a note merely because it is untranslated.** Translate one when both hold:

1. It is the primary answer to a Tier 2 question that an English reader will reach from a module README
2. Its content has settled — a note still being corrected multiplies every later edit

**Once an English counterpart exists, `make i18n-check` compares its section structure against the
Japanese file on every commit.** That gate exists because the failure mode is invisible from the
English side: a reader has no way to tell that the Japanese version gained two subsections last
month. When it fires, the two honest options are to update the translation or to delete it — never to
leave it behind while editing Japanese.

A Japanese-only note is linked from English with a `(日本語)` marker, so a missing translation is a
labelled link rather than a broken promise.

**The marker applies to every link, not only the ones in a module README's question table.** That
distinction was left implicit, and the rule accordingly held in the index positions and drifted
everywhere else — a reader following a link out of body prose changed language with no warning, and
one afternoon of translation added thirteen such links. `make ja-markers` now enforces it.

What the gate deliberately does not ask for a marker on, because each would announce a translation
that is not missing:

| Not flagged | Why |
|---|---|
| Links into `docs/ja/reference/**` | Bilingual single files by design. The English prose is already there |
| Directory links such as `notes/` | These resolve to a listing, and `switcher-check` already decides which language's directory to point at |
| The generated switcher block | It names the language in its own link text |
| A link whose text already contains 日本語 | The warning is present, spelled differently |

The marker goes after the closing parenthesis, ahead of any sentence punctuation, because that is
where a reader meets it:

```markdown
The items to clear are in [Pre-production review](../../../../ja/playbooks/04-build/checklists/pre-production-review.md) (日本語).
```

## What qualifies for eight languages

Tier 1 is **first-touch material only**: how to find your way around, and how to read the confidence
signals. A reader arriving in their own language needs to know where to go and how much to trust
what they find — nothing beyond that.

| Belongs in Tier 1 | Stays at ja + en or ja |
|---|---|
| The hub, navigation, how to read the evidence tiers | Anything carrying a number, a limit, or a threshold |
| Anonymization and contribution policy a reader must understand before acting | Anything describing an irreversible operation |
| Labels and wording a reader meets before choosing a path | Notes, checklists, decision trees, comparison matrices |

The dividing line is consequence. **A mistranslation in first-touch material sends someone to the
wrong page, which they will notice. A mistranslation in a design judgment does not announce itself
and can be acted on.** Deep technical material is therefore deliberately not promoted, even when a
translation would be easy to produce.

Promotion is also gated on stability. Translating a document that is still changing multiplies every
later edit by eight. Promote when the content has settled, not when it is first written.

## Declaring authority

Every Tier 1 document states which version is authoritative, symmetrically:

- The Japanese version states that it is the authoritative one for technical accuracy.
- Every other language states that Japanese is authoritative and that discrepancies should be
  reported.

This is a plain paragraph, not a heading, so it does not affect section parity. It exists because
translations here are produced with machine assistance and are not natively reviewed before
publication — a reader deciding whether to act on a statement is entitled to know that.

**The operating model is publish, then correct on report.** Waiting for native review before
publishing would mean shipping nothing outside Japanese and English. Instead the limitation is
stated, the report path is one click away, and a translation correction is treated as an ordinary
correction rather than a special case. That trade is only honest while the notice stays visible and
the scope stays narrow — which is why first-touch material is the boundary, not a starting point to
expand from.

Tier 1 requires matching section structure and count across the languages the manifest names for that
file. When you change one language, change all of them in the same commit.

`docs/ja/reference/**` is currently written as **bilingual single files** (Japanese and English prose
sharing the same tables). It is therefore not split per language yet, and English pages link into
`docs/ja/reference/`. When adding to `reference/`, follow the existing bilingual style rather than
creating a partial `docs/en/reference/` tree.

## Language switcher

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
