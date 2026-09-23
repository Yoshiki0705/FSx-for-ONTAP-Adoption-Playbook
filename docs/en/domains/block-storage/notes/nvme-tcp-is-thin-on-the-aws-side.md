---
title: NVMe/TCP is thin on the AWS side across the board — the security-group table, the protocol list, and the API alike
lifecycle: [design, build, operate]
domains: [block-storage, security-governance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: en
---

# NVMe/TCP is thin on the AWS side across the board

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/nvme-tcp-is-thin-on-the-aws-side.md) | [English](nvme-tcp-is-thin-on-the-aws-side.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

[🏠 Repository home](../../../README.md) | [Domain — Block storage](../README.md)

---

## Conclusion

**The FSx for ONTAP security-group requirements table does not list the NVMe/TCP ports.** It does list iSCSI's TCP 3260. So **if you design a security group from the requirements table alone, NVMe/TCP will not connect.**

**Two ports need to be open: TCP 4420 for data, TCP 8009 for discovery.** This was measured in our own environment. But **we have not confirmed that "these two are exhaustive"** (no negative control was taken; see [Verification environment](#verification-environment)).

**It is not only the table that is missing them.** They also do not appear in the body of the same page, nor in the AWS API responses.

| AWS-side surface | iSCSI | NVMe/TCP |
|---|---|---|
| Port in the security-group requirements table | Listed as TCP 3260 | **Not listed** |
| The protocol list in the same page's body | Listed | **Does not appear in the list** |
| The endpoint from `describe-storage-virtual-machines` | `Iscsi` is returned | **`Nvme` is `null`. Not returned even when reachable** |

> **Tier**: `verified` (verified 2026-09-05, `ap-northeast-1`, `MULTI_AZ_2` second generation, 1 HA pair, ONTAP 9.18.1P5, Amazon Linux 2023 kernel 6.18.44) — the port numbers and `Nvme: null`. **The presence or absence of documentation was confirmed by reading the relevant pages through on 2026-09-12.**

---

## The scope searched, and the result

**As of 2026-09-12, the following three pages were read through.**

| Page | Treatment of 4420 | Treatment of 8009 |
|---|---|---|
| [File System Access Control with Amazon VPC](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limit-access-security-groups.html) (the requirements table) | Not stated | Not stated |
| [Provisioning NVMe/TCP for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html) (procedure) | **Appears only as `trsvcid=4420` inside an example output**; not stated as a port to open | Not stated |
| [Use NVMe/TCP to mount FSx for ONTAP file system on Linux instance](https://www.repost.aws/knowledge-center/ec2-mount-fsx-ontap-nvme-tcp) (Knowledge Center) | **Allowing 4420 inbound is stated explicitly as a prerequisite** | Not stated |

**Only the third states 4420 as a requirement.** It is a Knowledge Center article, not the requirements table, and it does not touch 8009. **A reader who starts from the requirements table as the entry point never reaches it.**

As for 8009, **no mention could be found in any of the above.** The absence of a statement is not the same as its being unnecessary. In our measurement discovery succeeded on 8009.

---

## The procedure to follow when designing a security group

**Start from the requirements table and add per-protocol from the procedure pages.** Not treating the table as an exhaustive list is this note's practical consequence.

| Protocol | Port | Source |
|---|---|---|
| iSCSI | TCP 3260 | The requirements table |
| NVMe/TCP (data) | TCP 4420 | Measured. Not in the requirements table |
| NVMe/TCP (discovery) | TCP 8009 | Measured. No mention found on public pages |

The CloudFormation used by the [30-minute quickstart](../quickstart.md) opens iSCSI only (`fsxontap-iscsi-quickstart.yaml`). To try NVMe/TCP, add 4420 and 8009 to the same `SecurityGroupIngress`.

---

## The consequence of not being able to get the NVMe endpoint from the AWS API

The `Endpoints` of `describe-storage-virtual-machines` does not include `Nvme`; it returns `null`. This does not change even when NVMe/TCP is actually reachable.

**So the connection address cannot be obtained from the AWS API alone.** It uses the same two addresses as iSCSI, but to learn them you read the `Iscsi` endpoint or look at `network interface show` on the ONTAP side. In our measurement the `services` of `iscsi_1` / `iscsi_2` contained both `data-iscsi` and `data-nvme-tcp`, so **the same two addresses served both protocols.**

This is the same dividing line as [LUNs and igroups are outside the AWS API (日本語)](../../../../ja/domains/block-storage/notes/block-objects-are-outside-the-aws-api.md), but **that one is "cannot be created through the AWS API" and this one is "cannot be read through the AWS API".** It is separated as a matter of reading a running configuration rather than creating one.

---

## Verification environment

| Item | Value |
|---|---|
| ONTAP version | 9.18.1P5 |
| Region | `ap-northeast-1` |
| Configuration | `MULTI_AZ_2` (second generation), 1 HA pair, throughput capacity 384 MBps, SSD 1024 GiB |
| Client | Amazon Linux 2023, kernel 6.18.44 |
| Verification date | 2026-09-05 |

> **Note**: the above is a measurement in this environment and does not guarantee a general service limit or reproduction in a production environment.

**This verification has no negative control.** All that was observed is that "discovery used 8009 and data used 4420." **Whether a connection succeeds with only 4420 and 8009 open** was not tried. So there is no basis for writing "these two are exhaustive." If you place exhaustiveness as a premise of your own design, run step 3 below.

---

## How to confirm in your own environment

| # | Step | What it tells you |
|---|---|---|
| 1 | `network interface show -vserver <svm> -lif <iscsi_lif> -fields services` | Whether that address serves `data-nvme-tcp`. Whether the iSCSI addresses can be used as-is is decided here |
| 2 | On the client, run `nvme discover -t tcp -a <lif_ip> -s 8009` and `nvme connect-all -t tcp -a <lif_ip>`, then read `trsvcid` with `nvme list-subsys` | Which port discovery and data each used |
| 3 | **Create a new security group allowing only 4420 and 8009, attach only it, and re-run step 2** | **Exhaustiveness.** If this passes, you can write "two are enough." We have not done this |
| 4 | `aws fsx describe-storage-virtual-machines --storage-virtual-machine-ids <id> --query 'StorageVirtualMachines[].Endpoints'` | Whether `Nvme` is returned. If it is `null` in your environment too, build the procedure on the premise that the address is taken from the ONTAP side |

For the overall application procedure, see [Before adopting into production](../../../evidence-policy.md#before-adopting-into-production).

---

## Common misconceptions

| Misconception | Reality |
|---|---|
| The security-group requirements table is an exhaustive list of the ports needed | **For block protocols it is not exhaustive.** iSCSI's 3260 is there, but NVMe/TCP's 4420 and 8009 are not (confirmed 2026-09-12) |
| The NVMe/TCP ports are written on the procedure page | The `4420` that appears on the procedure page is **the value of `trsvcid` inside an example output**. It is not stated as a port to open |
| Opening only 4420 is enough to connect | In our measurement discovery used 8009. Whether 4420 alone is enough was not confirmed |
| A separate address is issued for NVMe/TCP | In our measurement **the same two addresses** as iSCSI served both protocols. But because the AWS API's `Nvme` returns `null`, the address is taken from the `Iscsi` side or the ONTAP side |
| If there are two block protocols, AWS's documentation treats them comparably | NVMe/TCP is missing in three places: the security-group requirements table, the protocol list on the same page, and `describe-storage-virtual-machines` |

---

## Related documents

- [The block protocol choice is narrowed first by generation and HA pair count (日本語)](../../../../ja/domains/block-storage/notes/protocol-choice-is-bounded-before-you-choose.md) — the decision of which to choose
- [Paths are the failover mechanism itself (日本語)](../../../../ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md) — path count and failover after connecting. **NVMe/TCP cannot form native multipath on Amazon Linux 2023**
- [LUNs and igroups are outside the AWS API (日本語)](../../../../ja/domains/block-storage/notes/block-objects-are-outside-the-aws-api.md) — the dividing line on the creation side
- [The 30-minute block storage quickstart](../quickstart.md) — CloudFormation that opens iSCSI only

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/block-storage/notes/nvme-tcp-is-thin-on-the-aws-side.md) | [English](nvme-tcp-is-thin-on-the-aws-side.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
