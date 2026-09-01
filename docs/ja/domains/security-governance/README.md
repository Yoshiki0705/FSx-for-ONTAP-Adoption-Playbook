# Domain — セキュリティ・ガバナンス (Security & Governance)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/security-governance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

暗号化、監査、権限設計、規制ワークロードでの考慮事項を扱います。ここに書かれているのは設計上の考慮事項であり、法務・コンプライアンス上の判断ではありません。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | 暗号化の選択肢とその境界はどこか | [保存時は自動、転送時は既定で無効](notes/what-the-platform-gives-and-what-stays-yours.md#プラットフォームが提供するものと自分に残るもの) |
| 2 | 誰が何をしたかをどう記録するか | [監査は 2 つの面に分かれ、片方に穴があります](notes/what-the-platform-gives-and-what-stays-yours.md#監査の-2-つの面と片方の穴の存在) |
| 3 | 権限設計をどう最小権限に寄せるか | [管理者を分ける](notes/what-the-platform-gives-and-what-stays-yours.md#権限設計--管理者の分離) |
| 4 | 規制ワークロードで問われる論点は何か | [問われる論点の整理](notes/what-the-platform-gives-and-what-stays-yours.md#規制ワークロードで問われる論点) |
| 5 | OT / IT 境界をまたぐ場合の考慮事項は何か | [境界をまたぐときに使える仕組みと限界](notes/what-the-platform-gives-and-what-stays-yours.md#分離された境界をまたぐときに使える仕組みとその限界) |
| 6 | 取り消せない操作をどう統制するか | [不可逆な操作の承認は作業の承認とは別に取る](notes/irreversible-operations-need-separate-approval.md) |
| 7 | S3 Access Point 経由のアクセスをどう絞るか。ポリシーをどう書くか | [S3 Access Point の権限設計 — 評価順序と、絞り込みを担う 2 つの層](notes/access-point-authorization-layers.md) |
| 8 | 管理者権限を渡さずに Snapshot とクローンを使わせるには何を縛るか | [実験ブランチを配るときに縛る対象は権限だけではない](notes/self-service-without-storage-admin.md) |
| 9 | SMB のログオン成功・失敗・ログオフは監査ログに残るか | [4624 は記録される。ただし数えられるのはセッション](notes/smb-logon-audit-event-coverage.md) |
| 10 | 監査を有効化すると可用性に何が起きるか | [監査宛先の枯渇はアクセスを止める。ただし満杯の瞬間ではない](notes/audit-log-space-and-client-access.md) |

---

## 構成

| ディレクトリ | 内容 |
|---|---|
| [`notes/`](notes/) | 知見の最小単位。1 ファイル = 1 論点。frontmatter に `evidence` 区分を持ちます |
| [`checklists/`](checklists/) | 現場で使うチェックリスト |

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
🌐 [日本語](README.md) | [English](../../../en/domains/security-governance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
