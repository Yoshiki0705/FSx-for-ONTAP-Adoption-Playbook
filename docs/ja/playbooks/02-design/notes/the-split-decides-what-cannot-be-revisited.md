---
title: 分割の単位が決めているのは、後で決め直せない範囲
lifecycle: [design]
domains: [multiprotocol-identity, security-governance, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-svms.html
lang: ja
---

# 分割の単位が決めているのは、後で決め直せない範囲

[🏠 リポジトリトップ](../../../../../README.md) | [Playbook — 02 設計](../README.md)

---

## 結論

**「いくつに分けるか」は性能や整理の問題として現れますが、決めているのは別のことです。** 不可逆な設定がどの範囲に固定されるかです。

**3 つの境界があり、それぞれ固定するものが違います。**

| 境界 | ここに固定されるもの | 決め直すには |
|---|---|---|
| **ファイルシステム** | デプロイタイプ、世代、配置する AZ、HA ペア数の上限 | **新しいファイルシステムを作ってデータを移す** |
| **SVM** | AD 参加、ブロック用 LIF、S3 Access Point の制約の適用範囲、管理者の分離 | SVM を作り直す（データの移動を伴う） |
| **ボリューム** | ボリューム名、SnapLock の有効化と保持モード、Snapshot locking | ボリュームを作り直してデータを移す |

**同じ範囲に置いたものは、まとめて決め直すことになります。** 分けておけば片方だけを作り直せます。**分割の判断は「分けると何が独立に決め直せるようになるか」で見るのが実際的です。**

---

## 境界ごとの帰結

### ファイルシステムを分けると独立になるもの

**デプロイタイプと世代はファイルシステム単位で、いずれも変更できません。** Multi-AZ と Single-AZ が混在する要件があるなら、**1 つのファイルシステムでは表現できません。**

詳細は [デプロイタイプは一度しか決められない](deployment-type-is-decided-once.md#チェックリストに載っていない不可逆項目) にあります。**HA ペアの追加は不可逆で、削除できません。**

### SVM を分けると独立になるもの

| 項目 | SVM 単位である帰結 |
|---|---|
| **AD 参加** | **1 つの SVM は 1 つのドメインに参加します。** 別ドメインの要件があれば SVM を分ける以外にありません。参加後に計算機オブジェクトを移動すると `misconfigured` になります（[AD への依存は生涯続く](../../../domains/multiprotocol-identity/notes/ad-dependency-lasts-the-lifetime.md)） |
| **ブロック用 LIF** | **1 SVM に 2 本、ノードごとに 1 本。** SVM を増やすと増えます（[パスはフェイルオーバーの仕組みそのもの](../../../domains/block-storage/notes/paths-are-the-failover-mechanism.md)） |
| **S3 Access Point の制約** | 適用単位が SVM です（[S3 Access Point の制約](../../../domains/data-utilization/notes/s3-access-point-constraints.md)） |
| **管理者の分離** | **`vsadmin` は SVM 単位です。** 指定しないと管理は `fsxadmin`（ファイルシステム全体の管理者）になります（[ONTAP 側の設定に届く経路の比較](../../../reference/comparison/ontap-configuration-routes.md)） |
| **SMB サービス** | CIFS サーバーを削除した SVM は SMB を提供できなくなります（[SMB を提供できない SVM がある](../../../domains/multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md)） |

**運用担当者を分けたいなら、SVM を分けたうえで `vsadmin` を作成時に指定します。** 後から最小権限に寄せる経路が、作成時の指定に依存します。

### ボリュームを分けると独立になるもの

**不可逆な項目が最も多い境界です。** SnapLock の有効化と保持モード、Snapshot locking はいずれもボリューム単位で、決め直しに作り直しが伴います。

**そして影響がボリュームの外に出る項目があります。** SnapLock 監査ログボリュームは、**最低 6 か月のあいだボリューム・SVM・ファイルシステムのいずれも削除できなくなります。** 一覧は [不可逆な項目の一覧](../../04-build/checklists/pre-production-review.md#不可逆な項目の一覧) にあります。

**ここは「分けたから独立」が成り立たない唯一の例です。** 1 ボリュームの選択がファイルシステム全体を拘束します。

---

## 決める順序

**上から決めます。下の境界の選択肢が上で狭まるためです。**

| 順 | 決めること | 狭まるもの |
|---|---|---|
| 1 | ファイルシステムをいくつにするか | デプロイタイプと世代の組み合わせ。**混在は分割でしか表現できません** |
| 2 | SVM をいくつにするか | AD ドメイン、管理者の分離、LIF の本数 |
| 3 | ボリュームの粒度 | 不可逆項目の影響範囲。**復旧の粒度**（[LUN の並べ方が決めているのは復旧の粒度](../../../domains/block-storage/notes/lun-layout-decides-recovery-granularity.md)） |

**1 と 2 を飛ばしてボリュームから決めると、後で SVM を分ける必要が出たときに移動が発生します。**

---

## 分離パターンの不扱い

**分割の数と配置のパターンは、それを運用しているリポジトリにあります。**

| 知りたいこと | 所在 |
|---|---|
| マルチテナントの分離パターン（3 段階） | [マルチテナント設計パターン](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns/blob/main/docs/ja/multi-tenant-design.md) |
| ボリュームを作る前に決めることの順序 | [最初に決めること — Origin ボリュームを作る前に](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/design-first-decisions.md) |

**どのパターンが良いかは書きません。** こちらは運用していないので、比較の根拠を持ちません。**このノートが持つのは、どのパターンを採っても共通する「何が固定されるか」です。**

---

## 自環境での確認手順

**分割案を決めたら、決め直しの経路を 1 件ずつ確認してください。**

1. 案の中で**不可逆な項目**を列挙する（上の 3 表を使う）
2. 各項目について「決め直すとき何を作り直すか」を書く
3. **作り直しにデータ移動が伴う項目**に印を付ける
4. 印の付いた項目が要件の変わりやすい部分に載っていないかを確認する

**4 で載っていたら、その境界を分ける理由があります。** 逆に、どの不可逆項目も安定した要件にしか載っていなければ、分けない理由があります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| SVM を増やすと管理が煩雑になるだけ | **管理者の分離と AD ドメインの単位でもあります。** 後から分けるとデータ移動を伴います |
| ボリュームを分ければ影響も分かれる | **SnapLock 監査ログボリュームは例外です。** 1 ボリュームがファイルシステム全体を 6 か月拘束します |
| デプロイタイプは後から変えられる | **変えられません。** 新しいファイルシステムを作ってデータを移すことになります |

---

## 関連ドキュメント

- [デプロイタイプは一度しか決められない](deployment-type-is-decided-once.md)
- [本番投入前レビュー](../../04-build/checklists/pre-production-review.md)
- [Domain — マルチプロトコルと ID](../../../domains/multiprotocol-identity/README.md)
