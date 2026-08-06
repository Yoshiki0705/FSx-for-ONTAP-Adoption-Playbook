# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Added

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

- **The pre-production checklist cited an AWS Prescriptive Guidance URL that returns 404.** The page
  appears to have been moved or retired since it was indexed. The affected claim — tier latency
  levels — is now sourced to the AWS Storage Blog sizing article, which states it directly. Re-sourcing
  also surfaced a more actionable fact that has been added: tiering behaviour changes by utilization
  band, and stops entirely at 98% SSD, not merely degrading past the 80% recommendation.
- `tools/check_links.py --external` reported false failures for hosts that redirect a `HEAD` to a
  landing or sign-in page returning 404 while `GET` answers 200. A failure is now confirmed with
  `GET` before being reported. Reporting working links as broken trains people to ignore the check.
