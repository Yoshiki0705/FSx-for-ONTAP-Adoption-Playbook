---
title: サイバーレジリエンス機能マップ — どの Spoke が NIST CSF 2.0 のどの機能を担うかの 1 枚
lifecycle: [assess, design]
domains: [security-governance, data-protection, observability]
evidence: documented
source: https://www.nist.gov/cyberframework
lang: ja
---
# サイバーレジリエンス機能マップ

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

このページは、エンドツーエンドのサイバーレジリエンシーを 1 枚で見るための索引です。NIST CSF 2.0 の 6 機能（Govern / Identify / Protect / Detect / Respond / Recover）それぞれについて、どの sibling リポジトリ（Spoke）が持ち場を担うかを示し、詳細はその Spoke のドキュメントへ送ります。

各 Spoke には機能の中の自分の持ち場だけを割り当てます。1 つの Spoke に鎖全体を持たせません。これは、同じ内容を 2 か所に書くと片方だけが更新されて古い側が残る、という問題を避けるためです。

このページは知見を持ちません。各セルは Spoke のドキュメントへのリンクで、実装の詳細・測定値・版はリンク先にだけあります。

> **区分**: `documented` — 各リンク先のドキュメントの所在を記載しています。CSF 2.0 の機能定義は [NIST Cybersecurity Framework 2.0](https://www.nist.gov/cyberframework) に基づきます。このマップに行があることは、その機能が FSx for ONTAP で検証済みであることを意味しません。検証状況は各リンク先の区分を読んでください。

---

## この地図の読み方

Spoke は 3 つあり、持ち場が機能ごとに分かれています。

- サイバーレジリエンスの実装パターン（以降「cyber リポジトリ」）— ストレージネイティブの保護、インラインスキャン、イベント駆動の対応、復旧の選択肢
- Observability 連携（以降「observability リポジトリ」）— ONTAP イベントの取り込み、ダッシュボード、SIEM 連携、検証済み復旧ポイント
- Amplify ベースのファイルポータル（以降「ポータル」）— Cognito 認証画面からの S3 Access Points 経由アクセスと、人の承認を挟んだ操作

Hub（このリポジトリ）は実装を持たず、機能と Spoke の対応だけを置きます。Govern は組織の責任で、どの Spoke も証跡アーティファクトを供給するだけです。

---

## NIST CSF 2.0 と Spoke の対応

機能ごとに、どの Spoke が持ち場を担うかを 1 行で示します。詳細はリンク先にあります。

| CSF 2.0 機能 | cyber リポジトリ | observability リポジトリ | ポータル | Hub の持ち場 |
|---|---|---|---|---|
| Govern (GV) | 証跡アーティファクトの供給 | 証跡アーティファクトの供給 | 証跡アーティファクトの供給 | 組織の責任（どの Spoke も実装は持たない） |
| Identify (ID) | `DataClassification` タグ | コンテンツ / PII 分類 | — | 機能と Spoke の対応 |
| Protect (PR) | SnapLock、Tamperproof Snapshot、MAV、インラインスキャン、論理エアギャップボールト（文書のみ） | — | S3 Access Points の 2 層ポリシー | 機能と Spoke の対応 |
| Detect (DE) | ARP / FPolicy | EMS / FPolicy パイプライン、SIEM の ML | — | 機能と Spoke の対応 |
| Respond (RS) | Step Functions による承認ベースの隔離 | Lambda 直接ブロック | — | 機能と Spoke の対応 |
| Recover (RC) | 論理エアギャップボールトの復旧アカウントからのリストア（Option D） | 検証済みクリーン復旧ポイントの事前選別 | 承認を挟んだリストアの起票 | 機能と Spoke の対応 |

Detect の ARP / FPolicy は cyber リポジトリと observability リポジトリの両方に現れます。cyber リポジトリが検知の設定を持ち、observability リポジトリが取り込みと SIEM への連携を持ちます。表の 1 セルに両方を書かず、持ち場で分けています。

---

## 機能別の持ち場

### Govern (GV)

組織の責任です。リスク戦略・役割・監督は組織が決めます。どの Spoke も実装は持たず、監査証跡やコンプライアンス証跡などの証跡アーティファクトを供給するだけです。

### Identify (ID)

observability リポジトリがコンテンツ / PII の分類を担い、cyber リポジトリがボリュームの `DataClassification` タグを担います。Office / PDF の抽出は observability リポジトリの現状のスコープ外です。

### Protect (PR)

cyber リポジトリが SnapLock、Tamperproof Snapshot、MAV、インラインスキャン、論理エアギャップボールト（文書のみ）を担います。ポータルは S3 Access Points の 2 層ポリシー（IAM アクセスポイントポリシーとファイルシステムのユーザー）を担います。これらが保護するのは復旧点とファイルの可用性・完全性で、認可された読み取りによる持ち出しは別の機能で扱います。

### Detect (DE)

ARP / FPolicy は cyber リポジトリと observability リポジトリの両方に関わります。cyber リポジトリが ARP / FPolicy の検知設定を持ち、observability リポジトリが EMS / FPolicy パイプラインと SIEM の ML を持ちます。FPolicy は NFS / SMB のみに関わります。

### Respond (RS)

cyber リポジトリが Step Functions による承認ベースの隔離を担い、observability リポジトリが Lambda 直接ブロックを担います。検知元を問わず起点にできます。

### Recover (RC)

cyber リポジトリが論理エアギャップボールトの復旧アカウントからのリストア（Option D）を担い、observability リポジトリが検証済みクリーン復旧ポイントの事前選別を担い、ポータルが承認を挟んだリストアの起票を担います。

---

## 詳細の参照先

機能別の実装の詳細は、以下に置かれています。このページでは繰り返しません。

- 機能ごとの詳細な対応は、cyber リポジトリの単一のマッピング（[docs/ja/cyber-resilience-framework-mapping.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ja/cyber-resilience-framework-mapping.md)）にあります。暗号化・破壊型と持ち出し型のシナリオ別対応、管理面の侵害、証跡の種別を含みます。
- 6 機能すべての実装レベルの詳細は、observability リポジトリの既存の機能マップ（[docs/ja/cyber-resilience-capability-map.md](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/blob/main/docs/ja/cyber-resilience-capability-map.md)）にあります。このページはそこを指すだけで、内容は写しません。

---

## 論理エアギャップボールトの扱い

論理エアギャップボールトは、上の表では Protect（文書のみ）と Recover（Option D のリストア）に現れます。このボールトを隔離方式の 1 つとしてデータ保護ドメインに追加する作業は、別の Issue（[#316](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/316)）で扱います。SnapLock・Tamperproof Snapshot・別アカウントへの SnapVault と並べたトレードオフ、Vault Lock のコンプライアンスモードが常に有効であることなどの不可逆な設定の承認経路は、#316 に委ねます。このページでは繰り返しません。

このマップは機能と Spoke の対応を見る reference であり、#316 はデータ保護ドメインの隔離方式の内容です。2 つは別の持ち場で、重複しません。

---

## 関連ドキュメント

- [プロジェクト間の引用索引](cross-repo-index.md) — どの主張をどの Spoke から引いているかと、分担の原則
- [Reference](README.md) — 横断リファレンスの一覧

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

<!-- lang-switcher:start -->
🌐 [日本語](cyber-resilience-capability-map.md) | [English](../../en/reference/cyber-resilience-capability-map.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
