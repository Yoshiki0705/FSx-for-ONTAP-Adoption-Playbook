# Domain — Data Utilization

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/data-utilization/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->

---

How to use NAS-resident data from analytics, AI, and applications without multiplying copies of it.

---

## Questions this module answers

| # | Question | Notes |
|---|---|---|
| 1 | What is and is not possible over the S3 API | [FSx for ONTAP S3 AP is not "S3 you can use as S3"](../../../ja/domains/data-utilization/notes/s3-access-point-constraints.md) (日本語) |
| 2 | How to connect an analytics platform | [Connecting an analytics platform](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#分析基盤への接続) (日本語) |
| 3 | How to handle permissions in AI / RAG | [What flattened permissions mean](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#権限が平坦化されることの意味) (日本語) |
| 4 | What a copy-minimizing design looks like | [Three ways to reach data without copying](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#コピーを増やさない-3-つの手段) (日本語) |
| 5 | Where read acceleration is worth applying | [When FlexCache helps](../../../ja/domains/data-utilization/notes/reaching-data-without-copies.md#flexcache-が効く条件) (日本語) |
| 6 | Which path exposes data to end users over a browser or SFTP | [Four paths end users take to the data](../../../ja/playbooks/02-design/notes/how-end-users-reach-the-data.md) (日本語) |

---

## Working implementations — sibling repositories

Reference architectures that implement the concepts in this module. When you need concrete code beyond the knowledge notes, start here.

| Project | What it does | Stack |
|---|---|---|
| [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | Collect via S3 API, consume via FlexCache NFS/SMB. No copy job, p50 8 ms propagation. Suited for HiL test benches, EDA, rendering, IoT | CFn + SAM. [Blog post](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| [File Portal UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | Browser access to NAS files without VPN + AI processing (classification, anomaly detection, semantic search). Works alongside Nextcloud | Amplify Gen2 + Bedrock. [Blog post](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| [Lakehouse integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Query files via Athena / Glue / Spark through S3 AP. Data stays on NAS | S3 AP + Glue / Athena |
| [Agentic RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | RAG that respects NAS permissions. Propagates original ACLs to the AI pipeline | CDK + Bedrock |

---

## Structure

| Directory | Contents |
|---|---|
| [`notes/`](../../../ja/domains/data-utilization/notes/) | Smallest unit of knowledge. One file = one concern. Frontmatter carries the `evidence` tier |

---

## How to read this

Always check the `evidence` field in each note's frontmatter.

| Tier | Meaning |
|---|---|
| `verified` | Reproduced by the author in the stated environment. `verified_on` gives the date |
| `documented` | Stated in vendor / AWS documentation. `source` gives the reference |
| `field-observation` | Observed once in the field, not reproduced. Do not generalize |
| `hypothesis` | Reasoned expectation, untested |

See the [Evidence Policy](../../evidence-policy.md) for the full criteria.

---

## Related

- [Browse by lifecycle](../../navigation.md#lifecycle-axis--playbooks)
- [Comparison Matrices](../../../ja/reference/comparison/)
- [Navigation Guide](../../navigation.md)
- [Glossary](../../../ja/reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](../../../ja/domains/data-utilization/README.md) | [English](README.md) | [🏠 Repository home](../../README.md)
<!-- lang-switcher:end -->
