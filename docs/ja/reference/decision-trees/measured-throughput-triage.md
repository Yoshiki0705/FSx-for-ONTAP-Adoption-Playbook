---
title: 手元のスループット値は何を測ったのかを判定する — 上限は 4 か所にあり、1 つずつ潰す順序がある
lifecycle: [assess, design, optimize]
domains: [performance, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/performance.html
lang: ja
---

# 手元のスループット値は何を測ったのかを判定する

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [決定木](README.md) | [Domain — 性能](../../domains/performance/README.md)

---

## 結論

**「思ったより遅い」という数字を持ってきたとき、最初にすべきことはチューニングではなく、その数字が何の上限を測ったのかの切り分けです。**

上限は 4 か所にあり、**当たっている場所によって打つ手が正反対になります。**

| # | 上限の場所 | 当たっている合図 | 打つ手 |
|---|---|---|---|
| 1 | **クライアント 1 フローの帯域**、またはサービス側のクライアント単位クォータ | 単一マウント・単一セッションで止まる | **どちらかを先に切り分けます。** 1 フロー上限なら接続数を増やせば超えられ、サービス側クォータなら超えられません |
| 2 | **クライアントの実効帯域** | 複数接続にしても伸びず、時間経過で落ちる | クライアントの型を保証値のものに替える |
| 3 | **ファイルシステムのネットワーク帯域** | 台数を増やすと合計が天井に張り付く | スループット容量ではなくベースライン帯域を確認する |
| 4 | **ディスクの帯域 / IOPS** | 読むデータがキャッシュに無いときだけ遅い | SSD 容量とプロビジョンド IOPS、キャッシュの効き方を見る |

**1 と 2 はクライアント側、3 と 4 はファイルシステム側です。** 順序を守って切り分けないと、効かない側を触り続けることになります。

> **区分**: `documented` — 分岐の条件は AWS 公式ドキュメントの記載と、[プロジェクト間の引用索引](../cross-repo-index.md) に登録した sibling プロジェクトの実測に基づきます（2026-09-05 に確認）。
> **このリポジトリでは再測定していません。** 実測値そのものは [単一接続で測った値はストレージの性能ではない](../../domains/performance/notes/a-single-connection-measures-the-client.md) に条件付きで転記しています。
> **引用元の測定環境は削除済みです。**

---

## 切り分けのフロー

```mermaid
graph TD
    START[スループットが想定に届かない] --> CONN{接続数を数えたか}

    CONN -->|数えていない| COUNT["まず数える<br/>NFS: nconnect の値<br/>SMB: Get-SmbMultichannelConnection"]
    COUNT --> CONN

    CONN -->|1 接続| WHICH{どのサービスを測っているか}
    WHICH -->|FSx for ONTAP| FLOW["上限 1: クライアント 1 フローの帯域<br/>約 5 Gbps で止まります<br/>接続数を増やせば超えられます"]
    WHICH -->|他のストレージサービス| QUOTA["サービス側のクライアント単位クォータを先に確認<br/>接続数では超えられません<br/>例: EFS は 500 MiBps"]
    FLOW --> RAISE["nconnect / SMB Multichannel で<br/>接続数を増やしてから測り直す"]

    CONN -->|複数接続| PROTO{プロトコル}
    PROTO -->|NFS| XFER{"tcp-max-xfer-size を<br/>確認したか"}
    PROTO -->|SMB / ブロック| CLIENT
    XFER -->|既定 65536| DEFAULT["rsize が 64 KiB に切り下がります<br/>引き上げてから測り直す"]
    XFER -->|引き上げ済み| CLIENT{"クライアントの<br/>ネットワーク値は保証値か"}

    CLIENT -->|バースト型| BURST["上限 2: クライアントの実効帯域<br/>測定対象がクライアントです<br/>保証値の型で測り直す"]
    CLIENT -->|保証値| HOSTS{台数を増やすと合計が伸びるか}

    HOSTS -->|伸びる| MORE["まだ上限に当たっていません<br/>必要な台数まで増やす"]
    HOSTS -->|伸びない| SHARE{"各ホストは同じデータを<br/>読んでいるか"}

    SHARE -->|同じデータ| NET["上限 3: ネットワーク帯域<br/>キャッシュから返るので<br/>ディスクには当たっていません"]
    SHARE -->|重ならない領域| DISK["上限 4: ディスクの帯域 / IOPS<br/>同条件で 5.5 倍の差が出ます"]

    NET --> NETCHK["ベースライン帯域を確認する<br/>スループット容量の設定値とは別の数字です"]
    DISK --> DISKCHK["SSD 容量とプロビジョンド IOPS を確認する<br/>SSD 容量は IOPS の要件でも決まります"]

    RAISE --> TWICE
    DEFAULT --> TWICE
    NETCHK --> TWICE
    DISKCHK --> TWICE
    MORE --> TWICE

    TWICE{"同じ測定を 2 回続けて回し<br/>差を見たか"}
    TWICE -->|見ていない| RUN["回す<br/>同一構成で 45% 振れた実測があります"]
    TWICE -->|差が大きい| CACHE["キャッシュの状態差です<br/>測定ミスではありません<br/>幅で報告する"]
    TWICE -->|差が小さい| DONE["この構成の値として記録する<br/>接続数・共有の有無・キャッシュ状態を併記する"]

    RUN --> TWICE
```

---

## 各分岐の根拠

| 分岐 | 何に基づくか |
|---|---|
| FSx for ONTAP の単一接続で約 5 Gbps | AWS は 1 ネットワークフローあたり全二重 5 Gbps の上限を明記しています。実測では NFS 591.62 MB/s（4.7 Gbps）、SMB 574.24 MB/s（4.6 Gbps） |
| 他サービスは別の上限に当たりうること | 同じ測定で Amazon EFS の素マウントは 499.79 MB/s でした。**これは 5 Gbps ではなく EFS のクライアント単位クォータ 500 MiBps に一致します。** 引用元は当初この 3 行を同じ上限として説明し、あとで訂正しています |
| `tcp-max-xfer-size` の既定値 | 既定 65,536 のままだとクライアントの `rsize` が 64 KiB に切り下がります |
| クライアントの保証値とバーストの違い | インスタンス型によってネットワーク性能が保証値かバーストかが違います。バースト型では測定対象がクライアントになります |
| 同じデータか重ならない領域か | 8 台・128 接続の実測で、同一ファイル共有 11,916.29 MB/s に対し重ならない領域が 2,173.37 MB/s（0.18 倍）でした |
| スループット容量とベースライン帯域が別 | 実測構成はスループット容量 6,144 MBps で、ネットワークのベースラインは 12,500 MBps でした |
| 45% の幅 | 同一設定・同一パラメータ・同一測定器で 2 回測って 3,551.18 と 5,148.56 MB/s。差はキャッシュの状態だけです |

数値の測定条件は [単一接続で測った値はストレージの性能ではない](../../domains/performance/notes/a-single-connection-measures-the-client.md#測定条件) に全項目あります。

---

## この決定木が答えないこと

| 問い | 置き場所 |
|---|---|
| 接続数を増やす手段の選び方 | [スループットを上げる手段の比較](../comparison/throughput-levers.md) |
| スループット容量の設定値が何を決めているか | [スループットは 1 つの設定値では決まらない](../../domains/performance/notes/where-throughput-is-determined-and-shared.md) |
| p99 レイテンシをどう見るか | [p99 は CloudWatch のメトリクスからは出せない](../../domains/performance/notes/what-you-cannot-read-from-cloudwatch.md) |
| 世代差・S3 API との比較 | **未測定です。** 引用元が未測定として挙げている範囲は [引用元が未測定としている範囲](../../domains/performance/notes/a-single-connection-measures-the-client.md#引用元が未測定としている範囲) にあります |
| コストとの兼ね合い | [EBS が安くなくなる境目](../../domains/block-storage/notes/when-ebs-stops-being-the-cheaper-answer.md) |

---

## 関連ドキュメント

- [決定木](README.md) — 他の決定木
- [Domain — 性能](../../domains/performance/README.md) — このモジュールのハブ
- [スループットを上げる手段の比較](../comparison/throughput-levers.md) — 上限 1 に当たっているときの選択肢
- [プロジェクト間の引用索引](../cross-repo-index.md) — この数値をどこから引いているか
- [知見の分類ポリシー](../../evidence-policy.md)
