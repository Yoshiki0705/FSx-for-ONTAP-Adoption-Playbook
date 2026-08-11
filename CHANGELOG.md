# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Added

- **The first two checklists outside the build phase**, both derived from notes that already exist so
  that no new factual claim was introduced. Sources were re-pulled on 2026-08-11 and each checklist
  states that date, because commands and limits move.
  - **[Cutover-day checklist](docs/ja/playbooks/03-migrate/checklists/cutover.md)** is ordered by
    position relative to the outage rather than by topic, since **downtime is only the interval
    between stopping clients and resuming them** — the transfer completes before it. Everything that
    can be done with clients still running is kept in a separate section, so moving an item into the
    outage window is visible as a mistake. It names the four SnapMirror actions that force a fresh
    baseline sync, and states plainly that no operation reverts a cutover: rollback is a decision
    about data already written to the destination.
  - **[Inventory checklist](docs/ja/playbooks/01-assess/checklists/inventory.md)** annotates every
    item with the later irreversible decision it feeds, and excludes anything for which that use
    cannot be written. Two items are called out as the ones most often missed — the largest file size
    (above 50 GiB an S3 access point cannot be the write path) and the count of sharing forms that
    have no ACL counterpart.
- **`make i18n-check` now compares any document that exists in both Japanese and English**, not only
  Tier 1 and Tier 2. Tier 3 English stays optional — a file enters the check only by being
  translated, so the gate cannot block a Japanese-only note. What it can do is stop an existing
  translation from drifting, **which it caught on its first run**: the English copy of "Having
  snapshots is not the same as being able to recover" was missing two subsections, and they were the
  two that matter most — that 1,023 is the ceiling only when there is space for the metadata, and
  that locking snapshots disables the keep-count so an hourly schedule can reach 1,023 undeletable
  snapshots. Both are now translated.
  - The gate was verified in both directions before being trusted: it reports 20 groups in parity,
    and appending one heading to an English file makes it fail with the file and the marker count.
- **Glossary coverage for terms the notes already use**: HA pair, FlexVol, FlexGroup, constituent and
  inode under storage structure; XDP, common snapshot and Compliance Clock under data protection; and
  two new sections for identity (Active Directory, SID, LDAP, Kerberos, DACL/SACL) and for
  performance and billing units (throughput capacity, baseline versus burst, SSD tier, capacity pool
  tier, tiering policy). Every entry carries an inline link to the AWS or NetApp page it came from.

- **A migrate-phase note for SaaS and cloud storage sources, carrying only the planning half.** The
  transfer mechanisms — DataSync location types, each SaaS admin API, the S3 access point size
  limits — stay in the sibling repository's document and are linked rather than restated, so what is
  here is what to establish, what to measure, and where to stop.
  - **Three checks classify the source before any method evaluation**: whether it exposes an
    S3-compatible API, whether it is self-hosted open source, and — the one most often skipped —
    whether the object storage is primary storage or an external mount. In a primary-storage
    configuration the bucket holds only identifier-keyed bodies, so **copying it succeeds and still
    cannot be restored**; the failure surfaces later as users unable to open their own files.
  - **Tenant admin authorization is an organizational question, not a technical one.** The five main
    collaboration SaaS products offer tenant-wide admin authorization, so per-user OAuth consent is
    not required and the migration can be run centrally. What has to be established is whether the
    organization can issue that credential for the migration window, and whether a revocation step
    exists.
  - **Two Assess numbers are added because discovering them late rebuilds the plan**: largest file
    size, since above 50 GiB the file cannot be written through an S3 access point, and the count of
    external shares, which sizes the un-mappable part of the permission model.
  - **Go/No-Go is stated as three stop conditions**, deliberately without numeric thresholds: many
    sharing forms with no ACL counterpart (the work is a redesign, not a migration), rate limits not
    yet measured (**do not fix a downtime figure**), and an undecided system of record.
  - **Whether migration is the requirement at all is checked first.** Bedrock Knowledge Bases managed
    connectors provide cross-source search without moving bytes; the constraint is stated
    symmetrically — content still leaves for embedding generation, so "not migrating" does not mean
    the data stays put.
  - Six items the primary source marks unconfirmed are carried over as unconfirmed, including that
    the DataSync location and Bedrock connector coverage are a 2026-08 snapshot.
  - Linked from the 03-migrate and 01-assess module READMEs in both languages, and from the migration
    method decision tree, which covers only ONTAP and on-premises NAS sources.
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

- **Snapshot locking (Tamperproof Snapshot) is documented as a second instance of the same lock-in class**,
  not as a SnapLock footnote. It matters because **it applies to volumes that are not SnapLock volumes at
  all** (ONTAP 9.12.1+), so "we do not use SnapLock" is not protection. ONTAP's own enable-time warning
  states the shape: locking cannot be disabled until every locked snapshot expires, and a volume with
  unexpired locked snapshots cannot be deleted — which is one of the five conditions in the `525057`
  refusal already recorded here.
  - **The compound trap is the new finding.** Retention overrides the snapshot keep count, so locked
    snapshots accumulate past a policy's count. Combined with the **measured** ceiling of 1,023 snapshots
    per volume, an hourly schedule with a long retention can arrive at 1,023 *undeletable* snapshots, at
    which point new snapshot creation stops and waiting out the retention is the only recovery. The
    checklist now asks for retention × frequency < 1,023 to be calculated before enabling.
  - **The failure mode inverts relative to the audit log volume.** There the six-month floor itself was
    unacceptable, so the fault was "could not choose". Here retention is settable down to hours, so the
    fault would be **"could have chosen and did not"**.
  - **No AWS API parameter exists** — `CreateOntapVolumeConfiguration` has no field for it, so it is
    reachable only through ONTAP. That also means **no AWS-side guardrail**: no IAM condition key, no
    console warning. Any credential that reaches ONTAP can create the lock, which is now a checklist item
    about who holds `fsxadmin`.
  - **The FabricPool interaction is recorded as unresolved rather than answered.** ONTAP documentation lists
    FabricPool under unsupported features; a NetApp KB treats FSx for ONTAP as an exception because its object store
    is managed and inaccessible. Capacity-pool tiering *is* FabricPool, so this is not academic — but it
    stays `documented` with the tension stated, because verifying it would mean creating the lock. AWS
    Support has been asked for the FSx for ONTAP position.
  - The guard covers these operations now, and **proved itself the moment it was wired up**: it blocked an
    attempt to run its own verification command, because that command contained `-snapshot-locking-enabled`
    as a literal string. The correct response was the built-in `--selftest` (26 cases, both directions), not
    rewording the sample to slip past the pattern — so the cases live inside the script.

- **A rule, a mechanism, and a note covering irreversible operations**, written because this repository
  broke the rule it already documented. During the verification recorded below, a SnapLock audit log
  volume was created without asking which retention period to use, and the governing warning was read
  only after the operation would not reverse. One 128 MiB volume made the volume, its SVM, and **the whole
  file system** undeletable for six months. Privileged delete had already been set to
  `PERMANENTLY_DISABLED`, closing the last route out. **The feature behaved exactly as specified** — the
  failure was in the approval step, and the verification itself produced no usable finding.
  - New note: [approval for an irreversible operation is separate from approval for the task](docs/ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md).
    It states the gate — never infer a retention value, name the widest scope and its cost, say whether
    any documented early exit exists, and **read the delete page before the enable page**, because
    reversibility is a property of the exit and is documented separately from the entry.
  - The scope is deliberately wider than SnapLock. The same shape appears in S3 Object Lock, S3 Glacier
    Vault Lock, AWS Backup Vault Lock, and EBS snapshot lock: **a feature whose purpose is to remove the
    ability to delete cannot be enabled on an implementer's own judgement**, because working correctly it
    is indistinguishable from an outage you caused.
  - New mechanism: `scripts/guard_irreversible_ops.py`, stdlib-only and project-agnostic, blocks matching
    mutating commands while leaving read-only inspection alone — an implementer who cannot read the current
    state will guess instead. It blocks rather than prompts, on the reasoning that a prompt gets approved
    in the flow of work whereas a block forces the reasoning into the conversation. Over-blocking is
    treated as a defect for the same reason: a guard that fires on reads gets switched off, and one such
    case (`get-object-lock-configuration` matching a `lock-` verb) was found and fixed during testing.
  - `AGENTS.md` carries the rule so it travels with the repository, and the pre-production checklist now
    lists the audit log volume and the permanently-disabled state among the irreversible items — the
    checklist previously named SnapLock enablement but not either of these.
  - **Deciding not to use privileged delete removes the exposure entirely**, since the audit log volume is
    only required in order to use it. That is now the first thing the checklist asks.

- **Verified against a live file system through the ONTAP REST API**, which reaches behaviour the AWS API
  does not expose. Recorded in [limits](docs/ja/reference/limits/) with the environment and the access path.
  - **A SnapLock audit log volume locks the volume, its SVM, and the whole file system from deletion for at
    least six months — Enterprise mode included.** This is the most consequential constraint recorded so
    far, and it corrects an earlier implication in this repository: the previous text said releasing the
    designation "requires an ONTAP-level operation", which reads as though ONTAP-level access solves it.
    **It does not.** The SVM-level designation can be released via ONTAP REST — after unmounting, which is
    itself a required first step — but the volume's own `is_audit_log` field is read-only, so the volume
    stays undeletable until retention expires. The scope beyond the volume is documented by AWS in a
    warning; the operation-by-operation results are measured here. Creating one during this verification is
    why a single verification volume remains in the environment.
  - **The 1,023 snapshot ceiling is now measured, not just cited** — and the measurement changed the advice.
    On a 100 MiB volume creation stopped at **694** with `No space left on device`; after growing the same
    volume to 8 GiB it stopped at exactly **1,023** with `Cannot exceed maximum number of snapshots.` So
    **1,023 is the ceiling given enough space**, and on a small volume the space limit binds first — with an
    error that, as with inode exhaustion, names capacity rather than the real cause. Each snapshot cost
    roughly **150 KiB even on an empty volume**, which matters when planning retention against the 5%
    default snapshot reserve.
  - **A failed volume deletion cannot be diagnosed from the AWS API.** `delete-volume` is accepted, moves to
    `DELETING`, then silently returns to `CREATED` — no error, no `AdministrativeActions` entry. The reason
    appeared only in the ONTAP REST job message. Worse, **blockers surface one at a time**: clearing the
    first revealed a second, with no way to see the full list up front.
  - **A leftover backup blocks deletion while looking like something else.** ONTAP reported a SnapMirror
    relationship, but the visible relationship list held only an unrelated entry on another SVM and the
    source-side query returned nothing. The actual cause was an `AVAILABLE` backup, identifiable by the
    `backup-<backup-id>` snapshot it leaves on the volume. Hence the practical note to delete verification
    volumes with `SkipFinalBackup=true`, or the final backup blocks the next deletion.
  - **The ONTAP version is obtainable after all**, which corrects a limitation stated throughout the earlier
    read-only work. `DescribeFileSystems` does not return `FileSystemTypeVersion`, but ONTAP REST
    `GET /api/cluster?fields=version` returns `NetApp Release 9.17.1P7D1`. Only one of the two file systems
    was queried, so the sections resting on the other still carry no version — stated per section rather
    than applied to all of them.
  - The access path is recorded because it is the part that generalizes: a **Session Manager port-forward**
    to the management endpoint needs **no additional IAM permission on the instance and puts no password
    into SSM command history**, unlike passing credentials through `send-command --parameters`.

- **Five claims verified with create, modify and delete operations** against a live file system, recorded
  in [limits](docs/ja/reference/limits/) with the environment and method. Two of the seven candidates were
  declined and two turned out not to be measurable this way; all four are listed with the reason.
  - **The strongest result is inode exhaustion.** On a 20 MiB volume: 566 inodes total, **96 already used
    on an empty volume**, 470 files created to reach 100%. At that point `df -h` still showed **19M with
    448K used (3%)**, creating a new file failed with **`No space left on device`**, and **writing to an
    existing file still succeeded.** So the error names the wrong resource, and the symptom is partial —
    creation stops while writes continue, which is a harder failure to diagnose than a total stop.
  - **DP volumes cannot be backed up** — confirmed with a control: the same `CreateBackup` call succeeded
    on an RW volume, so the rejection is not a permissions or environment artefact.
  - **The CLI tiering default is now causal, not correlational**: a volume created via AWS CLI with no
    `TieringPolicy` came back `SNAPSHOT_ONLY` / cooling `2`. The console side remains unverified and is
    labelled as such.
  - **SnapLock**: `PERMANENTLY_DISABLED` is terminal, with both `ENABLED` and `DISABLED` rejected. And the
    retention mode is fixed in a stronger sense than "cannot be changed" — **`UpdateVolume` has no
    parameter for it at all**, the same shape as deployment type.
  - Also recorded three boundaries found by trying: **`CreateSnapshot` is OpenZFS-only** so ONTAP snapshots
    are outside the AWS API; a **SnapLock audit log volume cannot be deleted through the AWS API** and can
    only be mounted at `/snaplock_audit_log`; and **`UpdateVolume` is asynchronous and records no
    `AdministrativeAction`**, so a 200 response is not confirmation. That last one produced a false
    "silently ignored" diagnosis during the work, which is recorded rather than quietly corrected.
  - Not measured, with reasons stated: 4,091 backups (impractical), the 90%/98% tiering thresholds
    (**declined** — cannot be isolated from live volumes on the same file system), and patch-time I/O pauses
    (needs a maintenance window plus sustained load). The 1,023 snapshot ceiling was listed here as needing
    ONTAP credentials; it has since been measured, above.
- **Case studies are now findable by industry and by workload**, via a new linked index of
  [published FSx for ONTAP case studies](docs/ja/case-studies/public-case-studies.md). Both axes reach the
  same material, because a matching workload is often more useful than a matching industry and a reader
  arriving with either attribute should land somewhere.
  - Industry axis: energy, semiconductor/EDA, financial services, healthcare, medical devices, telecom,
    public health and education, media, and IT — plus one account whose industry is not disclosed.
    Workload axis: NAS migration, SQL Server, EDA, SaaS tenancy, hybrid and branch caching, media
    production, and multi-Region deployment.
  - **Figures from those accounts are deliberately not restated.** Most published case studies omit the
    ONTAP version, Region, configuration and measurement method, which puts them below `documented` in
    this repository's terms — they establish that an organization published an account, not a value to
    design against. A seven-point "what to check while reading" table makes that judgement transferable
    instead of asking readers to take it on trust.
  - Industry-specific *design* material is listed separately from case studies, since an EDA best-practices
    paper is more use for a decision than an EDA success story. TR-4937 is cited **by report number rather
    than URL**, because that distribution URL moves and a number does not.
  - The directory now separates **three** kinds rather than two: public, field, and verification.
- **`case-studies/` has its first entry**, and the directory now distinguishes **two kinds**: field cases
  from technical-support work, and **verification cases from this repository's own environment.** The
  distinction exists so a reader cannot mistake whose environment is being described — both are
  single-environment observations, but only one comes from an engagement.
  - The first entry is a verification case: [a documented default did not
    reproduce](docs/ja/case-studies/documented-default-did-not-reproduce.md), written about the inode
    correction in this same release. It is the shape the template asks for and rarely gets — an account of
    **being wrong**, with the three things that did not go as expected stated plainly: the cause was the
    absence of measurement rather than weak research, **the incorrect table was the more usable one**
    (specific thresholds beat "measure it yourself" as guidance), and the observation was a *negative*
    result, which supports "not seen here" but not "does not exist".
  - **No engagement case studies were invented.** Case studies are accounts of real work; fabricating them
    would misrepresent experience rather than merely misstate a fact. The directory index stays honest
    about having one entry.
- **`reference/comparison/` now has content**, where the index previously read "none added yet". Two
  matrices, both following the directory's own authoring rules — trade-offs stated symmetrically
  including for the recommended option, a "how to choose" section, and a dated comparison point.
  - [Data protection methods](docs/ja/reference/comparison/data-protection-methods.md): snapshot, volume
    backup, AWS Backup and SnapMirror, plus the two SnapLock modes as a separate axis since **immutability
    is not a recovery method**. Frames the four as **not alternatives** — they cover different failure
    domains and are combined rather than chosen between. The constraint that decides DR designs gets its
    own section: only read-write volumes can be backed up, so backing up a SnapMirror replica is not
    available and the backup has to be taken on the source side.
  - [Tiering policies](docs/ja/reference/comparison/tiering-policies.md): `NONE`, `SNAPSHOT_ONLY`, `AUTO`,
    `ALL`, organized around the two axes that actually differ — what gets moved, and whether a read pulls
    it back. Includes the **measured defaults** and states plainly that while `AUTO` and `SNAPSHOT_ONLY`
    volumes coexisted in one file system, **which creation path produced which was not recorded, so the
    causal claim was not verified** — only the values.
- **First `verified` entries from a live environment**, in [limits](docs/ja/reference/limits/): SSD IOPS
  defaulting to 3 per GiB, `AUTO` cooling defaulting to 31 days and `SNAPSHOT_ONLY` to 2 across 32
  volumes, first-generation Single-AZ running one HA pair, the maintenance window format, and the absence
  of any deployment-type parameter on `update-file-system`. All matched the documentation.
  - Recorded with the environment and method the evidence policy requires, including two honest gaps:
    **the ONTAP version could not be captured** (`DescribeFileSystems` returned no
    `FileSystemTypeVersion`), and the measurement was **read-only observation** — nothing was created,
    modified or deleted.
  - A **"not yet measured" table** lists what stays `documented` and names the operation each would
    require, so the boundary between observed and cited is visible rather than implied. No note was
    promoted to `verified` wholesale, because no note's central thesis was reproduced end to end — only
    specific values were.
- Note: [p99 cannot be read from the CloudWatch metrics](docs/ja/domains/performance/notes/what-you-cannot-read-from-cloudwatch.md).
  The volume latency metrics expose **total time and total operation count, with `Sum` as the valid
  statistic** — so dividing them yields an average by construction and **tail latency is not derivable
  from them at all.** p99 has to be measured at the client; no amount of detail on the storage side
  produces it.
  - The reproducibility finding: **burst credits sway a benchmark.** A file system accrues credits while
    below baseline and spends them to exceed it, so the same test run with a depleted balance returns a
    different number. A benchmark that does not record `FileServerDiskThroughputBalance` and
    `FileServerDiskIopsBalance` before starting is not reproducible even when the procedure is identical.
  - Also settles two questions by stating what does **not** exist: **there is no per-protocol bandwidth
    allocation** — NFS, SMB, iSCSI and S3 access points share one HA pair's budget along with background
    tasks, and the only documented prioritization is client traffic over background work. And **cache size
    cannot be set directly**; in-memory and NVMe cache size is determined solely by throughput capacity,
    so "give it more cache" means "raise throughput capacity".
- Note: [the AD dependency lasts the lifetime, not just the join](docs/ja/domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md).
  A valid service account is required **for the lifetime of the file system**, because replacing a failed
  file system or SVM and patching ONTAP both require unjoining and rejoining the domain. So an expired
  credential is **symptomless in normal operation** and surfaces at the next maintenance window — which,
  per the maintenance note, cannot be deferred past 14 days. "AD integration is working" is a statement
  about normal operation only.
  - Two AD-side actions silently break things: **moving the computer objects FSx for ONTAP created**, and
    **deleting the directory while an SVM is joined**. Both leave the SVM misconfigured.
  - Join failure names two causes — unmet port requirements or insufficient service account permissions on
    the target OU — and **the error text does not distinguish them**, so checking both in order is the
    correct procedure rather than a thorough one.
  - For dual-protocol access, records the layer usually missed: protocol **version** is enabled separately,
    so NFS v3 can be disabled while NFS is enabled, and v3 needs six ports where v4 needs only TCP 2049.
- Note: [an S3 access point authorizes every request as one identity](docs/ja/domains/data-utilization/notes/reaching-data-without-copies.md).
  `FileSystemIdentity` is the identity used to authorize **all** file access requests made through an S3
  access point, so **the original per-file ACLs do not carry into anything reading through it.** IAM and
  CloudTrail still show who called, but the file-system layer never evaluated whether that person could
  read the file.
  - This is the starting point for AI and RAG permission design, not a detail: permissions are flattened
    at the moment the index is built, so retrieval scoping has to be designed **in the index** — either
    one index and access point per permission boundary, or permission metadata carried in the index and
    filtered at query time. Leaving it to file ACLs does not work on this path.
  - Covers the three ways to reach data without copying and what each costs: S3 access points, FlexClone,
    and FlexCache. **FlexCache suits read-heavy workloads with infrequent changes**, because a change at
    the origin requires the cache to refresh — and cache misses and writes are both bound by the link to
    the origin, so the path decides the performance rather than the cache existing.
  - Both FlexCache and FlexClone are **ONTAP CLI only**, which is another instance of the IaC boundary.
- Note: [enabling SnapLock is not the same as locking](docs/ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md).
  SnapLock carries **three separate irreversible decisions**: enabling it on a volume, the retention mode
  (`COMPLIANCE` or `ENTERPRISE`, which cannot be changed once set), and permanently disabling privileged
  delete, which is a terminal state. And enabling SnapLock locks nothing by itself — the retention period
  and the WORM transition do.
  - Privileged delete is narrower than it sounds. It is Enterprise-only, requires a **SnapLock audit log
    volume in the same SVM** first (minimum retention six months), and **cannot be used on a file whose
    retention has already expired** — a normal delete is what works then. Reading it as "an admin can
    always delete" produces the wrong runbook.
  - Ransomware readiness is written as four layers with each limit stated: prevention via FPolicy only
    catches extension-driven behaviour, detection is not recovery, snapshots live in the same file system
    and die with the volume, and SnapLock Compliance buys immutability at the price of **not being able to
    delete it yourself either**, which is a capacity commitment for the length of the retention period.
- Note: [maintenance cannot be deferred past 14 days](docs/ja/playbooks/05-operate/notes/maintenance-cannot-be-deferred.md).
  ONTAP patching is performed by the service, so the only decision is when. And the deferral has a hard
  edge: **a maintenance window must occur at least once every 14 days**, and if a patch is released and no
  window happens in that period, maintenance proceeds anyway.
  - Two states make patching materially worse, and both are avoidable in advance. **SSD above 90% causes
    throughput to be throttled for the duration of patching** — a third consequence of that band, on top
    of the caching change already recorded. And on Multi-AZ, **missing routes with no room left in the
    route table disconnect connected clients** for the duration of patching.
  - The I/O pause happens **twice**, not once: failover before patching a file server and failback after,
    each under 60 seconds. Whether that is acceptable is decided by application timeouts, not by the
    storage figure, so the drill measures the application rather than the platform.
  - Also recorded: offline volumes are brought online for the patching window and are **not accessible to
    clients** while that lasts, so a deliberately offline volume does not stay offline.
- Note: [the IaC boundary is set by the API surface](docs/ja/playbooks/04-build/notes/what-iac-cannot-reach.md).
  What to manage in IaC is settled before it is decided, because some settings simply cannot be reached
  that way. File systems, SVMs, volumes, backups and tags are template-managed; **SMB encryption
  enforcement, the volume inode maximum and FlexVol-to-FlexGroup conversion are ONTAP CLI only.** So a
  successful template does not mean a complete configuration, and verification has to cover two layers.
  - The trap in the template itself: **`RootVolumeSecurityStyle` on an SVM is `Replacement`**, so changing
    it recreates the SVM. That is a different situation from volume-level security style, which is
    modifiable.
  - **Omitting `SvmAdminPassword` costs least privilege**: without it, managing that SVM requires
    `fsxadmin`, which is a file-system-wide administrator. Setting it allows `vsadmin` instead.
  - FlexClone has an interaction worth knowing before relying on it for test environments: **creating a
    clone after an SSD decrease operation has started pauses that operation** until the clone is deleted.
- Note: [the rollback window closes when clients start writing](docs/ja/playbooks/03-migrate/notes/where-the-rollback-window-closes.md).
  A SnapMirror destination is **read-only until the relationship is broken**, and breaking it does not
  affect the source — so rollback is free right up until clients write to the destination. After that,
  going back means discarding those writes or reversing the replication direction. **There is no "undo
  the cutover" operation**, which is why the note frames rollback as a data decision rather than a
  configuration one.
  - The largest schedule risk is elsewhere: **incremental transfer depends on the newest common snapshot**,
    so deleting SnapMirror's snapshots on the source forces a full baseline transfer again.
  - Records that downtime is bounded by `quiesce` through remount, not by transfer time, so the thing to
    shorten is the cutover procedure. And that `Idle` means "not transferring", not "current" — data
    recency is read from `Last Transfer End Timestamp`.
- Note: [tiering defaults differ by creation method](docs/ja/playbooks/06-optimize/notes/tiering-defaults-differ-by-creation-method.md).
  **The default tiering policy depends on how the volume was created.** The console defaults to `Auto`
  with a 31-day cooling period; the AWS CLI, the API and the ONTAP CLI default to `Snapshot Only` with
  2 days. Those policies do not move the same data — `Snapshot Only` never tiers user data — so a
  console-built test environment and an IaC-built production environment tier differently while both
  look like "the default".
  - Whether a read pulls data back to SSD also depends on the policy **and on the access pattern**:
    under `Auto` a random read promotes the block back to primary while a sequential read (an antivirus
    scan, for instance) leaves it cold, and under `ALL` a read never promotes. So `ALL` keeps paying
    capacity-pool request charges on data that is read repeatedly.
  - Records an ordering rule the repository had not stated: **try changes in order of reversibility**,
    not expected impact. Tiering policy and storage efficiency are reversible, throughput is reversible
    with a failover, and adding HA pairs is not reversible at all — so it goes last.
- Note: [at rest is automatic, in transit is off by default](docs/ja/domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md).
  Encryption at rest cannot be disabled and covers data and metadata, so it is not a design decision.
  Encryption in transit is the opposite: **not enabled by default**, and Kerberos for NFS and SMB
  requires the SVM to be joined to Active Directory or LDAP — which makes AD a prerequisite for
  in-transit encryption, not only for authentication. Requiring SMB encryption also **disconnects
  clients that do not support it**, so it is a security change and an availability change at once.
  - The finding most likely to surface during an audit: **SMB access auditing records only the first
    read and the first write per object.** Opens, deletes, renames and unlinks are recorded, but
    "how many times did this user read this file" cannot be answered from the log.
  - Deliberately stops at what gets asked and what can be stated as fact. Compliance determinations
    belong to the reader's own audit and legal process, so the note makes that boundary explicit.
    Question 5 of that module, on the OT/IT boundary, is left unanswered rather than filled with
    material this repository has no source for.
- Note: [billing splits into provisioned and consumed](docs/ja/domains/cost/notes/provisioned-versus-consumed.md).
  SSD capacity, SSD IOPS and throughput are billed on **what is provisioned** — unused space included —
  while capacity pool and backups are billed on **what is consumed**. Most estimate errors sit on that
  line. Capacity pool additionally carries **per-read and per-write request charges**, so tiering data
  that turns out to be read regularly can cost more rather than less.
  - **Deduplication and compression do not lower the bill.** They reduce consumed space, but SSD is
    billed on provisioned capacity, so nothing changes until provisioned capacity is actually reduced.
    Reporting the gain as "free space" hides that the invoice did not move.
  - Also corrects an assumption in the other direction: **cross-AZ replication traffic for Multi-AZ is
    included in the throughput capacity price**, so treating it as a separate transfer charge overstates
    the cost of Multi-AZ. And 3 IOPS/GB is included, so raising IOPS is not automatically billable.
- Note: [deployment type is decided once](docs/ja/playbooks/02-design/notes/deployment-type-is-decided-once.md).
  **Deployment type cannot be changed after creation** — not even Single-AZ 1 to Single-AZ 2 — and the
  same single choice fixes the scale-out ceiling. Only second-generation Single-AZ supports more than one
  HA pair, so "start on Multi-AZ and add pairs when performance runs short" is not a path that exists;
  it becomes a rebuild and a data migration.
  - Adding HA pairs has consequences the checklist did not cover: the new pair arrives with **matching
    SSD capacity**, so it is a cost decision too; **existing volumes must be moved and clients remounted**
    before anything gets faster; the pairs **cannot be removed**; and **past six pairs iSCSI and NVMe/TCP
    stop being available**, which combined with non-removability makes it a one-way door.
  - Covers file-system-level irreversibility, complementing the volume- and SVM-level table already in
    the pre-production checklist rather than restating it.
- `llms.txt` now carries a **findings section** listing each note with a one-line statement of what it
  establishes. Previously the file described the taxonomy — the twelve modules and the two axes — so an
  agent reading it learned how the repository is organized but not that any findings existed. It also
  states the coverage count, so an agent is not left to infer that an empty module is an oversight.
  - Mermaid node labels containing a colon are now quoted. Nothing was known to be broken; a malformed
    diagram renders as an error box on GitHub and no gate in this repository parses Mermaid, so the
    failure mode is silent and worth closing off rather than trusting.
- Note: [free space does not mean you can still write](docs/ja/playbooks/01-assess/notes/counting-bytes-is-not-counting-files.md).
  A volume counts files, directories **and snapshot copies** as inodes, and once inodes are exhausted
  the volume rejects writes even with capacity left. The trap is in how the default scales: **one inode
  per 32 KiB only up to 648 GiB.** Past that, every volume gets the same 21,251,126 regardless of size,
  so a 10 TiB volume has the same default inode budget as a 648 GiB one.
  - The note publishes the break-even average file size derived from that default — below roughly
    **505 KiB on a 10 TiB volume, or 2.5 MiB on a 50 TiB volume**, inodes run out before capacity. These
    are labelled as arithmetic from the documented default, not measurements. Raising the limit helps but
    is bounded: one inode per 4 KiB, hard-capped at 2 billion per volume, which still leaves ~27 KiB as
    the break-even on 50 TiB.
  - The rest of the inventory is organized by **which later decision consumes each measurement**, on the
    principle that an item is only worth collecting if a decision changes based on its value — and that
    the items skipped are the ones that resurface as irreversible settings. Each row links to the note
    that establishes the dependency, so 01-assess now acts as the entry point into the rest of the repo.
  - Also recorded: protocol inventory taken from configuration is wrong in both directions (enabled but
    unused shares, and paths absent from the register), and a performance baseline recorded without the
    region, generation and statistic cannot be compared against after migration.
- Note: [monitoring fails on averages](docs/ja/playbooks/05-operate/notes/monitoring-fails-on-averages.md).
  Which statistic you graph has to be decided before the threshold, because `Average` hides saturation
  for two structural reasons: **odd-numbered file servers are preferred and even-numbered ones are
  standby**, so averaging them roughly halves the reading by design; and utilization metrics emit one
  data point per aggregate, while a FlexVol lives on exactly one aggregate — so the saturated aggregate
  is precisely the one holding the affected volume. The alarm recipe in the AWS documentation uses
  `MAX(StorageCapacityUtilization)` for the same reason.
  - 80% is a recommendation, not the only threshold. **At 90% capacity-pool reads stop being cached on
    SSD, and at 98% tiering stops entirely.** Recovery from 98% requires getting back under 90%, not
    just under 98%.
  - A third failure mode is not fixable by choosing a statistic: **client traffic is prioritized over
    background tasks** (tiering, storage efficiency, backups), so those fall behind at peak without
    alarming. `NetworkThroughputUtilization` counts that background traffic too, which is why high
    network utilization does not imply high client load.
  - Also recorded: all writes land on SSD first regardless of tiering policy and metadata always stays
    there, so an `All`-tiered volume still consumes SSD at roughly 1:10; and if deleting data does not
    free SSD, snapshots are still holding it — which makes retention design part of capacity design.
- Note: [having snapshots is not the same as being able to recover](docs/ja/domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md).
  Snapshot, backup, and SnapMirror cover **different failure domains**, and the mechanism most people
  rely on does not survive the failure they most fear: a snapshot lives inside the same file system,
  which is why restores are fast and also why the snapshot is lost along with the volume or file system.
  - The finding most likely to break a DR design: **read-write is the only volume type that can be
    backed up.** Data-protection, load-sharing-mirror, and FlexCache/SnapMirror destination volumes
    cannot be. So "replicate to another Region with SnapMirror, then back up the replica" does not
    work — the backup has to be taken on the source side.
  - Restores are not unconditional. If a snapshot newer than the restore target is tied to an existing
    backup, **the restore is refused** until the newer side is removed. That is a constraint people
    tend to discover mid-incident, so the note puts it in the drill rather than in a warning box.
  - Recovery time depends on generation: second-generation file systems give read access within minutes
    of starting a restore, while first-generation waits for the whole volume. The same RTO cannot be
    claimed for both.
- Note: [FSx for ONTAP S3 AP is not "S3 you can use as S3"](docs/ja/domains/data-utilization/notes/s3-access-point-constraints.md).
  Access points attached to an FSx for ONTAP volume carry restrictions that bucket access points do
  not: ONTAP 9.17.1 or later, same AWS account, same Region. Cross-account designs do not work at all,
  which is a plan-level constraint rather than a configuration detail.
  - Enabling S3 access points **lowers the volume-count ceiling** — 500 to 491, and 1,000 to 975 at
    two HA pairs or 903 at twelve. More pairs means a larger reduction, so "add pairs to get more
    volumes" does not hold.
  - Object size limits are kept as a link to the sibling repository rather than restated. They are
    measurements, and a measurement separated from its environment gets misused. The note does carry
    the operationally important part: the whole-object limit is evaluated at
    `CompleteMultipartUpload`, so an oversized upload fails *after* transferring everything, which
    makes client-side validation the only cheap check.
- Note: [throughput is not set by one value](docs/ja/domains/performance/notes/where-throughput-is-determined-and-shared.md).
  The ceiling depends on generation, AZ configuration, and **region** — first-generation file systems
  reach half the documented IOPS and throughput outside four named regions. Raising the throughput
  setting alone does not reach the ceiling either; it requires a matching SSD capacity and IOPS
  configuration.
  - The consequence most likely to be designed around wrongly: a FlexVol lives on exactly one
    aggregate, and each HA pair has one aggregate. So a file system with twelve HA pairs still serves
    a FlexVol at one pair's performance. Using more than one pair in a single namespace requires a
    FlexGroup, spanning all aggregates with an even constituent count.
  - Also recorded that adding HA pairs raises the **minimum** throughput, not just the maximum, so
    it is a cost decision as well as a performance one.
- Note: [ACL preservation is a privilege problem, not a tool problem](docs/ja/playbooks/03-migrate/notes/preserving-acls-during-migration.md).
  SMB migrations lose ACLs for two reasons that have nothing to do with tool capability — the defaults
  do not include them, and an account without the right privilege skips unreadable ACLs silently and
  still exits successfully. `robocopy` defaults to `/COPY:DAT`, which carries no ACLs at all; DataSync
  carries DACLs but not SACLs unless asked. "No errors" is therefore not evidence of preservation, and
  the note gives the sample comparison that is.
- **A version-compatibility gate in the migration decision tree.** When the source is ONTAP,
  SnapMirror is only a candidate if the source and destination version combination appears in the
  compatibility matrix — so the tree now asks that before recommending it, and gives three routes
  when the answer is no: upgrade the source, upgrade through an intermediate version, or switch to a
  method that is not SnapMirror.
  - Recorded explicitly that **"within N versions" is not a usable rule.** Compatibility is defined
    by a matrix, not an arithmetic window, and the matrix absorbs cloud-only releases,
    platform-limited releases, and constraints that only apply once a feature is enabled.
  - Also recorded that the destination version is not a free choice — AWS manages it — and that
    FSx for ONTAP supports volume-level SnapMirror only, so a plan that assumes synchronous
    replication does not hold.
- **An index of published primary sources**, at
  [`docs/ja/case-studies/public-references.md`](docs/ja/case-studies/public-references.md).
  Information about FSx for ONTAP is split across an AWS side and a NetApp side, and reading only one
  hides constraints documented on the other. The page maps where things are rather than summarising
  them, because summaries go stale while the structure lasts.
  - It also carries a weighting table: the same `evidence` discipline applied to external sources.
    A Q&A answer is a field observation, a vendor case study reports what worked and rarely what
    constrained it, and a number without its measurement environment is unusable regardless of how
    official the source is.
  - Individual bloggers are deliberately not listed. A curated list of people cannot be kept current,
    and inclusion or omission reads as a judgement. The page gives search strategies and a single
    test instead: does the article state its ONTAP version, region, and configuration.
- **The two first-touch guides are now available in all eight languages.** `navigation.md` and
  `evidence-policy.md` join the hub READMEs, so a reader arriving in their own language can find
  their way and understand the confidence signals before deciding whether to act.
  - Scope is deliberate: first-touch material only. Anything carrying a number, a limit, or an
    irreversible operation stays at ja + en. A mistranslated navigation label sends someone to the
    wrong page and they notice; a mistranslated design judgment does not announce itself.
  - Every Tier 1 document now declares which version is authoritative. Japanese is authoritative for
    technical accuracy; the other languages say so and invite corrections. These translations are
    machine-assisted and not natively reviewed before publication, and a reader deciding whether to
    act is entitled to know that.
  - `docs/i18n-terms.md`: the never-translate list, fixed renderings for the twelve terms that carry
    a judgment, and the authority wording per language. Without a fixed table the same term drifts
    between files, and drift in a word like "irreversible" changes what a reader believes is allowed.
- **Environment-first entry point** in the navigation guide (ja, en): pick the row matching your
  configuration — migration source, protocol mix, AD dependency, running vs greenfield — and get a
  reading order. The existing entry points branch on "what do you want to know", which assumes the
  reader already knows where their question belongs.
- **"Before adopting into production"** in the evidence policy (ja, en): what to confirm per evidence
  tier, the adoption sequence, and the rule that irreversible settings cannot skip a test
  environment. The tiers said how far a finding could be trusted but never how to act on one.
- First note: [security style determines the permission model](docs/ja/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md)
  — why denying ID mapping does not block SMB on NTFS-style volumes, and why a check run as a member
  of the file system administrators group produces a false negative.
- First checklist: [pre-production review](docs/ja/playbooks/04-build/checklists/pre-production-review.md)
  — scoped to two questions only, what cannot be changed later and what hits a limit, with an
  explicit table of irreversible items.
- Authoring rule: every diagram repeats its information in prose or a table. Mermaid does not render
  everywhere, is not reliably reachable by a screen reader, and is not extractable by a crawler.
- `tools/new_note.py` template now carries a "verify in your own environment" section, so the path
  from reading a note to adopting it is part of every note rather than an afterthought.
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

- **`AGENTS.md` documented a `--verify-parity` flag that was never implemented.** The check it
  described does exist and always has — `check_language_links()` in `sync_lang_switcher.py` runs
  unconditionally and reports the offending file and line rather than a set difference — so the
  correction is to describe the mechanism instead of the flag. The original spec item lived on in the
  documentation after the implementation solved it differently, which left an agent reading
  `AGENTS.md` to conclude the gate was missing.
- **The English coverage policy is now stated rather than implied.** English is complete through
  Tier 2 (hubs, guides, all twelve module READMEs) and opt-in below it, with two conditions for
  translating a note: it answers a Tier 2 question an English reader will reach, and its content has
  settled. The stopping point is deliberate — Tier 3 carries the numbers, thresholds, and
  irreversible operations, where a mistranslation does not announce itself.
- **`llms.txt` claimed three decision trees where one exists.** It listed flowcharts for protection
  scheme and protocol selection alongside the migration method tree. Corrected to describe the one
  that is actually written, rather than leaving a promise for a reader or a crawler to follow.
- **Two questions in the 02-design module README were answered by sections that address something
  else.** "How to divide file systems and SVMs" pointed at what happens when an HA pair is added, and
  "how to size capacity and throughput" pointed at the ceiling of a single HA pair. Both questions are
  now stated as what those sections do answer, and the original two are listed as `_未追加_` — the
  first use in a module README of a marker the hubs have documented in all eight languages.
- **A heading and its five referrers said "how to present trade-offs".** The section is about weighing
  options for one's own decision, not explaining them to someone else, so it is now
  「トレードオフの見比べかた」 / "How to weigh trade-offs".
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

- **A failed volume deletion *can* be diagnosed from the AWS API.** An earlier entry in this release claimed
  it could not, and that only the ONTAP job message carried the reason. That was wrong, and it was the same
  class of mistake as the incident it was describing: concluding without reading what was already available.
  `DescribeVolumes` returns `LifecycleTransitionReason`, which in this case read
  `Cannot delete the volume because it contains unexpired log files.` — **more precise than ONTAP**, which
  enumerates five possible conditions. Only `Lifecycle` and `AdministrativeActions` had been read.
  - What survives: the `delete-volume` **response** carries no reason and `AdministrativeActions` stays
    `null`, so a follow-up `DescribeVolumes` is required. The transition from `DELETING` back to `CREATED`
    as the failure signal is documented behaviour.
  - Also recorded: the AWS troubleshooting page for failed SVM and volume deletions does **not** list
    SnapLock audit log volumes among the causes, so that page alone does not lead to this diagnosis. The
    feature request raised on the false premise was retracted with AWS Support and replaced by a
    documentation request for that page.

- **AWS Support confirmed in writing that there is no early exit.** Deleting the SnapLock audit log volume
  before its retention expires is not possible, deleting the file system that contains it is not possible,
  and **no path exists other than closing the account**. The explicit statement was requested precisely so
  that this section could stop hedging: the volume and its file system are fixed in place until 2027-02.

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
