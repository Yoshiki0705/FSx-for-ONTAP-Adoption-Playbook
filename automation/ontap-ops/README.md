# ONTAP-ops 削除 Lambda

AWS FSx for ONTAP 管理面では削除できない ONTAP オブジェクト（FlexCache、FlexClone、
オブジェクトストアバケット、vserver 監査宛先、FPolicy、SnapMirror リレーション
シップ）と、それらに依存していたボリューム・SVM を、依存順に削除する再利用可能な
Python AWS Lambda。ファイルシステムの VPC 内で動く。設計は [DESIGN.md](DESIGN.md)。

## 位置づけと検証状態

これは運用ツールであり、App-Modernization その他の検証済みスライスの一部ではない。
Hub に置くことで各 Spoke が再利用できる。

ONTAP 側の挙動は、実クラスタでの 1 回の実行が済むまで `hypothesis`（未検証）として
扱う。本コードが組み立てる REST の method/path/body はテストで固定しているが、それが
実機で意図どおり削除することは別の確認を要する。

本ツールは SnapLock / Object-Lock / Vault-Lock / 保持（retention）系の操作を一切
実装せず、呼び出しもしない。削除能力を奪う機能は扱わない。リポジトリのガード
`scripts/guard_irreversible_ops.py` が引き続き権威を持ち、本コードはそれを通過する。

## 安全ゲート（削除前に必ず通る門）

- イベントは `file_system_id` を必須とする。
- `ONTAP_OPS_ALLOWLIST`（env）に無いファイルシステム ID は、1 件の変更呼び出しよりも
  前に拒否される。allowlist が空なら全件を拒否する。
- `ONTAP_OPS_KEEP_LIST`（env）に含まれる ID は、allowlist にあっても拒否する（多重防御）。
- `dry_run` は既定で True。削除が起きるのはイベントが `confirm: true` を明示したときだけ。
  dry-run は読み取り専用 GET から「何を消すか」の順序付き計画を返す。
- シークレットは明示指定（env `ONTAP_SECRET_ID` またはイベント）。名前推測はしない。
  使用前に、シークレットの `FileSystemId` タグ（または説明文）が対象と一致することを
  検証し、不一致なら中断する。認証失敗時は即座に中断し、再試行しない（fsxadmin ロックの危険）。

## 実行時の入力

| フィールド | 要否 | 意味 |
|---|---|---|
| `file_system_id` | 必須 | 対象ファイルシステム ID |
| `confirm` | 任意 | `true` のときだけ削除を実行（既定: dry-run） |
| `svm_uuid` | 任意 | 対象 SVM の絞り込み |
| `svm_name` | 任意 | SnapMirror の絞り込み |
| `parent_volume_name` | 任意 | FlexClone の親ボリューム名 |
| `split_clones` | 任意 | クローンを split してから削除するか（既定: 直接削除） |
| `secret_id` | 任意 | env `ONTAP_SECRET_ID` を上書き |

## 削除の依存順

SnapMirror 解放 → FlexClone split/削除 → S3 バケット削除 → 監査宛先解放 →
FPolicy 撤去 → FlexCache 削除 → 非 root ボリューム削除 → SVM 削除。各削除は 202 を
返せばジョブ完了まで待ち、削除後は GET の 404/空で消えたことを確認する。

## デプロイ

`cfn/ontap-ops-stack.yaml` が VPC Lambda、インターフェース VPC エンドポイント
（secretsmanager, fsx）、最小権限 IAM（対象シークレットに絞った
`secretsmanager:GetSecretValue`、FSx for ONTAP の Describe 系のみ）を作る。allowlist は
デプロイ時にパラメータ（環境変数）で渡し、コードには焼き込まない。実行時の依存は
boto3 と urllib3 のみで、どちらも Lambda ランタイム提供。

## テスト

`tests/` は実クラスタを必要としない。各パターンがモック上で正しい method/path/body を
組み立てること、わざと壊したスタブが落ちること、allowlist/keep-list/dry-run ゲートが
対象外入力を拒否すること、Secrets Manager の解決と FSx for ONTAP の describe（到達可能な範囲）を
検証する。

テストは Python 標準ライブラリ（`unittest` と `unittest.mock`）のみを使う。Hub の
stdlib-only のテスト規約に合わせており、pytest / moto / hypothesis は使わない。
Secrets Manager と FSx for ONTAP の呼び出しは `unittest.mock` でスタブ化した boto3 セッションで
置き換える。Hub の `make test`（`TEST_DIRS` にこのディレクトリを登録済み）で走る。

```bash
# Hub ルートから。追加の依存は不要（標準ライブラリのみ）。
python3 -m unittest discover -s automation/ontap-ops/tests -t . -q
```

---

## English (mirror)

A reusable Python AWS Lambda that deletes the ONTAP objects the AWS FSx for ONTAP control plane
cannot delete — FlexCache, FlexClone, object-store buckets, the vserver audit
destination, FPolicy, and SnapMirror relationships — then the volumes and SVMs that
depended on them, in dependency order. It runs inside the file system's VPC. Design:
[DESIGN.md](DESIGN.md).

### Status and scope

This is operational tooling. It is **not** part of any App-Modernization or other
verified slice. It lives in the Hub so every Spoke can reuse it.

ONTAP-side behavior is `hypothesis` / not verified until a real-cluster run. The REST
method/path/body each pattern assembles is pinned by tests, but that it deletes as
intended against a live cluster is a separate confirmation.

It never implements or calls any SnapLock, snapshot-locking, Object Lock, Vault Lock, or
retention operation. The repository guard `scripts/guard_irreversible_ops.py` stays
authoritative and this code passes it.

### Safety gates

- The event requires `file_system_id`.
- A file system ID not in `ONTAP_OPS_ALLOWLIST` (env) is refused before any mutating
  call; an empty allowlist refuses everything.
- An ID in `ONTAP_OPS_KEEP_LIST` (env) is refused even if allowlisted (defense in depth).
- `dry_run` defaults true; deletions happen only when the event sets `confirm: true`.
  A dry run returns the ordered plan from read-only GETs.
- The secret is supplied explicitly (`ONTAP_SECRET_ID` or the event); never name-guessed.
  Before use, its `FileSystemId` tag (or description) must match the target, or the run
  aborts. On auth failure the run aborts immediately and is not retried (fsxadmin lock
  hazard).

### Deletion order

SnapMirror release → FlexClone split/delete → S3 bucket delete → audit destination
release → FPolicy teardown → FlexCache delete → non-root volume delete → SVM delete.
Every delete returning HTTP 202 is polled to completion; each is then confirmed by a GET
returning 404/empty.

### Deploy

`cfn/ontap-ops-stack.yaml` provisions the VPC Lambda, interface VPC endpoints
(secretsmanager, fsx), and a least-privilege role (`secretsmanager:GetSecretValue`
scoped to the one secret, FSx for ONTAP Describe-only). The allowlist is passed at deploy time as a
parameter (environment variable), never hardcoded. Runtime dependencies are boto3 and
urllib3 only, both provided by the Lambda runtime.

### Tests

`tests/` needs no live cluster. They assert each pattern assembles the correct
method/path/body against a mocked client (and that a deliberately broken stub fails),
assert the allowlist/keep-list/dry-run gates reject out-of-scope input, and verify the
Secrets Manager resolve and FSx for ONTAP describe paths.

The tests use only the Python standard library (`unittest` and `unittest.mock`), matching
the Hub's stdlib-only test convention — no pytest, moto, or hypothesis. The Secrets
Manager and FSx for ONTAP calls are driven by stubbed boto3 sessions built with `unittest.mock`.
They run under the Hub's `make test` (this directory is registered in `TEST_DIRS`).

```bash
# From the Hub root. No extra dependencies (standard library only).
python3 -m unittest discover -s automation/ontap-ops/tests -t . -q
```
