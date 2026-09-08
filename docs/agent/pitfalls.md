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

### A guard tested from inside the repository can be inert where it runs

The workflow-observability hook shipped **inert**. `git diff` ran with the inherited working
directory, a hook process does not start inside the repository, git failed there, and **the empty
result read as "no unobserved workflow was touched"** — a silent pass on every merge.

It was tested from inside the repository, where it worked. **That is the same mistake a sibling
reported after reading a local pass as evidence about a hosted runner**, arriving one layer down:
not a different machine, a different working directory.

So a guard that runs outside the repository takes its paths from `__file__`, and **is exercised from
a directory that is not a repository at all.**

**The first test of it did not discriminate either.** It compared the list from outside against the
list from inside, and on a branch touching no workflow both are empty — **a test that depends on the
branch's own diff proves nothing on most branches.** The assertion is now on the `cwd` git is given,
because the directory git runs in *is* the bug. Verified by removing the fix and watching it fail.

### A workflow no pull request runs is merged unobserved

`schedule` and `workflow_dispatch` are not observable triggers. **A change to such a workflow can be
merged with every check green and none of them about it** — the ticks are true and concern other
workflows. `cross-repo-external.yml` is in that position here, and the symptom was recorded in an
issue before the cause was: two stale entries survived while the scheduled run was working, because
nobody was reading its result.

A sibling measured the cost — merged behind **31 passing checks, none of which were that workflow**,
first dispatch failed, and diagnosing it took a second merge.

`scripts/check_workflow_observability.py` asks before `gh pr merge` when the branch touches one.
**`ask`, never `block`:** dispatching needs the branch pushed first, so a person drives push →
dispatch → read → merge, and a comment-only edit or a workflow waiting on a missing secret is a
legitimate exception.

**That argument got demonstrated rather than reasoned.** The first hook resolved the script through
`git rev-parse` in the hook process's working directory, which is not the repository, so it **failed
on every shell command and blocked unrelated work.** It was removed within a minute. A guard that
stops ordinary work does not survive to guard anything.

Two bugs the sibling hit are worth carrying even though neither reproduced here:

- **`\s{0,4}` for indentation.** `\s` matches a newline, the line anchor stops meaning anything, and
  every trigger after the first is lost — **two pull-request workflows were misclassified while the
  selftest stayed green**, because it covered the verdict and not the parse. Use `[ \t]{0,4}`.
- **A pinned count drifting from the scan.** A number counted over `*.yml` while scanning `*.y*ml`
  left two files outside the number and inside the scan. **Assert a property instead** — "nothing is
  called observed without an observing trigger" cannot drift.

The first did not reproduce here, because triggers are extracted and then intersected with a known
set, so over-consumption is filtered rather than fatal. **A mutation removing the `^` anchor from the
`on:` extractor did survive**, and a case with the word appearing mid-line was added to kill it.

### Hunting quiet failures will not find the loud ones

**"Look for the bug that leaves the run looking normal" is a good rule with a blind spot: the bug
that is wrong out loud.** A sibling repository hit it directly. Checking whether an exemption marker
was *inactive* tests for "the report is unchanged with and without it" — which finds markers that
suppress nothing, and **misses a marker that makes the checker report a problem that does not exist.**
The correct predicate is asymmetric: **a suppression is justified only if ignoring it *increases* the
report.**

Both wrong shapes exist, and only one is quiet:

| Shape | Report | Found by "unchanged"? |
|---|---|---|
| suppresses nothing | unchanged | yes |
| **invents a finding** | **changed** | **no — it looks justified** |

So when a rule is written to catch silence, ask what its loud counterpart would be. Here the loud
counterpart was in the budget itself: **prose mentioning a marker was counted as a marker**, so
writing about one could fail `make allow-budget` with nothing wrong.

### Two checks answering the same question differently is a fifth axis

`shrink-only` asks whether a suppression is justified. The axis before it asks whether the thing is a
suppression at all. **The axis before *that* asks whether every check answers that identically.**

The judgement "is this a marker" was written in three places here, and a fourth removed markers from
the raw line while the others detected them in the code-span-stripped one. **A width that differs by
one step produces a line that fails whether the marker stays or goes** — remove it and the audit
reports the violation, keep it and the budget reports an inert marker. **Each check is correct alone;
only the pair is a contradiction, and no single-check test can see it.**

Named by a sibling repository, which reported both halves of the fix:

- **Extract the judgement, do not align the copies.** Two copies get touched one at a time.
- **Pin the relationship, not the examples.** Its individual cases all passed for the entire period the
  contradiction existed, so the selftest asserts that "inert" and "load-bearing" never both hold, over
  the whole corpus.

Its asymmetry had a plausible reason too — *the inert check should read the original line, since that
is where the marker sits.* **Reasonable, and wrong.** The same shape as an asymmetry documented here as
deliberate one release earlier.

**The extraction cost one mutation, exactly as predicted.** The string a fenced-marker mutation targeted
moved into the new function, and the harness reported `0 matches` — **unverifiable, not killed.** That is
what requiring exactly one match buys.

### Before asking whether a suppression is justified, ask whether it is a suppression

`shrink-only` covers two ways an exemption can be wrong — it suppresses nothing, or it invents a
finding. **Both assume the thing is a suppression at all.** A sibling repository named the third
axis: the layer that decides **"is this a marker"** sits before the layer that judges whether the
marker earns its place, and it was missing on both sides.

Everything found here lived in that layer: prose mentioning a marker, a marker shown in a code span,
a marker shown inside a fence. **None of them are directives, and all three were honoured.**

### A marker must be a directive, not a mention of one

Two readings were too loose, and both were live holes:

| Written as | Was it honoured? | Should be |
|---|---|---|
| `allow:naming` bare in prose | **yes** | no |
| `` `<!-- allow:naming -->` `` in a code span | **yes** | no |
| the marker inside a fenced block | **yes** | no |

**Every line documenting these markers was therefore exempting itself**, and appending a code-span
marker to any sentence silenced the detector on it. The marker now requires the HTML comment wrapper,
and code spans are stripped before markers are extracted — while findings still match the original
line, so a forbidden term inside a code span is still reported.

**A fence and a code span are one rule in two shapes — this is code, not prose — and only the
code-span half was implemented.** The fence half was closed a day later, after a sibling reported the
identical split in its own detector, where a heading telling authors to add a marker went unreported
because the example silenced the line describing the feature. **The recorded rule was not missing; its
scope was one step too narrow** — which is a different failure from forgetting to apply it, and the
one that survives a review of "is the rule written down".

**The fixes cover different sentences and each needs its own test.** The mutation harness proved
it: a test using a backticked mention passes with the wrapper requirement removed, because the code
span was already stripped. Only a bare mention exercises the wrapper.

### Removing markers in bulk edits the documentation of the markers

Deleting 56 inert markers by script damaged three files, in two ways that `make all` does not catch:

- **`CONTRIBUTING.md`** shows the syntax inside a ` ```markdown ` fence. The rule about excluding
  fenced blocks was already recorded in this file for the heading detector, **and was not applied.**
- **`AGENTS.md`** shows it inside inline code spans, and the removal left empty backticks — **valid
  markdown, so nothing failed.**

Both were caught by reading the diff, not by a gate. **A scripted edit across 20+ files needs the
diff read for the files that describe the thing being edited.**

### An exemption list has to be shrink-only, and the surplus is the quiet half

**Adding an allow marker looks exactly like fixing the problem it silences: the audit passes either
way.** So the set is pinned in `docs/agent/allow-marker-budget.txt` and `make allow-budget` fails when
it grows. Counting per file and category rather than per line is what keeps the baseline readable —
line numbers move on almost every edit here.

**Both directions fail, and the second is the one worth explaining.** A budget recording *more* than
exists breaks nothing at the time, which is why it is dangerous: the surplus is headroom, so the
marker it once counted can come back with nothing reported. **The failure is silence, not a crash** —
the same shape a sibling repository found while keeping a known-divergence list shrink-only.

Regenerating is the deliberate act: `python3 tools/check_allow_budget.py --write`. **Before running
it after an `added` verdict, confirm the marker is the narrowest option** — a file-wide
`audit-file-allow` where one line-level `allow:` would do turns the whole document into a blind spot.

### Prose describing a gate does not follow the gate

**A gate's registration table is the gate. A list of its contents written in prose is a snapshot that
stops being true the moment the table changes** — and nothing fails when it drifts, because prose is
not executed.

It happened here. An issue proposing the division of labour with a sibling enumerated seven probe
strings in its body. Two were later replaced, and from that moment the enumeration described a gate
that no longer existed. **The sibling read the enumeration as the implementation, reported one of the
strings as broken, and the string had never been registered at all.** Nothing was broken; the body
was stale. The repair belonged to the prose, not to the gate.

So the rule when telling another repository what a gate checks: **a one-line reference to the
registration table, never a copy of its contents.** Copying reintroduces the same drift, one
generation later. And before reporting a failure, a retraction, or a gap in someone else's gate,
**read the registration rather than the description of it.**

The general form is already in this file twice, in different clothes — a check whose tool is absent
is indistinguishable from one that passed, and a prohibition is enforceable only where the enforcing
code can be reached. **This is the documentation-facing member of the same family: the description of
a control is not the control.**

### "The server did not answer" is a third verdict, and both ways of collapsing it are wrong

A probe has three outcomes, not two. Collapsing the third into either neighbour fails, in opposite
directions:

| Collapsed into | What breaks |
|---|---|
| broken | The run fails over someone else's outage. **A check that is wrong when nothing is wrong stops being read** |
| fine | **A permanently unreachable URL looks verified.** Silent, and the worse direction |

The second one is not hypothetical. A sibling repository measured github.com's HTML endpoint
returning **504 persistently** for particular repositories on a hosted runner while the REST API
answered immediately — so a rule of "5xx means fine" would have retired those checks permanently
without a word. It had also read a local pass as evidence about the runner, where the failure was
reproducible and the local behaviour was not.

Both checks here now report `?` separately: `check_links.py` marks the verdict with `UNDETERMINED`
and does not fail, and `check_cross_repo.py --external` fails only on 404, which means the cited file
moved. **The residual limit is stated rather than fixed:** a citation undetermined every week looks
the same as one that passes. Reporting it every run is the whole mitigation; consecutive-run state
would need storage this repository does not have.

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
