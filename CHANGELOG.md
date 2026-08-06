# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Added

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
