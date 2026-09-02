# Changelog

Notable additions and corrections. Follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

Corrections matter as much as additions in a knowledge base: a reader who acted on an earlier
version needs to know what changed. **Record demotions of an `evidence` tier here explicitly.**

## [Unreleased]

### Fixed

- **The audit note's `-autosize` row named a parameter but not the command.** Following up on the
  documentation case, AWS Support confirmed FlexVol autosizing is available on FSx for ONTAP via the
  ONTAP CLI `volume autosize`, which is the actionable form — the row now names the command and links
  the AWS page, so a reader can act on "grow it before it fills" rather than just be told to consider
  it. This is the mitigation the same note argues for, since the destination-full-to-stop window was
  measured at 19–65 seconds and does not reproduce, so detect-then-react cannot be relied on.

- **The localization tiers did not classify `case-studies/` or `workshop-studio/`.** Both sit under
  `docs/<lang>/` with a `README.md`, which reads as Tier 2 — yet neither is a module whose question
  list is the index, so requiring English through Tier 2 would have been wrong. The tier table now
  places both explicitly in Tier 3, and records that the `case-studies/README.md` already in English is
  there as reachable navigation, not because the tier demands the tree. This matches what
  `check_i18n_parity.py` already enforces (its Tier 2 scan covers only `playbooks` and `domains`);
  the rule was correct and unwritten, which is what invited re-deciding it each pass. No files moved
  or were translated — the remaining Japanese-only material under these two trees is Tier 3 and
  optional by design.

- **`AGENTS.md`'s repository layout omitted `docs/ja/workshop-studio/`.** Six files live there, and the
  root README, `ja/navigation.md`, and `en/navigation.md` all link to it, but an agent reading the
  layout to orient itself would not know the subtree exists. Added one line. The file had eight bytes
  of headroom, so the context budget was raised 30,000 → 31,000 rather than shaving an unrelated
  comment to pay for the line — the reasoning is recorded at the constant in
  `scripts/check_agent_context_budget.py`, which is the deliberate, visible bump the tool is built to
  require. The ceiling still sits close enough that the next approach to it is a prompt to move
  material to `docs/agent/`, not to raise it again by reflex.

- **The `(日本語)` marker rule was stated, unenforced, and half-observed.** `docs/agent/localization.md`
  promises that a Japanese-only note is linked from English with a marker "so a missing translation is
  a labelled link rather than a broken promise". Nothing checked it, so it held in module README
  question tables and drifted everywhere else: **20 links changed language with no warning**, and 13 of
  those were added by the two translation batches merged earlier the same day. Markers added to all 20,
  and `make ja-markers` (`tools/check_ja_only_markers.py`) now enforces it inside `make all`.
  - The gate deliberately does not ask for a marker on links into `docs/ja/reference/**` (bilingual
    single files, so the English prose is already there), on directory links (`switcher-check` already
    owns which language's directory to point at), on the generated switcher block, or on links whose
    text already says 日本語. Each of those would announce a translation that is not missing.
  - The rule in `docs/agent/localization.md` now says explicitly that it covers every link rather than
    only the index positions, which is the ambiguity the drift grew in.
  - Wired with a break case in `scripts/tests/test_doc_gates.py` and a `--selftest` covering all seven
    accept/reject shapes, because a gate that only passes on a clean tree proves nothing about whether
    it can still detect anything.

- **A section heading counted three findings and the table under it listed four.** In
  `what-iac-cannot-reach.md`, the heading said 3 while the table carried four rows, and the sentence
  that followed referred to "the third" while describing the fourth — the asynchrony of
  `UpdateVolume`. Found while translating, because a translation has to decide which item the sentence
  points at. The count is dropped from the heading and the finding is named instead, so the reference
  cannot drift again when a row is added. No inbound link cited that anchor.

- **"Some SVMs cannot serve SMB, and only recreating the SVM fixes it" was wrong on the cause, the
  remedy and the indicator.** The vendor reproduced the behaviour and identified it: `data-cifs` is
  granted to **every** SVM at creation regardless of AD membership, and it is **removed when a CIFS
  server is deleted** — which includes detaching an Active Directory configuration. Recreating the CIFS
  server with ONTAP CLI `vserver cifs create` succeeds, reports a healthy server, and **does not restore
  it**; recreating it through ONTAP REST `POST /api/protocols/cifs/services` does. The broken state's
  service list matched the affected SVM exactly, and the provisioning code has no date-dependent
  branch.
  - **The remedy was the costliest error.** The note said data migration to a new SVM was the only
    option. It is recoverable in place by deleting the CIFS server and recreating it over REST.
  - **The date claim is refuted by this repository's own data.** Six SVMs on one file system, ordered by
    creation: 2026-05-14 has `data-cifs`, 2026-05-22 does not. There is no threshold. What correlates is
    whether a CIFS server exists. The apparent date boundary was age acting as a proxy for having had a
    CIFS server deleted — and the control that convinced me, a freshly created SVM that had it, had it
    because nothing had deleted a CIFS server yet.
  - **`Endpoints.Smb` was recommended as the check and does not work.** It follows AD membership, not
    `data-cifs`: the vendor observed an SVM with `data-cifs`, a running CIFS server and port 445 open
    reporting `Endpoints.Smb: null` because it was not AD-joined. A workgroup SVM reads as `null` when
    healthy. Judge by whether `services` contains `data-cifs`. The two agreed in my sample only because
    it contains no non-AD SVM with a working CIFS server.
  - Renamed to `smb-service-lost-on-cifs-server-delete.md`; the old name asserted the refuted cause.
    The mechanism and the recovery are the vendor's and are **not** reproduced here — doing so means
    deleting a CIFS server on a shared file system — and neither is publicly documented yet.
- **"The cause is the absence of a name mapping" is withdrawn.** For an S3 access point with a `UNIX`
  `FileSystemIdentity` against an NTFS-security-style volume, the vendor tested with an explicit name
  mapping present *and* the mapped user permitted by the NTFS ACL, and access still failed. So "add the
  mapping and it works" does not follow, and the inference rested on an EMS line the note already
  flagged as belonging to a different workload. Whether that combination is supported at all is open
  with the vendor. What does exist in the documentation is the pairing guidance — UNIX identity with
  UNIX security style, Windows identity with NTFS — now cited; what is missing is what happens when you
  pair them the other way.
- **The retention section stopped at "the two are exclusive".** Added, from vendor verification on the
  same ONTAP build: REST rejects the combination too (`400` on `POST` and `PATCH` of
  `/api/protocols/audit`), so the exclusivity is inside ONTAP rather than CLI argument parsing — and
  **setting `retention.count` alone silently reverts `retention.duration` to `PT0S`**, meaning one
  choice disables the other. Also the part that makes the choice actionable: `-rotate-size` defaults to
  100 MB, `-rotate-limit` bounds the total at `rotate-size × rotate-limit` plus the active file, and
  the retention that `-rotate-limit` gives up is observable by watching the oldest file's timestamp.

- **The lockout note framed the risk as using the wrong credential, and a correct one locked the
  account anyway.** Reproduced on 2026-09-02 while investigating whether an unrelated automation was
  the cause: authentication succeeded at `06:00:57` with the value from the secret, and the account was
  locked by `06:08:27`. In between, the only authentication attempts used that same working password
  over an SSM port-forward that had stopped responding — `nc` reported the port open and the next `ssh`
  got `Connection refused`. **Attempts that never complete appear to count toward the five**, so a few
  retries through a flapping tunnel reach a threshold that has no automatic release. The note now says
  to confirm tunnel stability with spaced probes and then send exactly one authentication, and prefers
  a single REST request over SSH when the path is suspect. What the ONTAP counter actually counts is in
  the unverified list: the account cannot be read while locked, and unlocking resets the counter, so
  there is no after-the-fact check.
- **Two diagnostic corrections in the same note.** `LastAccessedDate` was offered as the way to find
  who reads a shared secret; it is daily granularity and useless against a five-minute schedule, so
  CloudTrail `GetSecretValue` replaces it — it yields time, caller and which secret. And **reading a
  secret is not authenticating with it**: the automation suspected here reads both `fsxadmin` secrets
  on a schedule, and its own logs end in "0 rows examined" every run with no sign of reaching ONTAP.
  Recorded because the earlier working hypothesis blamed it on the read alone.
- **The recovery procedure told you to log in immediately after resetting the password.** `Lifecycle`
  stays `AVAILABLE` while the change moves `PENDING` → `IN_PROGRESS` → `COMPLETED`, so it is not the
  signal that the reset landed — and testing early spends one of the five attempts on the account you
  are trying to recover. The procedure now polls `AdministrativeActions[0].Status` first; the reset
  measured about 44 seconds.

- **`CONTRIBUTING.md` still told contributors that a missing tool means a skipped check.** It called
  `markdownlint-cli2` optional and said the gate skips when it is absent, which stopped being true
  when every gate was changed to fail instead — so the quickstart promised the one behaviour the
  gates were rewritten to remove. It now states that all three external tools are required, and
  carries the toolchain detail that `AGENTS.md` has no room for: the pinned `ruff`, how to bump it,
  and the non-virtualenv route. **Including that a `uv`-created `.venv` has no `pip`**, so the
  documented `.venv/bin/python -m pip install -r requirements-dev.txt` fails with
  `No module named pip` — hit while bumping `ruff` to 0.16.5, which is exactly when a contributor
  first needs the command to work.

- **"There is no audit-specific EMS event" was a statement about the pattern I searched, not about
  ONTAP.** The query was `event log show -message-name *audit*`, and `adt.stgvol.*` cannot match it.
  ONTAP does define `adt.stgvol.nospace` (severity `EMERGENCY`) for staging exhaustion, plus
  `monitor.volume.full` / `nearlyFull` against `MDV_aud_*` — surfaced by AWS Support in reply to the
  documentation case. **Re-queried with `adt.*` and `*stgvol*`: still zero across both denials**, in a
  log window that still holds the `monitor.volume.full` from each, so the absence is not retention
  expiry. That inverts what the finding is worth: it is now positive evidence *against* staging
  exhaustion as the cause, since the event that would announce it never fired and `MDV_aud_*` never
  reached 95% either. The note keeps the mechanism unattributed and now says why. Also re-measured:
  across the whole window the only other events are an unrelated workload's `secd.nfsAuth.noNameMap`
  every ~5.5 min, and **nothing records the client denial itself**. The advance warning does not
  reproduce any better than the grace window did — 65 s in the first run, **19 s in the second, where
  `nearlyFull` (95%), `wafl.vol.full` and `full` (99%) all landed in the same second.** Alarming at
  95% to buy reaction time assumes a gap that is not always there.
- **"No AWS or NetApp documentation covers the deletion order for a volume that had an S3 Access
  Point" now has a vendor answer.** AWS Support reproduced the orphaned association and explained it:
  the bucket is `amazon-fsx-fsvol-<volume ID>`, it survives both detach and a failed create, and its
  removal is part of **Amazon FSx's** volume-deletion path — which is why ONTAP CLI refuses and
  `aws fsx delete-volume` works. There is no user-facing path to delete the bucket on its own. The
  error wording is emitted by ONTAP, so Amazon FSx cannot change it. The note is re-tiered
  accordingly: behaviour `verified`, mechanism from Support, and **still absent from public
  documentation** — a submitted feedback is not a published one.
- **The note referenced an object-store-server conflict in a section that never stated it.** That gap
  is closed with the constraint itself plus what AWS Support added: it applies **per SVM**, there is
  no workaround inside the same SVM, and the way around it is to attach the access point to a volume
  on a different SVM (which needs `vserver add-protocols -protocols s3`). The mechanism is that
  attaching creates a management object store server on the volume's SVM, so an existing one collides.
  **The workaround does not cover the case that led here**: an audit destination must sit in the
  audited volume's own SVM namespace, so reading EVTX through an access point cannot be moved to
  another SVM. Either drop the existing object store server or read the logs another way — the ONTAP
  REST file API works without mounting. Raised on the case as well, since documenting only "use a
  different SVM" would not tell an operator that the audit-log use case is excluded.
- **"SACL missing means zero events" is measured behaviour, not a guarantee.** AWS Support declined to
  document it as such: the SACL requirement is already stated ("You need to configure audit
  policies…"), and behaviour when a required setting is absent is not a specified contract. Recorded
  inline, because the consequence is concrete — **zero events is equally consistent with "no access",
  "no SACL" and "no category", so no audit logic may read it as "nobody touched this".**
- **`is not a recognized command` for a role-restricted command is ONTAP behaviour rather than
  anything specific to FSx for ONTAP.** Same wording as a misspelled command, so it invites debugging
  the spelling; the NetApp KB
  attributing it to the role or privilege level is now cited where the restriction is documented, with
  the check that actually answers it (`security login role show -role <role>`).

- **"The audit log filling up denies client access" is correct, and an earlier version of this entry
  said it was not — because that measurement was under-loaded.** The first pass drove five SMB
  operations against a destination at 99% and concluded access does not stop. Re-measured on the same
  purpose-built throwaway SVM with a 10,000-file workload: the client created **794** files and was
  then denied with `{Audit Failed} An attempt to generate a security audit failed.` (Windows system
  error 606), which also blocks `net use` session setup, not just writes. **The variable is not how
  full the destination is, it is how many operations occur while consolidation is stalled** — five fit
  in the buffer, 757 did not. Timeline (UTC 2026-09-01): `wafl.vol.full` at `19:41:06` (audit asked
  for 1.01 MB, 752 KB free), last record reaching the destination at `19:42:05.63` (422 records,
  files 1–37), then **4,538 records generated over ~16 s with the client still succeeding and nothing
  written**, denial at `19:42:22`, still denied at `19:50:05` so it does not self-heal, space freed at
  `19:51:22`, consolidation resuming ~1 s later, client confirmed working by `19:53:30`. **No records
  were lost at either load**: the final count is files 1–794, **zero gaps**, original timestamps and
  order preserved — `-strict-guarantee true` trades availability for completeness exactly as designed.
  Two things stayed silent throughout: `event log show -message-name *audit*` returned nothing, and
  `vserver audit show` kept reporting `Auditing State: true` while access was denied, so destination
  volume utilisation is the only advance warning and it leads the outage by about 65 seconds. **The
  cause of the stop is explicitly not attributed**: it happened after ~5 MB of buffered records, far
  below the 2 GB staging volume the documentation describes, and `MDV_AUD_*` is not visible from
  `fsxadmin`, so staging exhaustion is not established. Also recorded: writes to the destination
  volume itself produced zero audit records, so there is no self-amplification by default; and reading
  the 5,246,976-byte EVTX through the ONTAP REST file API in one request returned a **truncated
  multipart body with no error**, so large reads must be chunked and the size checked afterwards.
  **The blast radius is the audited path, not the SVM.** A second volume was added to the same SVM
  with no SACL and shared from the same CIFS server, same data LIF, same local user. With the
  destination exhausted the audited volume was denied at operation 57 while the non-audited volume
  completed **5,000/5,000** — and contributed zero audit records, confirming it was genuinely outside
  the audited set. So auditing an SVM does not make its unaudited shares fragile; it makes the audited
  ones the first to stop, which is the opposite of convenient when auditing is the compliance
  requirement. **And the grace period does not reproduce**: the same configuration and workload gave
  794 successful operations in one run and 56 in the next, because how much buffer the preceding audit
  activity had already consumed is not observable. Nothing about the window should be designed
  against. `-client-session-timeout 60` also did not reap an idle local-user SMB session within
  9m17s, so that setting is not a mechanism for producing a 4634 on idleness.
  File renamed to `audit-log-space-and-client-access.md` in the earlier pass; the name is neutral on
  the outcome and stays.
- **"4634 only on a graceful client logoff" was right but incomplete, and one reading of it was an
  artefact of collecting too early.** Six teardown paths measured: destroying the client SMB session
  (`Restart-Service LanmanWorkstation`) and the client process exiting both emit 4634 — the latter
  about three seconds later. Removing the *share mapping* (`net use /delete`, `Remove-SmbMapping`)
  emits nothing at that moment because the authenticated session survives; the event arrives when the
  session is finally destroyed. An orphaned session after connection loss is reaped server-side in
  about three minutes and still emits nothing, which now rests on observing the session disappear
  rather than on a short window. Four of the six paths are silent. The note records the collection-
  window trap, because reading "`Remove-SmbMapping` produces no 4634" out of a too-early collection is
  exactly the mistake it invites. **A seventh path is now measured: idleness terminates nothing.** With
  `Client Session Timeout` lowered from the 900 s default to 60 s, a mapped local-user session left
  completely untouched survived **17m30s** — `idle-time` rising monotonically, so no client request was
  reaching the server — and emitted no 4634. That is the only session timeout the SVM exposes, so
  "no activity for N minutes produces a logoff event" does not hold at any setting. Five of the seven
  paths are silent. The first attempt at this measurement was invalidated by an unrelated
  `net use * /delete /y` from a concurrent test, which destroyed the session and made timeout
  indistinguishable from teardown; the note records that too, since an idle test is exactly the kind
  that other work silently ruins.
- **"A volume that had an S3 Access Point attached" understated when the bucket association appears.**
  The association is created even when `CreateAndAttachS3AccessPoint` never reaches `AVAILABLE`:
  reproduced on 2026-09-01 with an attach that ended `FAILED`, where detaching succeeded, the
  attachment was gone from `DescribeS3AccessPointAttachments`, and ONTAP still refused to delete the
  volume. "The create failed, so nothing was left behind" does not hold — which bites hardest in a
  verification environment that is rebuilt repeatedly.
- **The auditable-SMB-event list was presented as the whole set when it is one category.** The
  enumeration in `what-the-platform-gives-and-what-stays-yours.md` (open, delete, read/write,
  hard link, rename, unlink) is the file-access category, copied from the AWS table — which omits the
  Logon and Logoff rows that the same AWS page's prose describes as a default category. A reader
  checking whether SMB logons can be audited would have concluded they cannot. The section now names
  the category it is listing and links the measured logon-event note.
- **The heading checker's noun allowlist never fired, and removing it is the honest state.** It listed
  問い, 扱い, こと, もの, 選び方 and six more as nouns that the verb pattern might catch. Once `れ` left
  the character class, none of them could match it any more — measured across the whole tree, the
  allowlist overturned zero verdicts. A gate carrying a list that protects nothing states a guarantee
  it is not providing, and a later maintainer widening the pattern to a blanket `い$` would have
  assumed eleven listed words covered an open class. What actually keeps those nouns clean is that
  `ない` is a literal rather than `い$`, so that boundary is now asserted directly in
  `scripts/tests/test_heading_style_detection.py` and fails loudly if it is widened.

- **"Not in the price list, so not charged" was wrong about `CopyBackup` cross-Region transfer.** The
  reasoning was that backups sit in AWS-managed S3 and never traverse the customer VPC, so an
  EC2-style inter-Region charge cannot apply. EBS snapshots refute it: they are also in AWS-managed
  storage, also never traverse a VPC, and their cross-Region copies do incur AWS Data Transfer,
  billed as `*-AWS-Out-Byte` under "EC2 - Other". The check behind the claim was also unsound —
  inter-Region transfer bills under `AWSDataTransfer`, not under the originating service's price
  list, and there is a generic service-agnostic SKU at the same rate as the AWS Backup Amazon FSx one. The
  note now says to budget as though it is charged, still `unverified` because it was not reconciled
  against a bill.
- **The measured restore duration was left without its scaling.** 13 to 16 minutes was a 9.4 MiB
  volume, and quoting it in an RTO table invited extrapolation. Restore is a background process
  bounded by unused throughput capacity, so `min(published rate, throughput capacity)` governs:
  multi-TB volumes take hours and tens of TB take days, and a small-file data set does not speed up
  with more throughput because the published 100 MBps binds first.
- **The bare-`FSx` naming rule exempted the cases it most needed to catch.** Its
  "is this an identifier rather than prose?" test ran against the whole line, so one URL or one
  backticked token anywhere on a line exempted every bare `FSx` beside it. These notes cite sources
  constantly, so that covered most prose, and `make audit` reported a clean tree throughout. The
  test now runs against a window around each match, with URLs and code spans blanked out first.
  Tightening it surfaced one violation that had been in `docs/ja/reference/limits/` for as long as
  the rule existed. `Amazon FSx` is now recognized as the official family name rather than the
  forbidden abbreviation. `scripts/tests/test_bare_fsx_detection.py` asserts both directions,
  because a rule that only ever passes and a rule that flags `AWS::FSx::Volume` both end up switched
  off.
- **The transfer-charge billing account was stated as settled when two AWS sources disagree.** The
  developer guide says the *destination* account sees the cross-Region transfer charge for a resource
  type AWS Backup does not fully manage; the pricing page says the charge goes to the account
  transferring the data out, which is the source. FSx for ONTAP is exactly such a resource type, so
  the disagreement lands on this case. Both are now quoted side by side and the point is marked
  `unverified`, with the advice to run one copy and read the bill.
- **The note block's longest line ran off the exported canvas.** With `whiteSpace=wrap` a long line
  wraps at the geometry width, but it is drawn starting from `spacingLeft`, so it overruns the right
  edge by that much — and the 12px export border does not cover the overrun. In the English diagram
  the wrap landed mid-phrase and `16 s through AWS Backup, at 9 MB` was cut off the image. Every
  note line now carries its own `<br>` instead of relying on the wrap. This is the second defect in
  this generator found only by opening the PNG: the XML parsed and `--check` passed both times.
- **Dark-theme edge labels exported blank.** draw.io puts an opaque white plate behind every edge
  label by default. On the dark canvas the plate stayed white while the text turned white with it,
  so each label rendered as an empty rectangle. The XML parsed, `--check` passed, and only opening
  the PNG showed it — which is why the diagram standard says to look at the picture. The generator
  now sets `labelBackgroundColor` from the theme.

- **The ruff gate misdiagnosed a broken install as a version mismatch.** It read the version through
  `ruff --version | awk '{print $2}'`, and a pipeline reports its *last* command's exit status, so a
  ruff that cannot execute produced an empty version string. The gate then refused — correctly — while
  saying `is , but CI pins 0.16.3` and pointing at the pinning instructions, which are not the fix for
  a binary that does not run. The version is now read without a pipeline and the two causes are
  reported separately. A sibling repository found the same masking in its own commit gate, in a worse
  shape: a pipeline chained with `&&`, which looks connected and never propagates a failure. Both are
  one fact — `&&` and `||` see the pipeline's status, not the interesting command's — and the same fact
  explains three commits in this session that landed over a failing `make all`, where `make` and
  `git commit` were separated by a newline rather than `&&`.
- **Locale digit grouping read as a changed measurement.** German, Spanish and French group
  thousands with `.` where Japanese and English use `,`, so `24.861` and `24,861` are one value
  written two ways - and the literal comparison would have reported the translation as carrying a
  number the reference does not. With eight languages that is the most dangerous false positive
  available, because it claims a measurement moved. Grouped numbers are now canonicalized before
  comparison while the message still quotes the literal as written; `24681` in a failure message
  cannot be found in a file that says `24,861`. Reported by a sibling repository that hit the same
  class in its own copy. Its third finding - a comma inside a group acting as a word boundary and
  splitting `300,000,000` into `300` - does not reproduce here: the grouped-number alternative is
  ordered ahead of the bare-integer one, which consumes the whole number first.
- **The anchor contract claimed two documents were cited externally when they were not.** The citing
  repository confirmed all 37 of its anchored links land on the two access point notes, and that it
  references the decision tree and the evidence policy in prose only. Those two are removed, 89
  anchors down to 66. A contract that over-claims makes the gate fire on renames that break nothing,
  and friction without benefit is how a gate ends up switched off.
- **Two schema rules were stated but not enforced, which is worse than not stating them.**
  `AGENTS.md` had asked for `region` on a measured finding since the schema was written, and
  `validate_frontmatter.py` never read the key — so a note whose title is literally about measured
  timings had been sitting in the tree with no region, its environment recorded only in prose where
  no gate could see it. A stated-but-unchecked rule reads as enforced, so nobody looks. `region` is
  now required whenever `evidence: verified`, and the error names the alternative: if the
  environment cannot be named, the tier is wrong rather than the field optional. Two notes were
  filled in from values their own bodies already stated.
- **A misspelled frontmatter key passed silently.** `regoin: ap-northeast-1` satisfied nothing and
  failed nothing: the value sits in the file where a reviewer reads it as present, while every gate
  ignores it. That is strictly worse than the key being absent, which at least fails a required-key
  check. Keys are now validated against a known set, `industry` and `scale_band` included for case
  studies, and an unrecognized key is an error rather than an extension point. Raised by a sibling
  repository weighing whether to add measurement metadata to its own frontmatter — the missing
  known-key check was the reason to say not yet.
- **The documented way to install the pinned toolchain did not work.** `pip install -r
  requirements-dev.txt` assumes a `pip` on `PATH` and a Python that accepts `--user`; on a Homebrew
  Python it is refused by PEP 668, and `pip` is often not present under that name at all. Harmless
  while a version mismatch was only a warning, and a dead end once the gate started failing — which
  is what happened on the first dependency bump after that change. `make python` now resolves
  `.venv/bin/ruff` before anything on `PATH`, so `PATH` order stops deciding which linter runs, and
  both a venv and a pinned `pipx` install are documented. This was the actual cause of the local
  0.15.20 / 0.16.x divergence: a Homebrew copy was shadowing the pinned one.
- **Validators walked into gitignored directories.** Creating a `.venv` made `make audit` fail on an
  SBOM inside an installed package, where a build path looked like leaked PII — a real finding by
  the rule, meaningless in substance, and the kind that turns a gate into something to work around.
  The skip list is now shared from `tools/frontmatter.py`, and a test fails when a gitignored
  top-level directory exists on disk but is missing from it, so the next tool needing a cache
  directory is covered rather than discovered the same way.
- **Three gates reported success when the tool they depend on was absent.** `make markdown`
  printed "skipping", `make audit` printed "skipping secret scan", and `make python` fell back to
  `py_compile` — a weaker check under the same name. The second one mattered most: gitleaks is not
  installed in CI's docs-quality job, so that half of `make audit` was decorative on every run
  there. All three now exit non-zero with an install line. Secret scanning is split into
  `make secrets` so the two questions cannot hide inside one target, and full-history scanning
  stays in `.github/workflows/gitleaks.yml`. `scripts/tests/test_gate_integrity.py` runs each gate
  with the tool removed from `PATH` and fails if it succeeds — which is how the `py_compile`
  fallback was found, after the other two had already been fixed.
- **The irreversibility guard that was actually running covered less than the one under review.**
  The `PreToolUse` hook pointed at a copy under `$HOME/.kiro/`, not at the tracked
  `scripts/guard_irreversible_ops.py`. Measured against the tracked file's own corpus, **10 of its
  26 documented cases were permitted by the copy that ran**: S3 Object Lock, Glacier Vault Lock,
  Backup Vault Lock, EBS snapshot lock, the ONTAP REST audit-log `POST`, a locking snapshot policy
  with a retention period, `-snaplock-expiry-time` at snapshot creation, and a SnapMirror
  long-term retention rule. `AGENTS.md` described mechanical enforcement and pointed at
  `--selftest` for proof, so the artifact being verified was not the artifact being enforced.
  The hook now runs the tracked file, and `scripts/tests/test_hook_wiring.py` fails if it stops
  doing so. Confirmed by real firing: the guard blocked a verification command issued during this
  change, which is the trap the in-file corpus exists to avoid.
- **`scripts/check_agent_context_budget.py` skipped its own steering checks in CI.** They were
  guarded by `if STEERING.exists()`, and `.kiro/` is gitignored, so the loader-thinness and
  authority checks did nothing there while the target still printed `healthy`. Absence is now
  reported on stdout instead of passing silently.
- **A note whose filename began with `_` was never validated.** The scaffolding skip in
  `tools/validate_frontmatter.py` tested every path component including the filename, so a
  `_draft.md` inside a real `notes/` directory had no evidence tier checked and produced no
  message. Scaffolding is now determined by directory only; `_template/` stays exempt.
- **The pinned-`ruff` mismatch was a warning that was easy to walk past** — the same silent
  divergence it warned about. `make python` now fails, and says to check `which -a ruff` for a
  second binary shadowing the pinned one, which is what was happening locally (0.15.20 ahead of
  the pinned 0.16.1 on `PATH`).

### Added

- **English counterparts for the three remaining settled primary notes.**
  `counting-bytes-is-not-counting-files.md` (Assess Q1), `deployment-type-is-decided-once.md`
  (Design Q1), and `what-iac-cannot-reach.md` (Build Q1). With the previous pair, **every module whose
  first question has a settled answer now has one in English.** `data-utilization` Q1 is still
  Japanese-only on purpose: its primary note changed the same day, so it fails the settled-content
  condition, and substituting a different note would answer a question nobody asked.
  - Twenty inbound links moved off their Japanese fallback, with **eleven Japanese anchors mapped to
    English headings** across three notes plus two outbound targets translated earlier.
  - **The bulk-prefix mistake from the previous batch is now structurally avoided.** File links are
    rewritten one filename at a time; the shared `notes/` directory link is rewritten unconditionally,
    because a directory link cannot 404 once the English directory exists. That split is what the
    earlier three broken links were teaching.
  - Also fixed while translating: the relinking pass rewrote the *new* English file's own switcher,
    pointing its 日本語 link into English. Regenerating with `sync_lang_switcher.py` restores it, but
    the pass now skips its own target.

- **English counterparts for two notes that were the primary answer to a module's first question.**
  `security-style-and-permission-evaluation.md` (Multiprotocol & Identity, question 1) and
  `monitoring-fails-on-averages.md` (Operate question 1, and Optimize question 1 links to the same
  note). Both satisfy the two conditions in `docs/agent/localization.md`: primary answer reachable from
  a module README, and content settled — unchanged since 2026-08-30. **The notes corrected this week
  are deliberately excluded**; translating a note that is still moving multiplies every later edit.
  - Adding a counterpart is mostly not translation. It moved **sixteen inbound links** off their
    Japanese fallback, which `switcher-check` requires, and **four of those carried Japanese anchors**
    that had to be mapped to the English headings. The `(日本語)` markers on those rows are dropped
    with them.
  - Section parity is now enforced for both pairs. **Verified by removing a heading from an English
    file and confirming `check_i18n_parity.py` fails**, rather than assuming the gate reaches Tier 3.
  - One trap worth recording: rewriting the shared `notes/` directory prefix in bulk also redirected
    links to *untranslated* notes in the same directory, which `make links` caught as three missing
    files. A per-file rewrite is not safe; the target must exist in English first.

- **The lockout threshold and the absence of an automatic unlock are readable from the role config,
  without locking anything.** `security login role config show -role fsxadmin -instance` at advanced
  privilege reports `Maximum Number of Failed Attempts: 5`, `Delay after Each Failed Login Attempt:
  4 secs`, and `Account Lockout Duration: -` — unset, so a locked account does not come back on its
  own. Five attempts is easy to reach in an account holding two `fsxadmin` secrets that share a
  username, and the only way back is the password reset. `Disallow Last 'N' Passwords: 6` also means a
  recovery routine must generate a fresh value each time.
- **`fsxadmin` locks out, and over REST the lockout is indistinguishable from a stale password.** Both
  return `401`, so a correct stored credential looks like a wrong one; only SSH says
  `Account currently locked`. Recovery is the Amazon FSx API password reset — ONTAP's
  `security login unlock` needs an admin login, which is circular — and the reset cleared the lock.
  What makes this easy to cause: `fsxadmin` is a separate account per file system but the username is
  shared, so trying the wrong secret records a failed login against a real account elsewhere. SSH
  reports the running total as `Unsuccessful login attempts since last login`; REST does not.
- **A deleted volume holds its space for 12 hours, and the recovery queue is only visible at advanced
  privilege.** `volume delete` places the volume in a recovery queue under a renamed key
  (`<name>_<number>`), so aggregate free space does not move until the retention period elapses or
  `volume recovery-queue purge` is run. Relevant to any create-and-delete verification loop, where the
  space appears released and is not.
- **Volumes created through the ONTAP CLI reach the Amazon FSx API asynchronously, with an
  inconsistent delay — and the same lag on deletion blocks the SVM deletion.** Four surfaced in
  `DescribeVolumes` within minutes while a fifth had not appeared after 28 polls over more than seven
  minutes, in the same session on the same file system. In the delete direction a volume removed
  through the ONTAP CLI lingered in the Amazon FSx inventory for over five minutes, and
  `DeleteStorageVirtualMachine` refused the whole SVM citing volumes that no longer existed;
  `aws fsx delete-volume` against the stale record is accepted and clears it. Automation should
  create *and* delete through the Amazon FSx API — mixing the two paths is what stalls.
- **SMB logon auditing, measured end to end on a workgroup SVM.** `cifs-logon-logoff` does write
  4624 / 4625 / 4634 to EVTX, on an AD-joined SVM and on a workgroup SVM with local users alike.
  Four notes carry it: what each audit category actually emits, why the audit destination filling up
  denies client access, why local-user inventory has no source other than the audit log, and why some
  SVMs cannot serve SMB at all. The measurements that most change a design: **4624 counts SMB
  sessions, not logins** — three `net use` / `net use /delete` cycles produced one 4624, because
  `net use /delete` drops the share mapping and leaves the authenticated session up — and **4634 only
  appears when the client sends a graceful logoff**, not on connection loss and not on an
  administrative `vserver cifs session close`. NTFS volumes also need a SACL before any file-access
  event appears at all, and applying a security descriptor from the ONTAP CLI replaces the DACL,
  which denied access to a user that had been reading the share moments earlier.
- **`data-cifs` on a data LIF is decided at SVM creation and cannot be added afterwards.** Three SVMs
  in the verification account cannot serve SMB: 445 stays closed even though `allowed-protocols`
  includes `cifs`, `vserver cifs create` succeeds and the CIFS server reports `up`. The fsxadmin role
  pins `network interface service-policy` to `readonly`, so neither the CLI, the ONTAP REST API, nor
  the Amazon FSx API can add it — the only route is a new SVM and a data migration. Nine SVMs across
  two file systems place the change between 2026-06-09 and 2026-06-24; a non-AD SVM created on
  2026-09-01 does get it, which is what rules out the AD-versus-non-AD explanation.
- **The noun-phrase heading rule now names the genres it does not apply to.** The rule assumes a
  heading is a label, and three genres break that assumption: chronological narrative, advice whose
  imperative mood *is* the content, and a stated goal or intention. Nominalizing those destroys the
  content — `心身の状態を整えておく` becomes `心身の状態の調整`, which is no longer advice. The test is
  whether the heading could serve as an entry in an index. The genres were found by surveying 109
  personal blog posts from 2019 to 2023; **none of them exist in this repository**, so the exemption
  changes nothing here today. It is recorded because a mechanical check cannot tell narrative from a
  label, and without it the next reader converts a timeline.
- **Japanese section headings are now required to be noun phrases, which supersedes the Japanese half
  of the action-first heading rule.** `はじめる` and `自分の環境で確かめる` were what "action-first"
  produced in Japanese, and a verb form, a question form, or a full predicate reads as a sentence
  fragment where a Japanese reader expects a label. Action-first still governs the *subject* of a
  heading — `はじめかた`, not `前提条件`. The nominalization has to keep the assertion: a heading here
  often carries the finding, so `監査は 2 つの面に分かれ、片方に穴があります` →
  `監査の 2 つの面と片方の穴` would degrade "there is a hole" to the noun "hole"; the claim is carried
  by a suffix instead (`片方の穴の存在`). The H1 and the frontmatter `title` are exempt, being a
  one-line claim by a separate convention. Recorded in `CONTRIBUTING.md`, with the conversion table
  and the anchor procedure in `docs/agent/documentation-design.md`.
  **151 headings across 34 files predate the rule and are not yet converted** — 100 verb or question
  forms and 51 predicates, of which 15 are listed in `docs/agent/external-anchor-contract.txt`. The
  bulk conversion is deliberately a separate change so this one stays readable, and the mechanical
  check comes with it rather than before it: a gate that fails on 151 pre-existing headings is a gate
  that gets switched off. Documents added from here on comply, so the two spellings coexist until the
  migration lands — that is visible inconsistency, accepted deliberately rather than by omission.
- **Two notes on hosting AI/ML training data, taken from a semiconductor defect-classification write-up
  and then checked against the AWS documentation.** The source article is explicit that it is an
  educational mimic — no ONTAP runs in it, and neither the FlexClone capacity saving nor the FlexGroup
  throughput was measured — so it is cited as the source for where the workflow friction sits, not for
  any behaviour. The primitives it maps to (Snapshot for dataset versions, FlexClone for experiment
  branches, FlexGroup for the image repository) each turned out to carry a constraint the article does
  not mention, and those constraints are what the notes are about.
- **A dataset version placed on the default snapshot policy is deleted by rotation within days.** The
  `default` policy keeps six hourly, two daily and two weekly snapshots and rotates them, so a
  three-month-old version does not exist. Two further ways a version disappears: the 1,023-per-volume
  ceiling, after which no new snapshot can be taken until one is deleted, and autodelete, which
  removes snapshots when the volume runs low on space — meaning versions vanish on the day capacity
  gets tight, and nobody notices until an experiment fails to reproduce.
- **Experiment branching with FlexClone runs out of volumes, not capacity, and clones do not inherit
  the parent's QoS.** The ceiling is 500 volumes per HA pair and 1,000 across all pairs, with FlexGroup
  constituents counting toward it at a default of eight per aggregate — so branches can exhaust the
  budget the production volumes need. Separately, a QoS policy group set on the parent does not carry
  to the clone, which makes "the production volume is throttled, so we are safe" false: thirty clones
  place thirty clones' worth of demand. Bounding the total requires a shared policy group, and
  `is-shared` cannot be changed on an existing policy.
- **Expanding a FlexGroup invalidates every dataset version taken before it.** Adding constituents
  turns all earlier snapshots into partial copies that cannot restore the volume, and breaks
  incrementality for Amazon FSx backups, AWS Backup and SnapMirror. Constituents cannot be removed.
  Growing the image repository and being able to reproduce an earlier experiment are therefore
  traded off by a single operation, so expansion has to be treated as a version boundary and decided
  before, not after.
- **The governed self-service model is recorded as `hypothesis`, with its audit gap named.** Each
  component has a source — `vsadmin` scoping, the ONTAP REST API path, QoS policy groups, the volume
  ceiling — but the combination has not been built or run here. Whether an operation issued through
  the ONTAP REST API appears in CloudTrail was **not** verified; CloudTrail records Amazon FSx API
  calls, and an HTTPS request to an SVM management endpoint is not one, so a design that assumes
  CloudTrail alone may leave self-service operations recorded nowhere. That check is the first
  verification step in the note rather than an assertion in its body.
- **Restore duration can reverse the first-generation recommendation.** The second generation lets
  clients mount and read while a restore is still running, once metadata loads — and metadata is 1-7%
  of the backup data. At small volumes that buys little against a higher floor. At tens of TB it is
  the difference between waiting for the whole restore and serving users after a fraction of it, so
  the recommendation is now conditional on data volume and on whether the RTO is measured in hours or
  days. Neither generation reaches SnapMirror, where the destination volume already exists.
- **No public measurement of a large restore was found, and the note says so.** AWS blogs, re:Post,
  the knowledge center and the documentation were searched for a restore duration stated together
  with a data volume at 10 TB or above; none was found as of 2026-08-29. Recorded as an absence with
  its date and scope rather than filled with a derived figure presented as measured.
- **The crossover volume moves with provisioned throughput, so the comparison is now two-dimensional.**
  Stating a single crossover implied the always-on side has one cost, when throughput is most of its
  floor. The note says the crossover rises with provisioned throughput and falls toward the minimum,
  so a comparison has to pair a data volume with a throughput rather than quote one number.
- **A DR standby belongs on the first generation, and that is a decision taken before it exists.**
  The first generation offers 128 / 256 / 512 / 1,024 / 2,048 MBps where the second starts at
  384 MBps, and a standby is sized for the replication transfer and the reads just after failover,
  not for production load. The deployment type cannot be changed after creation, so moving between
  generations means a restore or a migration.
- **What "no destination file system in steady state" is exchanged for.** Not paying for throughput
  and SSD is a real advantage, and the counterweight is that the same work arrives at failover:
  creating the file system (20 minutes measured) and the SVM, restoring the volume (13-16 minutes
  measured), then recreating export policies and SMB shares, rejoining the new SVM to Active
  Directory, and repointing clients because the new file system has different DNS names and IPs. The
  first three finish on their own; the rest need a person, during an incident. A SnapMirror design
  skips the first three and has the SVM already joined.
- **The native `CopyBackup` path has no cross-Region transfer charge that could be found.** The
  `AmazonFSx` price list contains no transfer usage type at all, for any Amazon FSx file system type,
  and the FSx for ONTAP pricing page scopes its data transfer line to S3 Access Point access.
  Backups live in AWS-managed S3 rather than in the customer VPC, so the copy is not egress from an
  ENI and does not have the shape those charges apply to. Recorded as `unverified` rather than as
  "free": absence from a price list is not proof, and it was not reconciled against a bill.
- **The data-protection comparison matrix carries the replication-versus-copy split too.** The table
  already used 複製 for SnapMirror and コピー for backup copies, but never said the two words describe
  different operations, so a reader could take both rows as answers to the same question. The new
  section states what sits at the destination in each case and links to the note. `復元` became
  `リストア` in the same file, so the two documents no longer disagree on the word.

- **"Running a destination file system costs more" holds only below a certain data volume.** The
  SnapMirror comparison listed paying for destination capacity and throughput as a standing
  trade-off, which reads as though a minute-level RPO always costs more. It does not, and the reason
  is in the rate structure: the Standard capacity pool rate is below the backup storage rate, backups
  accumulate across retained generations while the file system stores one copy, and the provisioned
  charges have minimums that put a fixed floor under the always-on side. The floor divided by the
  per-GB gap is a crossover volume; above it the always-on destination is the lower monthly figure
  while still carrying the better RPO, RTO and failback path. Two qualifiers travel with it: the
  capacity-pool advantage is Single-AZ only, since the Multi-AZ rate is close to backup storage, and
  `All` tiering does not remove the floor because file metadata always stays on SSD. The second
  generation's minimum throughput is three times the first's at a higher rate, so the same "minimum"
  standby file system has a very different floor - pick the generation before sizing. No unit prices
  are tabulated in the note; rates are revised, and the cost note already set that convention.
- **Going through AWS Backup does not change the backup storage rate.** FSx for ONTAP is not a
  resource type AWS Backup fully manages, so the storage charge appears under FSx for ONTAP rather
  than under AWS Backup - only a logically air-gapped vault moves all storage and transfer to
  AWS Backup. The same document states that for those resource types the cross-Region transfer is
  billed to the *destination* account, which decides where the bill lands in a cross-account design.
- **The KMS key for a cross-account backup copy is decided before the file system exists.** AWS
  Backup does not support a cross-account copy under an AWS managed key for a resource type it does
  not fully manage, because an AWS managed key's policy cannot be edited or shared across accounts —
  and FSx for ONTAP sits on that side. The measured cross-Region copy here did *not*
  meet that condition: the destination vault was left at its default, so the key was
  `alias/aws/backup` with
  `KeyManager: AWS`, and the copy still succeeded. That is looser than the general documented
  statement, so the two paths cannot be described under one condition. The design consequence is on
  ordering, not on configuration: a file system's KMS key is fixed at creation and
  `update-file-system` has no argument that changes it, so a customer-managed key is a decision that
  precedes the file system. Recorded with the cross-Region result as `verified` and the
  cross-account restriction as `documented`, since it was not measured.
- **Region exceptions to the copy paths are enumerated rather than summarized.** Cross-Region copy
  is unavailable for FSx for ONTAP, Lustre, Windows File Server and OpenZFS in Middle East (Bahrain)
  and Middle East (UAE); both cross-Region and cross-account copy are unavailable for FSx for ONTAP
  in Asia Pacific (New Zealand), China (Beijing) and China (Ningxia). The China entry needs the
  narrower reading: AWS Backup's own document history carries a same-day item about cross-account
  copy in the China Regions, which is about AWS Backup as a whole and does not extend to
  FSx for ONTAP.
- **The "previously not possible" row now carries the reading that disagrees with it.** A NetApp
  Community article holds that same-account cross-Region `CopyBackup` worked before the launch. The
  note states the three pieces of material behind the table's "not possible" — the 2026-07-05 archive
  of the ONTAP user guide lists no Copying backups subpage and limits restores to the same Region,
  `copy-backups.html` has no Internet Archive snapshot at all, and the What's New text describes the
  prior state as same-Region and same-account — and then says plainly what is not established:
  whether the API accepted an ONTAP backup before the launch. Documentation silence is not an API
  refusal, so that point stays `unverified`, and neither reading changes the date for AWS Backup
  cross-Region copy or for any cross-account copy.
- **Replication and copy are separated as terms, not just as mechanisms.** A new section in the
  data-protection note states what sits at the destination in each case: SnapMirror replication puts
  a `DP` volume there that follows the source, while an AWS Backup or `CopyBackup` copy puts a
  recovery point there that does not. The consequence is on the RTO — replication promotes a volume
  that already exists, a copy starts from creating a file system and an SVM.
  AWS's own wording splits the same way, and the console confirms it: Copy jobs, Copy rule and
  `Copy type` (observed 2026-08-29). Replication is the word for mechanisms whose destination tracks
  the source, as in Amazon S3 Cross-Region Replication. So "cross-Region replication with AWS
  Backup" reads as a tracking volume that is not there, and calling SnapMirror a backup misses that
  a file deleted on the source leaves the destination's current state after the next transfer.
  SnapVault is named as a third mechanism, and the note says plainly that backup copies do not
  create an ONTAP SnapVault relationship.

- **AWS Backup's cross-Region copy and restore for FSx for ONTAP, measured.** The note previously
  described that path from documentation only. Both halves are now measured on the same Tokyo to
  Osaka route: an on-demand backup (4 m 02 s) plus an on-demand copy job (8 m 35 s), and a
  plan-triggered backup (30 m 06 s, of which about 24 minutes was the start window) whose copy rule
  fired on its own (6 m 31 s), then a console restore (16 m 16 s). All five sha256 values matched,
  and the symlink, `0640` mode, UTF-8 filename, nested directories and mtimes survived.
  Four behaviours that change how the console is used: a plan-triggered job waits in `CREATED`
  inside the start window; the AWS Backup restore form checks "Enable storage efficiency" by
  default even when the source had it off, unlike the FSx for ONTAP console which pre-selects the
  source value; `SecurityStyle` comes back empty, which reproduces on this path what had been seen once on
  the other; and `BackupSizeInBytes` reads 0 while restore progress sits at `0.00%` for the whole
  16 minutes, so neither is a signal to alert on.
  Teardown carries a trap: an `EXPIRED` recovery point blocks vault deletion for several minutes
  while the underlying FSx for ONTAP backup is still `AVAILABLE`, and `delete-backup-vault` refuses
  with "contains recovery points" during that window.
  7 masked console screenshots under `docs/_assets/images/png/awsbackup-copies/`. English console,
  unlike the Japanese FSx for ONTAP screens, and said so where they appear.

- **The cross-Region backup copy diagram, generated rather than drawn.** The backup-copies note and
  both article drafts carried an ASCII-art figure. It is now a draw.io diagram built from a spec in
  `tools/build_diagrams.py`, with official AWS Architecture Icons from the current quarterly package
  embedded as data URIs, shipped in four files: Japanese and English, light and dark. `make diagrams`
  regenerates and exports; `make diagrams-check` fails on a hand edit. Neither is in `make all`,
  because both need the icon package and the package is never committed.
  The figure draws two paths rather than one, which is the point: the native `CopyBackup` reaches
  another Region inside one account with no scheduler, and AWS Backup reaches another Region and
  another account on a plan. The single arrow in the ASCII version is how a reader came away thinking
  cross-account copies arrived with the native path.
  Backups and recovery points are named boxes, not icons. The only backup marks in the AWS package
  are AWS Backup marks, and using one for the native copy would attribute the native path to AWS
  Backup — the exact confusion the figure exists to remove.

- **Backup copies across Regions and accounts, verified end to end.** New note
  `docs/ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md`, covering the
  August 2026 capability and the boundary around it: the restore target is still confined to the
  backup's own Region, so the destination file system and SVM have to be created at recovery time and
  that lands on RTO — 20 minutes measured. A Tokyo → Osaka copy and restore were reproduced
  (`ap-northeast-1` → `ap-northeast-3`, 2026-08-28): copy 7 m 15 s, restore 13 m 21 s, all five sha256
  digests matching after restore, with mode bits, symlink target, and a UTF-8 filename preserved, and a
  file added after the backup correctly absent. A backup whose source volume had already been deleted
  copied successfully. Two observations corrected working assumptions: **`OntapVolumeType` reads `DP`
  while a restore is in progress and becomes `RW` on completion** — caught only because a write probe
  from the client succeeded, and confirmed transient by a second restore that stated `RW` explicitly
  and still reported `DP` while `CREATING`; and **`CreateBackup` on a FlexGroup volume is accepted and
  then fails asynchronously** with a message that names no cause, recorded as a single unreproduced
  observation rather than a general claim, since the documented restriction is on *copying* FlexGroup
  backups and no `AVAILABLE` FlexGroup backup was ever produced to exercise it. Durations are stated
  with the caveat that at 9.4 MiB fixed overhead dominates and incrementality could not be
  demonstrated. Copy limits and the transient-`DP` behaviour are also recorded in
  `docs/ja/reference/limits/README.md`.
- **Console-only behaviour recorded for the copy and restore paths.** Six observations that the CLI does not
  surface, measured 2026-08-28: the copy form's destination Region **defaults to the current Region**, so
  leaving it produces an in-Region copy; changing the destination **switches the displayed KMS key to that
  Region's default key**, which is what "incrementality requires the same KMS key" means in practice; the
  restore dialog makes the **SVM a required field** on top of the file system; **the volume size field
  defaults to 1 TiB** even for a 1 GiB source, which alone fills a 1,024 GiB destination; the volume detail
  page shows `DP` during a restore even when RW was selected in the form; and that page **does not
  auto-refresh**, so it kept showing `DP` after the API had returned `RW`. The restore dialog also offers to
  enable SnapLock, which is called out as not a field to set in passing.
- **`recent-updates.md` gained a section on how updates are tracked.** This capability has two What's
  New posts and **no entry in the ONTAP User Guide document history**, which is how the stale
  constraint recorded under Corrected survived. Following the document history alone is not sufficient,
  and the AWS Backup What's New feed carries items that never appear on the FSx for ONTAP side.
- **A suppression marker that suppresses nothing is now an error.** `audit_public_output.py` holds the
  category vocabulary twice: as `CATEGORIES`, and as alternatives inside the regex that parses a line's
  `<!-- allow:... -->` marker. Only one direction was checked — the file-level `audit-file-allow`
  rejects an unknown category, while the line-level marker accepted whatever the regex matched.
  Demonstrated rather than assumed: renaming the category in the tuple and in the reporting side while
  leaving the regex alone leaves `allow:role-label` parsing successfully, joining the allowed set, and
  matching no finding, so an author who believed they had suppressed a finding still sees it reported.
  The harm is not the visible failure but the lost decision — the marker is a claim that someone read
  the finding and accepted it, and a dead marker discards that, leaving the next person with a CI
  failure and no record of why it was once allowed. Found by a sibling repository in its own copy of
  this file; the duplication is kept for the reason they gave, that a regex is not a list and
  assembling it at import time hides it from where a reader looks.
- **The declared vocabularies are now checked against the directory tree.** `LIFECYCLE`, `DOMAINS` and
  the two language lists restate what the layout already shows — `docs/ja/playbooks/01-assess` and
  `lifecycle: assess` are one fact written twice — and nothing noticed if they stopped matching. All
  four happened to agree; the exposure was that agreement could not be observed. Prompted by a sibling
  repository finding the same shape in its own tooling, a repository name held as a constant that git
  already knew.
  **Deriving would have been the wrong fix, and the difference matters.** Their constant had an
  authoritative source. These do not: the vocabulary *is* the authority and the tree conforms to it, so
  reading it off disk would invert that and a directory created with a typo would silently widen what
  the validator accepts instead of being rejected by it. The duplication stays and the divergence became
  an error. Both directions are checked, because each catches a different mistake — a declared value
  with no directory is usually a leftover rename, while an undeclared directory is a typo whose notes
  would be rejected with a confusing message. The two language lists are also compared with each other,
  since two tools carrying one list is how one of them falls behind.
- **`make pr-verify PR=<n>` confirms CI passed for the commit a pull request will actually merge.**
  `gh pr checks` answers a different question: it reports the latest results rather than results for
  the current head, so pushing one more commit and re-reading it returns the previous commit's verdict
  with nothing marking it stale. Both halves of that failure happened here — #53 was merged over a
  failing gate, and #55 nearly consumed a stale result after a CHANGELOG commit landed between reading
  the checks and merging. A procedure that must be remembered at exactly one moment is more expensive
  than a command, an argument made by the sibling repository that had reached the same conclusion.
  Every lookup is keyed on the head SHA, **a workflow that has not started for that SHA is a failure
  rather than a pass** (that being precisely what a stale read produces), and a path-filtered workflow
  is reported as filtered rather than missing so the gate does not claim a false absence. Verified
  against #53, which it refuses, and #55, which it accepts.
- **Past merges were audited by SHA rather than from memory.** Prompted by the sibling repository
  auditing its own seven: memory does not retain which commit a check result belonged to, so
  "I read the checks every time" is not an answer. Thirteen merged pull requests were re-checked with
  the merged head SHA as the key. One had failed (#53, already corrected); the other twelve had passed
  against the commit that was merged.
- **The claim that a tool is copyable is now a test.** `AGENTS.md` invites a reader to copy
  `guard_irreversible_ops.py` into their own repository, and two more tools were described the same
  way to a sibling repository. Those were promises, and a promise breaks silently: the moment a
  portable file reaches for a project path or a sibling helper it stops being portable while every
  other test still passes. The pattern comes from that sibling repository, which wraps its own
  copyable block in a test that executes it in an isolated namespace. Applying it here found a defect
  in the first minute: the instruction given for `check_anchor_contract.py` named one helper to copy
  alongside it, and that helper has a dependency of its own — following the instruction produced an
  `ImportError`. Each copy set is now staged into a temporary directory outside the repository and
  imported there, because import success inside this tree answers a different question. The test also
  fails when a set lists a file that is not needed, so the list does not quietly grow past the truth.
- **Table literals are now compared across languages, and externally cited anchors are pinned.**
  Both came from a sibling repository reporting a defect it had hit itself: it corrected an evidence
  attribution in Japanese, left the English row stale, and `make i18n-check` stayed green because it
  compares heading structure only. Reproducing the exposure here went wrong first, instructively. A
  whole-file tokenizer stripping link targets with a pattern that spans newlines deleted entire table
  rows, then reported the deleted values as "English only" - every finding it produced was
  fabricated. Counting occurrences was wrong too: how often prose mentions a number legitimately
  differs between languages. What survives is line-scoped, table-cell-only, and compares sets in
  **one direction** - a translation may omit a value but may not carry one the Japanese reference
  lacks, which is precisely the shape of a stale translated row. Six hubs carry a deliberately
  reduced table, and requiring both directions reported every measurement they leave out. Broken
  three ways before being trusted.
- **`make anchors`** records the section anchors of documents other repositories cite. A renamed
  heading now fails the gate instead of failing silently elsewhere: GitHub answers an unknown
  fragment with the top of the page, so the citing side keeps rendering a link that lands in the
  wrong place, and neither repository's link checker can see it - one resolves anchors only inside
  its own tree, the other does not have the tree. The snapshot duplicates data on purpose; that
  duplication is what turns a rename into a diff someone has to acknowledge.
- **Read-only through the bound identity alone, and the message that tells you which layer refused.**
  A sibling repository is changing its access point template default from UID 0 to a non-root user
  and asked for the measurement behind it, having only "root is a measurement condition, not a
  recommendation" so far. Measured: on a root-owned `755` volume, an access point bound to `nobody`
  **with no policy attached** serves `GetObject` and refuses `PutObject`, while the root-identity
  control on the same volume from the same caller writes. Read-only holds in Layer 2 on its own.
  Answering the question also turned up the trap it invites: this repository's own "read-only"
  access point does carry a non-root identity, yet what stops writes there is an explicit deny in its
  policy — **binding a non-root identity is not by itself read-only**, and the name says nothing
  about which layer acts. The three denials are now distinguishable from the error text, all three
  measured in one environment: an unqualified `Access Denied` is Layer 2, so searching the policy for
  it wastes the triage. Added to the decision tree's symptom table for the same reason.
- **`evidence-policy.md`: what the tiers do not answer** — a new section in all eight languages,
  prompted by a sibling repository whose own vocabulary distinguishes "documented but not chased on
  hardware" and "searched and found nothing", and which asked whether tiers should be added here to
  match. They should not, but the boundary was implicit and that is where a cross-repository link
  changes meaning. Now stated: a tier records **where a claim comes from**, not how far it was
  chased, so `documented` never implied that anyone reproduced it and the first of those two maps
  onto it without loss. The second is a statement about the documentation rather than about the
  product, so it is not a tier at all — it goes in the body with the date and scope of the search.
  Reaching for `hypothesis` there is the specific error the section names, because `hypothesis`
  asserts that a reasoned expectation exists. Summarized in `AGENTS.md` as well, since an agent
  deciding a tier reads that file and not this one.
- **The network layer of S3 access point authorization, and the two AWS pages that document it.**
  A sibling repository asked for one fact to be published so it could correct 15 documents against
  it: that an `Internet` origin access point *is* reachable through an S3 gateway endpoint. The note
  did not record which origin the `aws:SourceVpce` rows were measured on, and the records that would
  have settled it were not available — so it was re-measured from scratch rather than inferred, with
  the control the first run lacked. Changing only the condition value to a non-existent endpoint ID
  denies the same EC2 instance, which is what separates "the value matched" from "the condition is
  not evaluated on an Internet-origin access point". Reachability is decided by the caller subnet's
  routing, not by the origin type.
- **A layer the note was missing: the VPC endpoint policy.** Found while looking for the ARN
  primary source. [Configuring network access for Amazon S3 access
  points](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)
  enumerates the authorizing layers and independently documents the same-account union this
  repository had measured, so the central claim now carries both a measurement and a citation. Added
  with it: condition-key availability — `aws:SourceVpc` / `aws:SourceVpce` / `aws:VpcSourceIp` exist
  only on a request that traversed a VPC endpoint, `aws:SourceIp` only on one that did not, and the
  last two are mutually exclusive, so restricting by source IP through an endpoint with
  `aws:SourceIp` compares nothing. Also that gateway endpoints do not route traffic entering the VPC
  from VPN, Direct Connect, Transit Gateway or peering, which is the documented explanation for
  on-premises callers being denied while in-VPC callers succeed.
- **A primary source for the access point ARN form**, which had been carried as unverified agent
  knowledge. The troubleshooting page names it as a failure mode: service roles created
  automatically by other AWS services may reference the alias as a bucket-form ARN, and the fix is
  the access point ARN form.
- **The file-system half of S3 access point authorization, measured.** The access point note
  previously covered only AWS-side policy evaluation, which left the most common `AccessDenied` —
  the one with no policy involved at all — unexplained. Added, each with a control in the same
  session: changing only the volume root's owner and mode bits flips `PutObject` between
  `AccessDenied` and success with no access point policy attached, so the two layers are
  independent; neither LDAP nor an Active Directory join is required, since an SVM-local UNIX user
  and a **workgroup-mode** local Windows user both served reads and writes, which is broader than
  the AWS troubleshooting page states; ONTAP file access auditing records only the SID of the bound
  identity, with `SubjectUserName` unresolved and a `SubjectIP` that is an AWS service address
  varying between two requests of one session, so neither the caller nor its address is recoverable
  from the audit log alone; and a UNIX-style volume carrying only mode bits produced **zero** audit
  records with auditing enabled on the SVM, while the NTFS control produced two — attaching an audit
  ACE via SLAG then broke the data path in both directions, for reasons left explicitly unconfirmed.
- **`reference/limits/`: the SVM ceiling depends on throughput capacity** — 6 SVMs at 128 MBps,
  measured from the refusal message. Recorded because the remedy for hitting it is raising
  throughput capacity, so verification SVMs consumed early can block a production one later.
- **`make test` (42 tests, stdlib `unittest`, no new dependencies), wired into `make all` and CI.**
  The repository previously had no tests at all, so every gate was trusted on the evidence that it
  printed success. Each suite is written to fail on a deliberate break rather than to confirm a
  clean tree:
  - the guard's **block / ask / allow** contract driven through a real subprocess and stdin event,
    because exit 2 is the only code that blocks and any other non-zero silently continues;
  - `.PHONY` completeness, since `docs/`, `scripts/`, and `tools/` exist as directories and an
    undeclared target of the same name makes `make` report "up to date" without running anything;
  - one synthetic break per documentation gate — evidence tier promoted without `verified_on`,
    a role-labeled callout, forbidden naming, vendor-versus phrasing, cross-language section
    drift, a broken internal link, a hand-edited language switcher;
  - hook wiring: matchers that compile and match real tool names, no over-escaped `\\\\.` pattern,
    no undocumented `$KIRO_*` variable, no command ending in `|| true`, block-intent hooks using a
    `command` action on a trigger that can actually block;
  - test discovery: every directory holding `test_*.py` must appear in the Makefile's `TEST_DIRS`.
- **A third verdict in the guard: `ask`.** Destructive-or-opaque calls now prompt instead of
  passing — `delete-file-system` / `delete-volume`, which can return success while silently not
  deleting behind an unexpired WORM log, and `create-volume --cli-input-json file://…`, whose
  payload the guard cannot read.

### Changed

- **163 Japanese section headings across 36 files are now noun phrases, and `make lint` enforces it.**
  The rule landed in #77 and #79 with nothing enforcing it and every pre-existing heading in breach;
  this is the conversion plus `tools/check_heading_style.py`. They ship together on purpose: a gate
  that fails on 163 headings it did not cause is a gate that gets switched off. Assertions are carried
  by a suffix rather than dropped — `監査は 2 つの面に分かれ、片方に穴があります` became
  `監査の 2 つの面と、片方の穴の存在`, not `監査の 2 つの面と片方の穴`. 115 inbound anchor references
  were rewritten in the same commit.
- **Two boundaries in the detector were wrong, in opposite directions, and each was found only by
  running it against the whole tree.** `れ` was in the verb-ending character class; it is え-row, not
  う-row, so no dictionary-form verb ends in it and a bare `れ` ending is a nominalized 連用形 —
  `流れ`, `崩れ`, `遅れ` are nouns. That flagged an open-ended class no allowlist could have closed.
  In the other direction `ない` was missing, because it ends in い and the class excludes い so that
  `問い` and `扱い` stay clean; listing `ない` by name found twelve predicate headings the first run
  had passed. `make headings` now runs `--selftest` before the real check, so the gate proves it can
  still flag before it reports a clean tree.
- **20 anchors in the external contract moved, and no external citation actually consumed them.**
  The contract records every anchor of an externally cited *document*, not the anchors that are
  cited, so a `GONE` entry is a possible break rather than a confirmed one. The citing repository
  links to the two documents at file level with no fragment — checked against its current `main` —
  so nothing on that side lands anywhere new. The conservatism is worth keeping: the failure it
  guards against is silent, because GitHub answers an unknown fragment with the top of the page.

- **Three pieces of wording that read as jargon or as blame.** "床" was a metaphor for the minimum
  monthly charge and is now named as that; the English "floor" was doing double duty for a cost
  minimum and for a lower-bound duration, so the cost sense became "minimum monthly charge" and the
  duration sense became "at least" or "lower bound". "本番へ戻す" did not say which direction data
  moves, and is now "スタンバイ系からアクティブ系へのデータの切り戻し", with the English
  correspondingly explicit. And "払わされる" — along with the English "swallow the higher bill" and
  "what `All` tiering costs you" — framed a documented minimum as something imposed on the reader;
  those now state the constraint without the grievance. No figure or claim changed.
- **`復元` became `リストア` throughout the data-protection note, and `ネイティブ` was replaced with the
  service name.** "Native" names no service, so the paths are now called `CopyBackup` and AWS Backup.
  No externally cited anchor used either word, so `make anchors` still passes; the note's own
  internal link moved with its heading.

- **The backup-copy diagram draws the AWS Backup restore path too, and says the restore constraint is
  shared.** Both paths land on the same requirement — an existing file system and SVM in the
  destination Region, and a new volume — so the figure now runs an arrow from the backup vault into
  the same "created when recovering" frame rather than from the native copy alone. Drawing the
  constraint once per path was what made it look specific to `CopyBackup`.
  Diagram wording follows the article: 復元 became リストア, and "the native CopyBackup" became "the
  FSx for ONTAP CopyBackup", because "native" names no service.

- **`AGENTS.md` gave itself 341 bytes of headroom, which is not headroom.** The size budget was
  restored by trimming prose in the commit that broke it, and a sibling repository pointed out what
  that leaves behind: with the budget nearly full, the next edit to a file read on every turn gets
  spent shortening sentences rather than saying more, so the document gets worse instead of shorter.
  They had measured their own at 88 bytes remaining and moved a section out. Same fix here — the
  documentation design principles are authoring guidance, needed when restructuring a README and not
  on every turn, so they now live in `docs/agent/documentation-design.md` with one index line left
  behind. Headroom 341 bytes to 1,307. The drift check earned its keep twice while doing it: it
  refused the move until the new file was tracked by git, and again until the steering loader pointed
  at a tracked body.
- **`CONTRIBUTING.md` states which translation drift the gates do not catch.** Previously that limit
  existed only in a merged pull request body and a tool docstring, which is to say nowhere a
  contributor reads first. Value drift fails `make i18n-check`; a change to a claim's *backing* -
  "documented" becoming "observed once" - moves no literal and passes every check. The section says
  so, records that this was published once, and gives the only remedy available: touch `ja` and `en`
  in the same commit.
- **The access point note was retitled, renamed, and reorganized around the two layers, and its
  vocabulary now follows the AWS Japanese documentation.** The previous title asserted a conclusion
  in the negative ("an Allow is not an upper bound"), and the filename asserted it too, which fixes
  a conclusion into a path that outlives it. Both now name the subject: **evaluation order and the
  two layers that narrow access**. `上限` for a permission ceiling is a literal translation that does
  not appear in the AWS Japanese documentation and has been replaced throughout, along with
  `和` → `結合` and `暗黙の拒否` → `暗黙的な拒否`, in the note and in the decision tree so the two read as
  one vocabulary. Sections are ordered Layer 1 model → Layer 1 how-to → Layer 2 → audit, removing a
  jump back and forth between the layers. **The old path
  `notes/access-point-policy-allow-is-not-a-cap.md` no longer exists**; every reference in the
  repository was updated, including the eight `navigation.md` files and `llms.txt`.
- **Task-specific material moved out of `AGENTS.md` into tracked `docs/agent/`** (localization
  workflow, architecture diagram standards, pitfalls, carried-over domain knowledge), reducing a
  file read on every turn from 37.5 KB to 26.4 KB. `.kiro/steering/` now holds only thin loaders
  recording when to read each one, and `AGENTS.md` keeps a one-line index. The 15.5 KB
  always-loaded workspace steering file was replaced by a 0.75 KB loader: it restated rules that
  `AGENTS.md` already carries, which is how two copies drift apart, and `.kiro/` is not published
  so nothing there is available to a reader of the repository.
- **CI calls Makefile targets instead of repeating their commands.** The linted path list lives
  once in `PY_PATHS` and test directories in `TEST_DIRS`, so local and CI cannot inspect different
  trees.

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

- **`StorageEfficiencyEnabled` is not "lost by a restore" — it is a CLI default.** The backup-copy note and
  the limits reference both stated the attribute was not carried over, on the evidence that a restored
  volume read `true` while its source read `false`. Running the same restore through the console showed the
  field **pre-selected to the source value**, and it restored as `false`. The `true` came from omitting the
  field in the CLI `--ontap-configuration`; it is the API default when the field is absent, not restore
  behaviour. Both documents now say so. **This is the second claim in this work that a single observation on
  a single interface got wrong** — the first being the transient `DP` volume type — and both were caught the
  same way: by performing the operation a second way rather than by re-reading the first result.
- **`SecurityStyle` reads empty on a restored volume through both interfaces.** Previously recorded as a
  single unreproduced observation. It now reproduces across the CLI and the console, so the caveat narrows
  rather than disappears: both runs used the same UNIX-style source volume, and other security styles were
  not tested.
- **"Backups cannot protect against a Region-level failure" was true and is now false.** Three documents
  stated it as a constraint — `docs/ja/reference/comparison/data-protection-methods.md` and the JA and EN
  copies of `snapshots-are-not-a-recovery-plan.md` — in the comparison tables, the misconception tables,
  the decision flows, and the how-to-choose steps. Backups can be copied to another Region and account as
  of August 2026, so the conclusion drawn from the constraint no longer follows. **The underlying sentence
  was never wrong and still is not**: a restore target is confined to the Region where the backup is
  stored. What changed is which Regions a backup can be stored in, so all four places now separate "where
  a backup can live" from "where it can be restored to", and say that creating the destination file system
  lands on RTO. A reader who designed against the earlier text and concluded that SnapMirror was the only
  cross-Region option was reading a claim that held when it was written. **This is the failure mode the
  evidence tiers do not catch**: `documented` was the correct tier, the source was cited correctly, and the
  citation went stale underneath it without the document history recording a change.
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
