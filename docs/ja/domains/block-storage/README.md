# Domain — ブロックストレージ (Block Storage)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/block-storage/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

iSCSI と NVMe/TCP で LUN・namespace を提供するときの設計・構築・運用を扱います。ファイル共有と違い、**整合性とパスの面倒はホスト側の責任として残ります。** その分界線がこのモジュールの中心です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | iSCSI と NVMe/TCP のどちらを選ぶか。何が選択肢を狭めるか | [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](notes/protocol-choice-is-bounded-before-you-choose.md) |
| 2 | LUN をボリュームにどう並べるか。1 LUN 1 ボリュームは正解か | [LUN の並べ方が決めているのは復旧の粒度](notes/lun-layout-decides-recovery-granularity.md) |
| 3 | ブロックのどこまでを IaC で作れるか | [LUN と igroup は AWS の API の外側にある](notes/block-objects-are-outside-the-aws-api.md) |
| 4 | 容量はどこで二重に数えられるか。書けなくなるとどうなるか | [容量は 3 か所で数えられる](notes/capacity-is-counted-in-three-places.md) |
| 5 | パスは何本必要で、誰が面倒を見るか | [パスはフェイルオーバーの仕組みそのもの](notes/paths-are-the-failover-mechanism.md) |
| 6 | LUN の Snapshot はどこまで戻せるか | [LUN の Snapshot は既定で crash-consistent](notes/a-snapshot-of-a-lun-is-crash-consistent.md) |
| 7 | EBS で足りる場合と、共有ブロックが設計を変える場合の境目はどこか | [共有ブロックが設計を変える条件](notes/when-shared-block-changes-the-design.md) |
| 8 | Kubernetes にブロックを供給するとどこが詰まるか | [Kubernetes のブロック PV はボリューム数の上限に当たる](notes/kubernetes-block-volumes-and-the-volume-limit.md) |
| 9 | ブロックの性能値をどう読み、どう測るか | [公開ベンチマークの読み方](notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) |
| 10 | Multi-AZ で何が変わるか。ピアリング越しに届くか | [Multi-AZ が動かすのはアドレスではなくルート](notes/multi-az-moves-a-route-not-an-address.md) |
| 11 | フェイルオーバーで I/O は止まるか。iSCSI と NVMe/TCP で違うか | [パスはフェイルオーバーの仕組みそのもの](notes/paths-are-the-failover-mechanism.md#実測したフェイルオーバー) |
| 12 | igroup 以外にアクセス制御の手立てはあるか | [igroup の外側にある 2 つの制御](notes/igroups-are-not-the-only-access-control.md) |
| 13 | 複数 LUN にまたがる DB を止めずにバックアップできるか | [LUN に載せた DB は静止させずに復旧した](notes/a-database-on-luns-recovers-without-quiescing.md) |
| 14 | ブロックの監視で何が見えるか。LUN 単位で見られるか | [ブロックの監視で見えるものと見えないもの](notes/what-block-monitoring-shows.md) |
| 15 | Fibre Channel は使えるか | _未追加_（[用語集の FC の項](../../reference/glossary/README.md) に記載範囲があります） |

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト |

---

## 読み方

各ノートの frontmatter にある `evidence` を必ず確認してください。

| 区分 | 意味 |
|---|---|
| `verified` | 記載環境で著者が再現済み。`verified_on` に検証日 |
| `documented` | ベンダー / AWS 公式ドキュメントに記載あり。`source` に出典 |
| `field-observation` | 現場で一度観測。再現確認は未実施。一般化しないこと |
| `hypothesis` | 未検証の推論 |

判断基準の詳細は [知見の分類ポリシー](../../evidence-policy.md) を参照してください。

**このモジュールの `verified` は挙動の確認であって性能値ではありません。** 検証は 384 MBps の最小構成（Single-AZ と Multi-AZ の 2 環境）で行っており、スループットや IOPS の数値は取っていません。性能値の読み方は [公開ベンチマークの読み方](notes/when-shared-block-changes-the-design.md#公開ベンチマークの読み方) にあります。

**フェイルオーバーの秒数だけは例外です。** これは性能値ではなく可用性の挙動なので測りました（[実測したフェイルオーバー](notes/paths-are-the-failover-mechanism.md#実測したフェイルオーバー)）。測定条件はノート内に全部書いてあります。

---

## 関連

- [ブロックストレージ横断リソースマップ](../../reference/block-storage-resource-map.md) — AWS / NetApp の一次情報と公開 IaC の索引
- [ブロックプロトコルとレイアウトの決定木](../../reference/decision-trees/block-protocol-and-layout.md)
- [ブロックストレージの選択肢の比較](../../reference/comparison/block-storage-options.md)
- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/block-storage/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
