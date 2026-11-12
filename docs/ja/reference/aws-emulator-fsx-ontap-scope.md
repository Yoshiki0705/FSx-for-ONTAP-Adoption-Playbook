---
title: AWS Emulator で FSx for ONTAP を試せる範囲は、ファイルシステムの作成・更新までで、SVM・ボリューム・S3 Access Points と ONTAP の中身は対象外
lifecycle: [design, build]
domains: [client-access, data-utilization]
evidence: field-observation
source: https://aws.amazon.com/jp/blogs/aws/test-your-applications-against-aws-locally-with-aws-emulator/
lang: ja
---

# AWS Emulator と FSx for ONTAP の接点

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**AWS Emulator は、Amazon FSx for NetApp ONTAP のファイルシステムを作成・更新・参照する AWS API の呼び出しを、アカウントなしでローカルでテストするために使えます。ONTAP の中身は扱えません。** 2026-11-12 に公開リポジトリの v1.0.322 を実行して確認した範囲では、次のとおりです。

| 試したいこと | 結果 |
|---|---|
| ファイルシステムの作成・更新・参照、タグ、存在しない ID のエラー | 動く。作成は数秒で `AVAILABLE` になる |
| CloudFormation でファイルシステムだけを作る | 動く |
| SVM、ボリューム、スナップショットの作成と参照 | 未実装。HTTP 501 |
| FSx for ONTAP S3 Access Points の作成と参照 | 未実装。HTTP 501 |
| CloudFormation の `AWS::FSx::StorageVirtualMachine`、`AWS::FSx::Volume` | リソース型を認識せず、スタック作成の前に拒否される |
| ONTAP REST API、NFS、SMB、iSCSI、SnapMirror、SnapLock | 対象外。エミュレータは AWS の API エンドポイントだけを提供する |
| IAM ポリシーの評価 | しない（公式の記載）。S3 Access Points の二層認可は試せない |

**この文書の確認結果は 1 つの環境で 1 回だけ観測したもので、再現していません。** リリース番号がすでに v1.0.322 に達しており、更新の頻度は高いと見られます。表の「未実装」は、この日付とバージョンの断面です。

---

## 区分と測定条件

| 項目 | 内容 |
|---|---|
| 区分 | `field-observation`。実行した結果は 1 回の観測。公式の仕様と忠実度スコアの数値は、文書とリリース添付ファイルからの転記 |
| 対象 | `aws/aws-emulator` v1.0.322（commit `7753983`）。リリース日 2026-11-11 |
| 実行環境 | macOS（arm64）、Docker 29.5.3、aarch64 版 RPM から Amazon Linux 2023 の最小イメージにインストール。AWS CLI 2.38.3 |
| 設定 | リージョン設定 `us-east-1`、エミュレータ固有のダミーアカウント（全桁 0）、`--telemetry off` |
| 実行日 | 2026-11-12 |
| 実際の AWS との比較 | していない。ここでの「動く」は、エミュレータが成功を返したことを指し、実際の AWS と同じ結果であることは示さない |

実行時の応答の抜粋と実行手順は、非公開の記録にだけ保存しています。

---

## 確認した範囲

### 動いた操作

- `create-file-system`（`FileSystemType=ONTAP`、`MULTI_AZ_1`、`HAPairs=1`）は成功し、`Lifecycle` が `CREATING` で返りました。数秒後の `describe-file-systems` では `AVAILABLE` でした。
- `update-file-system` でスループットを変えると、`UPDATING` が返りました。
- `list-tags-for-resource`、`describe-backups` は成功しました。存在しないファイルシステム ID の `describe-file-systems` は、`FileSystemNotFound` とその ID を含むメッセージを返しました。
- 作成時に渡すサブネットは、先にエミュレータの EC2 で作ったものが必要でした。ID は `vpc-0000…` のような合成値です。
- `AWS::FSx::FileSystem`（ONTAP）だけを含む CloudFormation テンプレートは、`CREATE_COMPLETE` になりました。

### 動かなかった操作

- `create-storage-virtual-machine`、`describe-storage-virtual-machines`、`create-volume`、`create-snapshot`、`create-and-attach-s3-access-point`、`describe-s3-access-point-attachments` は、`NotImplemented`（HTTP 501）を返しました。メッセージは「scaffolded but not implemented」でした。
- `AWS::FSx::StorageVirtualMachine` と `AWS::FSx::Volume` を含むテンプレートは、`Unrecognized resource types` の `ValidationError` で、スタックが作られる前に拒否されました。
- `describe-file-systems` の結果に、ONTAP の管理エンドポイント（`Endpoints.Management`）が入っていませんでした。ONTAP REST の接続先を取り出す処理は、このままでは試せません。
- `s3control create-access-point` は、アカウント ID を付けたホスト名への接続に失敗しました。エミュレータ側かクライアント側の設定かは切り分けていません。

### 公開リポジトリの実装状況との一致

ソースを読むと、`fsx` サービスの crate（FSx for ONTAP 以外のファイルシステム種別も含む）は 48 操作のうち 33 が未実装（ファイル先頭に `SCAFFOLDED, NOT IMPLEMENTED` の印）、15 が実装でした。上の動かなかった操作は、すべて未実装側に入っています。`describe-volumes` は実装側にあり、空の一覧を返しました。

---

## 公式が示す仕様と制限

出典は [AWS の発表](https://aws.amazon.com/about-aws/whats-new/2026/11/aws-emulator-now-available/)、[AWS News Blog](https://aws.amazon.com/jp/blogs/aws/test-your-applications-against-aws-locally-with-aws-emulator/)、[リポジトリの README](https://github.com/aws/aws-emulator) です。

| 項目 | 公式の記載 |
|---|---|
| 提供形態 | Linux は RPM と Debian パッケージ。macOS と Windows は、短い Dockerfile から自分でイメージを作る。ビルド済みイメージは公開されていない |
| 費用とライセンス | 追加のサービス料金なし。ソースは CC0 1.0 |
| 状態 | メモリ上のみ。停止すると消える |
| アカウントとリージョン | 1 アカウント。クロスアカウント、クロスリージョンの動作はない |
| 署名 | SigV4 を必須とし、エミュレータが起動ごとに作る認証情報以外は拒否する |
| IAM | IAM ポリシーとリソースベースポリシーを AWS と同じようには評価しない。AWS が拒否する要求が通ることがある。セキュリティのテストに使わないよう明記されている |
| 未実装の操作 | HTTP 501 を返す |
| テレメトリ | 既定で有効。`--telemetry off` か環境変数で止められる |
| 忠実度の測り方 | 実際の AWS で検証したテストを、応答（ステータス、本文、エラーコードとメッセージ）と作られるリソースまで照合する。サービスごとの合格数をリリースに添付する |

### 忠実度スコアの転記

v1.0.322 に添付された `scores.json.gz` を集計した数値です。転記であり、このリポジトリでは再測定していません。数字はテスト数の増減で下がることがあると公式が述べています。

| 対象 | 合格 | 不合格 | スキップ |
|---|---|---|---|
| 全体（42,937 件） | 24,243 | 18,614 | 80 |
| `fsx` サービス（16 件） | 5 | 11 | 0 |
| S3（2,814 件） | 1,763 | 1,035 | 16 |
| S3 Control（77 件） | 37 | 40 | 0 |
| DataSync（29 件） | 4 | 25 | 0 |

`fsx` の不合格の主因は、上で確認した未実装の操作（501）です。合格は、ファイルシステム作成時の検証、タグ、バックアップからの復元、ストレージ容量の更新下限、データリポジトリ関連付けの検証でした。

---

## 使い道の想定

この節は**仮説**で、未検証です。

- **FSx for ONTAP を操作するコードのテスト**: ファイルシステムの作成を呼び、状態が `AVAILABLE` になるのを待つ処理や、更新の遷移を待つ処理を、ローカルと CI で繰り返し動かせる可能性があります。
- **エラー処理のテスト**: 存在しない ID のエラー形式が実際の AWS と一致するかは、スコアの対象テストで確認されています。この系統の異常系のテストを書きやすい可能性があります。
- **コーディングエージェントの試行錯誤**: デプロイなしで AWS API を試せるため、FSx for ONTAP を含むスクリプトの下書きを検証させる使い方が考えられます。ただし SVM とボリュームは 501 になるため、そこから先は実際の AWS で確認します。
- **S3 側のテスト**: FSx for ONTAP S3 Access Points を使うアプリケーションの S3 呼び出し部分を、通常のバケットに差し替えてテストする使い方が考えられます。差し替えで挙動が保たれるかは確認していません。

---

## 向かない用途

- ONTAP の中身（ボリューム、qtree、スナップショットポリシー、SnapMirror、SnapLock、ARP、FlexCache）の確認。エミュレータの対象は AWS の API で、ONTAP は動いていません。
- SVM と Active Directory の連携、SMB と NFS のアクセス確認、iSCSI の接続確認。
- IAM、リソースポリシー、S3 Access Points の二層認可の確認。公式が評価しないと述べています。
- 性能、コスト、可用性の見積り。メモリ上のエミュレーションで、実機の特性は何も表しません。
- 本番前の最終確認。公式も、セキュリティ設定とアプリケーション全体は AWS 上で確認するよう述べています。

---

## 使うかどうかの判断

| 確かめたいこと | 向く場所 |
|---|---|
| FSx for ONTAP の作成・更新を呼ぶコードの分岐と状態待ち | AWS Emulator |
| SVM・ボリュームを作る IaC やスクリプト | 実際の AWS。エミュレータでは 501 か、テンプレートの時点で拒否される |
| ONTAP の設定や挙動 | 実際の FSx for ONTAP |
| 認可の挙動 | 実際の AWS |

AWS Emulator 側の制約は表のとおりです。実際の AWS 側の制約は、課金と作成に時間がかかり、繰り返しの実行には向かないことです。

---

## よくある誤解

- **「AWS 全体がローカルで動くので、FSx for ONTAP のデモ環境もローカルにできる」**: ファイルシステムの作成呼び出しは動きますが、作られるのは API 上の記録だけです。マウントできる ONTAP は起動しません。
- **「サービス数が多いので、FSx for ONTAP の主要な操作は動く」**: サービスの数と、そのサービスの操作の実装率は別です。`fsx` サービスは 48 操作中 15 でした。
- **「テストがエミュレータで通れば、AWS でも通る」**: 公式が、動作の一致度はサービスと機能によって異なると述べています。この文書の「動いた」は、実際の AWS との比較をしていません。

---

## 自環境での再確認手順

1. 公式の [Getting started with Docker](https://docs.aws.amazon.com/emulator/latest/userguide/getting-started-docker.html) のとおりイメージを作り、`--telemetry off` を付けて起動します。
2. 手元の AWS CLI を、起動時に書き出される設定ファイルとエンドポイントに向けます。実際の AWS の認証情報の環境変数は外します。
3. 試したい FSx for ONTAP の操作を 1 つずつ実行し、`NotImplemented` が返るかを見ます。
4. 実装の状況は、リポジトリで `grep -rl '^//! SCAFFOLDED, NOT IMPLEMENTED:' services/service-com-amazonaws-fsx-*/src/ops/` を実行して数えます。`fsx` サービスの忠実度は、使うリリースに添付された `scores.json.gz` から取ります。
5. 後片付けでは、コンテナを止め、`~/.aws/emulator` を削除します。

---

## 関連文書

- [Reference の一覧](README.md)
- [知見の分類ポリシー](../evidence-policy.md)
- [FSx for ONTAP の適合条件](fsx-ontap-fit-conditions.md)
- [ONTAP のコマンド・REST API・権限の入口](ontap-commands-and-apis.md)

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
