---
title: FlexCache とストレージチューニングの NetApp／AWS 一次資料マップ — 設計・運用・構築で読む資料への導線
lifecycle: [design, build, operate, optimize]
domains: [performance, client-access, data-protection]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/flexcache/
lang: ja
---

# FlexCache とストレージチューニングの一次資料マップ

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md) | [Domain — 性能](../domains/performance/README.md)

---

## 結論

**Amazon FSx for NetApp ONTAP の FlexCache とストレージチューニングを設計・運用・構築するとき、一次情報は AWS と NetApp の複数の資料に分かれています。** 作成手順は AWS の ONTAP ガイド、キャッシュの動作原理と推奨設定は NetApp の Technical Report とドキュメント、FlexGroup の配置は別の TR、というように、1 つの論点の根拠が 1 か所にあるとは限りません。

**この索引は、資料ごとに「何に答える資料か」「設計・運用・構築のどの場面で読むか」を 1 枚にしたものです。** [性能実測の所在マップ](performance-evidence-map.md) が Spoke の実測記録を索引するのに対し、こちらは**ベンダー一次資料への導線**を索引します。

**この索引に資料の結論は転記しません。** キャッシュの挙動値や推奨設定は、バージョンと環境を切り離すと誤読されます。各資料が何を扱うかだけを示し、具体的な記述はリンク先で読みます。

> **区分**: `documented` — 各行は、公開されている AWS / NetApp の一次資料の所在と範囲を記載しています。**このリポジトリは、これらの資料の記述を再測定・再検証していません。** 本リポジトリで実機確認した知見は [FlexCache で「読めるのに書けない」ときに最初に見るところ](../domains/performance/notes/flexcache-origin-permissions-and-peering-constraints.md) と [FlexCache CLI 手順 (NFS編) – 簡易版](flexcache-cli-nfs-simplified.md) にあり、`verified` / `documented` の区分はそちらに付けています。

---

## この索引を読むときの前提

- **バージョンに依存する記述が多い。** FlexCache write-back は ONTAP 9.15.1 以降、Cache への NFSv4 アクセスは 9.10.1 以降、というようにバージョンで可否が変わります。資料を読むときは、自環境の ONTAP バージョンと資料が前提とするバージョンを照合します。
- **AWS 資料と NetApp 資料で管理面が分かれる。** FSx for ONTAP は AWS 管理面（コンソール / FSx for ONTAP の API）と ONTAP 管理面（REST / CLI）の二面構造です。FlexCache や QoS の多くは ONTAP 管理面の管轄で、AWS API に相当パラメータがない操作があります。
- **PDF 資料は本文を機械取得できない場合がある。** 下表で PDF と明記したものは、所在と範囲を指すポインタとして載せています。本リポジトリの主張の根拠には、本文を確認できた HTML ドキュメントを用いています。

---

## FlexCache の資料

| 論点 | 資料 | 何に答えるか / いつ読むか |
|---|---|---|
| FlexCache とは何か、FSx for ONTAP での構成（Origin/Cache の組み合わせ）、write-around / write-back の選択 | [AWS: Replicating your data with FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) | 設計の入口。Cache が読み書き可能であること、write-back が 9.15.1 以降であること、read-heavy か write-heavy かでモードを選ぶこと |
| FlexCache ボリュームの作成手順（LIF 収集・cluster peering・SVM peering・Cache 作成・マウント） | [AWS: Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html) | 構築時。手順の全体像 |
| write-back の概念・用語（dirty data, XLD/SLD, DDRS）、write-around との対比、origin あたりの上限 | [NetApp: Learn about ONTAP FlexCache write-back](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-overview.html) | write-back を検討するとき。write-around は origin あたり 100、write-back は 10 という上限の違い |
| write-back を使うときのガイドライン（単一 constituent 推奨など） | [NetApp: ONTAP FlexCache write-back guidelines](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-guidelines.html) | write-back の設計時。構成の推奨と、ガイドライン外で使う場合の検証の必要性 |
| write-back が効く / 効かないアクセスパターン | [NetApp: ONTAP FlexCache write-back use cases](https://docs.netapp.com/us-en/ontap/flexcache-writeback/flexcache-write-back-use-cases.html) | write-back の効果を見積もるとき。OPEN と CLOSE の間の書き込み量と性能向上の関係 |
| FlexCache の設計・運用の体系的な一次資料（TR-4743） | [NetApp Technical Report TR-4743: FlexCache in ONTAP](https://www.netapp.com/media/7336-tr4743.pdf) （PDF） | 設計を掘り下げるとき。キャッシュ無効化、refresh、ネットワーク律速の考え方。PDF のため所在ポインタとして掲載 |

---

## ストレージチューニング・配置の資料

| 論点 | 資料 | 何に答えるか / いつ読むか |
|---|---|---|
| FSx for ONTAP の性能の決まり方（スループットキャパシティ、SSD IOPS、ネットワーク） | [AWS: Amazon FSx for NetApp ONTAP performance](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html) | サイジング時。何がスループットの上限を決めるか |
| ストレージ階層とティアリングポリシー（SSD / Capacity Pool） | [AWS: FSx for ONTAP best practices (Prescriptive Guidance)](https://docs.aws.amazon.com/prescriptive-guidance/latest/fsx-ontap-enterprise-deployment/best-practices.html) | コスト最適化と性能のトレードオフを設計するとき <!-- allow:sales-vocabulary 出典ページの正式名称に best practices を含む --> |
| FlexGroup の構成とデータ配置（作成時にバランスし、その後は再配置しない） | [NetApp Technical Report TR-4571: FlexGroup volumes best practices](https://www.netapp.com/media/12385-tr4571.pdf) （PDF） | Cache ボリュームは常に FlexGroup のため、高ファイル数ワークロードの配置を設計するとき。PDF のため所在ポインタとして掲載 <!-- allow:sales-vocabulary TR-4571 の正式名称に best practices を含む --> |
| export-policy によるアクセス制御の設計 | [AWS Storage Blog: Restrict access using export policies](https://aws.amazon.com/blogs/storage/restrict-access-to-your-amazon-fsx-for-netapp-ontap-volumes-using-export-policies) | NFS アクセス制御を設計するとき。rule の順序と RO/RW の意味 |
| QoS による throughput ceiling / floor | [NetApp: Set a throughput ceiling with QoS](https://docs.netapp.com/us-en/ontap/performance-admin/set-throughput-ceiling-qos-task.html) | ワークロードごとに上限・下限を設計するとき |
| FSx for ONTAP の技術詳細（Tech Deep Dive） | [NetApp: Amazon FSx for NetApp ONTAP Tech Deep Dive](https://www.netapp.com/ja/pdf.html?item=/ja/media/138603-amazon-fsx-for-netapp-ontap-tech-deep-dive.pdf) （PDF・日本語） | 全体像を日本語で把握するとき。PDF のため所在ポインタとして掲載。本リポジトリの主張の根拠には用いていない |

---

## クラスタピアリングの資料

| 論点 | 資料 | 何に答えるか / いつ読むか |
|---|---|---|
| cluster peer ポリシー（無認証許可、パスフレーズ最小長） | [NetApp: cluster peer policy modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-policy-modify.html) | 無認証ピアを検討するとき。無認証ピアが残る間は認証必須へ戻せない制約 |
| cluster peer の属性変更（認証状態、暗号化） | [NetApp: cluster peer modify](https://docs.netapp.com/us-en/ontap-cli/cluster-peer-modify.html) | 認証付き / 無認証を切り替えるとき。両クラスタでの反映が必要 |

---

## 関連ドキュメント

- [FlexCache で「読めるのに書けない」ときに最初に見るところ](../domains/performance/notes/flexcache-origin-permissions-and-peering-constraints.md) — 本リポジトリで実機確認した切り分け
- [FlexCache CLI 手順 (NFS編) – 簡易版](flexcache-cli-nfs-simplified.md) — 作成手順の最短経路
- [性能実測の所在マップ](performance-evidence-map.md) — Spoke の実測記録の所在
- [知見の分類ポリシー](../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md) | [Domain — 性能](../domains/performance/README.md)

<!-- lang-switcher:start -->
🌐 [日本語](netapp-primary-sources-map.md) | [English](../../en/reference/netapp-primary-sources-map.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
