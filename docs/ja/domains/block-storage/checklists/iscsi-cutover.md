---
title: iSCSI を本番に出す前の確認 — 手順どおりに作ると落ちる 7 か所
lifecycle: [build, operate]
domains: [block-storage, performance, data-protection]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.17.1P7D1
lang: ja
---

# iSCSI を本番に出す前の確認

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## このチェックリストの位置づけ

**[quickstart](../quickstart.md) を通したあと、本番に出す前に確認する項目です。** 網羅的な設計レビューではありません。

入っているのは **手順どおりに作ると既定値のまま通ってしまい、あとで問題になる箇所** だけです。7 項目に絞っています。長いチェックリストは実行されません。

> **区分**: `verified` — 各項目は 2026-09-05 に `ap-northeast-1`、ONTAP 9.17.1P7D1、第 2 世代 `SINGLE_AZ_2`、`AWS::FSx::FileSystem` + ONTAP REST での実行で確認しました。**検証環境は撤去済みです。**
> **数値はこの構成での観測です。** 世代・HA ペア数・クライアント OS が違えば変わります。

---

## 1. パス数と推奨範囲の照合

- [ ] **`multipath -ll` のパス数を数えた。** 手順どおりに `iscsiadm --discovery` を流すと、**推奨の 4 倍のパスが立ちます**
- [ ] **立ったパスのうち、どれが `active` でどれが `enabled` かを確認した。** 数が合っていても、優先度が意図と違えばフェイルオーバー先が変わります
- [ ] **HA ペアの両ノードの LIF に到達できることを確認した。** 片側だけで動いてしまうため、テイクオーバーまで気づけません

なぜこうなるか、いくつに絞るかは [パスはフェイルオーバーの仕組みそのもの](../notes/paths-are-the-failover-mechanism.md) にあります。

---

## 2. 接続手順の 2 回目の実行

- [ ] **同じ手順を 2 回流し、LUN 数・igroup のイニシエータ数・マップ数・iSCSI セッション数・パス数の 5 つが 1 回目と一致することを確認した**
- [ ] **一致しなかった項目について、2 回目が何を追加したのかを特定した**

**「エラーが出なかった」は冪等の証拠になりません。** iSCSI の接続系コマンドは既存のセッションに対して非ゼロで返るものがあり、`set -o pipefail` の下では無言で止まります。この検証で見つかった 4 件のうち 2 件がそれでした。

観測すべき 5 指標と実行の記録は [quickstart](../quickstart.md) と [`examples/block-storage/verify-block.sh`](../../../../../examples/block-storage/verify-block.sh) にあります。

---

## 3. Linux の multipath 設定と NVMe 設定の競合

- [ ] **`mpathconf --enable` を流したあと、生成された設定ファイルの中身を読んだ。** 空ファイルは残りません。ディストリビューションによって書かれる内容が違います
- [ ] **カーネルの NVMe マルチパス設定が multipath デーモンと競合していないことを確認した。** iSCSI だけを使う構成でも、この設定は既定で入っていることがあります
- [ ] **再起動後にパスが同じ数で戻ることを確認した。** 手動で張ったセッションは残りません

---

## 4. 容量の 3 か所での計数

- [ ] **確保した SSD 容量・ボリュームの容量・LUN の容量の 3 つを別々に数えた**
- [ ] **`space.guarantee` の設定を確認した。** REST で作った LUN は既定で `false` になります。**「作れた」ことは「書き込める」ことを保証しません**
- [ ] **Snapshot の予約と、Snapshot が実際に使っている量を分けて把握した**

3 か所がどう食い違うかは [容量は 3 か所で数えられる](../notes/capacity-is-counted-in-three-places.md) にあります。

---

## 5. LUN 削除後の実際の解放

- [ ] **LUN を削除したあと、ボリュームの空き容量が戻ったことを確認した**
- [ ] **戻っていない場合、ONTAP 側の遅延解放を確認した。** 削除の応答が成功で返っても、解放は即時ではありません

**削除系の API が成功で返ったことは、削除された証拠になりません。** 数十秒後の状態で判定してください。

---

## 6. 手順書における 2 つの制御面の分離

- [ ] **AWS API で作るもの（ファイルシステム・SVM・ボリューム）と ONTAP で作るもの（LUN・igroup・マップ）を、手順書の中で分けて書いた**
- [ ] **ボリューム作成時のパラメータをハンドラの実際の挙動で確認した。** ドキュメントが省略可としているものが必須になっている箇所があります（この検証では `JunctionPath` がそうでした）
- [ ] **クライアントから FSx for ONTAP の AWS API に到達できることを確認した。** 管理エンドポイントの解決にはパブリックな名前解決が必要です。**VPC エンドポイントだけの私設サブネットからは届きません。** 到達できない環境では管理 IP とパスワードを直接渡す経路が必要です

境界の引き方は [LUN と igroup は AWS の API の外側にある](../notes/block-objects-are-outside-the-aws-api.md) にあります。

---

## 7. Snapshot から戻したあとのアプリ起動

- [ ] **LUN の Snapshot が既定で crash-consistent であることを把握した**
- [ ] **戻したあとにアプリケーションが起動するところまで、実際に試した**
- [ ] **DB を載せている場合、静止させる手順が必要かどうかを判断した**

**「戻せる」ことと「アプリが起動する」ことは別です。** 実測では静止なしで復旧しましたが、それは DB 自身が復旧処理を持っていたからです。詳細は [LUN の Snapshot は既定で crash-consistent](../notes/a-snapshot-of-a-lun-is-crash-consistent.md) と [LUN に載せた DB は静止させずに復旧した](../notes/a-database-on-luns-recovers-without-quiescing.md) にあります。

---

## このチェックリストに入れていないもの

**意図的に外しています。** 該当する場合はリンク先を読んでください。

| 項目 | 置き場所 |
|---|---|
| 世代・HA ペア数によるプロトコルの制約 | [ブロックプロトコルの選択肢は先に狭まる](../notes/protocol-choice-is-bounded-before-you-choose.md) |
| LUN の並べ方と復旧の粒度 | [LUN の並べ方が決めているのは復旧の粒度](../notes/lun-layout-decides-recovery-granularity.md) |
| CHAP と portset | [igroup の外側にある 2 つの制御](../notes/igroups-are-not-the-only-access-control.md) |
| Multi-AZ でのフェイルオーバー | [Multi-AZ が動かすのはアドレスではなくルート](../notes/multi-az-moves-a-route-not-an-address.md) |
| 監視の次元 | [ブロックの監視には LUN の次元もプロトコルの次元もない](../notes/what-block-monitoring-shows.md) |
| Kubernetes のボリューム数上限 | [Kubernetes のブロック PV はボリューム数の上限に当たる](../notes/kubernetes-block-volumes-and-the-volume-limit.md) |
| 不可逆な設定（SnapLock / Snapshot locking） | [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [クイックスタート](../quickstart.md) — この 7 項目の前に通す手順
- [本番投入前レビュー](../../../playbooks/04-build/checklists/pre-production-review.md) — プロトコルを問わない不可逆項目
- [知見の分類ポリシー](../../../evidence-policy.md)
