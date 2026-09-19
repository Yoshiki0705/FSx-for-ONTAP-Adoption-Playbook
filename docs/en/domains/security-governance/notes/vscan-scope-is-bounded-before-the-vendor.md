---
title: The antivirus choice is settled before the vendor — protocol, identity, availability and exclusions narrow the field first
lifecycle: [design, build, operate]
domains: [security-governance, multiprotocol-identity]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html
lang: en
---

# The antivirus choice is settled before the vendor

[🏠 Repository home](../../../README.md) | [Domain — Security and governance](../README.md)

---

## Conclusion

**Look into antivirus for Amazon FSx for NetApp ONTAP and the first material you find is a list of supported vendors. In the order things are actually decided, that list comes last.**

The AWS user guide names six (Deep Instinct / SentinelOne / Symantec / Trellix / Trend Micro / OPSWAT), **and states no constraints on that page.** The constraints are on the ONTAP Vscan side, and four of them narrow both the field and the configuration before any vendor is compared.

1. **Protocol** — on-access scanning is against SMB; an NFS export is reachable only by on-demand scanning
2. **Identity** — the privileged user a Vscan server connects to the SVM with is **a domain account**
3. **Availability** — with `scan-mandatory` on, a client file operation is **refused** when no Vscan server answers
4. **Exclusions** — even with `scan-mandatory` on, a file matching an exclusion is not scanned. **The default size exclusion is 2 GB**

**The fourth is the one that misleads.** Having enabled mandatory scanning does not mean every file is scanned.

> **Tier**: `documented` — based on AWS and NetApp documentation and a NetApp KB article (**retrieved 2026-09-15**). **No measurement was made in this repository.** As [Which constraints belong to ONTAP and which to FSx for ONTAP](#which-constraints-belong-to-ontap-and-which-to-fsx-for-ontap) records, **every constraint listed here is a general ONTAP property**; no FSx for ONTAP-specific difference was found.

---

## Where the six vendors are enumerated, and what is not written there

**The grounds for using third-party antivirus with FSx for ONTAP are in AWS's own user guide.** Few product combinations have a dedicated page in AWS documentation; this is one of them.

| Source | What it states | What it does not state |
|---|---|---|
| [AWS: Use NetApp ONTAP Vscan with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html) | Six names, and a link to each vendor's documentation | **Not one constraint.** No configuration procedure either |
| [NetApp: ONTAP Vscan partner solutions](https://docs.netapp.com/us-en/ontap/antivirus/vscan-partner-solutions.html) | The same six. Where to check interoperability (the NetApp Interoperability Matrix and each vendor's site) | The specific version combination. **That you have to look up yourself** |
| [NetApp: Antivirus architecture with ONTAP Vscan](https://docs.netapp.com/us-en/ontap/antivirus/architecture-concept.html) | The Vscan server's components, scanner pools, the privileged user, on-access policies, the file-operations profile | Any FSx for ONTAP-specific difference |

**The AWS page being thin is not an omission.** The six products' behaviour is outside what AWS warrants, and pointing at the vendor is the accurate thing to do. **From a reader's position, though, it reads as "choose one of six".** Four things are settled first.

---

## The four things settled before the vendor

### Protocol — on-access is SMB only

**The protocol the on-access policy creation command accepts is `CIFS`.**

```text
vserver vscan on-access-policy create -vserver <SVM> -policy-name <name> -protocol CIFS ...
```

On-access scanning cannot be configured against an NFS export. **A NetApp KB article names exactly that as a use for on-demand scanning: "a volume that cannot be configured for on-access scanning, such as NFS exports".**

**And on-demand is not a substitute for on-access.**

| Kind | Trigger | NFS | SMB |
|---|---|---|---|
| on-access | A client file operation (open / close / rename / write). **The operation is suspended until the result comes back** | Cannot be configured | In scope |
| on-demand | A cron schedule, or `vserver vscan on-demand-task run` by hand | In scope | In scope |

**On-demand requires an on-access policy to exist.** NetApp's documentation states that an on-access policy is required for an on-demand scan, and describes avoiding on-access scanning by setting `-scan-files-with-no-ext false` and `-file-ext-to-exclude *` to exclude every extension. **Configuring on the premise that "we are NFS-only so on-access is irrelevant" stops here.**

On-demand also **uses the existing Vscan servers.** There is no separate execution tier, so **even a configuration that only ever runs on-demand still needs Vscan servers operated.**

### Identity — the privileged user is a domain account

**The privileged user a Vscan server uses to connect to the SVM is a domain user account**, and it has to be present in the scanner pool's privileged-user list.

So **a configuration that uses Vscan presumes Active Directory.** If the SVM runs in workgroup mode, that premise is not met.

**And the dependency on AD does not end at the join.** Credential expiry surfaces during maintenance. The detail is in [Depending on AD lasts the lifetime, not the join](../../multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md). **Adding antivirus is also adding one more point of dependency on AD.**

### Availability — scan-mandatory coupled to client access

**With `scan-mandatory` on, a client's access is refused when no Vscan server answers.**

| Setting | When no Vscan server answers |
|---|---|
| `scan-mandatory on` | Retries until the scanner pool's timeout, and **denies the client's access request** if the request is not accepted |
| `scan-mandatory off` | **Allows access** with no Vscan server available |

**This is not the general observation that tightening security costs availability; it is a specific coupling that one setting switches.** The same shape exists for auditing — read it beside [An exhausted audit destination stops client access](audit-log-space-and-client-access.md). **What they share is that there is a setting which chooses how it stops.**

**The timeouts have an order.** NetApp advises setting the antivirus software's own timeout **five seconds below the scanner pool's scan-request timeout**. Inverted, file access is delayed or denied outright.

**Redundancy is the scanner policy.** `Primary` is always active, `Secondary` is active only when no Vscan server in the primary pool is connected, `Idle` is always inactive. **Custom scanner policies cannot be created** — the three are system-defined.

### Exclusions — files that are not scanned even under mandatory

**Turning `scan-mandatory` on does not put an excluded file in scope.** NetApp's documentation states this explicitly.

There are three exclusion paths.

| Path | Detail |
|---|---|
| `max-file-size` | Files above the size given. **The default size for exclusion is 2 GB** |
| `paths-to-exclude` | The paths given |
| `file-ext-to-exclude` | The extensions given. **This overrides `file-ext-to-include`** |

**Three further things are out of scope by default.**

| Not scanned by default | How to include it |
|---|---|
| Read-only volumes (only read-write by default) | The `scan-ro-volume` filter |
| An SMB share with `continuously-available` set to `Yes` | **There is no way.** Virus scanning is not performed on that share |
| A share whose `vscan-fileop-profile` is `no-scan` | Set the profile to `standard` or higher |

**The `continuously-available` row bears on design.** If a workload requiring continuous availability (a database over SMB, for instance) uses that share setting, **the share is not in scope for scanning.** It must not be included when declaring what antivirus covers.

**And rename behaves differently per profile.**

| `vscan-fileop-profile` | Scan trigger | Note |
|---|---|---|
| `no-scan` | none | Nothing on this share is scanned |
| `standard` (default, NetApp best practice) | open / close / rename | |
| `strict` | open / read / close / rename | For several clients holding the same file open at once. **More scan requests, so performance can be affected** |
| `writes-only` | Only when a modified file is closed | Fewer requests and better performance, but **the scanner must be configured to delete or quarantine unrepairable files** |

**There is a cap on the number of policies.** Ten on-access policies per SVM, but **only one can be enabled at a time.** Up to 100 excluded paths and extensions in one policy. **Since only one can be enabled, every exclusion ends up in the same policy.**

**A default policy exists.** ONTAP creates an on-access policy named `default_CIFS` and enables it for every SVM in the cluster. **"Nothing configured yet" is not the same state as "no policy".**

---

## Whether a write can be refused inline, by where it lands

**The protocol constraint decides not only what is in scope but when it can be stopped.**

Applying the fact that on-access is against SMB to **a configuration where writes land through an S3 access point** gives the result that **there is no way to refuse on that path at the moment the write lands.** **Recording and detection still work, though.** Conflating the two yields the false conclusion that nothing protects the path.

| Mechanism | A write over NFS / SMB | A write through an S3 access point | Tier |
|---|---|---|---|
| **Vscan on-access** | In scope | **Cannot be configured.** The on-access policy's protocol is `CIFS` | `documented` |
| **Vscan on-demand** | In scope | **In scope.** Afterwards, not at the moment it lands | `documented` |
| **FPolicy (`mandatory`)** | Fires, and blocks | **No notification, and no block.** There is no `s3` event protocol; it is refused with HTTP 400 | `verified` (measured in another note) |
| **ONTAP auditing** | Recorded | **Recorded** | `verified` (measured in another note) |
| **Autonomous Ransomware Protection** | Detects | **Detects** | `verified` (measured in another note) |

**The result is one line. For a write arriving through an S3 access point there is no mechanism that refuses it as it lands.** A record remains and behavioural anomalies are still detected, but **the write itself succeeds.** Where stopping it in real time is a requirement, this path does not meet it.

> **On confidence**: **this section is a composition of two sources.** The Vscan rows come from the documented fact that the on-access policy's protocol is `CIFS`; the FPolicy, auditing and ARP rows come from the measurement in [FPolicy does not see this path at all](access-point-authorization-layers.md#fpolicy-does-not-see-this-path-at-all). **No measurement of Vscan against a write through an S3 access point was made in this repository.** That an on-access policy does not intervene some other way was not observed; it is derived from the protocol parameter.

**If FPolicy is considered as an alternative, whether it fits is decided by where writes land.** The detail is in [Whether FPolicy fits is decided by how data is written, not how it is read](../../../../ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md) (日本語). **The reading side does not enter the judgement.** Reading the same volume through an S3 access point changes nothing as long as writes land over SMB.

---

## Which constraints belong to ONTAP and which to FSx for ONTAP

**Every constraint above is a general ONTAP property.** Neither the FSx for ONTAP documentation nor NetApp's records **any FSx for ONTAP-specific Vscan constraint that we found.**

| Attribution | Content |
|---|---|
| **General ONTAP** | on-access being SMB only, the privileged user being a domain account, `scan-mandatory` behaviour, the exclusions, the policy caps, `continuously-available` shares not being scanned, the four profiles |
| **FSx for ONTAP-specific** | **Not found.** This is not a claim that none exists — it is the state of having looked and found nothing (searched 2026-09-15) |

**The unverified items are stated.** These are what a later measurement could promote to `verified`.

| # | Unverified item | Why it matters |
|---|---|---|
| 1 | How far `fsxadmin` can run the `vserver vscan` commands | **FSx for ONTAP's `fsxadmin` does not carry the same rights as an on-premises cluster administrator.** Anything that cannot be configured becomes the first constraint |
| 2 | The connectivity requirements from an EC2 instance hosting the ONTAP Antivirus Connector to the SVM | The Connector is a download from the NetApp Support Site (login required), and placement and reachability need confirming in your own environment |
| 3 | The actual symptom when a Vscan server is taken down with `scan-mandatory on` | The documentation says access is denied; **the shape of the error a client sees** was not confirmed |

**Item 1 has the same structure as other areas.** A setting exists on the ONTAP side that the AWS API does not reach, and `fsxadmin`'s permission boundary sits across it. The same judgement as [Where a setting is created](../../../../ja/reference/decision-trees/where-a-setting-is-created.md) (日本語).

---

## The options compared symmetrically

**Vscan is not the only mechanism.** And the constraints on choosing Vscan are stated with the same weight.

| Mechanism | Suits | What it commits you to |
|---|---|---|
| **ONTAP Vscan (any of the six)** | Completing scanning on the storage side. Not depending on client configuration | **AD is a premise.** Operating Vscan servers (Connector plus antivirus). on-access is SMB only. The `scan-mandatory` setting couples it to access |
| **Scanning on the client or EDR side** | EDR already deployed to endpoints and EC2. Not touching the storage side | **Whether a file is scanned depends on the endpoint's state.** A write from an unmanaged endpoint goes through |
| **[External control through FPolicy](../../../../ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md) (日本語)** | Refusing by extension or by operation. Controlling operations rather than detecting malware | **It is not antivirus.** A mechanism for a different purpose, requiring an external server. **Whether it fits is decided by where writes land, and it does not fire through an S3 access point** |
| **ONTAP Autonomous Ransomware Protection** | Behavioural anomaly detection rather than known-pattern detection | **Not a replacement for virus scanning.** It detects something else |

**How to choose is not "which is better" but what is already settled.**

| What you have | The straightforward choice |
|---|---|
| The SVM is not AD-joined and there is no plan to join it | Vscan is not available. Client or EDR side |
| Running NFS only | Vscan is on-demand only. **If real time is a requirement, consider another mechanism** |
| Using a continuously available share | **That share is out of scope for Vscan.** Do not include it in what you declare |
| Writes land through an S3 access point | **No mechanism refuses them as they land.** Either pick them up afterwards with on-demand, or change the write path. [Detail](#whether-a-write-can-be-refused-inline-by-where-it-lands) |
| No owner decided for operating the Vscan servers | **Do not configure until there is one.** With `scan-mandatory on`, a gap in operations becomes an access outage |
| Already under contract with one of the six | After confirming the version combination in the interoperability matrix |

**Combining works.** Vscan and client-side EDR are not exclusive. But it produces **a configuration that scans the same file twice**, so the exclusions have to match on both sides. NetApp also strongly recommends **configuring the same exclusion set in the antivirus engine.**

---

## Verify in your own environment

| # | Step | What it establishes |
|---|---|---|
| 1 | Check whether the SVM is AD-joined | **If it is not, Vscan is not available.** The first branch |
| 2 | Count the shares and exports you want scanned, by protocol | The NFS share of them is on-demand only |
| 3 | List the SMB shares with `continuously-available` set to `Yes` | **Those are not scanned.** Remove them from what you declare |
| 4 | Check the state of the existing `default_CIFS` policy | "Unconfigured" may in fact be "the default is enabled" |
| 5 | Measure the largest file in scope and compare it with the 2 GB default exclusion | **Anything above it is not scanned by default** |
| 5-1 | **Write down the protocol each write path lands on** | **What can be refused in real time.** Any path through an S3 access point is reachable only by on-demand |
| 6 | Try `vserver vscan on-access-policy show` as `fsxadmin` | **Unverified item 1.** Where the permission boundary sits |
| 7 | Decide who operates, patches and monitors the Vscan servers | **Do not set `scan-mandatory on` before this is decided** |
| 8 | Confirm the ONTAP version and antivirus product version combination in the interoperability matrix | The last input the vendor choice needs |

**Leaving step 7 until later means an access outage the first time a Vscan server stops while `scan-mandatory` is on.**

---

## Common misconceptions

| Misconception | Actually |
|---|---|
| Choosing among the six is the first decision | **Protocol, identity, availability and exclusions come first.** The vendor is last |
| The AWS user guide states the constraints | **It states none.** It is a set of links to the six. The constraints are in the ONTAP material |
| NFS can be scanned in real time too | **on-access is against SMB.** An NFS export is in scope for on-demand |
| NFS-only means no on-access policy is needed | **An on-access policy is required for an on-demand scan** |
| On-demand means no Vscan server is needed | **It uses the Vscan servers configured for on-access** |
| Vscan completes on the storage side, so AD is not needed | **The privileged user is a domain user account** |
| `scan-mandatory on` means every file is scanned | **A file matching an exclusion is out of scope.** The default size exclusion is 2 GB |
| Adding antivirus does not affect availability | **With `scan-mandatory on`, access is denied when no Vscan server answers** |
| Creating a share puts it in scope automatically | **A share with `continuously-available` set to `Yes` is not scanned.** Nor is one whose `vscan-fileop-profile` is `no-scan` |
| Exclusions can be managed across separate policies | **One on-access policy can be enabled per SVM.** Every exclusion goes in that one |
| Nothing is scanned because nothing is configured | ONTAP creates `default_CIFS` and enables it for every SVM. **Check the state** |
| Antivirus stops a write whatever path it arrives on | **It depends where the write lands.** A write through an S3 access point has no mechanism to refuse it as it lands |
| Nothing protects a write through an S3 access point | **Recording and detection work.** ONTAP auditing records it and ARP detects it. What is absent is inline refusal |
| FPolicy stops the path Vscan cannot reach | **It does not fire on that path either.** There is no `s3` event protocol, and `mandatory` does not block |
| These constraints are specific to FSx for ONTAP | **They are all general ONTAP properties.** No FSx for ONTAP-specific difference was found |

---

## Primary sources consulted

| Point | Source | Retrieved |
|---|---|---|
| That FSx for ONTAP can run third-party antivirus through Vscan, and the six supported (Deep Instinct / SentinelOne / Symantec / Trellix / Trend Micro / OPSWAT) | [AWS: Use NetApp ONTAP Vscan with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-vscan.html) | 2026-09-15 |
| The list of six partners, and that interoperability is confirmed in the NetApp Interoperability Matrix and on each vendor's site | [NetApp: ONTAP Vscan partner solutions](https://docs.netapp.com/us-en/ontap/antivirus/vscan-partner-solutions.html) | 2026-09-15 |
| That the ONTAP Antivirus Connector and the antivirus software go on the same Vscan server; that the privileged user is a domain user account; that the three scanner policies are system-defined and cannot be customized; that the antivirus timeout should sit five seconds below the scanner pool's; the behaviour of the four `vscan-fileop-profile` values | [NetApp: Antivirus architecture with ONTAP Vscan](https://docs.netapp.com/us-en/ontap/antivirus/architecture-concept.html) | 2026-09-15 |
| The on-access policy's `-protocol CIFS`; that a file matching an exclusion is out of scope even with `scan-mandatory on`; the 2 GB default size exclusion; read-write volumes only by default; that an SMB share with `continuously-available` set to `Yes` is not scanned; ten policies per SVM with one enabled; 100 exclusions; that `default_CIFS` is created and enabled by default; that an on-access policy is required for an on-demand scan | [NetApp: Create ONTAP Vscan on-access policies](https://docs.netapp.com/us-en/ontap/antivirus/create-on-access-policy-task.html) | 2026-09-15 |
| That on-access suspends the SMB file operation | [NetApp: Virus scanning with ONTAP Vscan](https://docs.netapp.com/us-en/ontap/concepts/virus-scanning-concept.html) | 2026-09-15 |
| That on-demand covers volumes that cannot be configured for on-access, such as NFS exports, and reuses the existing Vscan servers | [NetApp KB: How does vscan work](https://kb.netapp.com/on-prem/ontap/da/NAS/NAS-KBs/How_does_vscan_work) | 2026-09-15 |
| The overall shape of configuring antivirus for an SMB share | [AWS Storage Blog: Securing your Amazon FSx for ONTAP Windows Share (SMB) against viruses](https://aws.amazon.com/blogs/storage/securing-your-amazon-fsx-for-ontap-windows-share-smb-against-viruses/) | 2026-09-15 |

---

## Related documents

- [Domain — Security and governance](../README.md) — this module's hub
- [How far antivirus scanning applies](../../../reference/decision-trees/vscan-antivirus-scope.md) — the decision-tree form of this judgement
- [ISV and SaaS solution map by problem](../../../reference/isv-solution-map.md) — the index of options for other problem areas
- [Whether FPolicy fits is decided by how data is written](../../../../ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md) (日本語) — what to check if it is considered as an alternative
- [FPolicy does not see this path at all](access-point-authorization-layers.md#fpolicy-does-not-see-this-path-at-all) — where the write-path table's measurements come from
- [An exhausted audit destination stops client access](audit-log-space-and-client-access.md) — the same "a setting couples it to access" shape
- [Depending on AD lasts the lifetime, not the join](../../multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) — the dependency the privileged user brings
- [Where a setting is created](../../../../ja/reference/decision-trees/where-a-setting-is-created.md) (日本語) — `fsxadmin`'s permission boundary
- [Evidence Policy](../../../evidence-policy.md)

---

[🏠 Repository home](../../../README.md) | [Domain — Security and governance](../README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md) | [English](vscan-scope-is-bounded-before-the-vendor.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->
