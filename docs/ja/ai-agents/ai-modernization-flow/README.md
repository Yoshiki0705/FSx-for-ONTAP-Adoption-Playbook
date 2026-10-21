# AI Modernization Flow はアプリ側を移し、このリポジトリがデータ側を受け持つ

[🏠 リポジトリトップ](../../../../README.md) | [ジャンル — AI エージェント](../README.md)

---

AI Modernization Flow（以降 AIMF）は、AI エージェントに決められた段階でアプリケーションコードを移行させる aws-samples のワークフローです。**アプリケーションのコードを移すのが AIMF で、そのアプリが読み書きするデータを Amazon FSx for NetApp ONTAP（以降 FSx for ONTAP）側でどう設計・移行・運用するかは、このリポジトリが受け持ちます。** このページは両者の分担と合流点を示す位置づけページで、FSx for ONTAP 側の実装知見そのものは [テーマ軸](../../navigation.md#テーマ軸--domains) と [ライフサイクル軸](../../navigation.md#ライフサイクル軸--playbooks) にあります。

---

## このページの確度

2 つの確度が混ざるので、冒頭で分けておきます。

| 何を書くか | 確度の扱い |
|---|---|
| AIMF の仕様（Phase 構成、スコープ境界、ライセンス） | `documented`。出典は [AWS ブログ][blog] と [aws-samples/sample-ai-modernization-flow][repo]（調査時点の版は v0.11.0） |
| 合流点・適合判断（このリポジトリの知見がどこで効くか） | `hypothesis`。著者環境での実測ではなく、未検証です |
| 実地で回した結果 | [FSx-for-ONTAP-App-Modernization-Patterns][appmod] リポジトリの `field-observation` / `verified`（各 1 回）。**このページは引用するだけで、測定をこのリポジトリの成果として言い直しません** |

> **版の注意**: AIMF は 0.x で、0.x の MINOR には破壊的変更が入ります（[CHANGELOG][changelog]）。Phase 構成や導入手順に依拠する前に、最新の版を確認してください。調査時点の版は v0.11.0 です。

---

## AIMF の役割とスコープ境界

**AIMF はアプリケーションコードの Refactor 型移行（ビジネスロジックを変えずにランタイム・フレームワークを更新する）を、Kiro / Claude Code に Phase 0a〜4 の手順で進めさせます。** MIT No Attribution（MIT-0）で公開されています（[ブログ][blog]）。

**クラウド環境の設計・構築は AIMF のスコープ外と明記されています**（[ブログ][blog]、[flow.md][flow]）。この境界が合流の継ぎ目です。**AIMF はアプリ側を持ち、このリポジトリはデータ / ストレージ側を持ちます。** 両者は重ならず、補い合います。

AIMF はマネージドな AWS エージェントではなく、Markdown のルール / skills・テンプレート・bash スクリプトで構成される移行ハーネスです。Phase 0a のコード分析に AWS Transform custom（`atx` CLI）を使います。

---

## 合流点（強いもの 4 点に絞った要約）

全 11 点の対応表は 2026-10-06 の調査報告（このリポジトリ外の作業メモ、未公開）にあります。ここでは強い 4 点に絞ります。**実地結果が裏付けた 1 点を除き、すべて `hypothesis`（未検証）です。**

| # | AIMF 側 | このリポジトリ側 | 合流の中身 | 区分 |
|---|---|---|---|---|
| 1 | Phase 0b リポジトリ間契約の棚卸し（共有ファイル・共有 DB を含む） | [プロトコル選択の決定木](../../reference/decision-trees/file-storage-selection.md)、[クライアント到達経路の決定木](../../reference/decision-trees/client-access-route.md)、[セキュリティスタイルが権限モデルを決める](../../domains/multiprotocol-identity/notes/security-style-and-permission-evaluation.md) | AIMF は共有ファイルを「契約」として数えますが、移行先でどのプロトコル・セキュリティスタイルで出すかの判断材料は持ちません。契約行を決定木へ渡します | `hypothesis` |
| 2 | Playbook 層の観点表（`analysis-appendix.md` の MP 行、②沈黙 / ③誤誘導） | [S3 Access Points は「S3 として使える」わけではない](../../domains/data-utilization/notes/s3-access-point-constraints.md)、[S3 Access Points は全リクエストを 1 つの ID で認可する](../../domains/data-utilization/notes/reaching-data-without-copies.md) | アプリのストレージ層を S3 API に寄せて FSx for ONTAP に置く場合、非対応 API・単一 ID 認可・元 ACL が引き継がれないことがサイレント障害になりえます。ストレージ起因の観点を候補として渡します | `hypothesis` |
| 3 | Phase 1 baseline / Phase 3 検証データの供給 | [データセットの版と実験ブランチ](../../domains/data-utilization/notes/dataset-versions-and-experiment-branches.md)、[ストレージ管理者なしのセルフサービス](../../domains/security-governance/notes/self-service-without-storage-admin.md) | 本番データの FlexClone / Snapshot を現新比較の入力にすれば同一データで比較できます。本番相当データの利用可否は AIMF 側で人の判断（Tier 2）に残ります | `hypothesis` |
| 4 | 判断項目「クラウド操作のガードレールは未提供」、HOLD-6（破壊的操作） | `scripts/guard_irreversible_ops.py`、[AGENTS.md の不可逆操作節](../../../../AGENTS.md)、[不可逆操作は別の承認が要る](../../domains/security-governance/notes/irreversible-operations-need-separate-approval.md) | AIMF はクラウド操作の統制を明示的に提供していません（[flow.md][flow]）。このリポジトリのガードは SnapLock・snapshot locking・S3 Object Lock などの不可逆操作をコマンド単位で止めます。AIMF の `PreToolUse` hook へ追加配線できますが、共存は未確認です | `hypothesis` |

---

## 実地で回した結果

AIMF を 1 回実地で回した結果は [FSx-for-ONTAP-App-Modernization-Patterns][appmod] リポジトリにあります（[段階 2 — AIMF による .NET モダナイゼーション][appmod-stage2]、[検証手順][appmod-reproduce]）。以下はそのリポジトリの結果の引用で、**各項目は 1 回の観測 / 1 セッションです。一般化しません。** 測定はあちらに属し、このリポジトリは引用するだけです。

- **AIMF の Phase 0a〜4 を 1 セッションで完走**し、ADR-1〜5 と独立検証（2 レンズ）まで到達した。独立検証は「機能欠落」を REFUTED、「スコープ」を UPHELD と判定した（1 セッション）。
- **旧 Worker（201 バイト）と近代化 Worker（181 バイト）は JSON 同値**だった。バイト数は違うが、空白 20 バイトの差で、出力は等価（1 回の観測）。
- **同じ ntfs ボリュームでも、アクセス経路で大文字小文字の扱いが違う**。SMB（Windows、cifs）は区別せず、NFS と S3 Access Points は区別した（各 1 回、陽性対照つき）。
- **観測費用は約 21.18 USD**（Cost Explorer、UnblendedCost、Credit と Refund を除外。タグ・リソース ID で帰属できた範囲）。基盤の破棄後に残存ゼロを確認した。

> **費用の注意**: この約 21.18 USD は Cost Explorer の観測値で、`Estimated: true` です。**請求書ではありません。** 試算と請求額の区別、および測定環境（ap-northeast-1、Single-AZ、使い捨てファイルシステム）は、引用元リポジトリの記載に従ってください。

---

## 使うときの境界 — 「Playbook」という語の衝突

**AIMF の「Playbook」と、このリポジトリの `playbooks/` は別物です。** 併記するときは区別してください。

| 語 | 意味 |
|---|---|
| AIMF の「Playbook」 | ドメイン知見の層（Java / .NET / C 言語など、移行対象ごとの観点と手順）。[3 層構成（Method / Playbook / Harness）][repo]の中段 |
| このリポジトリの `playbooks/` | ライフサイクル軸（評価 → 設計 → 移行 → 構築 → 運用 → 最適化）。[ナビゲーション](../../navigation.md#ライフサイクル軸--playbooks) |

**AIMF の Playbook 層は 1 プロジェクトに 1 つしか入りません**（`authoring-playbook.md`）。そのため将来 FSx for ONTAP 向けの観点を AIMF に合流させる場合、独立した Playbook ではなく、既存 Playbook へ差し込む補助パックの形になります。**これは推論で、未検証です。補助パックの作成はこのページの範囲外（実地で複数回確かめてから判断）です。**

---

## AIMF と AWS Transform の関係（対称に）

AIMF の Phase 0a は AWS Transform custom（`atx`）を呼びます。両者は役割が違うので、トレードオフを両側に書きます。

| 観点 | AIMF | AWS Transform |
|---|---|---|
| 位置づけ | アプリコードの移行手順を規律づけるワークフロー（ハーネス） | マネージドな移行・変換サービス。AIMF の Phase 0a はこれを呼ぶ |
| 向く場面 | 段階・記録・ゲートを明示してエージェントに移行させたいとき | コードベース分析やワークロード変換をマネージドに走らせたいとき |
| トレードオフ | ルールは Markdown / スクリプトで、実行環境の整備（Kiro / Claude Code）が要る。クラウド操作の統制は未提供 | 提供リージョン・コード送信先・課金が前提になる。移行の段階規律は利用側で設計する |

優劣ではなく、用途で選びます。移行先ストレージとしての AWS Transform と FSx for ONTAP の対応は [直近のアップデート](../../reference/recent-updates.md#aws-transform-が-fsx-for-ontap-をサポートga-2026-08) にあります。

---

## 関連

- [AWS ブログ「AI Modernization Flow を公開しました」][blog]
- [aws-samples/sample-ai-modernization-flow][repo]
- [FSx-for-ONTAP-App-Modernization-Patterns][appmod] — AIMF を実地で回した結果を持つリポジトリ
- [ジャンルハブ — AI エージェント](../README.md)
- [モダナイゼーション旅程マップ](../../reference/modernization-journey-map.md) — 段階 2（アプリのモダナイゼーション）での分担
- [知見の分類ポリシー](../../evidence-policy.md)

[blog]: https://aws.amazon.com/jp/blogs/news/aidm-introducing-ai-modernization-flow/
[repo]: https://github.com/aws-samples/sample-ai-modernization-flow
[flow]: https://github.com/aws-samples/sample-ai-modernization-flow/blob/main/ja/method/flow.md
[changelog]: https://github.com/aws-samples/sample-ai-modernization-flow/blob/main/CHANGELOG.md
[appmod]: https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns
[appmod-stage2]: https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/stage-2-aimf-modern-dotnet.md
[appmod-reproduce]: https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns/blob/main/docs/ja/reproduce.md

---

[🏠 リポジトリトップ](../../../../README.md) | [ジャンル — AI エージェント](../README.md)
