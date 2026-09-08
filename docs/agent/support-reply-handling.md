# Handling a vendor support reply

<!-- audit-file-allow: support-attribution -->

Read this when a claim in a published document would otherwise be sourced to what a vendor's support
desk told us. `make audit` enforces the rule as `support-attribution`.

## The other half: do not send the reader to a support desk

`support-referral` is the sibling category. A referral is the absence of knowledge, and it is usually
the visible half of an impossibility claim that was never researched — which is how it reached this
repository in the first place. Publish the mechanism; if there is no answer yet, the open question
goes in `.private/`. Procedure:
[Concluding that something is impossible](pitfalls.md#concluding-that-something-is-impossible).

## The rule

**A vendor's support reply cannot be the published basis for a claim.** AWS treats replies from AWS
Support as its confidential information under the customer agreement, and asked in a reply on a case
in 2026-09 that they not be published. NetApp, Databricks and Snowflake carry comparable terms, so
the rule is vendor-neutral.

**Paraphrasing is not a way around it.** What is confidential is the content, not the wording, so
"Support confirmed X", "サポートの回答によれば X" and "X であるとの回答を得た" are the same act.

**A reply may still change what you conclude.** What it cannot do is appear as the reason. That
distinction is the whole rule: the judgement is yours to change, the published basis is not yours to
borrow.

## What to do after a reply

One of three things, before the claim is published:

| Route | Result | Tier |
|---|---|---|
| Find the public page that says it, read it in full, cite the URL | the claim stands | `documented` |
| Run it in your own environment and record the environment and date | the claim stands | `verified` |
| Neither is available | say so in the document | `open` |

The third route is not a failure. `open` with a sentence saying what could not be established is
more useful to a reader than a confident claim they cannot check.

Reply-derived detail worth keeping goes in `.private/support-derived/`, which is gitignored. Removing
it from a published note does not mean discarding it.

## What stays publishable

Deliberately not matched by the detector, because losing these would remove the only honest way to
describe an open question:

- that a question was asked, and when
- that a feature request or a documentation request was filed
- your own observation, with environment and date
- a public documentation URL and what it says
- "サポート対象" / "サポートされません" about whether a product supports something — that is about a
  product, not about a support desk
- a support portal or login being required to reach something

## This inverted an earlier rule

Attribution to a case that happened used to be explicitly permitted here, and
`tools/audit_public_output.py` said so in a comment: recording where a fact came from is not the same
as sending the reader to a support desk. That reasoning was right about referrals — which is still a
separate category, `support-referral` — and wrong about publication. Attribution makes a published
claim rest on a source the reader cannot consult and the author is not free to quote.

The 21 occurrences it had permitted were re-grounded rather than deleted. Most needed no weakening,
because the note already carried its own evidence alongside the attribution; the attribution was
corroboration that could simply go. Where a claim only ever rested on a reply, it became `open`.

## Detector

```bash
make audit                     # the repository
python3 tools/audit_public_output.py --path <dir>
```

Tests: `scripts/tests/test_support_attribution_rule.py`. The permitted direction is checked with the
same weight as the blocked one, because a rule that flags ordinary prose gets switched off wholesale.

Two shapes the pattern does not catch, and which a reviewer still has to: an internal detail no
customer could observe stated as fact ("there is no branch in that code path"), and a vendor's
expectation reported as "想定されています". Both are reply content wearing different clothes.
