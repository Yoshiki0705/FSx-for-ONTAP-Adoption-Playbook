# ガードレール配線メモ — `guard_irreversible_ops.py` を AIMF の PreToolUse に足す

[🏠 リポジトリトップ](../../../../../README.md) | [補助パック](README.md)

---

AIMF はクラウド操作の統制を明示的に提供していません。このリポジトリの [`scripts/guard_irreversible_ops.py`](../../../../../scripts/guard_irreversible_ops.py) は、SnapLock・snapshot locking・S3 Object Lock などの不可逆操作をコマンド単位で止めるガードです。このメモは、それを AIMF ワークスペースの `PreToolUse` hook に **AIMF 自身の hook と併存させて**追加配線する手順です。

> **併存は未確認（`hypothesis`）です。** hook の実行順序、Kiro の `--agent migration` 前提との相互作用は検証していません。配線後に自分の環境で `--selftest` を通してから使ってください。

---

## コピーは単一ファイル

AIMF は別リポジトリなので、AIMF ワークスペースへは `guard_irreversible_ops.py` を **1 ファイルだけ**コピーして配線します（[AGENTS.md](../../../../../AGENTS.md) の「copy it into other repositories — that file alone」に従います）。このリポジトリ内で使うときは tracked file を直接指すのが原則ですが、別リポジトリへはコピーが要ります。コピー先で改変しないでください（判定ケースはスクリプト内に持たせてあり、コマンドラインに照合文字列を渡す必要がありません）。

---

## 配線手順

1. `guard_irreversible_ops.py` を AIMF ワークスペースの `scripts/` 相当の場所へ 1 ファイルだけコピーする。
2. AIMF 自身の `PreToolUse` hook（turn-log、work-declaration-guard など）を **置き換えず**、このガードを追加の hook として並べる。どちらかを無効化しないこと。
3. 配線後に 3 判定（block / ask / allow）を確認する。

```bash
python3 scripts/guard_irreversible_ops.py --selftest
```

`--selftest` は block（exit 2）・ask（exit 0 + `permissionDecision`）・allow（exit 0、無出力）の 3 判定を網羅します。**ガードが block することだけでなく、通常の読み取り操作を allow することも確認してください。** 通常作業まで止めるガードは無効化されます。

> **AIMF の最新 hook 構成を確認する。** この手順は AIMF の `harness/README.md` の hook 構成に依拠します。0.x の版差で hook 一覧が変わりうるので、配線前に最新の構成を確認してください。

---

## WORM 系の扱い（AIMF の HOLD-6 と対応づけ）

SnapLock・snapshot locking（Tamperproof Snapshot）・S3 Object Lock・Glacier Vault Lock・AWS Backup Vault Lock・EBS snapshot lock などの WORM 系は、**保持期間を名指しした人の指示なしに有効化しないでください。** これは AIMF の破壊的操作の HOLD（HOLD-6）と対応します。ガードはこれらをコマンド単位で止めますが、ガードがあることは人の判断を省く理由にはなりません。有効化が正しく働くと、起こした障害と区別がつかなくなります。

根拠と事例は Hub にあります。

- [AGENTS.md の不可逆操作節](../../../../../AGENTS.md)
- [不可逆操作は別の承認が要る](../../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [補助パック](README.md)
