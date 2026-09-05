---
title: LUN に載せた DB は静止させずに復旧した — write fence 付き Snapshot が 0.52 秒で、復旧は DB 自身がやる
lifecycle: [design, build, operate]
domains: [block-storage, data-protection]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# LUN に載せた DB は静止させずに復旧した

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**データと WAL を別の LUN に分けた PostgreSQL に対して、書き込みを止めずに consistency group の Snapshot を取り、そのクローンから起動したところ、DB は自分で WAL を再生して整合した状態になりました。**

- **write fence 付きの Snapshot は 0.52 秒**で返り、2 つのボリュームに**同一時刻**の Snapshot ができました
- クローンから起動した PostgreSQL は **`database system was not properly shut down; automatic recovery in progress`** と記録し、**0.84 秒で redo を完了**しました
- **fence の直前にコミットされていた行はすべて残っていました。** 欠番もありません
- **`pg_backup_start` に相当する操作は一度も使っていません**

**「crash-consistent だから DB には使えない」ではありません。** **crash-consistent は、DB が自分でクラッシュから立ち上がれる限りにおいて DB に使えます。** 効いているのは Snapshot の種類ではなく、**依存関係のある書き込みの順序が壊れていないこと**です。だから **複数の LUN にまたがるなら fence が必要**になります。

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`MULTI_AZ_2` 第 2 世代 1 HA ペア、ONTAP 9.18.1P5、Amazon Linux 2023、PostgreSQL 16、XFS）— fence の所要時間、Snapshot の時刻の一致、復旧のログ、残った行数、`nouuid` の要否。
> **これは 1 つの DB エンジンでの 1 回の観測です。** 他のエンジンや他の設定に一般化しないでください。

---

## 構成

| 要素 | 配置 |
|---|---|
| データディレクトリ | 40 GiB の LUN（ボリューム A） |
| WAL | **別の** 20 GiB の LUN（ボリューム B）、`initdb -X` で指定 |
| ファイルシステム | 両方 XFS |
| 負荷 | コミット付きの INSERT を連続実行（検証中ずっと継続） |

**NetApp の PostgreSQL 向けの手引きも、データとログを別ボリュームに分ける構成を示しています。** ただしそちらは NFS マウントの例です。**ここでは同じ分割を LUN で行いました。**

---

## write fence が必要な理由と、その所要時間

**2 つの LUN を別々に Snapshot すると、2 つの時点が混ざります。** データが新しくて WAL が古い、あるいはその逆になり得ます。**DB の復旧が前提にしている「WAL がデータより進んでいる」という関係が壊れます。**

consistency group は複数ボリュームを 1 単位として扱い、**write fence を掛けている間に全ボリュームの Snapshot をまとめて確定します。**

```text
vserver consistency-group create -vserver <svm> -consistency-group cg_pg \
                                 -volumes <data-vol>,<wal-vol>

vserver consistency-group snapshot create -vserver <svm> -consistency-group cg_pg \
                                 -snapshot cgfence1 -consistency-type crash -write-fence true
```

実測です。

| 項目 | 結果 |
|---|---|
| コマンドが返るまで | **0.52 秒** |
| 2 つのボリュームの Snapshot 作成時刻 | **同一**（`Sat Sep 05 07:24:52 2026`） |
| fence の直前の `max(id)` | 210,000 |
| fence の直後の `max(id)` | 213,000 |

**NetApp は consistency group の Snapshot に内部で 7 秒のタイムアウトがあると記載しています。** **0.52 秒はその中に十分収まりました。** ただし **ボリューム数と負荷が増えれば近づきます。** fence が失敗したときに何が起きるかは、この検証では観測していません。

**`-consistency-type` の既定は `crash` です。** スケジュール実行の Snapshot は常に crash になります。

**`fsxadmin` で `vserver consistency-group` 系のコマンドが使えました。**

---

## クローンの受け渡し

Snapshot からボリュームをクローンし、**別ホストの igroup に割り当てました。**

```text
volume clone create -vserver <svm> -flexclone clone_pgdata \
                    -parent-volume <data-vol> -parent-snapshot cgfence1
lun map -vserver <svm> -path /vol/clone_pgdata/pgdata -igroup <他ホストの igroup>
```

**クローンの中の LUN は serial が親と別です。** つまり WWID が別で、ホストからは別のディスクとして見えます。

| LUN | 親の serial | クローンの serial |
|---|---|---|
| data | `…717a6976` | `…717a697a` |
| WAL | `…717a6977` | `…717a6a30` |

**クローンした LUN は明示的に `lun map` する必要があります。** 親のマッピングは引き継がれません。

**マウントに `-o nouuid` は要りませんでした。** これはラウンド 1 の観測を狭めます。

| 状況 | `nouuid` |
|---|---|
| 親のファイルシステムを**同じホスト**にマウントしている | **必要。** XFS は UUID が一致するファイルシステムの二重マウントを拒否します |
| 親を**別ホスト**にマウントしている（今回） | **不要。** そのまま `mount` できました |

**`nouuid` はクローンの性質ではなく、同一ホストでの UUID の衝突に対する回避です。** クローンを別ホストに渡す運用では要りません。

---

## 復旧の中身

**クローン側の PostgreSQL は、事前準備なしで起動しました。** `postmaster.pid` を消しただけです。

```text
LOG:  database system was interrupted; last known up at 2026-09-05 07:24:11 UTC
LOG:  database system was not properly shut down; automatic recovery in progress
LOG:  redo starts at 0/1543818
LOG:  invalid record length at 0/5C40768: expected at least 24, got 0
LOG:  redo done at 0/5C40740 system usage: ... elapsed: 0.84 s
LOG:  checkpoint starting: end-of-recovery immediate wait
LOG:  checkpoint complete: ...
```

| ログの行 | 読み方 |
|---|---|
| `was not properly shut down` | **Snapshot が「電源が落ちた状態」に見えているということです。** これが crash-consistent の意味です |
| `redo starts` → `redo done`（0.84 秒） | **DB が WAL を再生しました。** 人手の操作はありません |
| `invalid record length` | **WAL の終端を示す通常の行です。破損ではありません。** 再生はここで止まるのが正しい動作です |
| `checkpoint complete` | 復旧後のチェックポイント |

データの確認です。

| 項目 | 結果 |
|---|---|
| `count(*)` | 212,000 |
| `min(id)` / `max(id)` | 1 / 212,000 |
| 欠番 | **なし**（count と max が一致） |

**212,000 は fence 直前の 210,000 と直後の 213,000 の間にあります。** つまり **fence より前にコミットされた行はすべて残り、fence の窓の中でコミットされた行も一部残りました。** 失われたコミット済みの行はありません。

**`pg_backup_start` / `pg_start_backup` は使っていません。** **NetApp の PostgreSQL 向けの手引きにもこれらは登場しません。**

---

## 言えることと言えないこと

**言えること**（この環境での実測）。

- 複数 LUN にまたがる DB を、書き込みを止めずに 1 時点として取れる
- その時点から起動した DB は自分で復旧し、コミット済みのデータを失わない
- 復旧のために追加の操作は要らない

**言えないこと。**

| 主張 | なぜ言えないか |
|---|---|
| すべての DB エンジンで同じになる | **PostgreSQL 16 で 1 回観測しただけです** |
| fence が失敗する条件と症状 | **観測していません。** 7 秒のタイムアウトに近づいた場合の挙動は未確認 |
| ボリュームが多い構成でも 0.52 秒で済む | **2 ボリュームでの値です** |
| application-consistent が不要 | **要件次第です。** 下の区別を読んでください |

**crash-consistent と application-consistent の区別は、この検証では変わりません。** **NetApp は 2 つのフラグが記録用であり、ONTAP の観点では違いがないと書いています。** 静止させるのはストレージの外側の仕組みです。**つまり判断はバックアップ製品の有無ではなく、「その時点で復旧して足りるか」という要件の側にあります。** 詳細は [LUN の Snapshot は既定で crash-consistent](a-snapshot-of-a-lun-is-crash-consistent.md) にあります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | データと WAL / redo を別ボリュームの LUN に分ける | fence が要る構成になっていること |
| 2 | `vserver consistency-group create` が通るか確認する | **`fsxadmin` で使えること** |
| 3 | 負荷を掛けた状態で `snapshot create … -write-fence true` を実行し、**返るまでの時間を測る** | **7 秒のタイムアウトに対する余裕** |
| 4 | `volume snapshot show -snapshot <名前> -fields volume,create-time` | **全ボリュームの時刻が一致していること** |
| 5 | 直前と直後にコミット済みの最大キーを記録する | 後で失われた範囲を判定する足場 |
| 6 | クローンを**別ホストの igroup** に割り当て、起動する | **`lun map` が別途必要なこと** |
| 7 | 起動後のログで `redo starts` / `redo done` を確認する | **DB が実際に再生したこと。** これが無ければ検証になっていません |
| 8 | 記録した最大キー以下の行がすべてあるかを数える | **失われたコミットが無いこと** |
| 9 | `-write-fence false` でも同じことを行い、結果を比べる | **fence の効果**（本番では行わないこと） |

**手順 9 は検証環境で行ってください。** fence 無しで壊れた状態を作る手順です。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| crash-consistent な Snapshot は DB に使えない | **DB が自分でクラッシュから立ち上がれるなら使えます。** 実測で 0.84 秒で復旧しました |
| DB を静止させないと Snapshot が無意味 | **静止させずに取ったクローンからコミット済みデータが全部戻りました** |
| 複数 LUN でもボリュームごとに Snapshot すれば足りる | **時点が混ざります。** fence が要ります |
| write fence は I/O を長く止める | **この構成では 0.52 秒でした**（2 ボリューム） |
| `-consistency-type application` にしないと危ない | **既定は `crash` で、これで復旧しました。** 判断は復旧目標の側です |
| `pg_backup_start` が必要 | **使っていません。** NetApp の手引きにも登場しません |
| クローンのマウントには常に `nouuid` が要る | **親を同じホストにマウントしているときだけです** |
| クローンの LUN はすぐ使える | **`lun map` が別途必要です。** 親のマッピングは継がれません |
| クローンの LUN は WWID が同じ | **serial が別なので WWID も別です** |
| `invalid record length` はデータ破損 | **WAL の終端を示す通常の行です** |

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| デプロイタイプ | `MULTI_AZ_2`（第 2 世代、1 HA ペア） |
| スループット容量 | 384 MBps |
| DB | PostgreSQL 16（Amazon Linux 2023 のパッケージ） |
| データ LUN | 40 GiB、XFS |
| WAL LUN | 20 GiB、XFS、別ボリューム、`initdb -X` |
| クライアント | Amazon Linux 2023、kernel 6.18.44-99.149.amzn2023.x86_64。クローンの起動は別 AZ の別ホスト |
| 検証日 | 2026-09-05 |

> **注意**: 上記はこの環境での 1 回の実測です。**fence の所要時間はボリューム数と負荷で変わります。** 本番の構成で測ってください。

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| `vserver consistency-group snapshot create` の構文、`-consistency-type` の既定が `crash` であること、`-write-fence` があること、admin 権限で使えること | [NetApp: vserver consistency-group snapshot create](https://docs.netapp.com/us-en/ontap-cli/vserver-consistency-group-snapshot-create.html) |
| consistency group が write fence を掛けて全メンバーの同一時点のイメージを作ること | [NetApp: Manage application consistency groups](https://docs.netapp.com/us-en/ontap-restapi-9161/manage_application_consistency_groups.html) |
| オンデマンドの Snapshot が application consistent か crash consistent を選べ、既定が crash であること。スケジュール実行は常に crash であること | [NetApp: Manage application consistency group snapshots](https://docs.netapp.com/us-en/ontap-restapi-9171/manage_application_consistency_group_snapshots.html) |
| consistency group の概念と、複数ボリュームにまたがる保護の保証 | [NetApp: Learn about ONTAP consistency groups](https://docs.netapp.com/us-en/ontap/consistency-groups/) |
| PostgreSQL でデータとログを別ボリュームに分ける構成、復旧手順、`pg_backup_start` を用いないこと | [NetApp: PostgreSQL with ONTAP](https://docs.netapp.com/us-en/ontap-apps-dbs/postgres/postgres-overview.html) |
| application-consistent と crash-consistent のフラグが記録用であり、ONTAP の観点では違いがないこと | [NetApp: Application snapshots (REST API)](https://docs.netapp.com/us-en/ontap-restapi/application_applications_application.uuid_snapshots_endpoint_overview.html) |
| FlexClone の作成と、親 Snapshot の指定 | [NetApp: volume clone create](https://docs.netapp.com/us-en/ontap-cli/volume-clone-create.html) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [LUN の Snapshot は既定で crash-consistent](a-snapshot-of-a-lun-is-crash-consistent.md) — 整合性の定義と、要件の側の判断
- [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) — なぜデータと WAL を分けるか
- [容量は 3 か所で数えられる](capacity-is-counted-in-three-places.md) — クローンと Snapshot が容量に効く経路
- [ブロックの監視で見えるものと見えないもの](what-block-monitoring-shows.md)
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
