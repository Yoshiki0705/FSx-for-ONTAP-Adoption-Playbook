---
title: Windows ファイルサーバーのデータを Amazon Quick で扱う 90 分版 — 成立するが、AD は当日に作れない
lifecycle: [assess, design, build]
domains: [data-utilization, multiprotocol-identity]
evidence: hypothesis
lang: ja
---

# Windows ファイルサーバーのデータを Amazon Quick で扱う 90 分版

[🏠 リポジトリトップ](../../../../README.md) | [Workshop Studio](../README.md)

[EDA ログ版](../eda-s3-access-points-90min/)の題材を、NFS の EDA ログから
**SMB の Windows ファイルサーバー相当のデータ**に差し替えた構成です。

> **このタイムテーブルは未検証です。** 個々の要素は[実測](#実測した数値)しましたが、
> 90 分を通しでリハーサルした結果ではありません。初回開催前に一度通してください。

## 結論を先に

**技術的には成立します。検証済みです。** ただし前提が 1 つ重く、当日には作れません。

1. **SMB で書いたデータは、Windows ID の S3 Access Point 経由で S3 API から読めます。**
   NTFS セキュリティスタイルのボリュームで、AD 参加済みの SVM でも動作を確認しました。
2. **Active Directory は当日に作れません。** AWS Managed Microsoft AD の作成は 15〜30 分かかり、
   これに SVM の AD 参加、SMB 共有、ドメイン参加した Windows クライアントが加わります。
   **開催前に用意する前提**でなければ 90 分に入りません。
3. **本家ワークショップの手順はほぼ使えません。** 本家のデータ生成は NFS 前提、
   アクセスポイントは UNIX ID 前提で、SMB と AD のモジュールは存在しません。
   これは「本家を実施する」ではなく「本家を題材にした別構成」になります。

## 題材として EDA ログと比べたときの違い

どちらが優れているという話ではなく、聞き手と準備コストで選ぶものです。

| 観点 | EDA ログ版（NFS） | Windows ファイルサーバー版（SMB） |
|---|---|---|
| 事前準備 | 少ない。NFS マウントとスクリプトだけ | **重い。AD・SMB 共有・ドメイン参加クライアントが必要** |
| 本家手順の流用 | ほぼそのまま使える | ほぼ使えない。自作が必要 |
| 聞き手の共感 | 半導体設計に馴染みがないと遠い | **多くの参加者が自社にある構成** |
| Quick との相性 | ログはテキストとして索引される | **Office 文書は Quick の本来の対象** |
| 当日の failure mode | 少ない | **AD 到達性が全データ操作の前提になる** |
| 権限の説明 | UNIX パーミッション | **NTFS ACL と S3 AP の認可の対比が示せる** |

**選び方**: 準備に時間を割けるなら SMB 版、当日の確実性を優先するなら EDA ログ版です。
Storage-JAWS の参加者層を考えると SMB 版の題材は刺さりますが、
初回はEDA ログ版で運営を固め、2 回目に SMB 版へ移す進め方が安全です。

## 90 分タイムテーブル

事前準備（下記）が完了している前提です。

| 経過 | 分 | 内容 | 種別 |
|---|---|---|---|
| 00:00 | 10 | 導入。ファイルサーバーのデータが分析に使えていない話とゼロコピーの考え方 | 説明 |
| 00:10 | 8 | Windows クライアントから SMB 共有へ文書を投入（部門フォルダー構成） | 実習 |
| 00:18 | 12 | Windows ID の S3 AP を作成し、SMB で書いた文書が S3 API で見えることを確認 | 実習 |
| 00:30 | 12 | Amazon Quick セットアップ。**この枠の終わりで同期を開始する** | 実習 |
| 00:42 | 8 | NTFS ACL と S3 AP の認可モデルの対比（同期待ち） | 説明 |
| 00:50 | 10 | Athena で集計 CSV を SQL 参照（同期待ち） | 実習 |
| 01:00 | 5 | 予備・質疑。同期の余裕を吸収する枠 | 説明 |
| 01:05 | 17 | Quick に文書の内容を自然言語で質問 | 実習 |
| 01:22 | 8 | まとめ。撤収手順の案内 | 説明 |

同期には **23 分の猶予**があります（00:42 開始 → 01:05 に質問開始）。
実測 11.5〜14.1 分に対して倍近い余裕です。

### AgentCore の実演を入れる場合

Athena の 10 分を[AgentCore の実演（形態 C）](../eda-s3-access-points-90min/measured-timings.md#3-つの実施形態と見積もり)
8〜10 分と入れ替えます。ゲートウェイは開催前に構築しておく必要があります。
Athena を外すと「同じデータが SQL からも読める」話と、AI の回答を突き合わせる場面が無くなります。

## 事前準備（当日の 90 分に含めない）

上 4 つは当日には作れません。**ここが EDA ログ版との最大の差**です。

| 作業 | 目安 | 理由 |
|---|---|---|
| Active Directory の用意 | 15〜30 分 | 作成そのものに時間がかかります |
| SVM の AD 参加 | 2〜5 分 | 失敗時は `MISCONFIGURED` からの再試行が必要 |
| NTFS ボリュームと SMB 共有の作成 | 5 分 | |
| ドメイン参加した Windows クライアント | 5〜10 分 | 参加者が文書を置くために必要 |
| Quick のサインアップと S3 有効化 | 15 分 | [EDA ログ版と同じ落とし穴](../eda-s3-access-points-90min/facilitation-risks.md#amazon-quick-は-iam-だけでは-s3-に届かない)があります |
| 集計 CSV の準備 | 5 分 | Athena を残す場合のみ |

### SVM に既存の ONTAP S3 サーバーがあると作成できない

**事前に必ず確認してください。** 検証中、AD 参加済みの SVM でアクセスポイント作成が
37 秒後に `FAILED` になりました。

返ってきた `LifecycleTransitionReason` は次のとおりです（検索できるよう原文のまま載せます）。

> `Amazon FSx is unable to create an S3 access point because of an existing ONTAP object storage server on SVM svm-xxxxxxxx. Please delete the existing s3 server and retry.` <!-- allow:naming -->

手動で構成した ONTAP の S3 オブジェクトストレージサーバーと、FSx for ONTAP が管理する
S3 アクセスポイントは **同じ SVM 上で共存できません。**
使い回しの検証環境では踏みやすく、当日に気づくと回復できません。
別の SVM を使うか、既存の S3 サーバーを削除しておきます。

## 実測した数値

測定条件は[EDA ログ版の測定条件](../eda-s3-access-points-90min/measured-timings.md#測定条件)と同じ環境です。
SMB 側は AD 参加 SVM の NTFS ボリューム、クライアントはドメイン参加した Windows Server 2025 です。

| 操作 | 実測 | 備考 |
|---|---|---|
| SMB で 23 ファイル書き込み（.docx 7 / .csv 6 / .html 6 / .txt 3 / .md 1、14.8 KiB） | **1.68 秒** | 部門フォルダー 6 個を含む |
| Windows ID の S3 AP 作成 → `AVAILABLE` | **33.9 秒** | UNIX ID の 14.3 秒より遅い |
| `HeadBucket` | 0.8 秒 | メタデータのみ |
| `ListObjectsV2`（データ操作） | 1.20 秒 | SMB で書いた文書が列挙される |
| `GetObject`（文書 1 件） | 1.20〜1.45 秒 | |

**Windows ID の作成が UNIX ID の 2 倍以上かかります。** CIFS と AD による ID 解決が
入るためと考えられますが、原因は未検証です。いずれも 1 分以内なので構成上の問題にはなりません。

## 未検証の点

| 項目 | 状態 |
|---|---|
| 実物の Office 文書を Quick が解析できるか | **未検証**。読み出せた `.xlsx` は過去検証のプレースホルダー（47 バイト）で、実体は Office 文書ではありませんでした。Quick の S3 統合は「文書・プレゼンテーション・スプレッドシート」を対象と明示していますが、この環境では確認できていません |
| 生成した実文書での通し確認 | **未検証**。実物の `.docx` を作った共有は、上記の ONTAP S3 サーバー競合がある SVM 上にあり、アクセスポイントを作れませんでした |
| 90 分の通し | **未検証** |
| NTFS ACL が S3 API 側の認可に与える影響 | **未検証**。アクセスポイントは単一の Windows ID で全リクエストを認可するため、元の ACL は引き継がれないと考えられます（[関連](../../domains/data-utilization/notes/reaching-data-without-copies.md)） |

## 関連

| ドキュメント | 内容 |
|---|---|
| [EDA ログ版 90 分シナリオ](../eda-s3-access-points-90min/) | NFS 版。本家手順をそのまま使える構成 |
| [セキュリティスタイルと権限評価](../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) | NTFS / UNIX / MIXED の違いが権限評価モデルを決める |
| [AD への依存は生涯続く](../../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md) | SMB を選ぶと AD が恒久的な依存になる |
| [S3 Access Point の認可モデル](../../domains/data-utilization/notes/reaching-data-without-copies.md) | 1 つの ID で全リクエストを認可する構造 |
