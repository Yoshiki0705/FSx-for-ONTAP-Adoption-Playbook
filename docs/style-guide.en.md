# Write technical documents readers can use to decide and reproduce

[日本語](style-guide.ja.md)

This guide defines the contributor rules for creating or updating technical documents in this repository.
Dedicated sections define the structures for notes and checklists.
The repository applies it to existing documents in stages.

## Reader-first technical prose

Lead with the conclusion and the reader's next action.
Address one question per file and do not repeat the same explanation across sections.
Name the actor and action, and prefer active voice.
Human review decides whether each subject is clear; CI does not claim to detect omitted Japanese subjects.

Use plain US English and avoid idioms.
Target 25 words or fewer per sentence.
Split longer sentences unless an indivisible technical token would make the result less clear.
Remove machine-translation artifacts, unnecessary passive voice, and stacked noun phrases.

## Claims and evidence

Connect facts to primary sources.
For reproduced observations, state the environment, date, procedure, and result.
Label a one-time field observation as not reproduced, and do not generalize it.
Label a hypothesis as untested, and do not state it as a fact or observation.
See the [evidence policy](en/evidence-policy.md) for tier definitions and frontmatter requirements.

Separate sample runs from production estimates and named test environments from general service limits.
Do not present design considerations as legal, compliance, or regulatory judgments.
Separate AI assistive signals from decisions made by people.

## Design views and operational observations

Visually separate design views and operational observations from documented facts, such as with a block quote.
Include assumptions, supporting evidence, and conditions where the view does not apply in the same note.
A design view alone does not change the frontmatter `evidence` tier.

Use topic-based labels such as `Security note`, `Cost note`, or `Operational observation`.
Do not use job titles, personal names, or labels that imply a review that did not occur.

## Glossary links at first use

Link the first prose occurrence of a defined technical term to the [glossary](ja/reference/glossary/README.md).
Do not link later occurrences in the same document.
This rule covers prose paragraphs and list items.
It excludes headings, tables, fenced code, inline code, URLs, block quotes, and generated language switchers.
Use the [translation terms](i18n-terms.md) for fixed wording; do not translate product names, identifiers, or commands.

## Neutral explanations

Organize options by use case and conditions, with symmetric benefits and constraints for every option.
Include selection guidance and the recommended option's own constraints in each comparison.
Do not use superiority claims, marketing adjectives, or unsupported outcome claims.

## Future note order

Notes created or migrated in later phases use the following order.
This phase does not rewrite the existing note corpus.

1. A question-form H1 as the first non-empty content after frontmatter.
2. A one-line summary.
3. Exactly two bullets under `## What you will learn`.
4. Exactly two bullets under `## What this note does not answer`.
5. One of `basic`, `intermediate`, or `advanced` under `## Prerequisite level`.
6. `## Body`.
7. A non-empty language-tagged command fence and independently non-empty content under `### Expected output` within `## Verify it in your environment`.
8. Exactly one link under `## Read next`.

Keep the summary to 15 words or fewer.
The structure report treats the headings above as fixed labels.

## Future checklist order

Operational checklists use a separate structure in the following order.

1. `## Purpose`.
2. `## Applicability`.
3. `## Verification procedure`.
4. Exactly one link under `## Read next`.

## Review before contribution

See [CONTRIBUTING.md](../CONTRIBUTING.md) for automated checks, human review criteria, staged adoption, and commands.
