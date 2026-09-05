# Domain — データ活用 (Data Utilization)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/data-utilization/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

NAS 上のデータを、コピーを増やさずに分析・AI・アプリケーションから使うための知見です。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | S3 API 経由のアクセスで何ができ、何ができないか | [FSx for ONTAP S3 AP は「S3 として使える」わけではない](notes/s3-access-point-constraints.md) |
| 2 | 分析基盤にどう接続するか | [分析基盤への接続](notes/reaching-data-without-copies.md#分析基盤への接続) |
| 3 | AI / RAG で権限をどう扱うか | [権限が平坦化されることの意味](notes/reaching-data-without-copies.md#権限が平坦化されることの意味) |
| 4 | データコピーを増やさない設計とは | [コピーを増やさない 3 つの手段](notes/reaching-data-without-copies.md#コピーを増やさない-3-つの手段) |
| 5 | 読み取り加速をどこで効かせるか | [FlexCache が効く条件](notes/reaching-data-without-copies.md#flexcache-が効く条件) |
| 6 | エンドユーザーにブラウザや SFTP で見せる経路はどれか | [エンドユーザーがデータに届く経路は 4 つある](../../playbooks/02-design/notes/how-end-users-reach-the-data.md) |
| 7 | AI / ML の学習データセットの版と実験ブランチをどう扱うか | [学習データセットの版をスケジュール Snapshot に載せると消える](notes/dataset-versions-and-experiment-branches.md) |

---

## 動く実装 — sibling リポジトリ

このモジュールの知見を実装したリファレンスアーキテクチャです。知見だけでは判断しにくい「実際にどう組むか」を示します。

| プロジェクト | 何ができるか | 技術スタック |
|---|---|---|
| [S3 Burst on ONTAP Files](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files) | S3 API でデータを収集し、FlexCache の NFS/SMB で利用する。コピージョブなし、反映 p50 8 ms。HiL テストベンチ・EDA・レンダリング・IoT に向く | CFn + SAM。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-s3burst-flexcache-collect-s3-consume-files) |
| [ファイルポータル UI (Amplify Gen2)](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/tree/main/solutions/amplify-portal) | NAS 上のファイルに VPN なしでブラウザアクセス + AI 処理（分類・異常検知・セマンティック検索）。Nextcloud との併用も可能 | Amplify Gen2 + Bedrock。[解説記事](https://hakobiya.hatenablog.com/entry/fsxn-file-portal-1-browser-access) |
| [Lakehouse 連携](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations) | Athena / Glue / Spark から S3 AP 経由でファイルを分析。データは NAS に残したまま | S3 AP + Glue / Athena |
| [Agentic RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) | NAS の権限を反映した RAG。元ファイルの ACL を AI パイプラインに伝播 | CDK + Bedrock |

**「このモジュールのノートを読んだが、具体的なコードが欲しい」場合は上のリポジトリに進んでください。** 各リポジトリは独立して deploy 可能で、この Playbook は判断の根拠を、リポジトリは実装を担います。

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |

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

---

## 関連

- [ライフサイクル軸で探す](../../navigation.md#ライフサイクル軸--playbooks)
- [比較マトリクス](../../reference/comparison/)
- [ナビゲーションガイド](../../navigation.md)
- [用語集](../../reference/glossary/)

---

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/data-utilization/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
