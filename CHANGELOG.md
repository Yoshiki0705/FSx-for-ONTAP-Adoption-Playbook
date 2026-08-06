# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Added

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
