# ジャンル — AWS の AI エージェントを FSx for ONTAP に使う

[🏠 リポジトリトップ](../../../README.md)

---

AWS が提供するマネージド AI エージェント（AWS DevOps Agent, AWS FinOps Agent, AWS Security Agent, Amazon Quick, AWS Transform など）を、Amazon FSx for NetApp ONTAP の設計・構築・運用に**どう使うか**を扱うジャンルです。エージェントごとに 1 サブディレクトリへ分岐し、そこに知見を貯めます。

**このジャンルが扱うのは「エージェントの適合判断と使い方」で、FSx for ONTAP そのものの技術知見ではありません。** ストレージ側の知見は [テーマ軸](../navigation.md#テーマ軸--domains) と [ライフサイクル軸](../navigation.md#ライフサイクル軸--playbooks) にあります。ここは、そのストレージ運用にエージェントを重ねるときの判断を書きます。

---

## このジャンルの前提

**ここに書くのは、著者が公式ドキュメントで確認したエージェントの仕様と、それが FSx for ONTAP 運用に効くかどうかの判断です。** 2 つの確度が混ざるので、各ページで分けて書きます。

| 何を書くか | 確度の扱い |
|---|---|
| エージェントの仕様（何ができ、どの信号源を見るか） | 公式ドキュメントに出典。`documented` 相当 |
| FSx for ONTAP 運用への適合判断（効く/効かない、どの指標を見るべきか） | **著者環境での実測ではない。本文で「未検証」と明示する** |

このジャンルは `docs/ja/domains/` の 9 テーマとは独立した器なので、`notes/` ディレクトリは使いません（frontmatter スキーマの対象外にするため）。証拠区分はページ本文と冒頭の但し書きで示します。判断基準の考え方は [知見の分類ポリシー](../evidence-policy.md) に準じます。

---

## 収録エージェント

現時点で AWS が提供するマネージド AI エージェントを網羅した一覧です。**提供状態は変わるので、各エージェントの状態は 2026-09 時点の公式ドキュメント調査に基づきます。** 本番採用前に最新の提供状態を確認してください。

| エージェント | 主な用途 | 提供状態（2026-09 調査） | FSx for ONTAP との距離 | 収録 |
|---|---|---|---|---|
| AWS DevOps Agent | 本番運用のインシデント解決・予防 | GA | 近い（運用に直接。CloudWatch 起点） | [AWS DevOps Agent を FSx for ONTAP 運用に使う](devops-agent/README.md) |
| AWS FinOps Agent | コストの継続監視・異常調査・最適化 | Public Preview | 近い（コスト運用） | _未追加_ |
| AWS Security Agent | アプリのオンデマンド侵入テスト・継続検証（現在は AWS Continuum の一部） | GA | 間接（アプリ層のセキュリティ。ストレージ運用とは距離あり） | _未追加_ |
| Amazon Quick | AI アシスタント / エージェント型デジタルワークスペース | GA | **近い（S3 Access Points 経由で FSx for ONTAP をデータソース化できる）** | [Amazon Quick を FSx for ONTAP のデータソースにする](quick/README.md) |
| AWS Transform | コード・ワークロードの移行と変換 | GA | 近い（移行先に FSx for ONTAP を選択可） | [移行の項へ](#aws-transform-の既存ページへの集約) |
| Amazon Bedrock Managed Agents (OpenAI) | OpenAI harness ベースのマネージドエージェント runtime | Limited Preview | 間接（AgentCore 上の runtime） | _対象外_ |
| Kiro | 仕様駆動のソフトウェア開発エージェント | GA | 遠い（現時点でデータソース連携なし。MCP 経由の将来連携は可能性） | _対象外_ |

**表記の意味**:

- `_未追加_` — このジャンルで深掘りページを書く対象だが、まだ書いていない
- `_対象外_` — 存在は記録するが、現時点では FSx for ONTAP 運用への直接の重ね方が薄く、深掘りページを設けない
- 「移行の項へ」— このジャンル内に新規ページを作らず、既存の移行ドキュメントへ繋ぐ（後述）

**エージェントの基盤系（Amazon Bedrock AgentCore, AWS Context, AWS Agent Registry など）は、この表に含めていません。** これらは「エージェントを作る・支える・統治する」基盤で、FSx for ONTAP 運用に重ねる対象ではないためです。エージェントを自作して FSx for ONTAP を扱わせるときの基盤として関わりますが、その観点は各エージェントのページ側で必要に応じて触れます。

---

## どのフェーズに効くか（横断の入口）

**エージェントによって効くフェーズが違います。** 手元の状況から、どのエージェントのページを先に読むかを決めます。

| 手元にあるもの | 先に読むエージェント | 理由 |
|---|---|---|
| **本番稼働中で、インシデント対応を速くしたい** | [AWS DevOps Agent](devops-agent/README.md) | インシデント検知・原因分析・予防が用途。CloudWatch アラームを起点に動く |
| **コストの異常を追い、最適化したい** | AWS FinOps Agent（_未追加_） | コストの継続監視と異常調査が用途 |
| **FSx for ONTAP 上のファイルをレポート・分析に使いたい** | [Amazon Quick](quick/README.md) | S3 Access Points 経由でファイルをナレッジベース化できる |
| **VMware / サーバーを移行し、移行先を FSx for ONTAP にしたい** | [移行ドキュメント](#aws-transform-の既存ページへの集約) | 移行の知見は既存ページにある |
| **アプリのセキュリティを継続検証したい** | AWS Security Agent（_未追加_） | オンデマンド侵入テストが用途。ストレージ運用とは距離あり |

各エージェントの詳細な適合判断は、それぞれのページにあります。

---

## AWS Transform の既存ページへの集約

AWS Transform と FSx for ONTAP の関係（移行先ストレージ種別としての対応、Finalize の物理容量、コンテナ化のスコープ）は、このジャンルで新しく書かず、**既存の移行ドキュメントへ繋ぎます。** 同じ内容を 2 か所に置くと片方が古くなるためです。

| 知りたいこと | 読むページ |
|---|---|
| AWS Transform が FSx for ONTAP をサポートした範囲と状態 | [直近のアップデート — AWS Transform が FSx for ONTAP をサポート](../reference/recent-updates.md#aws-transform-が-fsx-for-ontap-をサポートga-2026-08) |
| Finalize で物理容量が最大になる工程 | [AWS Transform の Finalize は後片付けではなく、物理容量が最大になる工程](../playbooks/03-migrate/notes/atx-finalize-flexclone-capacity.md) |
| コンテナ化と永続ストレージの関係 | [コンテナから FSx for ONTAP をデータストアにできるか](../reference/decision-trees/container-datastore-selection.md) |
| 移行の実装（Spoke リポジトリ） | [VMware-Migration-EC2-ONTAP](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP) |

---

## 新しいエージェントを足すとき

1. `docs/ja/ai-agents/<agent-slug>/README.md` を作る（`devops-agent/` を雛形にする）
2. ページ冒頭に「仕様は出典付き / 適合判断は未検証」の但し書きを置く
3. 上の「収録エージェント」表の `_未追加_` を実リンクに置き換える
4. **未検証の数値（しきい値・上限・価格）を焼き込まない。** 出典が付けられない数値は「どの指標を見るか」の観点に留める
5. 命名規約（初出は Amazon FSx for NetApp ONTAP、以降 FSx for ONTAP）を守る
6. `make audit` `make links` `make lint` を通す

**細目が増えたら、`<agent-slug>/README.md` と同階層に `<slug>.md` を足します。** observability のような `notes/` 分割が要るほど育った段階で、ディレクトリ構造を見直します。

---

## 関連

- [ナビゲーションガイド](../navigation.md)
- [知見の分類ポリシー](../evidence-policy.md)
- [テーマ軸で探す](../navigation.md#テーマ軸--domains) — FSx for ONTAP そのものの知見

---

[🏠 リポジトリトップ](../../../README.md)
