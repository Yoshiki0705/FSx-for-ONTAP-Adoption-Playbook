# FSx for ONTAP 補助パック — AIMF の移行プロジェクトに貼り込む観点集

[🏠 リポジトリトップ](../../../../../README.md) | [AI Modernization Flow 位置づけページ](../README.md)

---

このパックは、AI Modernization Flow（以降 AIMF）の移行プロジェクトに、Amazon FSx for NetApp ONTAP（以降 FSx for ONTAP）起因のサイレント障害の観点を貼り込むための補助パックです。AIMF がアプリケーションコードを移す Phase 0b〜3 で、そのアプリが読み書きするデータを FSx for ONTAP の NFS / SMB / S3 Access Points にまたがって扱うときに効きます。貼り込む断片は 3 種（観点表の行・検証スニペット・ガードレール配線メモ）で、本文はこの README から各断片へリンクします。

---

## AIMF Playbook との違い

**このパックは独立した AIMF Playbook ではありません。** AIMF の Playbook 層は 1 プロジェクトに 1 つしか入らないため（AIMF の `authoring-playbook.md`）、FSx for ONTAP の観点を独立 Playbook として置くと、案件の言語 Playbook（Java / .NET など）と並び、1 回の run で両方は選べません。そこでこのパックは、既存 Playbook の `00-analysis/analysis-appendix.md` に観点表の行を貼り込む形をとります。この判断の根拠は [位置づけページ](../README.md#使うときの境界--playbookという語の衝突) にあります。

---

## 貼り方

| 貼る断片 | 貼り先（AIMF ワークスペース側） | 中身 |
|---|---|---|
| [観点表の行](analysis-appendix-fragment.md) | プロジェクトの `00-analysis/analysis-appendix.md` の観点表 | FSx for ONTAP 起因のサイレント障害の観点（`MP-FSXN-N`）。検出コマンド付き |
| [検証スニペット](verify-snippets-fragment.md) | プロジェクトの `verify-snippets.md` | 各観点の否定テスト手順と、Snapshot / FlexClone で integration データを戻す例 |
| [ガードレール配線メモ](guardrail-wiring.md) | AIMF ワークスペースの `PreToolUse` hook 設定 | `scripts/guard_irreversible_ops.py` を AIMF 自身の hook と併存させる手順 |

`analysis-appendix.md` と `verify-snippets.md` は、AIMF の `install.sh --update-project` でも上書きされない差し込み先です（プロジェクト側でも追記するため。AIMF の `authoring-playbook.md`「稼働中のプロジェクトへ反映する」節）。したがって貼り込んだ行は版更新で消えません。

> **版の注意**: AIMF は 0.x で、0.x の MINOR には破壊的変更が入ります。差し込み先ファイルの構成に依拠する前に、最新の `authoring-playbook.md` の差し込み先リストを確認してください。この追随は人の確認事項で、このリポジトリの自動ゲートは追えません（上流は別リポジトリです）。

---

## 「Playbook」という語の衝突

AIMF の「Playbook」と、このリポジトリの `playbooks/` は別物です。併記するときは区別してください。

| 語 | 意味 |
|---|---|
| AIMF の「Playbook」 | ドメイン知見の層（移行対象ごとの観点と手順）。このパックが貼り込む先 |
| このリポジトリの `playbooks/` | ライフサイクル軸（評価 → 設計 → 移行 → 構築 → 運用 → 最適化） |

用語表は [位置づけページ](../README.md#使うときの境界--playbookという語の衝突) にあります。

---

## evidence の読み方

観点表の各行には evidence 区分が付いています。読むときの前提は次のとおりです。

- **`field-observation`** は、[FSx-for-ONTAP-App-Modernization-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-App-Modernization-Patterns) リポジトリが AIMF を実地で回したときの各 1 観測 / 1 セッションです。**このリポジトリ（Hub）は測定を持たず、引用するだけです。** 一般化しないでください。
- **`documented`** は AWS / NetApp の公式ドキュメント由来です。出典 URL が付きます。
- **`verified`** は Hub 自身が実測した行で、`MP-FSXN-6`（撤去時の停滞）の 1 行だけです。
- **`hypothesis`** は未検証の推論です。`MP-FSXN-2` がこれにあたり、FSx for ONTAP 上での発火は実測していません。

測定の主体がどちらかを取り違えないでください。App-Modernization-Patterns の測定を Hub の自前測定として言い直さず、Hub の実測を App-Modernization-Patterns が測ったかのようにも書きません。

---

## 関連

- [AI Modernization Flow 位置づけページ](../README.md) — AIMF とこのリポジトリの分担
- [観点表の行](analysis-appendix-fragment.md)
- [検証スニペット](verify-snippets-fragment.md)
- [ガードレール配線メモ](guardrail-wiring.md)
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [AI Modernization Flow 位置づけページ](../README.md)
