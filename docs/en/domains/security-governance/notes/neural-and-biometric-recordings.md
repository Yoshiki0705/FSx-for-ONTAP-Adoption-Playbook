---
title: "Before storing neural and biometric recordings: how to split volumes, the unit of the key, and the deadline for honoring a withdrawal"
lifecycle: [design, operate]
domains: [security-governance, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html
lang: en
---

# What does the data side have to decide when neural and biometric recordings go on Amazon FSx for NetApp ONTAP?

Split raw recordings from derived data into separate volumes, then choose the placement after counting two things: the key is per file system, and each copy has its own deadline for honoring a withdrawal of consent.

<!-- lang-switcher:start -->
🌐 [日本語](../../../../ja/domains/security-governance/notes/neural-and-biometric-recordings.md) | [English](neural-and-biometric-recordings.md) | [🏠 Repository home](../../../README.md)
<!-- lang-switcher:end -->

## What you will learn

- Why raw electroencephalography (EEG) and magnetoencephalography (MEG) recordings and the data derived from them belong on separate volumes
- That encryption at rest in FSx for ONTAP uses a key per file system, so a key per subject needs another mechanism
- That after you delete a file, snapshots, backups, SnapMirror destinations and clones each keep the data until their own expiry
- What you give up for each of four kinds of data (raw recordings, anonymized data, training data, audit and consent records) when you put it on WORM storage and when you do not

## What this note does not answer

- Whether an organization may handle neural data, and how to word consent (legal counsel and an ethics review decide)
- The laws of other jurisdictions
- Whether NetApp Volume Encryption can be enabled on FSx for ONTAP (not tried)
- A live reproduction of a configuration that combines one qtree and quota per subject

## Prerequisite level

intermediate

## Body

<a id="before-storing-neural-and-biometric-recordings-how-to-split-volumes-the-unit-of-the-key-and-the-deadline-for-honoring-a-withdrawal"></a>

[🏠 Repository Top](../../../README.md) | [Domain — Security & Governance](../README.md)

> This is the English translation. Japanese is authoritative for technical accuracy. Please report any discrepancy.

---

### Conclusion

**This note covers the technical design of storage and permissions. It is neither a legal determination nor legal advice.** Whether an organization may handle neural data, and how consent is worded, is decided by that organization's legal counsel and ethics review.

Four things need to be decided before choosing where the data goes.

| Decision | Answer in this note |
|---|---|
| Whether to separate raw recordings from derived data | Separate them. Protection, retention period and access scope differ for each |
| The unit of the key | Encryption at rest in FSx for ONTAP uses an AWS KMS key that you choose per file system. A key per subject needs application-side encryption or a split into several file systems |
| The deadline for honoring a withdrawal of consent | Deleting a file leaves copies that live until their own expiry. Count the deadline per copy |
| Whether to put data on WORM storage | If you do, nobody can delete it until the retention ends. If you do not, you must cover ransomware readiness by other means |

> **Evidence**: The opening claims are `documented` from AWS documentation (see `source` in the frontmatter). The legal developments cite only the public pages of the bills that were read, and are `documented`.
> Observations taken from the Cyber Resilience Patterns records carry that project's environment and date and were not re-measured in this repository.
> The combinations in the "Placement" and "Key" columns of the table are design judgments and are `hypothesis`.

---

### Nature of the data

Raw EEG and MEG recordings are kept as files in formats such as EDF or FIF, or as datasets laid out in the BIDS format. The data grows in proportion to recording time.

For placement, treat these two kinds separately.

| Kind | Examples | Nature |
|---|---|---|
| Raw recordings | Files written out by the recording equipment | Tied to a subject. May be subject to a withdrawal of consent |
| Derived data | Preprocessed data, features, training data | Built from raw recordings. How far a withdrawal reaches is decided by the organization's legal counsel and ethics review |

---

### Legal developments

Only two primary sources that were actually read are covered. No other jurisdiction is mentioned. Both are `documented`.

| Jurisdiction and document | Content |
|---|---|
| Colorado, US, [HB24-1058](https://leg.colorado.gov/bills/hb24-1058) | Added biological data, including neural data, to "sensitive data" in the Colorado Privacy Act. It applies to data used, or intended to be used, for identification. The governor signed it on 2024-04-17 and it took effect on 2024-08-07 |
| California, US, [SB 1223](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223) | The text of the bill adds "neural data" to sensitive personal information in Civil Code 1798.140. This note read only the bill text and did not check the bill's later status |

Both move neural and biological data into a category treated more strictly than ordinary personal data. Whether these laws apply to your data is for your legal counsel to decide.

---

### Volume split and two layers of access

Put raw recordings, anonymized data and training data on separate volumes, because protection, retention period and access scope differ for each.

For the raw-recording volume, one qtree per subject with a quota is one possible layout. That combination is a design judgment (`hypothesis`) and was not tried on a live system for this note.

Per-subject access is narrowed in two layers.

| Layer | How it narrows |
|---|---|
| S3 Access Points authorization | An explicit deny in the access point policy |
| File system | Mode bits and ACLs of the identity bound to the access point |

Writing a narrower `Allow` in an access point policy does not narrow access within the same account. How to write the explicit deny, and why the file-system permission is independent, are in
[Which of the two layers narrows an S3 Access Point?](access-point-authorization-layers.md).

---

### Unit of the key for encryption at rest

FSx for ONTAP encrypts data at rest with an AWS KMS key that you choose per file system ([AWS: Encryption at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html), `documented`).

Because the key belongs to the file system, a key per subject needs envelope encryption in the application or a split into several file systems.

For ONTAP volume encryption, the Cyber Resilience Patterns [read-only configuration probe](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md) recorded the following (`verified`; these are that project's values and were not re-measured in this repository).

| Item | Value |
|---|---|
| Target | A verification file system |
| ONTAP version | 9.19.1P4 |
| Date measured | 2026-11-24 |
| What was read | `encryption.enabled=false` on all 26 read-write volumes. There is no ONTAP key manager |

`encryption.enabled=false` shows that ONTAP volume encryption is not in use. It does not show that the file-system-level KMS encryption at rest is off.

Whether NetApp Volume Encryption can be enabled on FSx for ONTAP was not tried (`open`).

---

### Withdrawal of consent and the copies that remain

Honoring a withdrawal of consent takes more than deleting the file. The Cyber Resilience Patterns page [deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) records the following.

- After you delete a file, snapshots, backups, SnapMirror destinations and clones each keep the data until their own expiry
- A deleted file stayed readable through S3 Access Points at `.snapshot/<snapshot-name>/<path>` while the snapshot existed (2026-11-24, ap-northeast-1, ONTAP 9.19.1P4, UNIX-style volume, `verified`; that project's value, not re-measured in this repository)

On a SnapLock Compliance volume, and on a copy in a logically air-gapped vault, nobody can delete the data until the retention ends. Do not place raw recordings that may be subject to withdrawal there. If you do, write that retention period into the consent form. Enabling WORM cannot be undone, so a person must name the retention value ([Irreversible operations need separate approval](../../../../ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md) (日本語)).

---

### Edge capture and write-back

When recordings are captured at the edge, near the recording equipment, the ONTAP Edge to Cloud AI [AWS IoT and FlexCache integration scenario](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/en/iot-greengrass-flexcache-integration.md) is a starting point.

As recorded there, with FlexCache write-back the data is written to the edge cache first. You therefore have to decide in the design how long a recording stays at the edge. That a withdrawal request may leave data at the edge even after the origin copy is deleted is a design judgment (`hypothesis`) and was not tried for this note.

---

### How to choose

Each row is a kind of data. The "On WORM storage" column states what you give up both when you do and when you do not.

| Data | Placement | Key | On WORM storage (SnapLock, logically air-gapped vault) | What you give up instead |
|---|---|---|---|---|
| Raw recordings (subject to withdrawal) | A dedicated volume. One qtree and quota per subject | The file system's KMS key. For a key per subject, application-side envelope encryption or a split into file systems | Keep off WORM by default | If off WORM, cover ransomware readiness with another volume or another protection; those copies also count toward the withdrawal deadline. If on WORM, you cannot honor a deletion request until the retention ends |
| Anonymized data | A volume separate from the raw recordings | Same as above | An option only when the organization has decided it falls outside withdrawal | If off WORM, cover tampering and ransomware with another protection. If on WORM, you cannot delete it until the retention ends even if the anonymization judgment is later overturned |
| Training data | A separate volume | Same as above | Keep off WORM by default | If off WORM, arrange another way to pin the data for reproducing a training run. If on WORM, you cannot honor a withdrawal by the original subject until the retention ends |
| Audit and consent records | A separate volume, designed to hold no content that identifies a subject directly | Same as above | An option | If on WORM, you cannot correct or delete a record until the retention ends. If off WORM, you need another way to prevent tampering with the records |

Whether anonymized data falls outside a withdrawal, and whether training data follows a withdrawal of the raw recordings, are not decided here. Your legal counsel and ethics review decide.

---

### Common misconceptions

| Misconception | Reality |
|---|---|
| Deleting the file honors the withdrawal | Snapshots, backups, SnapMirror destinations and clones each keep the data until their own expiry. A record shows a deleted file stayed readable through S3 Access Points while a snapshot existed |
| Encryption at rest gives each subject a separate key | The key is per file system. A key per subject needs application-side envelope encryption or a split into file systems |
| Writing an `Allow` in the access point policy restricts access to the subjects it names | Within one account a narrower `Allow` does not narrow access. Narrow it with two layers: an explicit deny and file-system permissions |
| Putting data on WORM storage makes it safe to honor a withdrawal | Nobody can delete it until the retention ends, so there is a period in which a withdrawal cannot be honored |

---

### Limits of this note

- Only two legal developments are covered. What was read is the public page of the Colorado bill and the text of the California bill. The full status of enactment and effect was not followed.
- The layout of one qtree and quota per subject is a design judgment and was not tried on a live system.
- The Cyber Resilience Patterns observations come from that project's environment (ONTAP 9.19.1P4, 2026-11-24). They were not re-measured in this repository.
- Whether NetApp Volume Encryption can be enabled on FSx for ONTAP was not tried.
- The behavior of how long data stays in the edge cache was not tried.

---

### Primary sources

| Topic | Source |
|---|---|
| Encryption at rest uses an AWS KMS key chosen per file system | [AWS: Encryption at rest](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/encryption-at-rest.html) |
| Biological data including neural data added to sensitive data (signed 2024-04-17, effective 2024-08-07) | [Colorado HB24-1058](https://leg.colorado.gov/bills/hb24-1058) |
| Bill text adding "neural data" to sensitive personal information | [California SB 1223](https://leginfo.legislature.ca.gov/faces/billTextClient.xhtml?bill_id=202320240SB1223) |
| The read in which ONTAP volume encryption was not in use | [Read-only configuration probe](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/adversarial-configuration-probe.md) |
| Copies that remain after deletion, and the measurement of reading a deleted file from a snapshot | [Deletion requests and retained copies](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/data-protection/deletion-requests-and-retained-copies.md) |
| With FlexCache write-back, data is written to the edge first | [AWS IoT and FlexCache integration scenario](https://github.com/Yoshiki0705/ONTAP-Edge-to-Cloud-AI/blob/main/docs/en/iot-greengrass-flexcache-integration.md) |

The AWS CTO blog post [Tech predictions for 2027 and beyond](https://www.allthingsdistributed.com/2026/11/tech-predictions-for-2027-and-beyond.html) (2026-11-24) sets out the prediction "The mind becomes readable", which prompted this note. Its content is not reproduced here.

---

### Related documents

- [Which of the two layers narrows an S3 Access Point?](access-point-authorization-layers.md) — the access point policy and file-system permissions
- [Irreversible operations need separate approval](../../../../ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md) (日本語) — enabling WORM and the retention period
- [Domain — Security & Governance](../README.md) — the hub for this module
- [Evidence policy](../../../evidence-policy.md)

---

## Verify it in your environment

These steps are read-only. They change nothing.

| # | Step | What it establishes |
|---|---|---|
| 1 | ONTAP REST `GET /api/storage/qtrees?fields=name,volume.name` | Which volume holds each per-subject qtree |
| 2 | ONTAP REST `GET /api/storage/quota/rules` | Whether the qtrees carry quotas |
| 3 | ONTAP REST `GET /api/storage/volumes?fields=encryption.enabled` | Whether ONTAP volume encryption is in use |
| 4 | `KmsKeyId` from `aws fsx describe-file-systems` | The KMS key used for the file system's encryption at rest |
| 5 | ONTAP REST `GET /api/storage/volumes/<volume-uuid>/snapshots?fields=name,create_time,expiry_time` | The snapshots that keep data after a deletion, and their expiry |

```bash
aws fsx describe-file-systems --file-system-ids <file-system-id> --query "FileSystems[0].KmsKeyId"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/qtrees?fields=name,volume.name"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/quota/rules"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/volumes?fields=encryption.enabled"
curl -sk -u <admin-user> "https://<management-ip>/api/storage/volumes/<volume-uuid>/snapshots?fields=name,create_time,expiry_time"
```

### Expected output

```text
<kms-key-arn>
{"records":[{"name":"<qtree-name>","volume":{"name":"<volume-name>"}}],"num_records":<n>}
{"records":[{"qtree":{"name":"<qtree-name>"},"volume":{"name":"<volume-name>"},"space":{"hard_limit":<bytes>}}],"num_records":<n>}
{"records":[{"name":"<volume-name>","encryption":{"enabled":<true-or-false>}}],"num_records":<n>}
{"records":[{"name":"<snapshot-name>","create_time":"<timestamp>","expiry_time":"<timestamp-or-absent>"}],"num_records":<n>}
```

What you learn:

- Whether per-subject qtrees and quotas exist, and which volume each is on
- The single KMS key used for the file system's encryption at rest
- Whether ONTAP volume encryption is in use. An `enabled` value of `false` does not mean the file-system-level KMS encryption is off
- That while a snapshot exists, a copy of a deleted file remains

What you do not learn:

- Whether copies remain in backups, SnapMirror destinations and clones, and their expiry (check with other APIs)
- Whether a deleted file can be read through S3 Access Points (it depends on the access point configuration and permissions)
- Whether your legal counsel and ethics review allow this configuration

## Read next

[Which of the two layers narrows an S3 Access Point?](access-point-authorization-layers.md)
