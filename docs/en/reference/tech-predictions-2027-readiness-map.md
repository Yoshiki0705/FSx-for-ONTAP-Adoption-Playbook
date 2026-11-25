---
title: "Readiness map for the 2027 tech predictions: what to prepare on the data side for each of the five predictions, and where the detail lives"
lifecycle: [assess, design]
domains: [security-governance, data-protection, data-utilization]
evidence: documented
source: https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html
lang: en
---
# Readiness map for the 2027 tech predictions

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

---

## Conclusion

The five predictions in the AWS CTO's blog post [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html) each concern data that Amazon FSx for NetApp ONTAP (FSx for ONTAP below) holds, both structured and unstructured.

For each prediction, this page maps what to prepare on the data side to where the detail lives. This page carries no findings of its own. Each cell links to the document that holds them.

> **Tier**: `documented`. The predictions are the view of the AWS CTO's blog post, and this page does not judge whether they will hold. A row in the table does not mean the preparation has been confirmed on FSx for ONTAP. Read each linked document's tier for its state of confirmation.

---

## Preparation per prediction

| Prediction | What to prepare on the data side | Where the detail lives | Tracking issue |
|---|---|---|---|
| Computing returns to biology | Map the agent's memory tiers to tiering policies. Extend the "forgetting" process to Snapshots and backups. Reduce the bytes stored with deduplication, compression, and tiering. | [Agent memory tiers and forgetting](../domains/data-utilization/notes/agent-memory-tiers-and-forgetting.md), the Cyber Resilience Patterns document [Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md), and section 7 of the ONTAP Edge to Cloud AI document [Agentic AI on AWS](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/en/agentic-ai-on-aws.md) | [#438](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/438) |
| Every system defends itself | Place adversarial-perspective checks before design, before release, and in operation. The AWS documents read for this page do not list storage configuration as an input to AWS Security Agent or AWS Continuum (an inference, entry E-026 in the Cyber Resilience Patterns evidence registry, `hypothesis`), so read the storage configuration separately. The only trend assumed here is that the time and cost from finding a vulnerability to exploiting it are falling. | From Cyber Resilience Patterns: [Read-only configuration probe](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md), [Prompt for an adversarial review before implementation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent-prompts/adversarial-review.md), [Adversarial checks through every phase](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/architecture/continuum-security-agent-and-storage.md#全工程で続ける攻撃側の検査--adversarial-checks-through-every-phase), and [Clone isolation runbook around a penetration test](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/runbooks/pentest-clone-isolation.md) | [#439](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/439) |
| Sovereignty becomes a non-functional requirement | For each workload, decide the location, the keys, the destination of copies, the management plane, and the location of inference, and keep evidence for each deployment. | [Sovereignty as a non-functional requirement](../domains/security-governance/notes/sovereignty-as-a-non-functional-requirement.md) | [#440](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/440) |
| Collaboration between scientists and agents leads to new cures | Take a Snapshot for each dataset version and a FlexClone for each experiment. Attach S3 Access Points to the clone and record the Snapshot UUID. | [Reproducible research datasets for agents](../domains/data-utilization/notes/reproducible-research-datasets-for-agents.md), the S3 Access Points Serverless Patterns document [FlexClone serverless patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/guides/flexclone-serverless-patterns-en.md), and the S3-Burst on ONTAP Files record [S3 Access Points interoperability](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/en/reference/limits/s3ap-interoperability.md) | [#441](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/441) |
| The mind becomes readable | Treat neural and biometric recordings as a data class. Decide the location and permissions for each subject, and the range of copies that can honor a withdrawal of consent. | [Handling neural and biometric recordings](../domains/security-governance/notes/neural-and-biometric-recordings.md), and the Cyber Resilience Patterns document [Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) | [#442](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/442) |

---

## Reading order

1. **Sovereignty becomes a non-functional requirement**: the sovereignty decision fixes the location, the keys, and the destination of copies first. The other four sit on top of that decision.
2. **Every system defends itself**: adversarial-perspective checks target the configuration once location and keys are decided, so this comes second.
3. **Computing returns to biology**: memory tiers and "forgetting" can decide how far to reach into Snapshots and backups only after the destination of copies is decided.
4. **Collaboration between scientists and agents leads to new cures**: versioning research data relies on the same Snapshot and tiering decisions as the previous prediction.
5. **The mind becomes readable**: the range of copies that can honor a withdrawal of consent adds per-subject permissions on top of the memory and forgetting decisions.

---

## Related documents

- [Cyber resilience capability map](cyber-resilience-capability-map.md) (which Spoke covers which NIST CSF 2.0 function)
- [業種別リソースマップ](../../ja/reference/industry-resource-map.md) (日本語) (the reading order when entering from an industry, and a cross-index)

---

[🏠 Repository home](../README.md) | [Reference](../../ja/reference/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](../../ja/reference/tech-predictions-2027-readiness-map.md) | [English](tech-predictions-2027-readiness-map.md) | [🏠 Repository home](../README.md)
<!-- lang-switcher:end -->
