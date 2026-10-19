---
title: FSx for ONTAP 9.19.1 では QoS バーストのデフォルト値をユーザーが変更できる — 設定も実 I/O 挙動も確認済み
lifecycle: [design, operate, optimize]
domains: [performance]
evidence: verified
verified_on: 2026-10-18
region: ap-northeast-1
ontap_version: 9.19.1P2
deployment_type: SINGLE_AZ_1
lang: ja
---

# FSx for ONTAP 9.19.1 で QoS バーストのデフォルト値は変更できるか？

変更できます。ONTAP 管理面（REST private CLI / CLI）経由で設定が通り、実 I/O の挙動にも反映されました。

## このノートで学べること

- ONTAP 9.19.1 で追加された QoS バーストの 3 オプション（burst-percent / burst-duration / burst-iops）のデフォルト値が、Amazon FSx for NetApp ONTAP でもユーザー変更できること。
- 設定が通ること（HTTP 201/200 と読み戻し）だけでなく、ceiling を超えるバーストが指定どおり発生する実 I/O 挙動まで確認した結果。
- このオプションが adaptive QoS ではなく通常の throughput ceiling 用ポリシーグループに適用されること。
- 変更できる面（ONTAP REST / CLI）と変更できない面（AWS マネジメントコンソール / FSx for ONTAP の AWS API）の切り分け。

## このノートが答えないこと

- FSx for ONTAP でのダウングレード（revert）が運用上可能かどうか（未検証）。
- SnapMirror / MetroCluster など他機能とバースト設定の相互作用。
- バーストの各値がワークロード全体のコストや課金に与える影響。

## 前提レベル

intermediate

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

---

### 結論

**ONTAP 9.19.1 で追加された QoS バーストの 3 オプションは、FSx for ONTAP でもデフォルト値をユーザーが変更できます。** 経路は ONTAP 管理面（REST private CLI / CLI）です。create / modify が受け付けられ、読み戻しで値が確定し、ceiling を超えるバーストが指定どおり発生することを実 I/O で確認しました。

**AWS マネジメントコンソールと FSx for ONTAP の AWS API には、このバーストオプションに対応するパラメータがありません。** 従来からの二面構造どおり、設定は ONTAP 側で行います。

> **区分**: `verified` — ap-northeast-1 の検証用 FSx for ONTAP ファイルシステム（ONTAP 9.19.1P2, SINGLE_AZ_1）に対し、VPC 内の Linux クライアントから ONTAP REST / CLI と fio で確認しました（2026-10-18）。構成が違えば当たる上限も挙動も変わります。

---

### 対象の明確化

**このバーストオプションは adaptive QoS ではなく、通常の throughput ceiling 用 QoS ポリシーグループに適用されます。** 元の質問が adaptive QoS を念頭に置いていたとしても、正確な対象はこちらです。

ドキュメント（throughput ceiling 設定、throughput 保証）と実機の両方で確認しました。実機では adaptive-policy-group の REST スキーマに burst フィールドが現れず、通常の policy-group にのみ burst_percent / burst_duration / burst_iops が存在しました。

---

### 3 オプションの定義と既定値

| オプション | 既定値 | 意味 |
|---|---|---|
| burst-percent | 50% | ceiling を超える割合（ピーク超過幅） |
| burst-duration | 1 秒 | 超過を持続させる秒数 |
| burst-iops | 0 | 超過時の絶対 IOPS 上限（0 は未使用） |

**burst-percent と burst-iops は相互排他です。** 超過幅を割合で指定するなら burst-percent、絶対 IOPS で指定するなら burst-iops を使います。

---

### 設定が通ることの実測

ONTAP REST private CLI の `qos/policy-group` に対する create / modify が受け付けられ、読み戻しで値が確定しました。

| 操作 | 結果 |
|---|---|
| create（burst-percent=25） | HTTP 201、読み戻しで burst_percent:25 |
| modify（burst-duration=5） | HTTP 200、読み戻しで burst_duration:5 |
| create（burst-iops=3000, ceiling 2000 IOPS） | HTTP 201、読み戻しで burst_iops:3000 |

---

### 実 I/O 挙動の実測

ceiling を 2000 IOPS に設定し、VPC 内の Linux クライアントから fio（4k random read, NFSv3）で負荷をかけ、設定を変えながら per-second の IOPS を観測しました。QoS なしの基準線は 24,400 IOPS です。各パターンとも ceiling 適用前に idle を置いてバーストクレジットを蓄積してから流しました。

| パターン | 設定 | t=1s ピーク | 定常 | 支配する側面 |
|---|---|---|---|---|
| 2 | 既定（percent=50, duration=1） | 3017 | 2000 | 超過幅。1 秒だけ ceiling+50% 超過、2 秒目で収束 |
| 3 | percent=25, duration=1 | 2507 | 2000 | 超過幅。percent がピーク超過幅に直結し +25% に縮小 |
| 4 | percent=50, duration=5 | 約 3000 を t=1..5s 維持 | 2000 | 持続時間。duration が超過の継続秒数を決める |
| 5 | burst-iops=3000, duration=5（percent=0） | 約 3000 を t=1..5s 維持 | 2000 | 絶対値。超過時 IOPS が 3000 に張り付く |
| 6 | 無効（0/0/0） | 2020（約 +1%） | 2000 | 消滅。超過スパイクが消え概ね ceiling 内 |

**percent はピークの超過幅、duration は超過の持続時間、burst-iops は超過時の絶対 IOPS を支配し、0/0/0 でバースト自体が消えます。** 設定ごとに挙動のどの側面が動くかが分離して観測できました。

ドキュメント（load balancing の解説）では、ceiling は最大 10% 超過しうる、バースト時は最大 50% まで超過しうる、バーストは単一ノードでトークンが 150% まで蓄積したときに発生する、と記載されています。パターン 2 の +50% ピークとパターン 6 の約 +1% は、この記載と整合します。

---

### ONTAP 側の値制約

次の 2 つは ONTAP 本体の制約であり、FSx for ONTAP 固有の制約ではありません。実機でも ONTAP がこれらの組み合わせを拒否しました。

- **burst-iops と burst-percent は相互排他。** 両方を同時指定すると ONTAP が拒否します。既存ポリシーに burst_percent が残ったまま burst-iops へ切り替える場合は、先に burst-percent を 0 にリセットしてから burst-iops を設定すれば通ります。
- **burst-iops は max-throughput（ceiling IOPS）より大きい必要がある。** ceiling 2000 IOPS に対し burst-iops=500 は ONTAP が拒否し、burst-iops=3000 は通りました。コマンドリファレンスには、burst-iops が max-throughput 未満の場合は max-throughput が使われる、と記載されています。

> **補足**: 実機で得たエラーコード番号は本ノートでは省略しています。挙動として重要なのは「どの組み合わせを ONTAP が拒否するか」であり、番号は環境により変わりうるためです。

---

### ダウングレード前の注意

> **区分**: `documented` — 9.19.1 でバーストを変更した QoS ポリシーグループは、9.18.1 へ revert する前に 3 値（burst-percent / burst-iops / burst-duration）を 0 に戻す必要があります。出典は [ONTAP revert: QoS ポリシーグループの変更](https://docs.netapp.com/us-en/ontap/revert/modify-qos-policy-groups.html) です。

**FSx for ONTAP でダウングレード（revert）が運用上できるかは別問題で、本ノートでは未検証です。** バースト設定を 0 に戻す手順そのものはドキュメントに記載があるものの、FSx for ONTAP のマネージド環境で revert を実行できるかは確認していません。

---

### 変更できる面と変更できない面

**確認したのは ONTAP REST / CLI 経由のみです。** この経路ではバーストのデフォルト値を変更でき、実 I/O にも反映されます。

**AWS マネジメントコンソールと FSx for ONTAP の AWS API では設定できません。** これらにはバーストオプションに対応するパラメータがありません。FSx for ONTAP では QoS ポリシーグループ全般が ONTAP 管理面の管轄であり、バーストのデフォルト値変更もその一部です。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| FSx for ONTAP だとバーストのデフォルト値は変更できない | **ONTAP 9.19.1P2 で変更でき、実 I/O にも反映されました。** 経路は ONTAP REST / CLI です |
| このオプションは adaptive QoS 用 | **通常の throughput ceiling 用ポリシーグループに適用されます。** adaptive-policy-group の REST スキーマに burst フィールドは現れませんでした |
| AWS コンソールや FSx for ONTAP の AWS API から設定できる | **対応パラメータがありません。** ONTAP 管理面から設定します |
| burst-percent と burst-iops は併用できる | **相互排他です。** 絶対 IOPS で指定するなら先に burst-percent を 0 に戻します |
| burst-iops は任意の値を取れる | **max-throughput（ceiling IOPS）より大きい必要があります。** ceiling 未満は ONTAP が拒否します |
| 相互排他や値の下限は FSx for ONTAP の制約 | **ONTAP 本体の制約です。** FSx for ONTAP がブロックしているのではありません |
| 設定が通れば挙動も変わる、は確認しなくてよい | **設定受理と実 I/O 挙動は別の確認です。** 本ノートは両方を確認しています |

---

### 参照した一次情報

| 論点 | 出典 |
|---|---|
| QoS ポリシーグループで throughput ceiling を設定する手順。9.19.1 以降でバーストのデフォルト設定を変更できる旨 | [NetApp: Set a throughput ceiling with QoS](https://docs.netapp.com/us-en/ontap/performance-admin/set-throughput-ceiling-qos-task.html) |
| throughput 保証（floor）を設定する手順。バーストオプションが通常の policy-group に関わる文脈 | [NetApp: Set a throughput floor (guarantee) with QoS](https://docs.netapp.com/us-en/ontap/performance-admin/guarantee-throughput-qos-task.html) |
| burst-percent / burst-iops / burst-duration の定義、既定値、相互排他、burst-iops が max-throughput 未満なら max-throughput が使われる旨 | [NetApp: qos policy-group create](https://docs.netapp.com/us-en/ontap-cli/qos-policy-group-create.html) |
| ceiling が最大 10% 超過しうる、バースト時は最大 50% まで、トークンが 150% まで蓄積したときバーストが発生する挙動 | [NetApp: Load balancing concept](https://docs.netapp.com/us-en/ontap/concepts/load-balancing-concept.html) |
| 9.18.1 へ revert する前にバースト 3 値を 0 に戻す必要がある旨 | [NetApp: Modify QoS policy groups before reverting](https://docs.netapp.com/us-en/ontap/revert/modify-qos-policy-groups.html) |

---

### 関連ドキュメント

- [Domain — 性能](../README.md) — このモジュールのハブ
- [単一接続で測った値はストレージの性能ではない](a-single-connection-measures-the-client.md) — 性能値を測るときの条件の記録
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — 性能](../README.md)

---

## 自環境での確認手順

**まず読み取り専用で現在のバースト設定を確認します。** 次の手順は既存の QoS ポリシーグループに触れません。

ONTAP REST private CLI で現在のバースト設定を読む例です。

```console
GET /api/private/cli/qos/policy-group?fields=policy_group,max_throughput,burst_percent,burst_duration,burst_iops
```

CLI では次の相当コマンドです。

```console
qos policy-group show -instance
```

### 期待結果

各ポリシーグループの `max_throughput`（ceiling）とバースト 3 値が返ります。バーストを変更していなければ、burst_percent が 50、burst_duration が 1、burst_iops が 0 のまま表示されます。

### AWS 側から ONTAP 管理面に到達する前提

> **区分**: `verified` — 2026-10-19、ap-northeast-1、ONTAP 9.19.1P2 の検証用 FSx for ONTAP ファイルシステムで `aws fsx describe-file-systems` による管理エンドポイント取得を確認しました。

ONTAP 管理面（REST private CLI / CLI）は **VPC 内からのみ** 到達します。本文の「変更できる面と変更できない面」で述べたとおり、これらのバーストフィールドには AWS API 側の相当パラメータがないため、設定経路は ONTAP 管理面になります。

管理エンドポイントの DNS 名と IP は AWS CLI で取得します。

```console
aws fsx describe-file-systems --file-system-id <file-system-id> \
  --query 'FileSystems[0].OntapConfiguration.Endpoints.Management'
```

これが `DNSName` と `IpAddresses`（管理エンドポイント）を返します。VPC 内のホスト（例: Amazon EC2 インスタンスや踏み台）から HTTPS 443 で到達します。その経路のセキュリティグループでエンドポイントへの 443 を許可しておく必要があります。

認証は ONTAP 管理ユーザー（`fsxadmin`）で行います。認証情報は AWS Secrets Manager に置き、呼び出し時に読み取ってください。コマンドに直接埋め込まないでください。以降のコマンドは ONTAP REST private CLI（`/api/private/cli/...`）を使い、この管理エンドポイントに対して HTTP Basic 認証で到達します。

### 検証用ポリシーグループでの作成・変更・読み戻し・削除

> **区分**: `verified` — 実機の FSx for ONTAP ファイルシステム（ONTAP 9.19.1P2, ap-northeast-1, 2026-10-19）で、以下の REST private CLI リクエストが記載どおりの HTTP ステータスと読み戻し値を返すことを確認しました。

**実際に変更して試す場合は、検証用のポリシーグループを作って適用し、確認後に削除する可逆な範囲で行ってください。** 本番ボリュームに適用しているポリシーグループの値を直接変更すると、そのボリュームの I/O 挙動が即座に変わります。

下の 4 手順表の各ステップに対応するコマンドを示します。`<name>` / `<svm>` / `<volume>` はプレースホルダです。

ステップ 1-2（ceiling とバーストを付けた検証用ポリシーグループの作成）— REST private CLI POST:

```console
POST /api/private/cli/qos/policy-group
{"policy_group":"<name>","vserver":"<svm>","max_throughput":"2000IOPS","burst_percent":25,"burst_duration":5}
```

HTTP 201 を返します（読み戻し: `max_throughput:2000IOPS, burst_percent:25, burst_duration:5`）。

読み戻し:

```console
GET /api/private/cli/qos/policy-group?policy_group=<name>&fields=policy_group,max_throughput,burst_percent,burst_duration,burst_iops
```

burst_percent から burst_iops へ切り替える（相互排他のため、先に percent を 0 にリセットしてから iops を設定する）2 回の PATCH:

```console
PATCH /api/private/cli/qos/policy-group?policy_group=<name>
{"burst_percent":0}
```

続けて:

```console
PATCH /api/private/cli/qos/policy-group?policy_group=<name>
{"burst_iops":3000}
```

それぞれ HTTP 200 を返します（読み戻し: `burst_iops:3000`、`burst_percent` は返らなくなる。本文が述べた相互排他制約の実機での確認であり、先に 0 リセットする順序が必要な理由でもあります）。

ステップ 4（削除。可逆な状態に戻す）:

```console
DELETE /api/private/cli/qos/policy-group?policy_group=<name>
```

HTTP 200 を返します（読み戻し `num_records: 0`）。

> **区分**: `documented` — REST ではなく ONTAP CLI を使う場合の相当コマンドです。本ノートの検証で実行したのは上記の REST private CLI 経路のみのため、下の素の CLI 文字列は NetApp の `qos policy-group create` リファレンス（<https://docs.netapp.com/us-en/ontap-cli/qos-policy-group-create.html>）に基づく `documented` として扱います。

```console
qos policy-group create -policy-group <name> -vserver <svm> -max-throughput 2000IOPS -burst-percent 25 -burst-duration 5
qos policy-group modify -policy-group <name> -burst-percent 0
qos policy-group modify -policy-group <name> -burst-iops 3000
qos policy-group delete -policy-group <name>
```

### 検証用ボリュームへの適用（手順 3）

> **区分**: `documented` — ボリュームへの適用は本ノートの検証では実機に対して実行していません（既存ボリュームは他の検証作業に属するため触れていません）。作成・変更・読み戻し・削除の経路は実証済みですが、ボリューム適用の形は NetApp ドキュメントに基づく `documented` です。

ポリシーグループをボリュームへ適用するコマンドの形です。

```console
volume modify -vserver <svm> -volume <volume> -qos-policy-group <name>
```

REST private CLI では `PATCH /api/private/cli/volume?vserver=<svm>&volume=<volume>` にボディ `{"qos_policy_group":"<name>"}` を送ります。detach はポリシーグループに `none` を指定します（`volume modify ... -qos-policy-group none`、いずれも `documented`）。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 検証用の QoS ポリシーグループを ceiling（max-throughput）付きで作成する | create が HTTP 201 で通ること（`verified`） |
| 2 | burst-percent / burst-duration / burst-iops を変更する | modify が HTTP 200 で通り、読み戻しで値が確定すること（`verified`） |
| 3 | 検証用ボリュームにポリシーグループを適用し、idle 後に I/O を流す | ceiling を超えるバーストが指定どおり発生すること（適用コマンドの形は `documented`、実機未実行） |
| 4 | ポリシーグループをボリュームから detach し削除する | 読み戻しで対象が消えること（削除は `verified`、detach の形は `documented`） |

手順 3 で挙動を観測するには、per-second の IOPS を記録できる負荷ツール（例: fio の per-second ログ）が必要です。1 回の平均値だけでは、ピークの超過幅と持続時間を分離できません。

<!-- lang-switcher:start -->
🌐 [日本語](qos-burst-defaults-are-user-modifiable.md) | [English](../../../../en/domains/performance/notes/qos-burst-defaults-are-user-modifiable.md) | [🏠 リポジトリトップ](../../../../../README.md)
<!-- lang-switcher:end -->
