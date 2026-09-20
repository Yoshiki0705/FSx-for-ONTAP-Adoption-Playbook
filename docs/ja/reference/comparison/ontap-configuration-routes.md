---
title: ONTAP 側の設定に届く経路の比較 — どれも「テンプレートの外」であることは変わらない
lifecycle: [build, operate]
domains: [security-governance, multiprotocol-identity]
evidence: verified
verified_on: 2026-08-06
region: ap-northeast-1
ontap_version: 9.17.1P7D1
lang: ja
---

# ONTAP 側の設定に届く経路の比較

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較](README.md) | [Playbook — 04 構築](../../playbooks/04-build/README.md)

---

## 結論

**どの経路を選んでも、その設定はテンプレートの管理外に出ます。** 選択で変わるのは管理外にする方法であって、管理下に戻せるかではありません。

**なので比べる軸は 3 つです。**

| 軸 | 何を意味するか |
|---|---|
| **資格情報をどこに置くか** | `fsxadmin` を使うと、SVM 1 つの担当者にファイルシステム全体の権限を渡すことになります |
| **失敗が見えるか** | テンプレートの成否と切り離れると、失敗が構築ログに出ない経路があります |
| **再実行できるか** | 同じ入力で 2 回流して同じ状態になるか。ならないなら手順書が必要です |

**推奨は置いていません。** 制約は、選びたい側も含めて対称に書いています。

---

## 比較

この表は**経路そのもの**を比較します。設定ごとのネイティブ到達性は次の表で確認します。

| 経路 | 資格情報 | 実行と再実行 | 引き受ける制約 |
|---|---|---|---|
| **ONTAP REST API** | `vsadmin`（SVM 単位）または `fsxadmin` | 呼び出し元で記録。冪等性は実装次第 | 管理エンドポイントへの到達性と実行主体が必要です |
| **ONTAP CLI（SSH）** | 同上 | 対話操作は別途記録。再実行は手順書次第 | REST にない操作や調査に使えますが、自動化と証跡を別に設計します |
| **CloudFormation カスタムリソース / Lambda** | Secrets Manager などから取得 | スタックの成否に統合。スタック更新で再実行 | ONTAP 側は自動でロールバックされません |
| **Systems Manager Automation** | Automation 実行ロールと実行手段側の資格情報 | Runbook の実行履歴を記録。ドキュメント単位で再実行 | 実行ステップに管理エンドポイントへの VPC 到達性が必要です。Lambda または管理対象ノードを介す構成を選びます |
| **Systems Manager Association** | 管理対象ノードのインスタンスプロファイルなど | Association の実行履歴を記録。ドキュメント単位で再実行 | EC2 などの管理対象ノードに適用します。ファイルシステムへ直接設定する仕組みではありません |
| **手作業** | 操作者が使用 | 記録と再実行を手順書で補完 | 環境差と操作漏れを受け入れる必要があります |

### 設定ごとのネイティブ到達性

| 設定 | Amazon FSx API? | ONTAP 層のみ? | 運用上の帰結 |
|---|---|---|---|
| SVM の AD 構成 / ルートセキュリティスタイル | Yes | No | CloudFormation も API 公開面を利用。スタイル変更は Replacement |
| 階層化ポリシー / cooling period | Yes | No | `CreateVolume` / `UpdateVolume` 後に値を読み直します |
| SMB 暗号化強制 | No | Yes | ONTAP の管理資格情報と到達性が必要です |
| inode 上限 | No | Yes | 容量とは別の構成・監視対象です |
| FlexVol から FlexGroup への変換 | No | Yes | 変換前のバックアップ削除と配置確認が必要です |
| ONTAP のオンデマンド Snapshot 作成 | No | Yes | ONTAP の Snapshot ポリシーまたは CLI / REST API を使います |
| SnapLock 監査ログボリュームの指定解除 | No | Yes | ONTAP REST で解除しても、保持中のリソースは削除できません |
| ボリューム削除失敗理由の取得 | Yes | No | `DescribeVolumes.LifecycleTransitionReason` を読みます |

> **Evidence**: AWS 文書へリンクした行は `documented` です。SnapLock 監査ログボリュームの
> 指定解除と、削除失敗時の実際の応答経路は、[IaC の境界](../../playbooks/04-build/notes/what-iac-cannot-reach.md#実測で見つかった境界)に
> 環境を示した `verified` の観測です。このファイルの `verified` frontmatter は、文書化された行を
> 実測へ格上げするものではありません。

**カスタムリソースや自動化は ONTAP 層への呼び出し経路です。** CloudFormation リソースまたは Amazon FSx API のネイティブ到達性を増やしません。実装側が資格情報、到達性、冪等性、失敗時の復旧を引き受けます。

**`vsadmin` を使えるようにするかは、作成時に決まります。** `SvmAdminPassword` を指定しないと、その SVM の管理は `fsxadmin` になります。**`fsxadmin` はファイルシステム全体の管理者**なので、SVM 1 つの運用担当者に全体の権限を渡すことになります（[シークレットの扱い](../../playbooks/04-build/notes/what-iac-cannot-reach.md#シークレットの扱い)）。

**委任された管理者アカウントで実行できない ONTAP 操作もあります。** 許可範囲を確認するときは [fsxadmin の権限と制約](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/fsxadmin-limitations.md) を参照し、実行前に現在の ONTAP CLI / REST API リファレンスと突き合わせます。できない操作の一覧はこちらへ複製しません。

**`FsxAdminPassword` には 8〜50 文字という制約があり、改行や特定の制御文字を含められません。** 自動生成のポリシーがこの範囲を外れていると作成時に失敗します。

---

## 選び方

**設定の性質から入ります。経路から入ると、資格情報の設計が後付けになります。**

| 状況 | 選ぶ経路 | 併せて必要になるもの |
|---|---|---|
| 構築の一部として毎回必ず入れる設定 | **カスタムリソース / Lambda** | **失敗時の扱い。** ONTAP 側はロールバックされません |
| 構築後に 1 回だけ入れる設定 | **ONTAP REST**（実行主体を決める） | 到達性と、再実行したときの冪等性 |
| 調査・一度きりの確認 | **ONTAP CLI** | **記録。** 対話的な操作は残りません |
| EC2 側の設定（ドメイン参加など） | **Systems Manager Association** | ファイルシステム側には効かないという前提 |
| どれも当てはまらない | **手作業を選ぶ前に、環境差を許容できるかを決める** | 複製した環境が一致しない前提での運用 |

**どの経路でも、判定は「読み直して意図した値になっているか」です。** AWS API 側は成功応答が反映を意味しません（[成功応答を成功と読めない 3 つの操作](../decision-trees/where-a-setting-is-created.md#成功応答を成功と読めない-3-つの操作)）。

---

## この比較が答えないこと

| 問い | どこにあるか |
|---|---|
| どの設定がそもそも ONTAP 側なのか | [この設定はどこから作るか](../decision-trees/where-a-setting-is-created.md) |
| 管理者権限をどう分けるか | [管理者を分ける](../../domains/security-governance/notes/what-the-platform-gives-and-what-stays-yours.md#権限設計--管理者の分離) |
| 管理者権限を渡さずに操作させる形 | [責務の分割](../../domains/security-governance/notes/self-service-without-storage-admin.md#責務の分割) |

**経路ごとの性能や所要時間は測っていません。** ここにあるのは、資格情報・失敗の見え方・再実行の 3 軸だけです。

---

## 関連ドキュメント

- [IaC の境界は API の表面で決まる](../../playbooks/04-build/notes/what-iac-cannot-reach.md)
- [本番投入前レビュー](../../playbooks/04-build/checklists/pre-production-review.md)
