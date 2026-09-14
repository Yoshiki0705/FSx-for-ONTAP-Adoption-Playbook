# Domain — Client Access

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/client-access/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

Reaching Amazon FSx for NetApp ONTAP data from an actual endpoint — a Windows machine, the Linux
inside WSL2, a Mac. **Access from an EC2 instance is out of scope here.** Other modules already
cover it, and it is not the same problem as access from an endpoint.

**The reason this module exists fits in one line.** FSx for ONTAP does not support access from the
public internet, and Amazon FSx detaches any Elastic IP address attached to a file system's elastic
network interface. **So endpoint access always carries a reachability design with it, and never
reduces to handing out a mount command.**

---

## Read first

**Turn what you already have in hand into the next single page to read.** The table of questions
below is a table of contents; this is the entry point.

| What you arrive with | Read first | What it resolves |
|---|---|---|
| **The endpoint is decided** (Windows, WSL2, or Mac) | [Endpoint capability comparison](../../../ja/reference/comparison/client-endpoint-capabilities.md) | **The storage forms available to you have already narrowed.** A Mac has no block option |
| **No reachability route yet** (no VPN, no Direct Connect) | [Endpoint reachability comparison](../../../ja/reference/comparison/endpoint-reachability-options.md) | The cost of each route, and what has to be installed on the endpoint |
| **A mount is failing** | [Client access route decision tree](../../../ja/reference/decision-trees/client-access-route.md) | Working back from the symptom to whether reachability, the protocol, or authentication refused |

---

## Questions this module answers

| # | Question | Note |
|---|---|---|
| 1 | Why an endpoint cannot be connected straight over the internet | [No route from the public internet (日本語)](../../../ja/domains/client-access/notes/no-route-from-the-public-internet.md) |
| 2 | How the endpoint changes which storage forms are available | [The endpoint narrows the protocol first (日本語)](../../../ja/domains/client-access/notes/the-endpoint-narrows-the-protocol.md) |
| 3 | Whether the Linux in WSL2 can use the same route as its Windows host | [The WSL2 network boundary (日本語)](../../../ja/domains/client-access/notes/wsl2-network-boundary.md) |
| 4 | What credentials end up stored on the endpoint | [Where endpoint credentials live (日本語)](../../../ja/domains/client-access/notes/where-endpoint-credentials-live.md) |
| 5 | Why an SMB mount failure looks different on each endpoint | [How SMB fails, per endpoint (日本語)](../../../ja/domains/client-access/notes/how-smb-fails-per-endpoint.md) |
| 6 | What an endpoint needs to reach S3 Access Points | [What an endpoint needs to reach S3 Access Points (日本語)](../../../ja/domains/client-access/notes/what-an-endpoint-needs-to-reach-s3-access-points.md) |
| 7 | Which routes exist for showing data in a browser | [Four routes reach end users (日本語)](../../../ja/playbooks/02-design/notes/how-end-users-reach-the-data.md) |

Notes are written in Japanese, marked (日本語) above. The English tree carries the module hubs.

---

## Endpoints under consideration

**This is the list of how far the module actually goes.** Nothing is hidden to make it look
complete, so **a row marked unverified or accepting requests is not yet decision material.**

Requests go to [Knowledge request](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/new?template=knowledge-request.yml)
with the `client-access` domain selected. **A row moves when a request arrives.**

| Endpoint | File (NFS / SMB) | Block (iSCSI) | Object (S3 Access Points) | How this module treats it |
|---|---|---|---|---|
| **Windows endpoint** | Built in | Built in (iSCSI initiator + MPIO) | AWS CLI / SDK | **Covered** |
| **Linux inside WSL2** | The distribution's client | **Depends on the kernel** | AWS CLI / SDK | **Covered** |
| **Mac endpoint** | Built in (Finder, `mount_smbfs`, `mount_nfs`) | **Not included** | AWS CLI / SDK | **Covered** |
| Native Linux endpoint | The distribution's client | `open-iscsi` + `multipath-tools` | AWS CLI / SDK | **Unverified.** Same route as WSL2, minus the boundary problem |
| Amazon WorkSpaces / AppStream 2.0 | From inside the desktop; nothing installed on the endpoint | Depends on the image | From inside the desktop | **Unverified.** AWS documents [using WorkSpaces with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-workspaces.html) |
| Chromebook / iPad / Android | **Not possible** (no mount mechanism) | **Not possible** | Browser only | **Covered as the browser route.** The implementation lives in a sibling repository |
| EC2 Mac instance | Built in | Not included | AWS CLI / SDK | **Out of scope.** AWS's macOS procedure assumes this ([source](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html)). The Dedicated Host cost does not pay for itself against a physical Mac |
| Thin client (VDI-only device) | From inside the desktop | From inside the desktop | From inside the desktop | **Accepting requests.** Expected to match the WorkSpaces row, unconfirmed |
| On-premises Windows Server | Built in | Built in | AWS CLI / SDK | **Accepting requests.** A server rather than an endpoint, so the route leans to Site-to-Site VPN or Direct Connect |
| Kubernetes node / CI runner | — | — | — | **Out of scope.** A workload, not an endpoint. See [Kubernetes block volumes and the volume limit (日本語)](../../../ja/domains/block-storage/notes/kubernetes-block-volumes-and-the-volume-limit.md) |

> **On the object column**: it means **FSx for ONTAP S3 Access Points**. Mount-style options
> (rclone, Mountpoint for Amazon S3) come up as endpoint choices, but **Mountpoint is Linux only and
> can neither update an existing file nor delete a directory.** Both are unverified here and
> accepting requests.

---

## Runnable implementations

| Where | What it does |
|---|---|
| [`examples/client-access/`](../../../../examples/client-access/) | The smallest environment reachable from an endpoint: a CloudFormation template serving workgroup-mode SMB and iSCSI, a separate template adding AWS Client VPN, and probe scripts emitting the same JSON shape on all three endpoints |
| [File portal UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | **The one route that installs nothing on the endpoint.** Browser-only reach brings Chromebooks and iPads into scope; in exchange, block and file mounts leave the list of options |

**The portal is not reimplemented here.** The division of labour is recorded in the
[cross-repository citation index](../../../ja/reference/cross-repo-index.md). What this module adds
is the endpoint's point of view.

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/client-access/notes/) | Smallest unit of knowledge, one concern per file, with an `evidence` tier in the frontmatter |

---

## How to read this

Always check the `evidence` value in a note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment; `verified_on` carries the date |
| `documented` | Stated in vendor or AWS documentation; `source` carries the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

**This module mixes items measured on a physical endpoint with items resting only on
documentation.** Which endpoint produced a measurement is recorded in each note's conditions table.
See the [evidence policy](../../evidence-policy.md).

---

## Related

- [Navigate by lifecycle](../../navigation.md)
- [Domain — Block storage](../block-storage/README.md) — LUN-side design and the iSCSI procedure from EC2
- [Domain — Multiprotocol and identity](../multiprotocol-identity/README.md) — permission evaluation when Active Directory is involved
- [Domain — Data utilization](../data-utilization/README.md) — what S3 Access Points can do
- [Comparison matrices](../../../ja/reference/comparison/)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/client-access/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
