# 用語集 / Glossary

[🏠 リポジトリトップ](../../README.md) | [Reference](../README.md)

---

ONTAP と AWS の用語を、このリポジトリで使う意味に限定して定義します。
用語そのものは翻訳しません（`ONTAP`、`SnapMirror` などは原語のまま使います）。

Definitions are scoped to how each term is used in this repository. The terms themselves are not
translated — `ONTAP`, `SnapMirror`, and similar stay in the original form.

---

## ストレージ構造 / Storage structure

| 用語 / Term | 定義 / Definition |
|---|---|
| SVM (Storage Virtual Machine) | データアクセスの論理単位。プロトコル設定、AD 参加、ボリュームを持つ / The logical unit of data access; owns protocol configuration, AD membership, and volumes |
| Volume | データを格納する論理単位。セキュリティスタイルを持つ / The logical container for data; carries a security style |
| LIF (Logical Interface) | IP を持つ論理ネットワークインターフェース。管理用とデータ用がある / A logical network interface with an IP; management and data variants exist |
| Aggregate | 物理ディスクをまとめた領域。ボリュームの配置先 / A pool of physical storage where volumes are placed |
| Security style | ボリュームの権限評価方式（`UNIX` / `NTFS` / `MIXED`）。**権限の種類**を決めるもので、アクセス可能なプロトコルを制限するものではない / How permissions are evaluated on a volume; determines the **type** of permissions used, not which protocols may access it |

---

## データ保護 / Data protection

| 用語 / Term | 定義 / Definition |
|---|---|
| Snapshot | ある時点のボリューム状態への参照。作成は瞬時で、変更ブロック分のみ容量を消費 / A point-in-time reference to volume state; instantaneous, consuming capacity only for changed blocks |
| SnapMirror | ボリュームをブロックレベルで複製する仕組み。DR と移行の両方に使う / Block-level volume replication, used for both DR and migration |
| SnapLock | 書き込み後変更不可（WORM）を強制する機能。**有効化は不可逆** / Enforces write-once-read-many. **Enablement is irreversible** |
| FlexClone | Snapshot から書き込み可能なコピーを瞬時に作る機能。初期容量消費なし / Creates a writable copy from a Snapshot instantly, with no initial capacity consumption |
| FabricPool | アクセス頻度の低いブロックを低コスト層へ自動移動する階層化機能 / Automatic tiering of infrequently accessed blocks to a lower-cost tier |

---

## アクセス / Access

| 用語 / Term | 定義 / Definition |
|---|---|
| FlexCache | 別の場所に読み取りキャッシュボリュームを置く機能 / A read cache volume placed at a different location |
| FSx for ONTAP S3 AP | ボリュームへの S3 API アクセスを提供する Access Point / An access point providing S3 API access to a volume |
| Export policy | NFS クライアントのアクセス制御ルール / Access control rules for NFS clients |
| Name mapping | Windows ユーザーと UNIX ユーザーを対応付ける設定 / Configuration mapping Windows users to UNIX users |
| FPolicy | ファイル操作イベントを外部に通知する仕組み / A mechanism for notifying external systems of file operation events |

---

## 用語の使い方 / Usage conventions

| ルール / Rule | 内容 / Detail |
|---|---|
| サービス名 / Service name | 初出は **Amazon FSx for NetApp ONTAP**、以降 **FSx for ONTAP** / First mention in full, then the short form |
| 略称 / Abbreviations | `FSxN`、単独の `FSx`、`FSx ONTAP` は使わない / Not used <!-- allow:naming --> |
| Access Point | FSx for ONTAP の文脈では **FSx for ONTAP S3 AP** と書く / Written in full when the context matters |
| 単位 / Units | GB と GiB を区別する。実測値は単位を明示 / GB and GiB are distinguished; measured values state the unit |

---

## 関連ドキュメント / Related documents

- [ナビゲーションガイド](../../docs/ja/navigation.md) / [Navigation Guide](../../docs/en/navigation.md)
- [AGENTS.md](../../AGENTS.md) — 命名規約の権威 / authoritative naming rules

---

[🏠 リポジトリトップ](../../README.md) | [Reference](../README.md)
