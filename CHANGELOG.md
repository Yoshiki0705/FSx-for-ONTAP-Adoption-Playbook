# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Added

- **A `workshop-studio/` area, holding what a published workshop does not tell you.** The first
  scenario covers running the public FSx for ONTAP S3 access point workshop as a 90-minute community
  session. It deliberately does not restate the workshop's instructions — those are one click away —
  so the content is measured durations, module selection, and the dependencies between modules.
  - **The headline measurement contradicts the workshop's own figure.** Generating the 1,952 EDA log
    files is stated as "about 90 seconds" inside a 10-minute module; measured it is **2.50 seconds**.
    Across every module selected for the 90-minute cut, total machine time is about **35 seconds** —
    so the schedule is governed by narration and GUI waits, not by compute. Access point creation
    reaches `AVAILABLE` in 14.27 s, all 1,952 keys list in 1.53 s, and each of the five Athena
    queries returns in 2–3 s.
  - **One hard constraint survives**: the Amazon Quick knowledge base sync, stated at 5–10 minutes.
    The timetable therefore starts it early and overlaps it with the Athena module, which is the only
    elastic block — 5 queries at ~3 s each compress or expand freely.
  - **A dependency the workshop's own module list hides.** The summary CSV is produced in the
    QuickSight Dashboards module's Step 1, but the Athena and Glue modules both read it. Dropping the
    dashboards module wholesale — the obvious cut for time — leaves the Athena queries returning zero
    rows.
  - **Three failure modes whose error messages point away from the cause**, recorded because a
    facilitator loses minutes to each: a Glue crawler blocked by **Lake Formation** with a message
    that never mentions the access point; `us-east-1` hardcoded into policy ARNs across seven modules,
    surfacing in another Region as access denied rather than as a Region mismatch; and IAM propagation
    making the first crawler-creation attempt fail on correct input.
  - **The Lake Formation workaround is recorded as unverified, not as a fix.** Granting the crawler
    role the missing permission requires Lake Formation administrator rights, which the test
    environment did not have, so the grant was refused with `Invalid principal`. What is established
    is the asymmetry that drives the curation decision: Athena succeeds without the crawler, because
    the table can be created by the participant's own principal.
  - **The Amazon Quick module was then measured too, and it is the one that governs the schedule.**
    The knowledge base sync took **11.5–14.1 minutes** against a stated "3–5 minutes" (and a
    "5–10 minutes" claim elsewhere), so the timetable now starts the sync at the 40-minute mark and
    leaves **25 minutes** before the module that depends on it. Once synced, a natural-language
    question answered in **under 54 seconds**.
  - **`Status: ACTIVE` from the API is not readiness.** `list-knowledge-bases` reported `ACTIVE`
    after 16.4 s while the console still showed `Syncing / In progress` for another eleven minutes.
    This is the same shape as `HeadBucket` succeeding on an access point whose data operations fail:
    the API that reports success and the state you can actually use are different things.
  - **The answer was verified against ground truth, not just observed.** Quick's per-feature
    breakdown of license failures matched the summary CSV exactly (17 total; 6/5/4/1/1), and it cited
    individual log files. Recorded alongside it: the same data supports two defensible counts of
    "license failures" — 17 rows carry a `license_feature`, but only 10 have `failure_type` set to
    `License Failure` — so the question has to say which one it means.
  - **A setting the workshop never mentions is mandatory**: Quick's account-level *Quick access to
    AWS services → Amazon S3*. Without it the knowledge base fails with "You do not have permissions
    to access the S3 bucket" no matter how the IAM and access point policies are written. A
    brand-new plain bucket failed identically, which is the cheapest way to prove the cause is not
    access-point-specific. Two further wrinkles: the bucket picker **does not list access point
    aliases** (add them through *Use a different bucket*), and a prefix is rejected on the connection
    step but accepted at the knowledge base's *Add specific content* step.
  - **`put-access-point-policy` replaces the whole document**, so the workshop's copy-paste command
    silently drops existing statements — the workshop does this to itself, module 08 overwriting
    module 07. Worse, **a policy naming a deleted role cannot be written back at all**: the principal
    is returned as a bare `AROA...` unique ID, which `put` rejects as `Invalid principal`. Such a
    policy is readable but not re-submittable, so merging is impossible until the dead statement is
    dropped. Generalized rule recorded: delete resource policies that name a role *before* deleting
    the role.
  - The dashboards and automations modules remain **listed as unmeasured rather than estimated**.
    `aws quicksight create-knowledge-base` does exist, so the sync can be moved out of the event
    window entirely — which, at 11.5+ minutes, is the recommendation.
  - **AgentCore Gateway is costed rather than measured**, and the estimate is labelled as such:
    35–45 minutes if attendees build it, 15–20 if the gateway is pre-built and only the Quick
    integration is done live, 8–10 for a facilitator demo. The 254-line CloudFormation template
    pasted by hand is the dominant risk, not the 5.5–7.5 minutes of unavoidable service waits.
    Fitting the 15–20 minute variant requires pre-syncing the knowledge base, which frees the Athena
    block — a trade that costs the "same data, also readable by SQL" message and the answer-checking
    demonstration.

### Changed

- **Every number was removed from the coverage statement.** The note and checklist counts had been
  rewritten twice in a single session, and the "some answers are still unwritten" qualifier became an
  understatement the moment the last question was answered. The statement now carries only the module
  completeness fact — which cannot rot, because the twelve modules are a fixed set and all are filled —
  and points readers at the `_未追加_` marker in each module README, so **coverage is reported next to the
  gap instead of in a summary that has to be maintained.**
  - The enumerated note list in the six first-touch hubs was replaced with a pointer to the module
    navigation for the same reason: adding a note meant editing nine files. Those titles were deliberately
    untranslated Japanese anyway, so a pointer carries the same information at a third of the edit surface.
    The `ja` and `en` hubs keep the full list with per-note descriptions, since both are fully maintained.
- **Coverage is now stated at module level only.** With all twelve modules filled, the eight hub READMEs
  and `llms.txt` say "all 12 modules have content (11 `notes/`, 1 `checklists/`)" and then note that
  answers are still missing at the question level — **without giving a number for it.** A count of
  answered questions would live in nine files across eight languages and would need editing on every
  note added, which is how the previous claim went stale. The module count is stable now that it is
  complete; the question-level gap is signposted in each module README instead, next to the gap itself.
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

- **The inode arithmetic in the assess note was measured and did not reproduce.** The note published a
  break-even average file size table derived from the documented statement that volumes of 648 GiB or
  more all default to 21,251,126 inodes. Reading `FilesCapacity` on a live file system showed inode
  capacity **scaling linearly with volume size instead**: 100 GiB → 3,112,959, 1 TiB → 31,876,709,
  2 TiB → 63,753,417, and a FlexGroup at the same ratio. The 2 TiB to 1 TiB ratio is **exactly 2.0**, and
  both are above 648 GiB, so the cap did not apply in this environment.
  - All four values match `size × 0.95 ÷ 32 KiB` to within 1–24 inodes, consistent with the documented
    default ratio being applied to post-reserve capacity at every size rather than capping.
  - The published table implied ~505 KiB at 10 TiB and ~2.5 MiB at 50 TiB as the point where inodes run
    out first. **Those figures are removed**, since a linear default puts the break-even near 32 KiB at
    any size — a materially different design conclusion.
  - The note's thesis is unaffected and is now stated as the actionable form: inodes are finite and
    exhausting them stops writes with capacity to spare, so **read `FilesCapacity` rather than assuming a
    number.** Both the documented and the measured value are recorded side by side in
    [limits](docs/ja/reference/limits/), which is what that page's own recording rule requires.
  - This is the repository's own argument landing on itself: the arithmetic was correct, its premise was
    documented, and it still did not survive a measurement.

- **All eight hub READMEs claimed `notes/` was not yet populated.** That stopped being true once the
  first notes landed, and it was the most misleading sentence in the repository: it sat on the landing
  page and told first-time readers there was nothing to read. The statement is now a count — 8 of 12
  modules have content — and it names the four modules that are still question-definition only, so the
  claim degrades into being merely out of date rather than actively wrong.
  - Each hub now carries an **"available today" list**, so a reader reaches the material without first
    having to learn the two-axis navigation. In the six first-touch languages the note titles are
    deliberately **left in Japanese**: a title here states a finding, and findings stay out of
    machine-assisted translation. The heading and lead-in are localized, because those are navigation.
  - Reverse links added where a document already pointed at the topic: the pre-production checklist now
    links to the restore drill and the monitoring note, the migration decision tree links to the
    inventory note, and the ACL note links back to the inventory item covering ACL readability.
- **The pre-production checklist cited an AWS Prescriptive Guidance URL that returns 404.** The page
  appears to have been moved or retired since it was indexed. The affected claim — tier latency
  levels — is now sourced to the AWS Storage Blog sizing article, which states it directly. Re-sourcing
  also surfaced a more actionable fact that has been added: tiering behaviour changes by utilization
  band, and stops entirely at 98% SSD, not merely degrading past the 80% recommendation.
- `tools/check_links.py --external` reported false failures for hosts that redirect a `HEAD` to a
  landing or sign-in page returning 404 while `GET` answers 200. A failure is now confirmed with
  `GET` before being reported. Reporting working links as broken trains people to ignore the check.
