---
title: Paths are the failover mechanism itself — session count is neither a default nor a limit, but a value you decide by measurement
lifecycle: [build, operate, design]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
deployment_type: [SINGLE_AZ_2, MULTI_AZ_2]
lang: en
---

# Are paths the failover mechanism itself?

Yes. Host-side multipath carries I/O continuity, and session count is decided by measurement, not by a default.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md) | [English](paths-are-the-failover-mechanism.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That block failover is carried by host-side multipath, and that path count changes from 2 to 24 depending on LIF count × session count
- The measurement that iSCSI was non-disruptive (0 failures across 1,161 samples) while NVMe/TCP cut for 423.8 seconds on AL2023's default kernel

## What this note does not answer

- The cut during an NVMe/TCP failover on a kernel where native multipath is enabled (not measured)
- Block performance figures (only I/O continuity during failover and how to count paths were measured)

## Prerequisite level

advanced

## Body

<a id="are-paths-the-failover-mechanism-itself"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**On block storage, the mechanism that keeps I/O continuing when a file server switches over is host-side multipath.** The storage side only goes as far as presenting multiple paths; deciding which one to use is the host's job. **This dividing line is the biggest difference from a file share.**

And **path count is not fixed by default. It moves from 2 to 24 depending on the session count you chose.**

**On Linux, the 8-session step is explicitly marked `(Optional)`.** In AWS's Linux procedure, the step that sets `node.session.nr_sessions` to 8 is a conditional, optional step: **"if you need throughput exceeding the single-client EC2 limit of 5 Gbps."** Connecting without applying it gave **2 paths** (measured in the [quickstart](../quickstart.md)). Applying it gives **LIF 2 × 8 sessions = 16 paths.**

**On Windows, 8 is baked into the procedure as the default.** AWS's published script has `$RecommendedConnectionCount = 8`, run against two portals, giving **16 sessions.** AWS's own published configuration-check script's success example also **displays 16 sessions spanning 2 nodes as the normal state.**

**These 16 paths do not violate NetApp's recommendation.** ONTAP's SAN configuration documentation states **"paths from a host to each node in the cluster should not exceed 8,"** and with 1 HA pair (2 nodes), 8 paths per node is within that range.

**A separate statement, "no more than 4 paths per LUN," has a different scope.** The corresponding statement in NetApp's Linux SAN host configuration documentation is about **ASA / AFF / FAS configurations**, and FSx for ONTAP is none of these. **A recommendation of 4 paths per LUN for FSx for ONTAP was not found published, as far as we could confirm.**

Further, **the connection procedure is not idempotent.** Running the 8-connection loop on Windows against the same portal a second time **increased sessions from 16 to 24, and paths to 24 too.** No warning appears.

> **Tier**: `verified` (verified 2026-09-05, `ap-northeast-1`, `SINGLE_AZ_2` and `MULTI_AZ_2` second generation, 1 HA pair, ONTAP 9.18.1P5, Amazon Linux 2023 and Windows Server 2022) — path count, how ALUA splits, non-idempotence, each default, and **I/O continuity and duration during failover**.
> **Failover was measured once in a Multi-AZ environment.** The result is in [The measured failover](#the-measured-failover). **iSCSI was non-disruptive; NVMe/TCP cut for 423.8 seconds.**
> **No performance figures are included.** The steps to confirm in your own environment are in [Verify it in your environment](#verify-it-in-your-environment).

---

### How path count is determined

**One SVM in FSx for ONTAP has 2 iSCSI LIFs.** In the verification environment these were `iscsi_1` (node -01) and `iscsi_2` (node -02), and **both carried both `data_iscsi` and `data_nvme_tcp`.** NFS and SMB use different LIFs.

**These 2 are per SVM.** Creating a second SVM produced its own `iscsi_1` and `iscsi_2`. **Counting LIFs without scoping to an SVM miscounts.**

Path count is the product:

```text
Path count = number of LIFs × sessions per LIF
```

| Setting | Verified result | Position in AWS's procedure |
|---|---|---|
| 2 LIFs, default session count (1) | 2 paths | Linux, without applying the optional step |
| 2 LIFs, 8 sessions | **16 paths** | Linux: `(Optional)`. **Windows: the script's default** |
| The same 8-connection loop run once more | **24 paths** | Not anticipated by the procedure. A consequence of non-idempotence |

**AWS's basis for the figure 8 is bandwidth.** It gives up to 625 MBps per session, 8 sessions as 40 Gbps / 5,000 MBps, and states this **"covers the top-end throughput capacity of 4,000 MBps."**

**But this arithmetic does not match the number of paths the same procedure lays down.** The procedure's text is "**8 sessions per initiator per ONTAP node** in each availability zone," and because an SVM has an iSCSI LIF on both nodes, **`nr_sessions=8` lays down 16 paths** (per the table above). **Meanwhile, 40 Gbps is 8 × 5 Gbps, not 16 × 5 Gbps.** Which counting this text intends is not settled by the wording. **What this note calls "8 sessions" is the `nr_sessions` value**, and **the number of paths is double that.** Because the two counting methods differ by a factor of 2 in provisioning, **settle which counting method you mean before deciding the value to put into `nr_sessions`.**

**This 4,000 MBps figure does not match the current quotas page.** The quotas page states second generation's ceilings as Multi-AZ 6,144 MBps and Single-AZ 73,728 MBps. **So at close to the ceiling on second generation, the basis for the number 8 cannot be reused as-is.**

**But treating Single-AZ's 73,728 MBps as iSCSI's ceiling overstates it.** [Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) restricts iSCSI usability to file systems with **6 or fewer HA pairs**, and 73,728 MBps is the value for 12 HA pairs. The ceiling meaningful in an iSCSI context is 6 × 6,144 = **36,864 MBps** (both pages confirmed 2026-09-08). **The protocol's availability range bites before the throughput ceiling does.**

> **Calculate the session count from your own configuration.** Using 625 MBps per session as a guide, derive the count that meets your required throughput. **Do not use the 8 written in the procedure as-is.** The 4,000 MBps cited as its basis does not match the second-generation figure in [Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) (both pages confirmed 2026-09-05).

---

### ALUA priority, and what it means

The verification environment's `multipath -ll` looked like this.

```text
3600a09806c5742304b5d2f656c533466 dm-1 NETAPP,LUN C-Mode
size=20G features='3 queue_if_no_path pg_init_retries 50' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| |- 8 paths
`-+- policy='service-time 0' prio=10 status=enabled
  |- 8 paths
```

| Display | Meaning |
|---|---|
| `hwhandler='1 alua'` | ALUA is active. **ONTAP uses ALUA for iSCSI and FC, ANA for NVMe** |
| `prio=50 status=active` | The path to the node that owns the LUN. **Normal I/O goes through here** |
| `prio=10 status=enabled` | The path via the HA partner. **Used when the owning node goes down** |
| `queue_if_no_path` | When all paths are down, queues rather than returning an error |
| `policy='service-time 0'` | NetApp's recommended path selector |

On Windows the same thing appeared as `TPG_State`. **Active/Optimized (TPG_Id 1000) had 8 paths, Active/Unoptimized (TPG_Id 1001) had 8 paths**, load balancing was `Round Robin with Subset`, and ALUA was `Implicit Only`.

**On both platforms, the higher- and lower-priority paths came out equal in count.** This follows from there being one LIF per node.

---

### Host-side defaults you need to change

**Left at their defaults, behaviour differs from what AWS assumes.** Defaults confirmed in the verification environment:

| Item | Default | AWS's instruction |
|---|---|---|
| Linux `node.session.timeo.replacement_timeout` | **120** | **5** |
| Windows `LoadBalancePolicy` | **None** | **RR** (round robin) |
| Windows `PathVerificationState` | **Disabled** | **Enabled** |
| Windows `PDORemovePeriod` | 20 | Changed by NetApp Windows Host Utilities |
| Windows `DiskTimeoutValue` | 60 | Same as above |

**`replacement_timeout`'s 120 seconds is the wait before I/O is errored out after a path goes down.** Changing it to 5 makes switchover faster. **Left unchanged, it is a configuration that waits 2 minutes while believing it has switched over.**

**Windows's `Set-MPIOSetting` returned "Settings changed, reboot required."** The setting takes effect after a reboot. **If the build procedure does not include a reboot, you end up in a state where you believe you configured it but it has not taken effect.**

**`MSFT2005 / iSCSIBusType_0x9` was already listed by `Get-MSDSMSupportedHW` at the moment `Enable-MSDSMAutomaticClaim -BusType iSCSI` was run.** The `New-MSDSMSupportedHW` AWS instructs is already satisfied once automatic claim is enabled.

---

### Placement of multipath.conf

**AWS instructs `mpathconf --enable --with_multipathd y`.** In the verification environment this created a **334-byte `/etc/multipath.conf`.**

**NetApp's documentation recommends a 0-byte `/etc/multipath.conf`.** Placing an empty file loads NetApp's compiled-in recommended values.

**In the verification environment, the 334-byte file still behaved per NetApp's recommended values** (`service-time 0`, `queue_if_no_path`, a 2-group structure equivalent to `group_by_prio`). **That the 334-byte content did not override the recommended values is this environment's result.** But **the two instructions are different things, so record which one you followed.**

Splitting NetApp's stated recommended values into what could and could not be confirmed:

| Value | Confirmed in the verification environment? |
|---|---|
| `path_selector "service-time 0"` | **Confirmed** (`policy='service-time 0'`) |
| `no_path_retry queue` | **Confirmed** (`features='3 queue_if_no_path ...'`) |
| Priority-based path grouping | **Confirmed** (2 groups, prio 50 / 10) |
| `dev_loss_tmo infinity`, `fast_io_fail_tmo 5`, `polling_interval 5`, `path_checker tur`, `detect_prio yes` | **Not confirmed** |

---

### Designing path count

**"More is safer" does not hold.** Placing two official statements side by side:

| Source | Statement |
|---|---|
| NetApp: Multipathing | **No more than 8 paths per node.** At least 2 paths per LUN per reporting node. Limit path count with Selective LUN Map, portset, igroup, or FC zoning |
| NetApp: SAN host multipathing (platform-independent) | **Paths from a host to each node in the cluster should not exceed 8** |
| NetApp: Linux SAN host configuration | **On ASA / AFF / FAS configurations, more than 4 paths per LUN is unnecessary, and more than 4 can cause problems during a failure.** FSx for ONTAP is neither of these |
| AWS: Provisioning iSCSI | **8 sessions per node per AZ** (`(Optional)` on Linux, the script's default on Windows) |

**"8 paths per node" and "4 paths per LUN" are different counting methods, and their applicable scope also differs.** The former is from ONTAP's platform-independent SAN configuration documentation; with 1 HA pair, 8 sessions gives 8 paths per node, **inside that ceiling**. The latter is about ASA / AFF / FAS configurations, **which do not include FSx for ONTAP.**

**So it is not accurate to say "AWS's procedure violates NetApp's recommendation."** As far as we could confirm, no statement recommending 4 paths per LUN for FSx for ONTAP was found.

**What remains to decide is real.** Session count is a value derived from required bandwidth, and it is neither a default nor a ceiling.

**But deriving session count by dividing bandwidth by a divisor did not hold up under measurement.** The divisor AWS's procedure places is 625 MBps per session (the EC2 single-flow limit of 5 Gbps), and arithmetic using it takes this form:

```text
Required session count = required bandwidth ÷ 625 MBps
Ceiling            = min(8 paths per node, client bandwidth ÷ 625 MBps)
```

**This form is wrong in both directions.** This was settled once block was measured (below). **At 1 session, it overestimates the required session count; at 16 sessions, it comes out to only a fifth of the expectation.** So **this formula cannot be used as a tool to decide the count.** The ceiling side (8 paths per node) is a configuration constraint and remains as-is, but the required-count side comes down to measuring in your own configuration.

You also cannot assume a single client will exhaust the capacity. This relationship is in [A single connection measures the client, not the storage](../../performance/notes/a-single-connection-measures-the-client.md).

#### Where the divisor comes from, and its relationship to measurement

**The 625 MBps divisor itself does have a source.** Both the iSCSI and NVMe/TCP block procedures write the same value as the preamble to the section on increasing sessions — [iSCSI](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html) and [NVMe/TCP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html) both say
"the Amazon EC2 single client maximum of 5 Gbps (~625 MBps)" (confirmed 2026-09-07).
**So "AWS states 625 MBps" is `documented`.**

**The divisor has a source, and it does not match measurement. Both are true.**

| Premise | State |
|---|---|
| **Linearity** — does n sessions become n times a single session | **Does not hold** (measured). For iSCSI, **1 → 2 moved sequential throughput by not one byte**, while 2 → 16 gave 1.74× reads and 2.17× writes |
| **Does the divisor match measurement** | **It does not, for either protocol group.** File falls short of the divisor, and **block was 1.82× over it in the most recent measurement** (below) |
| **Does re-measuring the same configuration give the same value** | **No** (measured). NVMe/TCP's multiplicity-1 case moved **from 591.64 to 1,135.88, a 1.92× swing.** **Environmental difference is ruled out by control, and the cause is unconfirmed** (below) |

**"AWS states 625 MBps" and "625 MBps was measured" are different claims.** The former is `documented`,
**the latter is false.**

#### The gap between the divisor and measurement (file protocols and block)

**The single-connection measurement of a file protocol on the same file system, the same client type, and the same instrument does not reach 625 MBps.**

| Cited measurement | Against 625 MBps |
|---|---|
| NFSv4.1 single connection, 591.62 MB/s | **94.7%** |
| SMB 3.1.1 single channel, 574.24 MB/s | **91.9%** |

##### Block not landing at the same position

**This note previously stated that if block landed at the same position, dividing by 625 would underestimate the required session count by about 5%,** and instructed adding 1 to the `nr_sessions` derived from the division.
**Block has since been measured and the premise was false, so this is withdrawn. The instruction's direction was backwards.**

There are two multiplicity-1 measurements on the same file system.

| Multiplicity-1 measurement (1 MiB sequential read) | Against 625 MBps |
|---|---|
| iSCSI, 1 session, 1,135.19 MB/s (= 9.08 Gbps) | **181.6%** |
| NVMe/TCP, 1 I/O queue, 1,135.88 MB/s (= 9.08 Gbps) | **181.7%** |
| File side's NFSv4.1 single connection, 591.62 MB/s (= 4.73 Gbps) | 94.7% |

**They did not land at the same position. Roughly double.** So adding a session on top of the divided figure **means provisioning 2 or more where the measured value shows 1 is enough.** Because the error runs the opposite direction, do not use the earlier instruction.

**And "then reduce it" does not follow either.** The cited source records the arithmetic itself as wrong in both directions, and **at 16 sessions it produces only a fifth of the expectation.** Because the divisor overshoots and undershoots, **applying a ratio to construct a different divisor does not hold either.**

**The protocol difference at 1 connection did not reproduce.** The gap between the two rows above is 0.06%.
**Protocol choice does not move single-connection throughput.** Place the reason for choosing on a different axis.

**Why the file side comes out at roughly double, the cited source itself has not confirmed.** The candidates raised are the single-flow limit of a newer-generation instance and the applicability conditions of the 5 Gbps figure. **Which applies has not been verified, so do not design around either as a premise.**

##### That the same configuration's multiplicity-1 swung 1.92× on remeasurement

**The second row of the table above was 591.64 MB/s in the earlier measurement.** At 4.73 Gbps, it sat at the documented 5 Gbps position and **matched the same environment's NFS single connection (591.62) too.** All four of the 1 MiB / 64 KiB read/write combinations landed in the 591.5–591.7 range, **a shape that looked like hitting a single ceiling somewhere on the path.**

**On remeasurement it came out at 1,135.88 — a 1.92× swing.** The requested parameters and the negotiated outcome were the same
(`--nr-io-queues=1`, NCQA/NSQA both 1, 1 controller), and **the cited source ruled out environmental difference with a control** — 4 KiB random reads agreed within 4% across all 3 configurations, and `connect-all` sequential reads agreed to within 0.007%. **The cause is unconfirmed.** The candidates raised are EC2-side flow placement, whether the connected portal is on the optimized side, and kernel-version differences. **This is a separate question from the "roughly double" above, with separate candidates too.** Both are unconfirmed, so **do not explain the two with a single cause.**

**The design implication is the larger one here.** "Block's multiplicity 1 lands at the divisor's position" was consistent with the value available at the time. **And yet the next measurement swung 1.92×.** In other words, **a single-connection block value is not an input to planning from a single measurement.** Both landing on the divisor and exceeding the divisor **can each move on the next measurement.**

> **A range not moving is not evidence of not having measured.** The cited source's 3 single-connection rows
> (500–592 MB/s) are a table that only answers "similar values arising from different causes," and **a measurement that does not fit the point does not go into the same table.** The block value's absence from it is not because it was not measured, but because **there is a judgment not to include it there.** **This side has placed a probe on that judgment** — placing it on the range itself would go silent if the judgment were withdrawn
> ([What a probe's silence does not mean (日本語)](../../../../ja/reference/cross-repo-index.md#probe-の沈黙が意味しないこと)).

**The path increment does not change.** `nr_sessions` is a per-node value, and because an SVM has an iSCSI LIF on both nodes, **moving `nr_sessions` by 1 moves the path count by 2.** This is the unit to use when re-deciding the count.

> **There is a range this measurement cannot be used as-is for.** Transcribing the conditions the cited source raises:
> **it is a raw-device value**, not a measurement of a configuration with a filesystem on the LUN.
> **The window is 300 seconds and includes a burst; it is not a baseline.** So 1,135 MB/s cannot be
> treated as a sustained value either. **"It came out above the divisor" is as far as this goes.**
>
> **This gap is not small.** In the file-side measurement, a **2.0× step** appears once burst credit runs out,
> and it took about 27 minutes to fall. **The drop is a step, not a gradual slope.**
> The step's size, timing, and slope of recovery, and that the credit itself disappears at higher stated
> values, are in
> [The burst and credit mechanism that breaks a benchmark](../../performance/notes/what-you-cannot-read-from-cloudwatch.md#how-large-the-step-is-and-how-long-until-it-falls).
> **Which side a value taken in a 300-second window falls on is not judged in this section.**

> **Evidence**: the divisor is `documented` (the 2 pages above, 2026-09-07). **Both the file side's 5–8% gap and
> block's 1.82× are transcriptions of
> [the cited source's measurement results](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md)**
> (measurement conditions are in the box above and in the cited source). **No remeasurement in this repository is included.**

**And write down the count you decided, and why, in your design document.** Writing "8" as a fixed value in a runbook leaves the next reader unable to judge why it is 8.

**Selective LUN Map was enabled by default.** The verification environment's LUN map listed **the owning node and its HA partner — 2 nodes** as reporting nodes. In a 1-HA-pair configuration this is all the nodes. **In a configuration with multiple HA pairs, this works as a mechanism restraining path count.**

---

### Non-idempotent connection procedure

**Running the 8-connection loop against one portal a second time on Windows increased sessions from 16 to 24.** Path count also became 24, in an asymmetric shape of 8 Active/Optimized paths and 16 Active/Unoptimized paths.

**Neither an error nor a warning appears.** `Connect-IscsiTarget` does not detect the existing session and simply adds the requested count.

**There are 2 consequences.**

| Consequence | Content |
|---|---|
| Re-running the runbook increases it | Running the build procedure twice doubles the path count from what was intended |
| Cannot work backward from state | A runbook that says "8 sessions" **only makes sense if you check the current count before running it** |

**Add a pre-execution session-count check, and a disconnect step if needed, to the build procedure.** AWS's verification script `CheckiSCSI.ps1` confirms session count, node distribution, and MPIO state.

---

### That NVMe/TCP's path depends on kernel configuration

**On Amazon Linux 2023, native multipath for NVMe/TCP was not enabled.**

The verification environment's kernel (`6.18.44-99.149.amzn2023.x86_64`) had **`CONFIG_NVME_MULTIPATH is not set`.** Consequences:

| Observation | Content |
|---|---|
| `/sys/module/nvme_core/parameters/multipath` | **Does not exist.** Because `nvme_core` is built in and this setting is disabled. **The confirmation step AWS's procedure instructs cannot be run** |
| `nvme list-subsys` | 2 live TCP controllers under 1 subsystem. This much was as expected |
| `nvme list` | **The same namespace was visible as 2 devices, `/dev/nvme2n1` and `/dev/nvme3n1`.** The `wwid` was identical on both |
| The subsystem's `iopolicy` | The attribute does not exist |

**AWS's procedure assumes RHEL 9.3.** There, native multipath is enabled. **Running the same procedure on Amazon Linux 2023 causes one namespace to appear as two disks, and using only one leaves failover ineffective.**

**This is not "NVMe/TCP cannot be used."** The connection is established. **Only multipath is not established.** Confirm `CONFIG_NVME_MULTIPATH` on your own kernel.

#### That this being unset is not limited to this one kernel

**We measured only 1 line, but a sibling repo confirmed the same result on 3 lines.**
Extracting the kernel config that `al2023-ami-kernel-default-x86_64` returns, from packages in the
`amazonlinux` repository, **all of 6.1.186-228.374 / 6.12.103-127.188 / 6.18.48-107.148 were unset**
(confirmed 2026-09-15, [the cited source's verification status](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification-status.md)).

**Even so, we cannot write "always disabled on AL2023."** A kernel's build configuration can always change.
Run step 9 of [Verify it in your environment](#verify-it-in-your-environment) before building.
**That 3 lines agreed is not grounds to skip the check — it means the check is unlikely to come up empty.**

#### Behaviour on a kernel where native multipath is enabled (cited)

**We do not have this configuration.** What follows is a transcription of a sibling repo's measurement, **not
our own verification.** Against the same file system, the same namespace, and the same filled data, a control
comparing a client with `CONFIG_NVME_MULTIPATH=y` (Rocky Linux 9.7, kernel 5.14.0-611.5.1.el9_7)
against AL2023. **The only difference is the kernel's ANA support.**

| Observation | Kernel with ANA enabled | AL2023 (table above) |
|---|---|---|
| `/sys/module/nvme_core/parameters/multipath` | **Returns `Y`.** The procedure's confirmation step succeeds | The file does not exist |
| Device node | **The 2 controllers consolidate into 1 device** | 2 devices with the same `wwid` |
| ANA state | Reports `optimized` / `non-optimized` | The attribute does not exist |
| The subsystem's `iopolicy` | **`queue-depth`.** Not the `round-robin` the procedure's confirmation instructs | The attribute does not exist |
| Sequential read | **23% higher** than optimized alone | — |

**The `iopolicy` value is where a reader trips.** AWS's procedure instructs confirming it is `round-robin`,
and its example output shows that. **The measurement was `queue-depth`, set by the udev rule
`71-nvmf-netapp.rules` that `nvme-cli` 2.16-1.el9 installs** (the kernel's default is `numa`). **Even
built per the procedure, you get a value the procedure calls "different."** The performance difference in
this configuration was 0.5%, so **it is not a reason to choose differently, but a matter of resetting
expectations.**

> **Tier**: `documented` (transcription of a sibling repo's measurement). **We did not remeasure it.**
> The conditions and each value are in
> [the cited source's verification status](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification-status.md)
> and
> [the cited source's measurement results](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification/perf-matrix-results.md).
> **It is stated explicitly that 4 KiB random reads did not add across the second path, and that write and
> `round-robin` / `numa` values are unmeasured**, so **this repository's judgment stops there too.**

---

### The measured failover

**Two attempts to induce it from the host side both failed.**

| Attempt | Result |
|---|---|
| Blocking outbound TCP 3260 to one portal at the Windows firewall | **Path count stayed at 16.** The already-established iSCSI session was unaffected |
| `Disconnect-IscsiTarget` against the connection to that portal | **Session count stayed at 16** |

**There is exactly one method that can induce it: changing throughput capacity.** `storage failover takeover` cannot be used. **FSx for ONTAP does not expose HA state to `fsxadmin`, and `storage failover show` returns an empty table.** And **second generation requires a 6-hour interval between changes.** In a short-lived test environment this leaves effectively one measurement, but **the constraint is not "once per environment," it is "6 hours apart."**

In a Multi-AZ environment, we changed 384 → 768 MBps and **recorded 1-second-interval 4 KiB direct writes while loading both iSCSI and NVMe/TCP.**

> **Not recorded**: the tool used for the write, whether the target was a raw device or a file, and **which of the two device nodes the NVMe side held.** The third is central to explaining this result itself (the app bound to one of the two, with no switchover target), so **the same procedure is not guaranteed to reproduce the same numbers.**

| Target | Samples | Failures | Slowest single write | Cut length |
|---|---|---|---|---|
| iSCSI LUN (via `dm-multipath`) | 1,161 | **0** | **2.101 seconds** | **None** |
| NVMe/TCP namespace (1 device node, kernel-native multipath disabled) | 752 | 11 | **412.741 seconds** | **423.8 seconds** (derived from the timeline below, 07:29:33 → 07:36:37; the observed value is the 412.741 seconds at left) |

**The concurrent PostgreSQL load did not stop, advancing to roughly 3.9 million rows.**

Timeline:

| Time (UTC) | Event |
|---|---|
| 07:27:40 | Throughput-capacity change requested |
| Between 07:28:10 → 07:28:31 | The NFS / SMB floating address's `/32` route target rewrites from the 1a ENI to the 1c ENI |
| 07:28:46 | **ANA flips.** The 1c-side LIF becomes `optimized`, the 1a-side becomes `non-optimized`. **About 66 seconds from the request** |
| 07:28:48 → 07:29:11 | `dm-multipath` follows. One path group goes to `prio=0` and eventually drops |
| 07:29:26 | **The only slow write on both protocols.** iSCSI 2.101 s, NVMe/TCP 2.201 s |
| 07:29:33 | **`nvme3` (the controller for the 1a-side LIF) goes to `connecting`.** An in-flight NVMe write blocks |
| 07:29:41 → 07:36:20 | While node -01 is being replaced, `nvme3` stays `connecting` |
| 07:36:22 | **iSCSI returns to 2 path groups** |
| 07:36:27 → 07:36:37 | `nvme3` returns to `live`, ANA passes through `change` to `non-optimized`. **NVMe writes resume** |
| Between 07:39:26 → 07:39:52 | The floating address's `/32` route returns to the 1a ENI (failback) |
| 07:49:38 | The change completes. **About 22 minutes from the request** |

**A throughput-capacity change is not a simple failover.** AWS documents that it **replaces file servers serially**, in the order "failover → failback → replacing the second unit." **That is why the total took 22 minutes, with one node absent for about 7 minutes.**

The documentation's "typically under 60 seconds" **has its scope explicitly stated as from failure detection to standby promotion.** **The roughly 66 seconds measured here starts from the API request** — a different starting point, since request acceptance and orchestration happen before it and there is no failure to detect for a throughput-capacity change. **The two cannot be mapped onto each other, so we do not.** Read **the 66 seconds as a measured value from request to ANA flip.**

**The same AWS page describes the failover and failback accompanying this operation as "usually a few minutes."** What was measured was 22 minutes.

#### Why iSCSI and NVMe/TCP diverged

**iSCSI was transparent.** `dm-multipath` switched to the second path, **no error occurred even once, and the cost was only about 2.1 seconds of stall.** This matches what AWS states about iSCSI being transparent on the throughput-capacity page.

**NVMe/TCP was not transparent.** But **the cause is not FSx for ONTAP; it is the host's kernel configuration.**

| Stage | What happened |
|---|---|
| Cause | Amazon Linux 2023's kernel is **built with `CONFIG_NVME_MULTIPATH` disabled** |
| Consequence 1 | One namespace appears as **2 device nodes sharing the same `wwid`** |
| Consequence 2 | The application binds to one of them. **There is no target to switch to** |
| Observation | A write to the device on the side whose controller went down **blocked for 412.741 seconds and then errored**, continuing to fail until the controller came back |

**This is where the reason AWS names NFS / SMB / iSCSI but not NVMe/TCP shows up.**

**This is not "NVMe/TCP cannot fail over."** On a kernel with native multipath enabled, the two controllers consolidate into one device and follow ANA. **We have not measured the cut in that configuration.** What was confirmed is that **it does not switch over on AL2023's default kernel.**

**The consolidation itself has been measured by a sibling repo**
([Behaviour on a kernel where native multipath is enabled](#behaviour-on-a-kernel-where-native-multipath-is-enabled-cited)). **But what is measured there is consolidation and reads, not the cut during a failover.** A value corresponding to the 412.741 seconds above **is not yet in either repository.**

**If using NVMe/TCP, confirm your kernel's `CONFIG_NVME_MULTIPATH` before building.** If disabled, the choice becomes iSCSI or a distribution with native multipath enabled.

**AWS's NVMe/TCP procedure also instructs a controller loss timeout of 1800 seconds.** Combined with the verification environment's 423.8-second cut, **this value is set to wait for the controller to come back.** Whether you can wait is a requirement on the application side.

**Dropping a LIF from the management side was not tried.** It changes the state of a LIF that Amazon FSx for ONTAP manages, and because the side effects on the verification were not fully understood, it was not performed.

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| Failover is the storage side's job | **Host-side multipath keeps I/O continuing** |
| multipath is optional | **AWS's documentation requires it for automatic failover** |
| More paths is safer | **More is not necessarily better.** ONTAP states no more than 8 paths per node. On ASA / AFF / FAS configurations, more than 4 paths per LUN can cause problems during a failure (**FSx for ONTAP is neither of these**) |
| Following AWS's procedure violates NetApp's recommendation | **It does not.** 8 sessions with 1 HA pair is inside the platform-independent ceiling of 8 paths per node |
| AWS's 8 sessions is always correct | **8 is "a value derived from required bandwidth."** The stated basis, 4,000 MBps, does not match the current quota's second-generation ceiling. Calculate from your own configuration |
| An iSCSI LIF is 2 per file system | **It is 2 per SVM.** It grows if you add SVMs |
| iSCSI and NVMe/TCP use different LIFs | **The same LIF carries both services** |
| The connection script gives the same result no matter how many times you run it | **It is not idempotent.** It went from 16 to 24 |
| Windows's MPIO setting takes effect the moment it is run | **A reboot is warned as required** |
| `mpathconf --enable` produces NetApp's recommended settings | **NetApp recommends a 0-byte file.** `mpathconf` created 334 bytes |
| multipath is automatic with NVMe/TCP | **Disabled at the kernel level on Amazon Linux 2023.** The same namespace appears as 2 devices |
| Checking `/sys/module/nvme_core/parameters/multipath` tells you | **AL2023 has no such file.** On a kernel with ANA enabled it returns `Y`, and the procedure's confirmation succeeds (cited) |
| Following the procedure guarantees `iopolicy` is `round-robin` | **A udev rule that `nvme-cli` 2.16-1.el9 installs sets `queue-depth`** (cited). The kernel's default is `numa`; the procedure's value is neither |
| Failover produces I/O errors even on iSCSI | **0 failures across 1,161 samples.** Only about a 2.1-second stall |
| NVMe/TCP is transparent like iSCSI | **Not transparent on AL2023.** A 423.8-second cut. The cause is the kernel's `CONFIG_NVME_MULTIPATH` being disabled |
| NVMe/TCP cannot fail over | **It is a kernel-configuration issue.** A sibling repo has measured the 2 controllers consolidating into 1 device on a kernel with ANA enabled (cited). **But the cut in that configuration is unmeasured in either repository** |
| `storage failover takeover` can be used to test failover | **`storage failover show` returns an empty table.** The only way to induce it is changing throughput capacity |
| A throughput-capacity change = a failover under 60 seconds | **The whole thing took about 22 minutes** (the same page states "usually a few minutes"). Because file servers are replaced serially. **The documentation's under-60-seconds covers detection through promotion; the measured 66 seconds starts from the request, so they do not correspond** |

---

### Verification environment

| Item | Value |
|---|---|
| ONTAP version | 9.18.1P5 |
| Region | `ap-northeast-1` |
| Deployment type | Path count, ALUA, idempotence, and defaults on `SINGLE_AZ_2`. **The measured failover on `MULTI_AZ_2`** (both second generation, 1 HA pair) |
| Throughput capacity | 384 MBps |
| Linux client | Amazon Linux 2023, kernel 6.18.44-99.149.amzn2023.x86_64 |
| Windows client | Windows Server 2022 Datacenter |
| iSCSI LIF | 2 per SVM, 1 per node |
| Verification date | 2026-09-05 |

> **Note**: the above is a measurement in this environment and does not guarantee a general service limit or reproduction in a production environment. **Path count changes with LIF count and the session-count setting.**

---

### Primary sources referenced

| Point | Source |
|---|---|
| multipath being required for automatic failover, setting `replacement_timeout` to 5, `mpathconf --enable`, 8 sessions per node per AZ, and the WWID being `3600a0980` + the serial hex | [AWS: Provisioning iSCSI for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html) |
| Windows's MPIO feature, `New-MSDSMSupportedHW`, `Set-MPIOSetting`, round robin, 8 connections per portal, `CheckiSCSI.ps1` | [AWS: Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) |
| The NVMe/TCP procedure, `nvme connect-all -l 1800`, confirming `/sys/module/nvme_core/parameters/multipath`, the assumed client being RHEL 9.3, and iSCSI and NVMe/TCP sharing the same LIF | [AWS: Provisioning NVMe/TCP for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html) |
| ONTAP using ALUA for iSCSI and ANA for NVMe. No more than 8 paths per node. At least 2 paths per LUN. Restricting paths with Selective LUN Map and portset | [NetApp: Multipathing](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |
| A 0-byte `/etc/multipath.conf` being recommended, the list of recommended parameters, and more than 4 paths per LUN being able to cause problems **on ASA / AFF / FAS configurations** (FSx for ONTAP is neither) | [NetApp: Linux SAN host configuration](https://docs.netapp.com/us-en/ontap-sanhost/hu-ol-9x.html) |
| Selective LUN Map being enabled by default on a new LUN map | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |
| The failover accompanying a throughput-capacity change being transparent to NFS / SMB / iSCSI. File servers being replaced serially. The test method for failover being a throughput-capacity change | [AWS: Managing throughput capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html) |
| The 4 triggers for failover, normally completing in under 60 seconds, **and naming only NFS and SMB as transparent** (the page above also names iSCSI) | [AWS: Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| Second generation's throughput ceilings (Multi-AZ 6,144 MBps, Single-AZ 73,728 MBps) | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| NVMe/TCP simplifying MPIO configuration compared with iSCSI | [AWS: FSx for ONTAP supports NVMe-over-TCP](https://aws.amazon.com/about-aws/whats-new/2024/07/amazon-fsx-netapp-ontap-nvme-over-tcp) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [Multi-AZ moves a route, not an address](multi-az-moves-a-route-not-an-address.md) — what rewrites during a failover, and what stays fixed
- [Two controls outside the igroup](igroups-are-not-the-only-access-control.md) — restricting path count with a portset
- [The block protocol choice is narrowed first by generation and HA pair count](protocol-choice-is-bounded-before-you-choose.md) — the LIF and port premises
- [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) — the host as a third control plane
- [LUN layout decides recovery granularity](lun-layout-decides-recovery-granularity.md) — Selective LUN Map and `lun move`
- [Throughput is not decided by a single setting](../../performance/notes/where-throughput-is-determined-and-shared.md) — the bandwidth behind the 8-session figure
- [Block storage cross resource map (日本語)](../../../../ja/reference/block-storage-resource-map.md) — index of where sources disagree
- [Evidence policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

## Verify it in your environment

| # | Step | What it tells you |
|---|---|---|
| 1 | Confirm the LIF count with `network interface show -vserver <svm> -data-protocol iscsi` (**scope to the SVM**) | Half of the path-count calculation |
| 2 | Record `iscsiadm --mode session \| wc -l` alongside `multipath -ll` | The relationship between session count and path count |
| 3 | Confirm whether `multipath -ll`'s prio values split into 2 groups | Whether ALUA is in effect |
| 4 | `grep replacement_timeout /etc/iscsi/iscsid.conf` | **The default is 120. Decide whether to change it to 5** |
| 5 | `wc -c /etc/multipath.conf` | **Is it 0 bytes, or `mpathconf`'s content? Record which you followed** |
| 6 | On Windows, `Get-MSDSMGlobalDefaultLoadBalancePolicy` and `(Get-MPIOSetting).PathVerificationState` | **The defaults are None and Disabled** |
| 7 | On Windows, run `mpclaim -s -d 0` and record the total path count and the Active/Optimized breakdown | Path count and ALUA |
| 8 | Run the connection script **twice** and confirm whether the session count grows | **Non-idempotence** |
| 9 | `grep CONFIG_NVME_MULTIPATH /boot/config-$(uname -r)` | **Whether multipath holds for NVMe/TCP** |
| 10 | After connecting NVMe/TCP, use `nvme list` to confirm whether multiple devices share the same `wwid` | A sign that multipath is not in effect |
| 11 | `lun mapping show -fields reporting-nodes` | The scope Selective LUN Map narrows |
| 12 | In a test environment, change throughput capacity and, **while loading both protocols**, record the success/failure and duration of a 1-second-interval direct write | **Whether I/O continues during failover. Second generation needs 6 hours between changes, so a retry comes after that** |
| 13 | Simultaneously record `nvme ana-log` and the controller `state` every 2 seconds | **The moment ANA flips** |

Do steps 8 and 12 **in a test environment.** Step 8 doubles path count in production. **For step 12, start your probe first and confirm where it records before requesting the change.** A retry comes 6 hours later.

Step 1's LIF count can be confirmed with this read-only command (scoped to the SVM).

```bash
ssh <svm-management-endpoint> network interface show -vserver <svm> -data-protocol iscsi
```

### Expected output

```text
1 iSCSI LIF per node, 2 per SVM. Path count = LIF count × session count.
Moving nr_sessions by 1 moves paths by 2 (because an SVM has a LIF on both nodes).
```

This command only reads LIFs; it changes nothing on the LIF or the session. The measured failover (step 12) needs a 6-hour gap between throughput-capacity changes on second generation.

## Read next

[What does a LUN snapshot guarantee by default?](a-snapshot-of-a-lun-is-crash-consistent.md)
