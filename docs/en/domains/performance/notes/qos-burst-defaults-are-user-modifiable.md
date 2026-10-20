---
title: On FSx for ONTAP 9.19.1 the QoS burst defaults are user-modifiable — confirmed in both configuration and real I/O
lifecycle: [design, operate, optimize]
domains: [performance]
evidence: verified
verified_on: 2026-10-18
region: ap-northeast-1
ontap_version: 9.19.1P2
deployment_type: SINGLE_AZ_1
lang: en
---

# Can the QoS burst defaults be changed on FSx for ONTAP 9.19.1?

Yes. The change is accepted through the ONTAP management plane (REST private CLI / CLI), and it is reflected in real I/O behavior.

## What you will learn

- That the defaults of the three QoS burst options added in ONTAP 9.19.1 (burst-percent / burst-duration / burst-iops) are user-modifiable on Amazon FSx for NetApp ONTAP as well.
- Not only that the configuration is accepted (HTTP 201/200 plus read-back), but the result of confirming, in real I/O, that a burst exceeding the ceiling occurs exactly as configured.
- That this option applies to a regular throughput-ceiling policy group, not to adaptive QoS.
- The split between the plane you can change it from (ONTAP REST / CLI) and the plane you cannot (the AWS Management Console / the FSx for ONTAP AWS API).

## What this note does not answer

- Whether a downgrade (revert) is operationally possible on FSx for ONTAP (unverified).
- How burst settings interact with other features such as SnapMirror / MetroCluster.
- The effect of each burst value on overall workload cost or billing.

## Prerequisite level

intermediate

## Body

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

---

### Conclusion

**The three QoS burst options added in ONTAP 9.19.1 have user-modifiable defaults on FSx for ONTAP as well.** The route is the ONTAP management plane (REST private CLI / CLI). create / modify are accepted, read-back confirms the values, and real I/O showed that a burst exceeding the ceiling occurs exactly as configured.

**The AWS Management Console and the FSx for ONTAP AWS API have no parameter corresponding to these burst options.** As in the long-standing two-plane structure, the configuration is done on the ONTAP side.

> **Tier**: `verified` — confirmed against a verification FSx for ONTAP file system in ap-northeast-1 (ONTAP 9.19.1P2, SINGLE_AZ_1), from a Linux client inside the VPC using ONTAP REST / CLI and fio (2026-10-18). A different configuration will hit different ceilings and show different behavior.

---

### Clarifying the target

**These burst options apply to a regular throughput-ceiling QoS policy group, not to adaptive QoS.** Even if the original question had adaptive QoS in mind, the precise target is the former.

This was confirmed both in documentation (throughput ceiling configuration, throughput guarantee) and on a live system. On the live system, the burst fields did not appear in the REST schema of an adaptive-policy-group; burst_percent / burst_duration / burst_iops existed only on a regular policy-group.

---

### Definitions and defaults of the three options

| Option | Default | Meaning |
|---|---|---|
| burst-percent | 50% | The percentage over the ceiling (how far the peak exceeds it) |
| burst-duration | 1 second | How many seconds the excess is sustained |
| burst-iops | 0 | The absolute IOPS cap during the excess (0 means unused) |

**burst-percent and burst-iops are mutually exclusive.** Use burst-percent to specify the excess as a percentage, or burst-iops to specify it as an absolute IOPS value.

---

### Measuring that the configuration is accepted

create / modify against `qos/policy-group` on the ONTAP REST private CLI were accepted, and read-back confirmed the values.

| Operation | Result |
|---|---|
| create (burst-percent=25) | HTTP 201, read-back shows burst_percent:25 |
| modify (burst-duration=5) | HTTP 200, read-back shows burst_duration:5 |
| create (burst-iops=3000, ceiling 2000 IOPS) | HTTP 201, read-back shows burst_iops:3000 |

---

### Measuring real I/O behavior

#### Test environment

| Item | Value |
|---|---|
| Deployment type | First-generation, Single-AZ (SINGLE_AZ_1) |
| ONTAP version | 9.19.1P2 |
| Throughput capacity | 128 MBps |
| Provisioned SSD IOPS | 3,072 (automatic; the default 3 IOPS per GiB on 1,024 GiB SSD) |
| Storage capacity | 1,024 GiB SSD |
| Region | ap-northeast-1 |
| Workload | 4 KB random read |
| QoS ceiling under test | 2,000 IOPS |
| Baseline without QoS | 24,400 IOPS |
| Observation resolution | 1 second (per-second IOPS captured with fio `--log_avg_msec=1000`) |
| Idle period before load | Present (to accumulate burst credit); duration not recorded |
| Client EC2 instance type | verification bastion, currently t2.medium (instance type at measurement time not recorded) |
| Protocol and mount options (NFS version, rsize/wsize, etc.) | NFSv3 (fio 3.32); rsize/wsize not recorded |
| fio parameter rw | randread |
| fio parameter bs | 4 KB |
| fio parameter iodepth | 32 |
| fio parameter numjobs | 4 |
| fio parameter direct | 1 |
| fio parameter size | 500 MiB (per-job test file) |
| fio ioengine | libaio |
| fio parameter runtime | not recorded |
| Idle-period duration (seconds) | not recorded |
| Number of trials / repetitions | not recorded |
| Volume tiering policy of the volume under test | not recorded (volume under test was a 1 GiB volume) |

The values that remain "not recorded" are the fio runtime, the idle-period duration in seconds, the number of trials, the mount rsize/wsize, the client instance type at measurement time, and the tiering policy of the volume under test. None were captured in the verification log, and they are listed so the reader knows the measurement's boundaries.

With the ceiling set to 2000 IOPS, load was applied from a Linux client inside the VPC using fio (4k random read, NFSv3), and per-second IOPS were observed while varying the settings. The baseline with no QoS is 24,400 IOPS. In every pattern, an idle period was placed before applying the ceiling so that burst credit accumulated before the load started.

| Pattern | Settings | t=1s peak | Steady | Dominant aspect |
|---|---|---|---|---|
| 2 | Default (percent=50, duration=1) | 3017 | 2000 | Excess width. Exceeds ceiling+50% for 1 second only, converges by the 2nd second |
| 3 | percent=25, duration=1 | 2507 | 2000 | Excess width. percent maps directly to the peak excess width, narrowed to +25% |
| 4 | percent=50, duration=5 | ~3000 held across t=1..5s | 2000 | Duration. duration determines how many seconds the excess continues |
| 5 | burst-iops=3000, duration=5 (percent=0) | ~3000 held across t=1..5s | 2000 | Absolute value. The excess IOPS pin at 3000 |
| 6 | Disabled (0/0/0) | 2020 (about +1%) | 2000 | Disappearance. The excess spike is gone, roughly within the ceiling |

**percent governs the peak excess width, duration governs how long the excess is sustained, and burst-iops governs the absolute IOPS during the excess; at 0/0/0 the burst itself disappears.** For each setting, it was possible to observe in isolation which aspect of the behavior moved.

The documentation (the load balancing explanation) states that the ceiling may be exceeded by up to 10%, that a burst may exceed it by up to 50%, and that a burst occurs when tokens accumulate up to 150% on a single node. The +50% peak in pattern 2 and the roughly +1% in pattern 6 are consistent with this description.

---

### Value constraints on the ONTAP side

The following two are constraints of ONTAP itself, not constraints specific to FSx for ONTAP. On the live system, ONTAP also rejected these combinations.

- **burst-iops and burst-percent are mutually exclusive.** Specifying both at once causes ONTAP to reject them. When switching an existing policy to burst-iops while burst_percent is still set, resetting burst-percent to 0 first and then setting burst-iops is accepted.
- **burst-iops must be greater than max-throughput (the ceiling IOPS).** Against a ceiling of 2000 IOPS, ONTAP rejected burst-iops=500, while burst-iops=3000 was accepted. The command reference states that if burst-iops is below max-throughput, max-throughput is used.

> **Note**: The error code numbers obtained on the live system are omitted from this note. What matters for the behavior is which combinations ONTAP rejects, and the numbers can vary by environment.

> **Note on isolation from FSx for ONTAP-side bursting**: ONTAP QoS burst and FSx for ONTAP-side (AWS-side) bursting are different layers. QoS burst governs how far a workload may exceed its ceiling; FSx for ONTAP-side bursting governs how much the file system itself can deliver. QoS is a mechanism that caps; it cannot push a workload above what the file system can deliver ([consistent with FSx for ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html)). In this measurement, the peak was ~3,000 IOPS (~12 MB/s) against ~24,400 IOPS available without QoS — a large margin — so FSx for ONTAP-side bursting did not affect the result. This test configuration (128 MBps, Single-AZ 1) IS subject to FSx for ONTAP-side bursting, as the performance page states; the point is the margin, not exemption. As a design expectation (not measured in this verification): if a design sets the sum of per-workload (ceiling + burst) above the file system's baseline (sustained) performance, then once FSx for ONTAP-side credits are exhausted a workload may not even reach its ceiling, and the same QoS settings can behave differently depending on credit state. The design guidance is to size so the sum of ceilings fits within the file system's baseline (sustained) performance, not its burst performance. This saturated case was not measured here.

---

### A caution before downgrading

> **Tier**: `documented` — a QoS policy group whose burst was changed on 9.19.1 requires the three values (burst-percent / burst-iops / burst-duration) to be reset to 0 before reverting to 9.18.1. The source is [ONTAP revert: Modify QoS policy groups](https://docs.netapp.com/us-en/ontap/revert/modify-qos-policy-groups.html).

**Whether a downgrade (revert) is operationally possible on FSx for ONTAP is a separate question and is unverified in this note.** The procedure for resetting burst settings to 0 is documented, but whether revert can be executed in the managed FSx for ONTAP environment has not been confirmed.

---

### The plane you can change and the plane you cannot

**What was confirmed is only the ONTAP REST / CLI route.** On this route the burst defaults can be changed, and the change is reflected in real I/O.

**They cannot be set from the AWS Management Console or the FSx for ONTAP AWS API.** These have no parameter corresponding to the burst options. On FSx for ONTAP, QoS policy groups in general are the domain of the ONTAP management plane, and changing the burst defaults is part of that.

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| The burst defaults cannot be changed on FSx for ONTAP | **They can be changed on ONTAP 9.19.1P2, and the change is reflected in real I/O.** The route is ONTAP REST / CLI |
| This option is for adaptive QoS | **It applies to a regular throughput-ceiling policy group.** The burst fields did not appear in the REST schema of an adaptive-policy-group |
| It can be set from the AWS Console or the FSx for ONTAP AWS API | **There is no corresponding parameter.** It is set from the ONTAP management plane |
| burst-percent and burst-iops can be used together | **They are mutually exclusive.** To specify it as an absolute IOPS value, reset burst-percent to 0 first |
| burst-iops can take any value | **It must be greater than max-throughput (the ceiling IOPS).** ONTAP rejects a value below the ceiling |
| The mutual exclusivity and the value floor are FSx for ONTAP constraints | **They are constraints of ONTAP itself.** FSx for ONTAP is not what blocks them |
| If the configuration is accepted, there is no need to confirm the behavior | **Acceptance of the configuration and the real I/O behavior are separate confirmations.** This note confirms both |

---

### Primary sources referenced

| Point | Source |
|---|---|
| The procedure for setting a throughput ceiling with a QoS policy group, and that the burst defaults can be changed on 9.19.1 and later | [NetApp: Set a throughput ceiling with QoS](https://docs.netapp.com/us-en/ontap/performance-admin/set-throughput-ceiling-qos-task.html) |
| The procedure for setting a throughput floor (guarantee), the context in which the burst options relate to a regular policy-group | [NetApp: Set a throughput floor (guarantee) with QoS](https://docs.netapp.com/us-en/ontap/performance-admin/guarantee-throughput-qos-task.html) |
| The definitions and defaults of burst-percent / burst-iops / burst-duration, their mutual exclusivity, and that max-throughput is used when burst-iops is below max-throughput | [NetApp: qos policy-group create](https://docs.netapp.com/us-en/ontap-cli/qos-policy-group-create.html) |
| The behavior that the ceiling may be exceeded by up to 10%, that a burst may reach up to 50%, and that a burst occurs when tokens accumulate up to 150% | [NetApp: Load balancing concept](https://docs.netapp.com/us-en/ontap/concepts/load-balancing-concept.html) |
| That the three burst values must be reset to 0 before reverting to 9.18.1 | [NetApp: Modify QoS policy groups before reverting](https://docs.netapp.com/us-en/ontap/revert/modify-qos-policy-groups.html) |

---

### Related documents

- [Domain — Performance](../README.md) — the hub for this module
- [A figure from a single connection measures the client, not the storage](a-single-connection-measures-the-client.md) — a record of the conditions when measuring performance figures
- [Evidence Policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Performance](../README.md)

---

## Confirming this in your own environment

**First, check the current burst settings read-only.** The following steps do not touch any existing QoS policy group.

An example of reading the current burst settings on the ONTAP REST private CLI.

```console
GET /api/private/cli/qos/policy-group?fields=policy_group,max_throughput,burst_percent,burst_duration,burst_iops
```

The equivalent CLI command is as follows.

```console
qos policy-group show -instance
```

### Expected result

Each policy group returns its `max_throughput` (ceiling) and the three burst values. If burst has not been changed, burst_percent shows 50, burst_duration shows 1, and burst_iops shows 0.

### Reaching the ONTAP management plane from AWS

> **Tier**: `verified` — confirmed the `aws fsx describe-file-systems` management-endpoint retrieval on a verification FSx for ONTAP file system in ap-northeast-1 (ONTAP 9.19.1P2) on 2026-10-19.

The ONTAP management plane (REST private CLI / CLI) is reached **from inside the VPC only**. As stated in "The plane you can change and the plane you cannot" above, these burst fields have no corresponding parameter on the AWS API side, so the configuration route is the ONTAP management plane.

Get the management endpoint's DNS name and IP with the AWS CLI.

```console
aws fsx describe-file-systems --file-system-id <file-system-id> \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management'
```

This returns `DNSName` and `IpAddresses` (the management endpoint). Reach it over HTTPS 443 from a host inside the VPC (for example, an Amazon EC2 instance or a bastion). The security group on that path must allow 443 to the endpoint.

Authenticate as the ONTAP admin user (`fsxadmin`). Keep its credentials in AWS Secrets Manager and read them at call time. Do not hardcode them. The commands below use the ONTAP REST private CLI (`/api/private/cli/...`), reaching this management endpoint with HTTP Basic auth.

### Create / modify / read-back / delete on a verification policy group

> **Tier**: `verified` — confirmed on a live FSx for ONTAP file system (ONTAP 9.19.1P2, ap-northeast-1, 2026-10-19) that the REST private-CLI requests below return the stated HTTP status and read-back values.

**If you actually change and try it, do so within a reversible scope: create a verification policy group, apply it, confirm, and delete it.** Directly changing the values of a policy group applied to a production volume immediately changes that volume's I/O behavior.

The commands matching each step of the 4-step table below. `<name>` / `<svm>` / `<volume>` are placeholders.

Steps 1-2 (create a verification policy group with a ceiling and burst set) — REST private CLI POST:

```console
POST /api/private/cli/qos/policy-group
{"policy_group":"<name>","vserver":"<svm>","max_throughput":"2000IOPS","burst_percent":25,"burst_duration":5}
```

Returns HTTP 201 (read-back: `max_throughput:2000IOPS, burst_percent:25, burst_duration:5`).

Read back:

```console
GET /api/private/cli/qos/policy-group?policy_group=<name>&fields=policy_group,max_throughput,burst_percent,burst_duration,burst_iops
```

Switch from burst_percent to burst_iops (they are mutually exclusive, so reset percent to 0 first, then set iops) — two PATCH calls:

```console
PATCH /api/private/cli/qos/policy-group?policy_group=<name>
{"burst_percent":0}
```

then:

```console
PATCH /api/private/cli/qos/policy-group?policy_group=<name>
{"burst_iops":3000}
```

Each returns HTTP 200 (read-back: `burst_iops:3000`, and `burst_percent` no longer present — the live confirmation of the mutual-exclusion constraint this note describes, and why the reset-to-0 ordering is needed).

Step 4 (delete; return to a reversible state):

```console
DELETE /api/private/cli/qos/policy-group?policy_group=<name>
```

Returns HTTP 200 (read-back `num_records: 0`).

> **Tier**: `documented` — the equivalent commands for readers who use the ONTAP CLI rather than REST. Since this note's verification executed only the REST private-CLI path above, the bare CLI strings below are treated as `documented`, per the NetApp `qos policy-group create` reference (<https://docs.netapp.com/us-en/ontap-cli/qos-policy-group-create.html>).

```console
qos policy-group create -policy-group <name> -vserver <svm> -max-throughput 2000IOPS -burst-percent 25 -burst-duration 5
qos policy-group modify -policy-group <name> -burst-percent 0
qos policy-group modify -policy-group <name> -burst-iops 3000
qos policy-group delete -policy-group <name>
```

### Applying to a verification volume (step 3)

> **Tier**: `documented` — the volume-apply step was not executed on the live file system in this note's verification (existing volumes belong to other verification work and were left untouched). The create / modify / read-back / delete path is proven, but the volume-apply form is from the docs.

The command form for applying the policy group to a volume.

```console
volume modify -vserver <svm> -volume <volume> -qos-policy-group <name>
```

The REST private CLI equivalent sends `PATCH /api/private/cli/volume?vserver=<svm>&volume=<volume>` with body `{"qos_policy_group":"<name>"}`. Detach specifies `none` on the policy group (`volume modify ... -qos-policy-group none`; both `documented`).

| # | Step | What it confirms |
|---|---|---|
| 1 | Create a verification QoS policy group with a ceiling (max-throughput) | That create is accepted with HTTP 201 (`verified`) |
| 2 | Change burst-percent / burst-duration / burst-iops | That modify is accepted with HTTP 200 and read-back confirms the values (`verified`) |
| 3 | Apply the policy group to a verification volume and apply I/O after an idle period | That a burst exceeding the ceiling occurs exactly as configured (apply command form is `documented`, not run live) |
| 4 | Detach the policy group from the volume and delete it | That read-back shows the target is gone (delete is `verified`; the detach form is `documented`) |

Observing the behavior in step 3 requires a load tool that can record per-second IOPS (for example, fio's per-second log). A single average value alone cannot separate the peak excess width from its duration.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/performance/notes/qos-burst-defaults-are-user-modifiable.md) | [English](qos-burst-defaults-are-user-modifiable.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
