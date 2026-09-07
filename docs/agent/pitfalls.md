# Common pitfalls

> Extracted from `AGENTS.md` so it is not loaded on every turn. Read this when a gate fails and the cause is not obvious, or before finalizing a change.
>
> `AGENTS.md` remains authoritative on any disagreement.

| Pitfall | Solution |
|---|---|
| `evidence: verified` without `verified_on` | `make lint` fails. Either add the date or downgrade the tier |
| A measured number with no environment stated | Always state ONTAP version, region, and configuration next to the number |
| Tier 1 doc updated in Japanese only | `make i18n-check` fails. Update every language the manifest names, in the same commit |
| Adjusting `../` counts while translating a file | The counterpart belongs at the same depth under `docs/<lang>/`. Only the language segment may differ |
| Hand-editing a switcher line, or adding a language to it manually | `make switcher-check` fails. Run `sync_lang_switcher.py --write` |
| A link that resolves but sends the reader into another language | `make links` cannot see this. `make switcher-check` can, and it runs that check unconditionally |
| Translating a note and then updating only the Japanese version later | `make i18n-check` compares every file that exists in both languages, not only Tier 1 and 2. A translation that exists has to keep up |
| Creating `docs/en/reference/` for one file | `reference/` is bilingual single files today. Follow that style or split the whole tree deliberately |
| Bare `FSx` or `FSxN` slipping into prose | `make audit` fails. Only "Amazon FSx for NetApp ONTAP" / "FSx for ONTAP" <!-- allow:naming --> |
| Suggesting BlueXP / Workload Factory / NetApp Console | Reframe to CloudWatch / ONTAP REST API / FabricPool / DataSync / Snapshot-FlexClone-SnapMirror <!-- allow:naming --> |
| **Enabling any immutability feature without an explicit instruction naming the retention value** | Stop and ask. See [Immutability (WORM) features](../../AGENTS.md#immutability-worm-features-never-enable-one-on-your-own-judgement). A 128 MiB SnapLock audit log volume locked a whole file system for six months |
| Reading the "how to enable" page but not the "how to delete" page | Reversibility is documented on the teardown page. Read the exit before the entry |
| Assuming "use the minimum retention" is protection | Find the parameter that actually binds. A volume `RetentionPeriod` of `0 YEARS` did not prevent a six-month lock set by a *different* parameter the AWS API cannot even express |
| Treating verification as a reason to skip the irreversibility gate | Use a disposable file system or account. The incident that created this rule was verification work |
| Vendor-versus phrasing in a comparison | State trade-offs symmetrically and add a "how to choose" section |
| Invented `**X Engineer lens**` callout | Relabel to a neutral topic note (`**Security note**`) |
| Case study with a recognizable configuration | Abstract to industry + scale band; drop anything identifying |
| Personal path `/Users/<name>/` in an example | Use `${PROJECT_DIR}` or a relative path |
| Dark diagram not regenerated after a light edit | Regenerate; the light/dark pair must stay in sync |
| Reading a `@2x` PNG directly | Exceeds the 2000px limit. Downscale to a preview first |
| Working past a `ruff` version mismatch | `make python` now fails instead of warning. Install the pinned version; if it still fires, a second binary is earlier on `PATH` (`which -a ruff`) |
| Citing another repo's finding without a link | Always link the source repository and doc |
| **Telling a reader to contact AWS or NetApp Support** | `make audit` fails (`support-referral`). Publish the mechanism instead; if there is genuinely no answer yet, the open question belongs in `.private/` |
| Writing "this cannot be done" from your own observations alone | Search first. See [Concluding that something is impossible](#concluding-that-something-is-impossible) |

## Silencing the audit

`make audit` has two escape hatches. Both are claims, not conveniences.

| Form | Scope | When it is honest |
|---|---|---|
| an HTML comment containing `allow:<category>` | the line it appears on | The match is a false positive — a proper noun, or a verbatim external title that contains a forbidden form |
| an HTML comment containing `audit-file-allow` plus a comma-separated category list | the whole file | The document *defines* the rules and therefore has to quote the patterns it forbids. `AGENTS.md` and `CONTRIBUTING.md` are the only files that qualify |

Both markers are matched anywhere on a line, HTML comment or not — so writing either token in
prose creates a real exemption. That is why the file-level one is spelled out in words here
instead of shown literally: quoting it would silence this file. Valid categories are `naming`,
`neutrality`, `pii`, `role-label`, and `all`.

Prefer the per-line form. A file-level allowance also exempts every mistake added to that
file later, which is how an exemption granted for one good reason turns into an unmonitored
file. Inside a table, the comment goes **within** the last cell — placing it after the
closing pipe adds a column and fails `markdownlint`.

## Concluding that something is impossible

**A statement that something cannot be done is a claim about the documentation, not an observation.**
Observations produce "this returned an error"; only a search produces "there is no documented way".

This has been got wrong here. A FlexClone relationship was blocking a volume deletion. Six things were
tried, all of which failed, including ONTAP's own `volume delete` at diagnostic privilege — and the
conclusion published was that the record could not be cleared and the remedy was to involve the
vendor. **The mechanism is ONTAP's volume recovery queue**: `volume delete` parks a volume there for
at least 12 hours, the clone relationship survives, and `volume recovery-queue purge` clears it in one
command. It is documented, and a NetApp KB names it for exactly this symptom. None of that was
searched for; the conclusion came from the failures alone.

**The observations were all correct.** What was wrong was treating "everything I tried failed" as
equivalent to "there is nothing that works". Six failures are evidence about six commands.

Before writing an impossibility into a document, or reporting one:

| # | Step |
|---|---|
| 1 | Search the vendor's documentation and KB for the **symptom text**, not the operation you were attempting. ONTAP's own error message named the wrong remedy here, so the working phrase was the error's *subject*, not its instruction |
| 2 | Search for the artefact you actually observed. A volume renamed to `<name>_<number>` and hidden from `volume show` is a documented behaviour with a name; the number was a data set ID |
| 3 | Check sibling repositories and `.private/` for the same symptom |
| 4 | Only then write it, and write **what was searched and when**, so the next reader can tell a documented negative from an unfinished search |

**The two halves of this failure travel together.** The support referral is what `make audit` can see;
the unresearched claim is not mechanically detectable without flagging every legitimate "cannot be
changed after creation" in the tree. So the gate catches the symptom and this section carries the
cause — if the gate fires, the claim beside it is the thing to re-examine.

## Two checks wanting opposite things from the same fenced block

`make audit` blanks fenced blocks before looking for a forbidden name or label; `check_cross_repo.py`
does **not** blank them when scanning for stale repository names. That is deliberate, and it means the
two cannot share a helper.

| Check | Fences | Why |
|---|---|---|
| Naming, neutrality, role labels | **blanked** | A fenced block showing a forbidden form is usually quoting the rule. Flagging it produces an allow marker, not a fix |
| Stale repository name | **scanned** | A `git clone` URL inside a fence is the one a reader executes, so it is where an old name does the most damage |

**Do not "fix" this by unifying them.** A sibling repository reached the same split independently while
porting the check, and documented it for the same reason: the next person to read either file assumes
the other behaves the same way.

## A gate that passed because it looked at nothing

Three shapes of this have occurred here, and in each the verdict logic was correct while the input set
was empty or narrower than the claim:

- `make security` returned "up to date" without running `bandit` once, because the target was not in
  `.PHONY`;
- the rename check reported clean on two of the seven names it was written for, because a case-only
  rename does not redirect;
- the role-label check reported clean on a section heading, because the pattern only matched callouts.

**A passing gate is evidence only about what it read.** When adding one, run its own break case first
and confirm it fails — `--selftest` where the tool has one — before trusting a clean run. And when a
detector is found to miss one member of a family, check the rest of the family rather than patching the
single case: the word list and the *form* are separate holes, and widening one leaves the other.

## A break test that cannot tell a correct fix from a lazy one

Proving a detector fires on a bad input shows it **can** fail. It does not show it can tell a correct
fix from the shortest one, and those are different properties.

The boundary tests for the audit were both positive — the Japanese-adjacent form and the spaced ASCII
form. **A version with the boundaries deleted outright passed both**, because removing a boundary only
ever widens a match. And "delete the boundary" is exactly the fix someone reaches for when the
Japanese case fails.

`scripts/tests/test_mutation_discrimination.py` applies each plausible wrong fix to a throwaway copy
and requires two things:

- **the discriminating test fails** — otherwise it does not discriminate;
- **the tests that were already green stay green** — otherwise the mutation is just broken, and says
  nothing about which test is doing the work.

Three rules when adding one:

1. **Mutate toward a plausible wrong fix**, not an arbitrary corruption. Nobody empties a regex by
   accident; people do delete a boundary to make a failing case pass.
2. **Keep the control on the same copy.** Without a clean run first, "the mutation was detected" and
   "the copy is broken" are the same observation. The first version of this harness copied only two
   directories and the control caught it immediately.
3. **A mutation whose target string no longer exists fails loudly.** Otherwise a refactor silently
   turns it into a test of nothing, which is the failure mode the harness exists to prevent.

**Nothing is mutated inside the repository.** The tree is copied out and `GIT_*` is scrubbed — a
harness whose job is to corrupt source must not be able to reach the real one, and this repository has
already had a test write to its real index through an inherited `GIT_DIR`.

## "Not a citation" is not "checked somewhere else"

The citation pattern carried a comment saying tree links were out of scope because `check_links.py`
resolved them. **It does not.** That check skips every `http(s)` URL unless `--external` is passed, and
`--external` was wired into no workflow. **Twenty-one tree links into one sibling repository were
verified by nothing at all**, and the comment is what made that look deliberate.

The category that decides where a link check belongs is **what a failure means**, not where the URL
points:

| Link | A failure means | Where it belongs |
|---|---|---|
| into this repository | a path we moved | **offline, per commit** — resolved against the working tree |
| into another repository in this account | a path we moved, in a repo we own | **network, scheduled, blocking** |
| a vendor or third-party page | possibly nothing we can fix | network, scheduled, **non-blocking** |

The third row is the reason external checks are opt-in, and **that reason does not transfer to the
first two.** A 404 we caused is not transient.

**A comment asserting that another check covers something is a claim, and it decays.** When writing
one, name the check and the condition under which it runs — `check_links.py --external`, which runs
weekly and never on a pull request — because "handled elsewhere" reads as coverage long after it stops
being true.

### Where the enforcing code sits decides whether a prohibition is enforceable

**Writing a prohibition in the source is not sufficient.** It also has to be reachable by a test. A
rule buried in `main()` can only be checked by asserting that the source *contains* certain strings —
which cannot tell a behaviour from its spelling, and which a mutation kills trivially without saying
anything about either.

That was the state of `pr-verify`'s stale-head guard: the decision lived inside `main`, and its tests
grepped for `if local and local != head:` and `return 1`. Renaming a local variable would have failed
them; changing the behaviour while keeping the text would have passed. **Extracting
`head_verdict()` as a pure function replaced four source assertions with a five-row truth table and
made two mutations possible.**

So the axis is two-dimensional:

| Prohibition written in | Enforcing code reachable by a test | Mutatable |
|---|---|---|
| source comment | yes — a pure function | **yes** |
| source comment | no — inside `main()`, or needs the network | **no; extract the function** |
| a document under `docs/` | either | **no** |

**The fix for the middle row is extracting a function, not moving the comment.** Named by a sibling
repository, which found the same shape in a rule keeping a baseline list shrink-only — enforced inside
`main()`, verified once by hand.

### Finding mutations: read the comments that forbid something

**A comment saying "do not do X" is a mutation candidate.** Apply X. If the suite kills it, the comment
is enforced. **If it survives, the comment was a claim nobody checks** — which is the same failure as
a detector that reports on a narrower tree than it names.

The technique came from a sibling repository, which turned two prohibitions in its own heading checker
into mutations and had both killed. Here, `tools/audit_public_output.py` says *"Do not replace them with
`\b`"* about the ASCII boundaries — now a mutation, and it restores the original defect exactly.

Two properties a mutation must have, both learned by getting them wrong:

- **Exactly one occurrence of the target string.** The replacement is bounded to the first, so a second
  copy leaves half the detector intact — and **that is quieter than survival**: the test still fails,
  the mutation reads as killed, and one site is unguarded. Zero was already caught; two was not.
- **A plausible wrong fix, not an arbitrary corruption.** Arbitrary damage is killed by every case, so
  it says nothing about the specific guard.
