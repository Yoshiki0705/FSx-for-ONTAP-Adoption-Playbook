---
title: ONTAP のコマンド・REST API・権限の入口 — 版ごとに取り直すものとして、確かめたいことから読むものを引く
lifecycle: [operate]
domains: [security-governance, observability]
evidence: documented
source: https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/ontap-command-api-snapshot.md
lang: ja
---

# ONTAP のコマンド・REST API・権限の入口

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**管理者が使える ONTAP の CLI コマンド・REST API・権限は、1 回調べて固定する設定ではなく、版ごとに取り直す記録です。** ONTAP のパッチはサービス側で適用されます。同じファイルシステムで 11 日後に `9.17.1P7D1` から `9.18.1P3D1` に上がった実測が、[ONTAP バージョンの取得経路](limits/README.md#ontap-バージョンの取得経路--where-the-ontap-version-comes-from)にあります。

**このページは知見を持ちません。** 手元の問いから、読むものへのリンクと判断の指針だけを置きます。数値と観測は Spoke にだけあり、ここに写すと Spoke 側だけが直されたときに古い値が残るためです。

> **区分**: `documented` — Spoke の記述の所在を示す入口です。Spoke の観測は **1 環境・1 バージョン（ONTAP 9.18.1P6）・`fsxadmin` のみ**で、他の版、Multi-AZ、`fsxadmin` 以外のロールは未確認です。

---

## 確かめたいことごとの読み先

| 手元の問い | 読むもの |
|---|---|
| いま使っている ONTAP のバージョンは | [ONTAP バージョンの取得経路](limits/README.md#ontap-バージョンの取得経路--where-the-ontap-version-comes-from) |
| `fsxadmin` で実行できるコマンドは | [ONTAP コマンドと REST API のスナップショット](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/ontap-command-api-snapshot.md)の CLI の節 |
| この版にどんな REST API があるか。権限で使えない API は | 同じ解説の REST の節と、403 になった GET の節 |
| 版が上がったら何が変わったか | [スナップショット Lambda](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/solutions/ontap-catalog-snapshot/README.md)。前回との差分を残します |
| 自分の環境で取るには。AI エージェントに実装させるには | 同じ Lambda の README と、[AI エージェント向けプロンプト](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/agent-prompts/ontap-catalog-snapshot.md) |
| MAV（複数管理者承認）は FSx for ONTAP で使えるか | [MAV の観測](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns/blob/main/docs/ontap-native/ontap-command-api-snapshot.md#mav-の観測)。次の節を先に読んでください |

Spoke の解説は、ONTAP 9.18.1P6・`fsxadmin`・2026-11-04 の値として、実行できる CLI コマンドを 1,744 件、REST エンドポイントを 570 件と記録しています。別の版・別の環境では値が変わります。

---

## MAV の観測の範囲

**このページは、MAV が使えるか使えないかを書きません。** Spoke の観測は、上の 1 環境・1 バージョン・`fsxadmin` に限られます。AWS 側の管理経路（コンソール、AWS CLI、API）で MAV を設定できるかは、Spoke でも確認されていません。結論は観測の表を読んで判断してください。Hub の MAV の扱いは[管理面の保護は複数の統制に分かれる](../domains/security-governance/notes/admin-plane-protection-depends-on-several-controls.md)にあります。

---

## 取得方法の選び方

どの経路にも制約があります。特定の経路を勧める表ではありません。詳しい比較は Spoke の README にあります。

| 経路 | 向く状況 | 制約 |
|---|---|---|
| 手で CLI（SSH） | 1 回だけ、結果をその場で読みたい | 管理エンドポイントへ SSH できる経路が要る。全コマンドの一覧は取れず、`?` を辿る方法は Spoke でも行われていない。版が変わるたびに手順を人が繰り返す |
| 手で REST（CLI パススルー） | 結果をファイルに残して突き合わせたい | 管理エンドポイントは VPC 内からのみ到達する。踏み台か Session Manager のポートフォワードが要る。`show-rest` では `fields=*` が使えず、フィールド名を列挙する |
| スナップショット Lambda | 版が上がるたびに同じ内容を取り、差分を残したい | SAM のデプロイと、VPC・シークレットの設計が要る。GET の可否はパスパラメータのない GET だけを実測する。実機で確認されたのは 1 環境・1 バージョン・`fsxadmin` のみで、認証失敗での停止と版の変更時の差分は、実機では起こしておらずユニットテストでの確認 |

---

## 管理者アカウントを守る注意

**どの経路でも、同じ管理者の認証情報を何度も使う操作では、認証失敗を繰り返さないでください。** 失敗が蓄積すると `fsxadmin` がロックされ、REST の応答ではロックとパスワード誤りが区別できません。経緯と回復手順は[fsxadmin はロックされる。REST では原因が判別できない](../playbooks/05-operate/notes/admin-account-lockout-and-recovery.md)にあります。

---

## 確認できていないこと

- ONTAP 9.18.1P6 以外の版での結果
- Multi-AZ 構成での結果
- `fsxadmin` 以外のロール（`fsxadmin-readonly`、`vsadmin` 系）が実行できるコマンドの一覧
- AWS 側の管理経路での MAV の設定可否

---

## 関連

| ドキュメント | 関係 |
|---|---|
| [ONTAP バージョンの取得経路](limits/README.md#ontap-バージョンの取得経路--where-the-ontap-version-comes-from) | バージョンが 11 日で上がった実測 |
| [メンテナンスは先送りできるか](../playbooks/05-operate/notes/maintenance-cannot-be-deferred.md) | パッチ適用がサービス側で行われること |
| [運用モジュール](../playbooks/05-operate/README.md) | ONTAP のバージョン更新を扱う問い |
| [知見の分類ポリシー](../evidence-policy.md) | `documented` と `verified` などの区分の意味 |

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
<!-- lang-switcher:start -->
🌐 [日本語](ontap-commands-and-apis.md) | [English](../../en/reference/ontap-commands-and-apis.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
