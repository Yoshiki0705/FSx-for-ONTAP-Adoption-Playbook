# Domain — 性能 (Performance)

<!-- lang-switcher:start -->
🌐 [日本語](README.md) | [English](../../../en/domains/performance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->

---

スループット設計、レイテンシ、キャッシュ、共有帯域の挙動を扱います。数値は必ず測定環境とセットで読んでください。

---

## 読む順序

**手元に「思ったより遅い」という数字があるなら、チューニングの前に切り分けです。**

| 順 | 読むもの | 何が分かるか |
|---|---|---|
| 1 | [手元のスループット値は何を測ったのかを判定する](../../reference/decision-trees/measured-throughput-triage.md) | 4 か所ある上限のどこに当たっているか。**当たっている場所によって打つ手が正反対になります** |
| 2 | [スループットを上げる手段の比較](../../reference/comparison/throughput-levers.md) | 6 つの手段の効く量とコストの向き。**最も大きく動いたのは追加料金のない手段でした** |
| 3 | [単一接続で測った値はストレージの性能ではない](notes/a-single-connection-measures-the-client.md) | 実測値と、その全測定条件 |

**性能要件をこれから書くなら、3 を先に読んでください。** 「MB/s」だけの要件は決まりません。

---

## このモジュールが扱う問い

| # | 問い | ノート |
|---|---|---|
| 1 | スループットはどこで決まり、どこで共有されるか | [スループットは 1 つの設定値では決まらない](notes/where-throughput-is-determined-and-shared.md) |
| 2 | プロトコル間で帯域をどう分け合うか | [プロトコル間で帯域はどう分け合われるか](notes/what-you-cannot-read-from-cloudwatch.md#プロトコル間での帯域の分け合い方) |
| 3 | レイテンシのテール（p99）をどう見るか | [p99 は CloudWatch のメトリクスからは出せない](notes/what-you-cannot-read-from-cloudwatch.md) |
| 4 | キャッシュが効くワークロードの条件は何か | [キャッシュが効く条件](notes/what-you-cannot-read-from-cloudwatch.md#キャッシュが効く条件) |
| 5 | ベンチマークをどう設計すれば再現できるか | [再現できるベンチマークの条件](notes/what-you-cannot-read-from-cloudwatch.md#再現できるベンチマークの条件) |
| 6 | 手元で測った値は何を測っているのか | [単一接続で測った値はストレージの性能ではない](notes/a-single-connection-measures-the-client.md) |
| 7 | 同じ構成で測った値が振れるのはなぜか | [45% の幅の正体](notes/a-single-connection-measures-the-client.md#45-の幅の正体) |
| 8 | スループットを上げる手段はどれを先に試すか | [スループットを上げる手段の比較](../../reference/comparison/throughput-levers.md) |

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
🌐 [日本語](README.md) | [English](../../../en/domains/performance/README.md) | [🏠 リポジトリトップ](../../../../README.md)
<!-- lang-switcher:end -->
