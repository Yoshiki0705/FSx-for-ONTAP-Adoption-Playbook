# ONTAP-ops deletion Lambda — design (confirmed)

Reusable, pattern-split automation that deletes ONTAP objects which the AWS FSx for ONTAP
control plane cannot delete (FlexCache, FlexClone, object-store buckets, vserver
audit destination, FPolicy, SnapMirror relationships), then the volumes and SVMs
that depended on them. Runs as a Python AWS Lambda inside the file system's VPC.

This is operational tooling, not part of any App-Modernization verified slice. It
lives in the Hub so every Spoke can reuse it.

## Location

`automation/ontap-ops/` in the Hub (FSx-for-ONTAP-Adoption-Playbook). New tree.

```text
automation/ontap-ops/
  shared/
    __init__.py
    ontap_client.py        # ported from fsxn-s3ap-serverless-patterns/shared/ontap_client.py
    fsx_helpers.py         # describe FS, discover Management endpoint IP, resolve+verify secret by FileSystemId tag
    safety.py              # allowlist gate, dry-run default, keep-list guard
  patterns/
    __init__.py
    base.py                # DeletePattern ABC: resolve_dependencies() -> delete() -> confirm_gone()
    flexcache_delete.py
    flexclone_split_delete.py
    s3bucket_delete.py
    audit_redirect.py
    fpolicy_teardown.py
    snapmirror_release.py
    volume_delete.py
    svm_delete.py
  orchestrator.py          # dependency-ordered run over one file system
  handler.py               # Lambda entry; event in, dry-run default, confirm=true to act
  cfn/ontap-ops-stack.yaml # VPC Lambda, interface endpoints, least-priv IAM
  requirements.txt         # boto3, urllib3 (runtime-provided); no test-only deps (stdlib unittest)
  tests/
  README.md                # JA primary + EN mirror pointer
```

## Base client (reuse)

Port `fsxn-s3ap-serverless-patterns/shared/ontap_client.py` verbatim as the base. It
already provides: generic get/post/patch/delete, Secrets Manager auth, production TLS
default (CERT_REQUIRED unless explicitly disabled), path-traversal rejection
(`is_unsafe_path`), `delete_flexcache`, `delete_snapmirror`, SnapMirror state control,
and `wait_ontap_job` (HTTP 202 async job polling). Add only the delete shortcuts it lacks.

## Patterns (each: resolve dependency -> delete -> read-back confirm)

| Pattern | ONTAP REST | Dependency to resolve first |
|---|---|---|
| flexcache_delete | DELETE /storage/flexcache/flexcaches/{uuid} | none (origin stays) |
| flexclone_split_delete | split or delete clone volume | clones of a parent |
| s3bucket_delete | DELETE /protocols/s3/buckets/{svm.uuid}/{uuid} | object-store buckets on the volume |
| audit_redirect | PATCH /protocols/audit/{svm.uuid} to move/disable destination | audit destination volume |
| fpolicy_teardown | disable policy -> delete policy -> delete event -> delete engine | FPolicy on the SVM (order from lakehouse configure_fpolicy.py) |
| snapmirror_release | DELETE /snapmirror/relationships/{uuid} | relationship on DP/origin volume |
| volume_delete | DELETE /storage/volumes/{uuid} | all of the above cleared |
| svm_delete | DELETE /svm/svms/{uuid} | all non-root volumes gone |

Orchestrator order per file system: snapmirror_release, flexclone_split_delete,
s3bucket_delete, audit_redirect, fpolicy_teardown, flexcache_delete -> volume_delete
(non-root) -> svm_delete. Every ONTAP delete that returns 202 is polled with
`wait_ontap_job`. After each delete, confirm by GET returning 404/empty before moving on.

## Safety (hard requirements)

- Input requires `file_system_id`. Env `ONTAP_OPS_ALLOWLIST` lists permitted FS ids.
  A file_system_id not in the allowlist is refused before any call.
- Env `ONTAP_OPS_KEEP_LIST` (e.g. fsxmaru) is refused even if passed — defense in depth.
- `dry_run` defaults true. Nothing is deleted unless the event sets `confirm: true`.
  Dry run returns the ordered plan of what WOULD be deleted (from read-only GETs).
- Secret id is supplied explicitly (env `ONTAP_SECRET_ID` or event). Never name-guessed.
  Before use, verify the secret's `FileSystemId` tag (or description) equals the target
  file_system_id; mismatch aborts. On auth failure, abort immediately — never retry
  (fsxadmin lock hazard).
- Must NOT call any retention / SnapLock / Object-Lock / Vault-Lock operation. The
  family guard (scripts/guard_irreversible_ops.py) stays authoritative; this code must
  pass it and must never implement anything that removes the ability to delete.
- Management endpoint discovered via describe-file-systems
  OntapConfiguration.Endpoints.Management.IpAddresses[0]; reachable only in-VPC.

## Lambda packaging (reuse RAG fsxn-ops-stack.yaml pattern)

- python3.12, VpcConfig (SubnetIds + SecurityGroupIds) to reach the private endpoint.
- Interface VPC endpoints (secretsmanager, fsx) + behavior for no-NAT subnets.
- Least-privilege IAM: secretsmanager:GetSecretValue scoped to the one secret;
  fsx Describe*; ec2 ENI perms via AWSLambdaVPCAccessExecutionRole; logs.
- Runtime deps are boto3 + urllib3 only (runtime-provided), so no vendoring.

## Tests (Q7)

- Standard library only (`unittest` + `unittest.mock`), matching the Hub's stdlib-only
  test convention; no pytest, moto, or hypothesis. Registered in the Makefile
  `TEST_DIRS` and run by `make test` via `python -m unittest discover`.
- The AWS-side (secrets manager resolve, fsx describe) is driven by stubbed boto3
  sessions built with `unittest.mock`; no live account is reached.
- ONTAP REST mocked by a recording fake: assert each pattern assembles the correct
  method+path+body, and that a pre-fix stub fails. Assert the allowlist/keep-list/
  dry-run gates reject out-of-scope input, using an explicit case table with subTest.
- Until a real-cluster run, all ONTAP-side behavior is `hypothesis` / not verified.
- `make all` (with PY_PATHS extended to include automation) must pass before commit.
