---
title: AI のアクセス経路別のコストと性能 — プロトコルと接続サービスで向き不向きが分かれる
lifecycle: [assess, design]
domains: [cost, data-utilization, performance, client-access]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html
lang: ja
---

# AI / 分析のアクセス経路は、どのプロトコルと接続サービスで何が変わるか？

NFS / SMB / S3 Access Points / ブロック / FlexCache 経由で、到達できるサービスとコスト・性能の効き方が変わります。数値は Spoke の実測を引用し、ここでは定性軸で整理します。

## このノートで学べること

- NFS / SMB / S3 Access Points / ブロック（iSCSI・NVMe/TCP）/ FlexCache の各経路で、どの AWS サービスがデータに到達できるか。
- 各経路のパフォーマンス特性（レイテンシ・スループットが効く場面）とコスト観点を、定性軸で見分ける方法。
- 具体的な実測値がどの Spoke にあるか。

## このノートが答えないこと

- 経路ごとのスループットの絶対値や月額。数値は Spoke の実測と AWS 料金ページを引用します。
- どの経路が「最速」「最安」か。状況によって答えが変わります。

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — コスト](../README.md)

---

### 結論

**AI / 分析のデータへの到達経路は、プロトコルと接続サービスで、到達できるかどうか・性能の効き方・コストの発生点が変わります。** FinOps for AI の観点では、この 3 軸を切り分けて見ると、トークン隣接コスト（[adjacent cost](../notes/finops-for-ai-adjacent-cost.md)）のどこに効くかが判断できます。

分かれ目は 3 つです。

1. **アクセス性** — その接続サービスがこの経路でデータに到達できるか。前提（同一アカウント・同一リージョンなど）を満たすか
2. **パフォーマンス** — レイテンシが効くか、スループットが効くか。繰り返し読むか 1 回だけか
3. **コスト** — 確保課金か消費課金か。リクエスト課金が乗るか。cost per call のどこに効くか

> **Evidence**: `documented` — 到達可否とコストの発生点は AWS / ベンダーの公式ドキュメントに基づきます（**取得日 2026-11-09**）。
> **NFS / SMB / S3 Access Points / FlexCache の性能は Spoke で実測済みです。** 所在は [性能実測の所在マップ](../../../reference/performance-evidence-map.md) にあり、各経路の数値はそこからたどる Spoke（`verified` で記録）を引用します。このノートは判断の指針を持ち、再測定はしません。
> 価格・提供リージョン・製品名は変動するため、選定時に最新の情報で確認してください。

---

### アクセス経路 × 接続サービスの到達性

**まず「この経路でどのサービスがデータに届くか」を確定します。到達できない組み合わせを性能やコストで比べても意味がありません。**

| アクセス経路 | 届く接続サービスの例 | アクセス性の前提 |
|---|---|---|
| **S3 Access Points** | Amazon Bedrock Knowledge Bases（S3 を要求）、Athena / Glue、SageMaker の S3 入力 | **同一アカウント・同一リージョンが前提。ネットワーク origin は呼び出し元で決まり、作成後に変更できません。** Bedrock Knowledge Bases、Athena、Glue のように VPC の外で動くサービスは Internet origin が要り、VPC origin では拒否されます。VPC 内のコンピュートは VPC origin と S3 の Gateway エンドポイントで使えます（[ネットワークの設定](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/configuring-network-access-for-s3-access-points.html)）。S3 標準のすべての操作が通るわけではありません（メタデータ操作の一部が失敗します） |
| **NFS** | EC2 / EKS 上の推論・学習、SageMaker の NFS マウント、HPC | POSIX 共有が要るワークロード。マウント先からの到達性 |
| **SMB** | Windows ベースの推論・前処理、ファイルポータル | AD 参加または NTFS ACL。Windows クライアント |
| **ブロック（iSCSI / NVMe/TCP）** | 単一ホストのデータベース・ベクトルストア | 単一アタッチが基本。共有は設計が要る |
| **FlexCache 経由（NFS / SMB）** | 上記 NFS / SMB と同じ接続先に、キャッシュ再利用を足す | Origin への到達性。Cache 側の制約（セキュリティスタイルは作成後変更不可など） |

**Bedrock Knowledge Bases が S3 を要求する点は、アクセス性の前提の代表例です。** RAG のソースを S3 Access Points 経由で読ませる場合、同一アカウント・同一リージョンが設計段階の制約になります。詳細は [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../../data-utilization/notes/s3-access-point-constraints.md) にあります。

---

### パフォーマンス特性（定性）

**数値は Spoke にあります**（所在は [性能実測の所在マップ](../../../reference/performance-evidence-map.md)）**。ここでは「どの軸が効くか」を整理します。**

| アクセス経路 | レイテンシの効き | スループットの効き | 繰り返し読むとき |
|---|---|---|---|
| **S3 Access Points** | オブジェクト単位のリクエストのレイテンシが効く。小さいファイルが多いと不利 | 大きいオブジェクトの一括読み出しに向く | 毎回 GetObject。容量プール上なら読み取りのリクエスト課金が乗る |
| **NFS** | 低レイテンシ。メタデータ操作が多いワークロードに向く | 単一接続は EC2 の 1 フロー上限に当たる。台数・`nconnect` で分散 | キャッシュが温まれば速い |
| **SMB** | NFS に近い。Multichannel で分散 | 単一接続の上限は NFS と同種 | 同上 |
| **ブロック** | 最も低い。データベース・ベクトルストアに向く | 単一接続はデプロイの性質で 2 つの位置に出る（プロトコル差は小さい） | ホスト側のキャッシュに依存 |
| **FlexCache 経由** | Origin への初回はミス。以降はキャッシュヒットで低レイテンシ | Cache 側のローカル読み出しに乗る | **最も向く。** 同じデータを繰り返し読む AI ワークロードで効く |

**単一接続のスループットは「クライアントを測っている」場合があります。** FSx for ONTAP のファイルプロトコルの単一接続が当たっているのは EC2 の 1 フロー上限で、ストレージ側の上限ではないことがあります。詳細は [1 接続はクライアントを測る](../../performance/notes/a-single-connection-measures-the-client.md) にあります。

**繰り返し読むか 1 回だけか**が、FinOps for AI では最も効く軸です。RAG の共通コンテキストや学習の epoch 反復のように同じデータを繰り返し読むなら FlexCache が cost per call を下げ、1 回しか読まないデータならキャッシュは温まる前に捨てられて効きません。

---

### コスト観点（定性）

**確保課金か消費課金か、リクエスト課金が乗るか、cost per call のどこに効くかで見ます。**

| アクセス経路 | 確保 / 消費 | リクエスト課金 | cost per call への効き |
|---|---|---|---|
| **S3 Access Points** | SSD は確保、容量プールは消費 | **容量プール上のデータは読み書きでリクエスト課金が乗る。** S3 Access Points 経由のリクエストとデータ転送も課金 | 1 クエリあたりの GetObject 回数 × 単価が直接乗る |
| **NFS / SMB** | SSD 容量・スループットは確保 | ファイルプロトコル自体にリクエスト課金はない（容量プールへ落ちた分は乗る） | 確保したスループットを複数クエリで分け合う |
| **ブロック** | SSD 容量・スループット・IOPS は確保 | 同上 | 単一ホストで占有。他ワークロードと分け合わない |
| **FlexCache 経由** | Cache 側の SSD は確保、Origin との同期は内部 | Origin が容量プール上ならミス時に乗る | **キャッシュヒットで Origin への呼び出しが消える。繰り返し読むほど下がる** |

**S3 Access Points の課金は「繰り返し読むか 1 回だけか」で逆転します。** 繰り返し読むデータを容量プールに置くと読み取りのリクエスト課金が積み上がるため、FlexCache や SSD の方が cost per call で有利になる場合があります。S3 標準と S3 Access Points の課金次元の対応は [FinOps — S3 標準と FSx for ONTAP S3 AP](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-s3-vs-s3ap.md) にあります。

**単価そのものは [AWS の料金ページ](https://aws.amazon.com/fsx/netapp-ontap/pricing/) です。** ここには固定値を置きません。改定されるためです。

---

### 実測の所在（Spoke 引用）

**数値はこのリポジトリでは持ちません。実測環境を持つ Spoke を引用します。**

| 知りたいこと | 所在 | そこにあるもの |
|---|---|---|
| S3 標準と S3 Access Points の費用構造の対応 | [FinOps — S3 標準と FSx for ONTAP S3 AP](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/reference/comparison/finops-s3-vs-s3ap.md) | 課金次元の対応。繰り返し読むか 1 回かで向く選択が変わる |
| S3 Access Points のコスト実測手順 | [コスト計測](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/cost-measurement.md) | Cost Explorer から実測する手順。見積りではない |
| FlexCache のキャッシュ再利用の実測 | [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 で集めて FlexCache の NFS/SMB で利用。反映 p50 8 ms |
| ファイルプロトコルの単一接続スループット | [性能実測の所在マップ](../../../reference/performance-evidence-map.md) | NFS / SMB の単一接続が当たっている上限 |
| 分析基盤に載せるときのコスト算定式 | [Cost Estimation](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/adoption-guide/cost-estimation.md) | 構成要素別の内訳とスケーリング算定式 |
| 権限を意識した RAG の実装 | [Agentic RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | 元の ACL は引き継がれず、別の索引に再構成して検索時に判定 |

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| S3 Access Points なら S3 標準と同じに使える | 同一アカウント・同一リージョンが前提で、メタデータ操作の一部が失敗します |
| Bedrock Knowledge Bases はどの経路のデータでも読める | S3 を要求します。S3 Access Points 経由にする場合は前提を満たす必要があります |
| 単一接続のスループットがストレージの上限だ | EC2 の 1 フロー上限を測っている場合があります |
| 繰り返し読むデータは容量プールに落とせば安い | 読み取りのリクエスト課金が積み上がります。FlexCache か SSD が向きます |
| FlexCache は常にコストを下げる | 1 回しか読まないデータには効きません。キャッシュが温まる前に捨てられます |
| 経路は性能だけで選べばよい | 到達性（アクセス性の前提）で先に絞られます |

---

### 選び方

**選択の指針は reference 側の比較マトリクスにまとめてあります。** フローチャート付きで、推奨案の制約も対称に書いてあります。

[AI のアクセス経路の選び方](../../../reference/comparison/finops-for-ai-access-paths.md) を参照してください。

---

### 参照した一次情報

| 論点 | 出典 | 取得日 |
|---|---|---|
| 容量プールの読み書きにリクエスト課金があること、S3 Access Points 経由のリクエストとデータ転送が課金されること | [AWS: What is Amazon FSx for NetApp ONTAP?](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/what-is-fsx-ontap.html) | 2026-11-09 |
| Bedrock Knowledge Bases のデータソースが S3 であること | [AWS: Set up a data source for your knowledge base](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-ds.html) | 2026-11-09 |
| 単価は料金ページで確認すること | [AWS: FSx for ONTAP 料金](https://aws.amazon.com/fsx/netapp-ontap/pricing/) | 2026-11-09 |

---

### 関連ドキュメント

- [Domain — コスト](../README.md) — このモジュールのハブ
- [AI のコストはトークンだけではない](finops-for-ai-adjacent-cost.md) — トークン隣接コストと Tokenomics の骨子
- [AI のアクセス経路の選び方](../../../reference/comparison/finops-for-ai-access-paths.md) — reference 側の比較マトリクス
- [FSx for ONTAP S3 AP は「S3 として使える」わけではない](../../data-utilization/notes/s3-access-point-constraints.md) — S3 Access Points のアクセス性の前提
- [1 接続はクライアントを測る](../../performance/notes/a-single-connection-measures-the-client.md) — 単一接続スループットの読み方
- [性能実測の所在マップ](../../../reference/performance-evidence-map.md) — NFS / SMB / S3 AP / FlexCache の実測の所在
- [プロジェクト間の引用索引](../../../reference/cross-repo-index.md) — どの主張をどの Spoke から引いているか
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — コスト](../README.md)

---

## Read next

[AI のアクセス経路の選び方](../../../reference/comparison/finops-for-ai-access-paths.md)
