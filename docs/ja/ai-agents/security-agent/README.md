# AWS Security Agent はアプリを検証し、FSx for ONTAP の設定は検証しない

> アプリのセキュリティを検証するエージェント。FSx for ONTAP との接点は **アプリ経由**だけで、ストレージの管理面（S3 Access Points のポリシー、SVM の権限、監査）は対象外。

[🏠 リポジトリトップ](../../../../README.md)

---

AWS Security Agent（現在は AWS Continuum の一部）を Amazon FSx for NetApp ONTAP 運用に重ねられるかを扱います。**結論から言うと、ストレージ運用には直接使えません。** このエージェントが検証するのはアプリケーション（設計文書・ソースコード・実行中のアプリ）で、FSx for ONTAP の管理面（ストレージ設定・権限）は見ません。**このページの主眼は、何を検証し何を検証しないかの境界を示すことです。**

**提供状態は機能ごとに異なります（2026-11-04 確認）。** 侵入テストとコード脆弱性は GA、コードスキャン・脅威モデリング・設計レビューは Preview です。内訳は [Security Agent とは](#security-agent-とはdocumented)の表にあります。

---

## このページの但し書き

| 内容 | 確度 |
|---|---|
| Security Agent の用途・対象・提供状態 | AWS 公式ドキュメントに出典（本ページ末尾）。`documented` 相当 |
| FSx for ONTAP との接点の判断 | **未検証。** 著者が Security Agent を FSx for ONTAP を使うアプリに対して動かして得た結果ではありません |

---

## Security Agent とは（documented）

AWS Security Agent は、**開発ライフサイクル全体のアプリケーションセキュリティ**を対象とするエージェントです。2026-06-17 に AWS Continuum へ統合され、機能名は「Continuum for 〜」に変わりました。用途と提供状態は次のとおりです。

| 用途（Continuum での名称） | 対象 | 提供状態（2026-11-04 確認） |
|---|---|---|
| オンデマンド侵入テスト（Continuum for penetration testing） | 実行中アプリの URL・認証情報・ソースコード。多段の攻撃シナリオで脆弱性を検証する | GA |
| コード脆弱性（Continuum for code vulnerabilities） | GitHub または S3 のコードと AWS 環境の情報。悪用可能かを隔離環境で確かめ、修正の PR を作る。発表時の限定プレビューから 2026-10-22 に GA。US East (N. Virginia) と US West (Oregon) で提供 | GA |
| コードセキュリティレビュー（Continuum code scanning） | GitHub / GitLab / Bitbucket / S3 buckets のソースコード。脆弱性を検出し修正の PR を作る | Preview |
| 脅威モデリング（Continuum for threat modeling） | 設計文書・ソースコード。STRIDE 分類で脅威を洗い出す | Preview |
| 設計セキュリティレビュー（Continuum for design security review） | 設計文書。コードを書く前の段階でセキュリティ要件との整合を評価する | Preview |

**状態の出典は発表記事で、ユーザーガイドの機能ページには提供状態の記載がありません。** 侵入テストの GA は 2026-06 の AWS News Blog と 2026-09-30 の What's New（6 リージョン追加）、コード脆弱性の GA は 2026-10-22 の What's New、Preview の 3 機能は 2026-06-17 前後の What's New と AWS News Blog に基づきます。2026-11-04 に What's New と AWS のブログを検索し、Preview の 3 機能について GA を告げる発表は見つかりませんでした。これは「発表されていない」ことの証明ではないので、採用前に Security Agent のコンソールで確認してください。

**侵入テスト・コードスキャン・脅威モデリング・設計レビューの対象は、いずれもアプリケーション層です**（設計文書、ソースコード、実行中のアプリ）。ストレージの管理面設定を評価する用途ではありません。コード脆弱性だけは、AWS 環境の情報（AWS Config のリソース、ネットワーク構成）を集めて到達可能性の判断に使います。その情報に FSx for ONTAP の設定が含まれるか、含まれた場合に評価の対象になるかは確認していません。

---

## FSx for ONTAP の管理面は見ない（適合判断・未検証）

**Security Agent は、FSx for ONTAP のストレージ管理面を評価しません。** 次のような FSx for ONTAP 側の設定は、このエージェントの対象外です。

| FSx for ONTAP 側の設定 | Security Agent が見るか |
|---|---|
| S3 Access Points のポリシー・公開範囲 | **見ない**（ストレージの管理面設定であり、アプリのコード・設計・実行ではない） |
| SVM の権限設計、AD 参加、name-mapping | **見ない** |
| ボリュームのファイル権限、監査設定 | **見ない** |
| SnapLock などの保護設定 | **見ない** |

**これらのストレージ側のガバナンスは、Security Agent とは別に設計・運用します。** 権限設計や監査の知見は [Domain — セキュリティ・ガバナンス](../../domains/security-governance/) にあります。**Security Agent がこれらを肩代わりするわけではありません。**

---

## 唯一の接点 — データソースに使うアプリのコード（適合判断・未検証）

**接点は 1 つだけあります。** FSx for ONTAP をデータソースに使うアプリのソースコードを Security Agent がレビューする場合です。このとき見えるのは**アプリのコードに現れる範囲**で、ストレージ側の設定そのものではありません。

| 現れる場所 | Security Agent が見られる範囲（未検証） |
|---|---|
| アプリコード中の S3 Access Points アクセス（IAM の使い方、認証情報の扱い） | コードレビューの対象に入りうる。認証情報のハードコードや過剰な権限要求はコードの問題として現れる |
| アプリの設計文書に書かれたデータフロー | 脅威モデリングの入力になりうる。データソースとしての FSx for ONTAP がアプリのどの信頼境界に接するかを記述していれば、その範囲で評価される |

**ただし、ここで見えるのはアプリコード側の表現であって、S3 Access Points の権限境界の正しさそのものではありません。** S3 Access Points の認可は 2 層（AWS 側の IAM 認可とファイルシステム側の権限）で決まり、その評価はストレージ側の設定に属します。この 2 層の仕組みは [S3 Access Point の権限設計](../../domains/security-governance/notes/access-point-authorization-layers.md) にあります。**Security Agent はこの 2 層を評価しません。** アプリコードが S3 Access Points をどう呼ぶかは見えても、S3 Access Points が誰に何を許すかは、ストレージ側で設計・検証します。

> **役割分担に関する補足**: 「アプリのセキュリティ検証」と「ストレージのガバナンス」は別の責務です。Security Agent はアプリ層を継続検証しますが、S3 Access Points の公開範囲・権限境界・監査は FSx for ONTAP 側で設計します。単一 ID 認可により元の ACL が引き継がれない性質（[全リクエストを 1 つの ID で認可する](../../domains/data-utilization/notes/reaching-data-without-copies.md)）も、ストレージ側の設計判断であり、Security Agent の対象ではありません。**両者を混同すると、どちらかに穴が残ります。**

---

## フェーズごとの使いどころ（適合判断・未検証）

**この節は著者の判断で、実測ではありません。**

| フェーズ | 何ができるか | 根拠（未検証） |
|---|---|---|
| 構築（04-build） | FSx for ONTAP を使うアプリのコードレビュー・脅威モデリングに使える | ストレージ構築そのものは対象外 |
| 運用（05-operate） | アプリの継続的なセキュリティ検証に使える | FSx for ONTAP の運用監視とは別 |
| 設計・評価（01-assess / 02-design） | アプリの設計セキュリティレビューに使える | FSx for ONTAP のストレージ設計とは別 |

**いずれもアプリに対する検証です。** FSx for ONTAP のストレージ運用そのものを Security Agent が改善するわけではありません。ストレージ側の検証は別に用意する前提で導入を判断してください。

侵入テストにどのデータを触らせるか、テスト中にストレージ層のどの検知が反応するか、自動修復の段階を上げるときの戻り先は、ストレージ側の決定木として Spoke にまとめています。内容は [Continuum と Security Agent の時代にストレージ層で決めておくこと](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/architecture/continuum-security-agent-and-storage.md)にあります（Spoke、未デプロイ）。

---

## 参考資料（一次情報）

- [What is AWS Security Agent (now part of AWS Continuum)（AWS 公式ドキュメント）](https://docs.aws.amazon.com/securityagent/latest/userguide/what-is.html) — 用途（設計レビュー / 脅威モデリング / コードレビュー / 侵入テスト）、対象、マルチクラウド対応
- [AWS Security Agent on-demand penetration testing GA 告知](https://aws.amazon.com/about-aws/whats-new/2026/03/aws-security-agent-ondemand-penetration/) — オンデマンド侵入テストの提供
- [Introducing AWS Continuum for security at machine speed（What's New、2026-06）](https://aws.amazon.com/about-aws/whats-new/2026/06/aws-continuum/) — Continuum 統合。侵入テストとコードスキャンの改称、コードスキャンと脅威モデリングが Preview
- [AWS Security Agent adds threat modeling, Kiro power and Claude Code plugin, and more（AWS News Blog）](https://aws.amazon.com/blogs/aws/aws-security-agent-adds-threat-modeling-kiro-power-and-claude-code-plugin-and-more) — 設計レビューと脅威モデリングが Preview、侵入テストが GA と記載
- [AWS Continuum for Penetration Testing now available in 6 additional Regions（What's New、2026-09-30）](https://aws.amazon.com/about-aws/whats-new/2026/09/aws-continuum-penetration/) — 侵入テストのリージョン追加
- [AWS Continuum for code vulnerabilities is now generally available（What's New、2026-10）](https://aws.amazon.com/about-aws/whats-new/2026/10/aws-continuum-for-code-vulnerabilities-is-now-generally-available/) — コード脆弱性の GA

---

## 関連

- [AI エージェントのジャンル入口](../README.md)
- [Domain — セキュリティ・ガバナンス](../../domains/security-governance/) — FSx for ONTAP 側の権限設計・監査（Security Agent の対象外の領域）
- [S3 Access Point の権限設計 — 2 層の評価](../../domains/security-governance/notes/access-point-authorization-layers.md) — Security Agent が評価しないストレージ側の認可
- [S3 Access Points は全リクエストを 1 つの ID で認可する](../../domains/data-utilization/notes/reaching-data-without-copies.md) — ストレージ側の設計判断
- [Continuum と Security Agent の時代にストレージ層で決めておくこと](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/architecture/continuum-security-agent-and-storage.md) — 侵入テストに触らせるデータ、テスト中に反応するストレージ層の検知、自動修復の段階を上げるときの戻り先の 3 つの決定木。FlexClone による隔離手順と CloudFormation テンプレートを含む（Spoke、未デプロイ）

---

[🏠 リポジトリトップ](../../../../README.md)
