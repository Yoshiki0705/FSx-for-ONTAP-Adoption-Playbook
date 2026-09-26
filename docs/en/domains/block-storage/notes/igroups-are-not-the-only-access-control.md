---
title: Two controls outside the igroup — CHAP and portset are usable with fsxadmin
lifecycle: [design, build, operate]
domains: [block-storage, security-governance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
deployment_type: MULTI_AZ_2
lang: en
---

# What controls exist outside the igroup?

CHAP and portset. Both are usable with `fsxadmin`, and the igroup alone cannot prevent IQN spoofing.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/igroups-are-not-the-only-access-control.md) | [English](igroups-are-not-the-only-access-control.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- That block access control includes not only the igroup but CHAP (IQN authentication) and portset (LIF restriction), and both can be operated with `fsxadmin`
- That CHAP's default is no authentication, and that while a portset narrows the path count, it leaves residue on the host side

## What this note does not answer

- Whether CHAP / portset are documented in FSx for ONTAP's official documentation (could not be found; usability was measured)
- Whether portset is deprecated (no statement of deprecation was found, and non-deprecation was not confirmed either)

## Prerequisite level

advanced

## Body

<a id="two-controls-outside-the-igroup"></a>

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

### Conclusion

**FSx for ONTAP's block access control is not the igroup alone.** ONTAP has **CHAP** (initiator authentication) and **portset** (restricting the LIFs a LUN is shown through), and **both were operable with `fsxadmin`.**

**Neither could be found in FSx for ONTAP's official documentation** (checked on 2026-09-05 against the iSCSI-related pages of the FSx for ONTAP User Guide. **Not an exhaustive search**). **That they are usable was measured.** **Do not read the absence of documentation as lack of support.**

| Control | What it restricts | Default |
|---|---|---|
| igroup | **Which initiator** can see the LUN | Created explicitly |
| CHAP | Whether **the IQN an initiator claims is genuine** | **`none`** (no authentication) |
| portset | **Through which LIF** the LUN is visible | None (the LIFs of all reporting nodes) |

**In an igroup-only configuration, spoofing an IQN reaches the LUN.** An IQN is a string written in a host-side config file, not a secret. **Whether to apply CHAP is a judgment on how you view IQN spoofing on that network.**

> **Tier**: `verified` (verified 2026-09-05, `ap-northeast-1`, `MULTI_AZ_2` second generation, 1 HA pair, ONTAP 9.18.1P5, Amazon Linux 2023) — whether the commands work, the defaults, the symptom on authentication failure, and the host-side state when a portset is applied.

---

### The commands usable with `fsxadmin`

**FSx for ONTAP's `fsxadmin` has restricted privileges.** This is the result of actually running the ones related to block control.

| Command | Result |
|---|---|
| `vserver iscsi security show` / `create` | **Worked** |
| `lun portset show` / `create`, `lun igroup bind` / `unbind` | **Worked** |
| `vserver consistency-group show` / `create` | **Worked** |
| `statistics lun show` | **Worked** |
| `storage failover show` | **Returned an empty table** |

**That `storage failover show` returned "This table is currently empty" is not a permission error.** **FSx for ONTAP does not show the HA state to `fsxadmin`.** As a consequence, **there is no path to induce a failover with `storage failover takeover`.** The only means to induce one is changing the throughput capacity (see [Paths are the failover mechanism itself (日本語)](paths-are-the-failover-mechanism.md)).

---

### CHAP's default, and how to apply it

**The default is no authentication.**

```text
Vserver      Initiator Name   Auth Type   Auth Policy   Inbound User   Outbound User
------------ ---------------- ----------- ------------- -------------- --------------
<svm>        default          none        -             -              -
```

**As long as the `default` row is `none`, anyone who claims an IQN on the igroup can log in.**

CHAP configuration is on the ONTAP CLI too, but **the CLI takes the password at an interactive prompt.** REST was used for automation.

```text
POST https://<management-ip>/api/protocols/san/iscsi/credentials
{
  "svm": {"name": "<svm>"},
  "initiator": "iqn.1994-05.com.redhat:xxxxxxxx",
  "authentication_type": "chap",
  "chap": {"inbound": {"user": "<chap-user>", "password": "<secret>"}}
}
```

The display after configuration. `Auth Policy` becomes `local`.

| Item | Value |
|---|---|
| Auth Type | `CHAP` |
| Auth Policy | `local` |

**The distinction between one-way and mutual authentication is inbound / outbound.**

| Kind | What to configure |
|---|---|
| One-way (the target authenticates the initiator) | The inbound user and password |
| Mutual (the initiator also authenticates the target) | Both inbound and outbound. **The same password cannot be used** |

The CHAP username is 1–128 bytes. **There is also `-initiator-address-ranges` to restrict by the initiator's address range.**

---

### The symptom when authentication fails

**CHAP was applied on the target side, and a login was made with nothing configured on the initiator side.**

```text
iscsiadm: Could not login to [iface: default, target: iqn...:vs.4, portal: <iscsi-1c>,3260].
iscsiadm: initiator reported error (24 - iSCSI login failed due to authorization failure)
iscsiadm: Could not log into all portals
```

On the `iscsid` side.

```text
iscsid: Login failed to authenticate with target iqn...
iscsid: session 3 login rejected: Initiator failed authentication with target
```

| Observation | Value |
|---|---|
| The exit code of `iscsiadm -m node -L all` | **24** |
| Sessions established | **0** |

**The symptom is clear.** It comes out not as "not visible" but as "rejected at authentication." **When starting to investigate with a symptom of the LUN not being visible, looking here before suspecting the igroup finishes the isolation.**

Configuring the initiator side and logging in again worked.

```bash
iscsiadm -m node --op=update -n node.session.auth.authmethod -v CHAP
iscsiadm -m node --op=update -n node.session.auth.username   -v <chap-user>
iscsiadm -m node --op=update -n node.session.auth.password   -v <secret>
iscsiadm -m node -L all      # exit code 0, session recovers
```

**Run the node record update without narrowing by `-T` / `-p`.** In the verification environment, the form specifying the portal returned `No records found`. The unnarrowed form worked.

---

### That a portset actually reduces the path count, and the residue

**A portset is the restriction "show this igroup only through this LIF."** It is an additional narrowing layered on top of Selective LUN Map.

```text
lun portset create -vserver <svm> -portset ps_1a_only -protocol iscsi -port-name iscsi_1
lun igroup bind   -vserver <svm> -igroup <igroup> -portset ps_1a_only
```

**`-protocol` is `mixed` (default) / `fcp` / `iscsi`.** A portset name is 1–96 characters and **case-sensitive**. **You cannot bind to an empty portset.**

**The effect showed up on the host side.** But **the excluded path does not disappear.**

The state after `iscsiadm -m session --rescan` and `multipath -r`.

```text
`-+- policy='service-time 0' prio=0 status=enabled
  `- 0:0:0:0 sda     8:0   active faulty running
```

| Observation | Detail |
|---|---|
| The path via the excluded LIF | **`faulty`, `prio=0`** |
| The `lsblk` size | **0B** |
| The map's `hwhandler` | **Dropped from `'1 alua'` to `'0'`** |

**The LUN just stops being reported; the SCSI device remains on the host.** Cleanup is needed.

```bash
multipath -f <wwid>
echo 1 > /sys/block/sda/device/delete
multipath -r
```

**This gives a healthy single-path map, and `hwhandler='1 alua'` returns too.**

**If you put a portset into operation, include host-side device deletion in the procedure.** Otherwise **a configuration with a `faulty` path left behind is thought to be healthy.**

There are two cautions on unbinding.

| Operation | Caution |
|---|---|
| `lun igroup unbind` | **Does not take a `-portset` argument.** Specify only the igroup |
| `lun portset delete` | **Cannot be deleted while an igroup is bound.** Unbind first |

**No statement that a portset is deprecated was found.** But **it was also not confirmed to be non-deprecated** — what was confirmed is only that it was created and worked in this verification environment.

---

### The judgment of which to use

**The three can be layered. Their purposes differ.**

| Purpose | What to use |
|---|---|
| Which LUN to show to which host | **igroup** (required) |
| Prevent IQN spoofing | **CHAP** |
| Reduce the path count, restrict the route | **portset** |
| Fit within the host's path-count limit | **portset** (or LIF-side design) |

**Whether to apply CHAP is decided by who can get onto that subnet.** Because the block address is an ordinary address inside the VPC CIDR (see [Multi-AZ moves a route, not an address](multi-az-moves-a-route-not-an-address.md)), **narrowing the reachable range with the security group is the first control.** CHAP is the layer above it. **It is not one or the other.**

**A portset is ONTAP's answer to the problem of too many paths.** There is also a way to adjust with the host-side session count, and **unless you record which one you narrowed with, the reason is not clear afterward.** The point that the path-count guidance conflicts between documents is in [Paths are the failover mechanism itself (日本語)](paths-are-the-failover-mechanism.md).

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| Block access control is the igroup alone | **There are CHAP and portset.** Both were usable with `fsxadmin` |
| CHAP cannot be used because it is not in AWS's documentation | **It was usable.** Being undocumented and being unsupported are different |
| No authentication is needed since it cannot reach unless on the igroup | **An IQN is a host-side config string, not a secret** |
| CHAP is enabled by default | **The default is `none`** |
| Mutual authentication can use the same password | **The same password cannot be used for inbound and outbound** |
| A CHAP failure appears as "the LUN is not visible" | **It is stated explicitly as `error (24 ... authorization failure)`.** The exit code is 24 |
| `iscsiadm --op=update` is done specifying the portal | **Run it without narrowing.** The specified form returned `No records found` |
| Applying a portset makes the host's path disappear | **It does not.** A `faulty` SCSI device remains and needs deletion |
| Unbind with `lun igroup unbind -portset …` | **There is no `-portset` argument** |
| A portset is deprecated | **No statement that it is deprecated was found.** In this environment it was created and worked (not a confirmation of non-deprecation) |
| An empty `storage failover show` is a permission error | **It is not an error.** FSx for ONTAP does not show the HA state |

---

### Verification environment

| Item | Value |
|---|---|
| ONTAP version | 9.18.1P5 |
| Region | `ap-northeast-1` |
| Deployment type | `MULTI_AZ_2` (second generation, 1 HA pair) |
| Throughput capacity | 384 MBps |
| iSCSI LIF | 2 (one per AZ) |
| Client | Amazon Linux 2023, kernel 6.18.44-99.149.amzn2023.x86_64 |
| Verification date | 2026-09-05 |

> **Note**: the above is a measurement in this environment. **The operations permitted to `fsxadmin` can change.** Confirm in your own environment before building it into a design.

---

### Primary sources referenced

| Point | Source |
|---|---|
| CHAP configuration, the one-way/mutual distinction, inbound/outbound, that the same password cannot be used, the username length, `-initiator-address-ranges` | [NetApp: vserver iscsi security create](https://docs.netapp.com/us-en/ontap-cli/vserver-iscsi-security-create.html) |
| The concept of iSCSI authentication methods | [NetApp: iSCSI authentication](https://docs.netapp.com/us-en/ontap/san-admin/iscsi-authentication-concept.html) |
| Creating a portset, the values and default of `-protocol`, the naming rules | [NetApp: lun portset create](https://docs.netapp.com/us-en/ontap-cli/lun-portset-create.html) |
| Binding an igroup and a portset | [NetApp: lun igroup bind](https://docs.netapp.com/us-en/ontap-cli/lun-igroup-bind.html) |
| That a portset restricts the LIFs a LUN is shown through, and that it is named as a means to hold down the path count | [NetApp: Multipathing](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |
| That Selective LUN Map is enabled by default | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |
| How a LUN is shown by an igroup | [AWS: Provisioning iSCSI for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html) |
| The ports that need to be opened for iSCSI in the security group | [AWS: File system access control with Amazon VPC](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limit-access-security-groups.html) |

---

### Related documents

- [Domain — Block storage](../README.md) — this module's hub
- [Paths are the failover mechanism itself (日本語)](paths-are-the-failover-mechanism.md) — the paths a portset narrows
- [Multi-AZ moves a route, not an address](multi-az-moves-a-route-not-an-address.md) — that the block address is inside the VPC
- [LUNs and igroups are outside the AWS API](block-objects-are-outside-the-aws-api.md) — that the igroup is outside IaC
- [Evidence policy](../../../evidence-policy.md)

## Verify it in your environment

| # | Step | What it tells you |
|---|---|---|
| 1 | `vserver iscsi security show -vserver <svm>` | **Whether `default` is `none`. Whether you operate with no authentication is clear here** |
| 2 | Whether `vserver iscsi security create` or the REST `credentials` works | **That CHAP can be configured with `fsxadmin`** |
| 3 | Log in with the initiator side unconfigured, and record the exit code and `journalctl -u iscsid` | **The symptom of authentication failure** (the footing for isolation) |
| 4 | Whether `lun portset create` and `lun igroup bind` work | **That a portset is usable with `fsxadmin`** |
| 5 | After binding, confirm the path count and any `faulty` with `multipath -ll` | **That the narrowing took effect, and the residue** |
| 6 | Delete the residue with `echo 1 > /sys/block/<dev>/device/delete` and confirm `hwhandler` returns | **The cleanup procedure** |
| 7 | Run `storage failover show` | **If an empty table, the HA state is not visible** |

Do steps 3 and 5 **in a test environment.** Both temporarily lose access.

CHAP's default in step 1 can be confirmed with this read-only command.

```bash
ssh <svm-management-endpoint> vserver iscsi security show -vserver <svm>
```

### Expected output

```text
If the default row's Auth Type is none, there is no authentication. Anyone who claims an IQN on
the igroup can log in. Whether to apply CHAP is decided by who can reach that subnet (the
security-group range).
```

This command only reads the iSCSI security configuration; it changes nothing on authentication or the LUN. If you put a portset into operation, include host-side device deletion for the excluded path in the procedure.

## Read next

[Can a database on LUNs recover without quiescing?](a-database-on-luns-recovers-without-quiescing.md)
