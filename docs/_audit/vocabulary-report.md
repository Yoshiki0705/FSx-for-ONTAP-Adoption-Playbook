# Current vocabulary findings

This is an English, nonlocalized current-state report. It records open source locations without reproducing the detected wording.

## Reproduction

Run from the repository root:

```bash
make vocabulary-report
```

The current command reports 99 findings across 51 files and 98 distinct file-and-line locations. One source line produces two findings and is marked below. The report target is an inventory command, not a release gate.

## Remediation categories

Apply the category that fits the surrounding sentence:

- Replace positioning language with the reader role, applicable condition, and concrete behavior.
- Replace unmeasured emphasis with a sourced fact or a measurement that names its environment; otherwise remove the emphasis.
- Replace claims about ease or continuity with the manual steps, interruption boundary, or prerequisite that the reader must account for.
- Rewrite option comparisons as symmetric trade-offs and include how to choose for the stated context.
- Remove duplicated emphasis when the surrounding evidence already carries the meaning.

Each source claim requires contextual review before editing. A line number identifies a remediation target; it does not determine which rewrite category applies.

## Current findings by file

- `CHANGELOG.md`: lines 237, 792, 1299, 1750, 1760, 2006, 2487, 2740, 2776, 3414
- `README.md`: lines 108, 114
- `docs/agent/domain-knowledge.md`: line 19
- `docs/agent/support-reply-handling.md`: lines 19, 82
- `docs/en/README.md`: line 106
- `docs/en/case-studies/README.md`: line 69
- `docs/en/domains/block-storage/README.md`: line 19
- `docs/en/domains/cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md`: lines 22, 146
- `docs/en/domains/multiprotocol-identity/README.md`: line 31
- `docs/en/domains/multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md`: line 52
- `docs/en/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md`: lines 22, 24, 37
- `docs/en/domains/security-governance/notes/audit-log-space-and-client-access.md`: lines 196, 210, 212, 227, 231
- `docs/en/domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md`: line 120
- `docs/en/playbooks/02-design/notes/deployment-type-is-decided-once.md`: lines 181, 194
- `docs/en/playbooks/05-operate/notes/monitoring-fails-on-averages.md`: line 165
- `docs/en/reference/decision-trees/smb-identity-and-audit.md`: lines 86, 108, 137
- `docs/en/reference/isv-solution-map.md`: line 101
- `docs/ja/case-studies/_template/case-study.md`: line 60
- `docs/ja/case-studies/public-references.md`: line 71
- `docs/ja/domains/block-storage/README.md`: line 18
- `docs/ja/domains/block-storage/notes/a-snapshot-of-a-lun-is-crash-consistent.md`: line 210
- `docs/ja/domains/block-storage/notes/capacity-is-counted-in-three-places.md`: line 73 (two findings); lines 177, 191, 227, 228
- `docs/ja/domains/block-storage/notes/lun-layout-decides-recovery-granularity.md`: lines 33, 56, 263, 298, 299
- `docs/ja/domains/block-storage/notes/when-shared-block-changes-the-design.md`: lines 115, 215
- `docs/ja/domains/client-access/notes/the-endpoint-narrows-the-protocol.md`: line 94
- `docs/ja/domains/cost/notes/archiving-and-tiering-are-ordered-not-alternatives.md`: line 167
- `docs/ja/domains/data-protection/notes/backup-copies-across-regions-and-accounts.md`: line 476
- `docs/ja/domains/data-protection/notes/third-party-backup-reaches-it-by-another-route.md`: line 132
- `docs/ja/domains/data-utilization/notes/dataset-versions-and-experiment-branches.md`: line 256
- `docs/ja/domains/multiprotocol-identity/README.md`: line 32
- `docs/ja/domains/multiprotocol-identity/notes/adding-a-protocol-does-not-need-a-clone.md`: line 52
- `docs/ja/domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md`: lines 20, 22, 34
- `docs/ja/domains/security-governance/notes/audit-log-space-and-client-access.md`: lines 59, 69
- `docs/ja/domains/security-governance/notes/self-service-without-storage-admin.md`: lines 35, 68, 250
- `docs/ja/domains/security-governance/notes/vscan-scope-is-bounded-before-the-vendor.md`: line 257
- `docs/ja/navigation.md`: lines 62, 111
- `docs/ja/playbooks/02-design/notes/deployment-type-is-decided-once.md`: line 191
- `docs/ja/reference/block-storage-resource-map.md`: lines 85, 98, 154, 205
- `docs/ja/reference/comparison/client-endpoint-capabilities.md`: line 115
- `docs/ja/reference/cross-repo-index.md`: lines 42, 365, 499
- `docs/ja/reference/decision-trees/block-protocol-and-layout.md`: line 150
- `docs/ja/reference/decision-trees/vscan-antivirus-scope.md`: line 158
- `docs/ja/reference/file-protocol-resource-map.md`: lines 91, 174
- `docs/ja/reference/fsx-ontap-fit-conditions.md`: lines 59, 61, 98, 169, 172
- `docs/ja/reference/isv-solution-map.md`: line 10
- `docs/ja/reference/limits/README.md`: line 558
- `docs/ja/reference/recent-updates.md`: line 230
- `docs/ja/workshop-studio/eda-s3-access-points-90min/facilitation-risks.md`: line 70
- `docs/ja/workshop-studio/eda-s3-access-points-90min/measured-timings.md`: line 164
- `examples/multiprotocol-ad/README.md`: line 53
- `llms.txt`: lines 104, 108

The inventory remains open until each listed occurrence has been reviewed and the report command returns no findings.
