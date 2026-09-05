---
title: パスはフェイルオーバーの仕組みそのもの — 手順どおりに作ると推奨の 4 倍のパスが立つ
lifecycle: [build, operate, design]
domains: [block-storage, performance]
evidence: verified
verified_on: 2026-09-05
region: ap-northeast-1
ontap_version: 9.18.1P5
lang: ja
---

# パスはフェイルオーバーの仕組みそのもの

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)

---

## 結論

**ブロックストレージでは、ファイルサーバーが切り替わったときに I/O を継続させる仕組みはホスト側の multipath です。** ストレージ側は複数のパスを見せるところまでで、どれを使うかを決めるのはホストです。**この分界線がファイル共有との一番大きな違いです。**

そして **AWS の手順どおりに構成すると、NetApp が推奨する上限の 4 倍のパスが立ちます。**

検証環境で AWS の指示（1 ノードあたり 8 セッション）に従うと、**LIF 2 本 × 8 セッション = 16 セッション**になり、**1 LUN あたり 16 パス**が現れました。ALUA の優先度で **prio=50 の 8 本（active）と prio=10 の 8 本（enabled）**に分かれます。Windows でも同じで、**16 パスが Active/Optimized 8 本と Active/Unoptimized 8 本**に分かれました。

**一方 NetApp の Linux SAN ホスト構成のドキュメントは、AFF/FAS について「1 つの LUN に 4 パス超は必要なく、4 本を超えると障害時に問題を起こしうる」と記載しています。** どちらも公式の記載で、噛み合っていません。

さらに **接続手順は冪等ではありません。** Windows で 8 接続のループを同じポータルに対してもう一度回すと、**セッションが 16 から 24 に、パスも 24 本に増えました。** 警告は出ません。

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`SINGLE_AZ_2` および `MULTI_AZ_2` の第 2 世代 1 HA ペア、ONTAP 9.18.1P5、Amazon Linux 2023 と Windows Server 2022）— パス数・ALUA の分かれ方・冪等でないこと・各既定値・**フェイルオーバー時の I/O 継続と所要時間**。
> **フェイルオーバーは Multi-AZ 環境で 1 回測りました。** 結果は [実測したフェイルオーバー](#実測したフェイルオーバー) にあります。**iSCSI は無停止、NVMe/TCP は 423.8 秒の断**でした。
> **性能値は含めません。** 自環境での確認手順は [自環境での確認手順](#自環境での確認手順) にあります。

---

## パス数が決まる仕組み

**FSx for ONTAP の 1 つの SVM には iSCSI の LIF が 2 本あります。** 検証環境では `iscsi_1`（ノード -01）と `iscsi_2`（ノード -02）で、**どちらも `data_iscsi` と `data_nvme_tcp` の両方を持っていました。** NFS と SMB は別の LIF です。

**この 2 本は SVM 単位です。** 2 つ目の SVM を作ると、そちらにも `iscsi_1` と `iscsi_2` ができました。**SVM を絞らずに LIF を数えると本数を誤ります。**

パス数は次の積になります。

```text
パス数 = LIF の本数 × 1 LIF あたりのセッション数
```

| 設定 | 検証結果 |
|---|---|
| LIF 2 本、セッション数の既定（1） | 2 パス |
| LIF 2 本、AWS 指示の 8 セッション | **16 パス** |
| 上に 8 接続のループをもう 1 回 | **24 パス** |

**AWS が 8 という数を出している根拠は帯域です。** 1 セッションあたり最大 625 MBps、8 セッションで 40 Gbps / 5,000 MBps とし、**「最上位のスループット容量 4,000 MBps を賄える」**と書かれています。**4,000 MBps は第 1 世代の上限です。** 第 2 世代の上限は Multi-AZ で 6,144 MBps、Single-AZ で 73,728 MBps なので、**この 8 という数は第 1 世代を前提にした計算です。**

---

## ALUA の優先度と、それが意味すること

検証環境の `multipath -ll` は次の形でした。

```text
3600a09806c5742304b5d2f656c533466 dm-1 NETAPP,LUN C-Mode
size=20G features='3 queue_if_no_path pg_init_retries 50' hwhandler='1 alua' wp=rw
|-+- policy='service-time 0' prio=50 status=active
| |- 8 本
`-+- policy='service-time 0' prio=10 status=enabled
  |- 8 本
```

| 表示 | 意味 |
|---|---|
| `hwhandler='1 alua'` | ALUA が有効。**ONTAP は iSCSI と FC で ALUA、NVMe で ANA を使います** |
| `prio=50 status=active` | LUN を所有するノードへのパス。**通常の I/O はここを通ります** |
| `prio=10 status=enabled` | HA パートナー経由のパス。**所有ノードが落ちたときに使われます** |
| `queue_if_no_path` | 全パスが落ちたとき、エラーを返さずキューに溜めます |
| `policy='service-time 0'` | NetApp が推奨するパスセレクタ |

Windows では同じものが `TPG_State` として現れました。**Active/Optimized（TPG_Id 1000）が 8 本、Active/Unoptimized（TPG_Id 1001）が 8 本**、負荷分散は `Round Robin with Subset`、ALUA は `Implicit Only` です。

**両方のプラットフォームで、優先度の高いパスと低いパスが同数になりました。** これは LIF が 1 ノードに 1 本ずつあることの帰結です。

---

## ホスト側で変える必要がある既定値

**既定のままでは AWS の想定と違う挙動になります。** 検証環境で確認した既定値です。

| 項目 | 既定値 | AWS の指示 |
|---|---|---|
| Linux `node.session.timeo.replacement_timeout` | **120** | **5** |
| Windows `LoadBalancePolicy` | **None** | **RR**（round robin） |
| Windows `PathVerificationState` | **Disabled** | **Enabled** |
| Windows `PDORemovePeriod` | 20 | NetApp Windows Host Utilities が変更 |
| Windows `DiskTimeoutValue` | 60 | 同上 |

**`replacement_timeout` の 120 秒は、パスが落ちてから I/O をエラーにするまでの待ち時間です。** 5 に変えることで切り替わりが速くなります。**変えないままだと、切り替わったつもりで 2 分待つ構成になります。**

**Windows の `Set-MPIOSetting` は「Settings changed, reboot required」を返しました。** 設定は再起動後に効きます。**構築手順に再起動を入れておかないと、設定したつもりで反映されていない状態になります。**

**`MSFT2005 / iSCSIBusType_0x9` は、`Enable-MSDSMAutomaticClaim -BusType iSCSI` を実行した時点で `Get-MSDSMSupportedHW` に載っていました。** AWS が指示する `New-MSDSMSupportedHW` は、自動クレームを有効にしてあれば既に満たされています。

---

## multipath.conf の置き方

**AWS は `mpathconf --enable --with_multipathd y` を指示します。** 検証環境ではこれが **334 バイトの `/etc/multipath.conf`** を作りました。

**NetApp のドキュメントは 0 バイトの `/etc/multipath.conf` を推奨しています。** 空のファイルを置くと、NetApp がコンパイル済みで持っている推奨値が読み込まれます。

**検証環境では、334 バイトのファイルがあっても NetApp の推奨値どおりに動いていました**（`service-time 0`、`queue_if_no_path`、`group_by_prio` 相当の 2 グループ構成）。**334 バイトの内容が推奨値を上書きしなかった、というのがこの環境での結果です。** ただし **2 つの指示は違うものなので、どちらに従ったかを記録してください。**

NetApp が挙げている推奨値のうち、確認できたものと確認していないものを分けます。

| 値 | 検証環境で確認できたか |
|---|---|
| `path_selector "service-time 0"` | **確認**（`policy='service-time 0'`） |
| `no_path_retry queue` | **確認**（`features='3 queue_if_no_path ...'`） |
| 優先度でのパスグループ分け | **確認**（prio 50 / 10 の 2 グループ） |
| `dev_loss_tmo infinity`、`fast_io_fail_tmo 5`、`polling_interval 5`、`path_checker tur`、`detect_prio yes` | **確認していません** |

---

## パス数の設計

**「多いほうが安全」ではありません。** 2 つの公式記載を並べます。

| 出典 | 記載 |
|---|---|
| NetApp: Multipathing | **1 ノードあたり 8 パスを超えないこと。** LUN あたり reporting node ごとに最低 2 パス。Selective LUN Map、portset、igroup、FC ゾーニングでパス数を制限すること |
| NetApp: Linux SAN host configuration | **AFF/FAS では 1 LUN に 4 パス超は必要なく、4 本を超えると障害時に問題を起こしうる** |
| AWS: Provisioning iSCSI | **1 ノード・1 AZ あたり 8 セッション** |

**「1 ノードあたり 8 パス」と「1 LUN あたり 4 パス」は別の数え方です。** LIF が 2 本ある構成で 1 ノードあたり 8 パスにすると、1 LUN あたりは 16 パスになります。**AWS の指示は前者の上限に張り付き、後者の推奨を 4 倍超えます。**

**判断はトレードオフです。** 帯域が要るなら AWS の 8 セッションに根拠があり、パス数を抑えたいなら NetApp の 4 に根拠があります。**どちらを採ったかと、その理由を設計文書に書いてください。** 帯域の見積りが第 2 世代の上限に対して行われているかも確認してください（AWS の 8 は第 1 世代の 4,000 MBps を前提にしています）。

**Selective LUN Map は既定で有効でした。** 検証環境の LUN マップは reporting node として **所有ノードと HA パートナーの 2 ノード**を列挙していました。1 HA ペアの構成ではこれが全ノードです。**HA ペアが複数ある構成では、これがパス数を抑える仕組みとして効きます。**

---

## 冪等でない接続手順

**Windows で 8 接続のループを 1 つのポータルに対してもう一度実行すると、セッションが 16 から 24 に増えました。** パス数も 24 になり、Active/Optimized 8 本と Active/Unoptimized 16 本という非対称な形になりました。

**エラーも警告も出ません。** `Connect-IscsiTarget` は既存セッションを検出せず、要求された数だけ追加します。

**帰結が 2 つあります。**

| 帰結 | 内容 |
|---|---|
| 手順書の再実行で増える | 構築手順を 2 回流すと、パス数が想定の 2 倍になります |
| 状態から逆算できない | 「8 セッション」と書いた手順書は、**現在いくつあるかを確認してから実行しないと意味を持ちません** |

**構築手順には、実行前のセッション数の確認と、必要なら切断を入れてください。** AWS が提供している検証スクリプト `CheckiSCSI.ps1` はセッション数とノード分散と MPIO の状態を確認します。

---

## NVMe/TCP のパスがカーネル構成に依存すること

**Amazon Linux 2023 では NVMe/TCP のネイティブ multipath が有効になっていませんでした。**

検証環境のカーネル（`6.18.44-99.149.amzn2023.x86_64`）は **`CONFIG_NVME_MULTIPATH is not set`** でした。帰結です。

| 観測 | 内容 |
|---|---|
| `/sys/module/nvme_core/parameters/multipath` | **存在しません。** `nvme_core` が組み込みで、この設定が無効なためです。**AWS の手順が指示する確認ステップが実行できません** |
| `nvme list-subsys` | 1 つの subsystem に 2 本の live な TCP コントローラ。ここまでは想定どおり |
| `nvme list` | **同じ namespace が `/dev/nvme2n1` と `/dev/nvme3n1` の 2 デバイスとして見えました。** `wwid` は両方同一 |
| subsystem の `iopolicy` | 属性が存在しません |

**AWS の手順は RHEL 9.3 を前提にしています。** そこではネイティブ multipath が有効です。**同じ手順を Amazon Linux 2023 で実行すると、1 つの namespace が 2 つのディスクとして見え、片方だけを使うとフェイルオーバーが効きません。**

**これは「NVMe/TCP が使えない」ではありません。** 接続は成立しています。**multipath が成立していないだけです。** 自環境のカーネルで `CONFIG_NVME_MULTIPATH` を確認してください。

---

## 実測したフェイルオーバー

**ホスト側から誘発する試みは 2 回失敗しました。**

| 試み | 結果 |
|---|---|
| Windows のファイアウォールで 1 つのポータル宛の TCP 3260 を outbound で遮断 | **パス数は 16 のまま。** 確立済みの iSCSI セッションは影響を受けませんでした |
| そのポータルへの接続に対する `Disconnect-IscsiTarget` | **セッション数は 16 のまま** |

**誘発できる方法は 1 つだけです。スループット容量の変更です。** `storage failover takeover` は使えません。**FSx for ONTAP は HA の状態を `fsxadmin` に見せておらず、`storage failover show` は空のテーブルを返します。** そして **第 2 世代はスループット容量の変更の間に 6 時間のクールダウンがあるので、1 つの環境で測れるのは 1 回だけです。**

Multi-AZ の環境で 384 → 768 MBps に変更し、**iSCSI と NVMe/TCP の両方に負荷を掛けた状態で 1 秒間隔の 4 KiB の direct write を記録しました。**

| 対象 | サンプル数 | 失敗 | 最も遅い 1 回 | 断の長さ |
|---|---|---|---|---|
| iSCSI の LUN（`dm-multipath` 経由） | 1,161 | **0** | **2.101 秒** | **なし** |
| NVMe/TCP の namespace（デバイスノード 1 つ、カーネルのネイティブ multipath 無効） | 752 | 11 | **412.741 秒** | **423.8 秒** |

**同時に走らせていた PostgreSQL の負荷は止まらず、約 390 万行まで進みました。**

時系列です。

| 時刻（UTC） | 出来事 |
|---|---|
| 07:27:40 | スループット容量の変更を要求 |
| 07:28:10 → 07:28:31 の間 | NFS / SMB の floating アドレスの `/32` ルートのターゲットが 1a の ENI から 1c の ENI に書き換わる |
| 07:28:46 | **ANA が反転。** 1c 側の LIF が `optimized`、1a 側が `non-optimized` に。**要求から約 66 秒** |
| 07:28:48 → 07:29:11 | `dm-multipath` が追従。片方のパスグループが `prio=0` になり、やがて落ちる |
| 07:29:26 | **両プロトコルで唯一の遅い書き込み。** iSCSI 2.101 秒、NVMe/TCP 2.201 秒 |
| 07:29:33 | **`nvme3`（1a 側 LIF のコントローラ）が `connecting` に。** 進行中の NVMe の書き込みがブロック |
| 07:29:41 → 07:36:20 | ノード -01 の置き換えの間、`nvme3` は `connecting` のまま |
| 07:36:22 | **iSCSI が 2 つのパスグループに復帰** |
| 07:36:27 → 07:36:37 | `nvme3` が `live` に戻り、ANA は `change` を経て `non-optimized`。**NVMe の書き込みが再開** |
| 07:39:26 → 07:39:52 の間 | floating アドレスの `/32` ルートが 1a の ENI に戻る（フェイルバック） |
| 07:49:38 | 変更が完了。**要求から約 22 分** |

**スループット容量の変更は単なるフェイルオーバーではありません。** AWS は **ファイルサーバーを直列に置き換える**と記載しており、順序は「フェイルオーバー → フェイルバック → 2 台目の置き換え」です。**だから全体で 22 分かかり、ノード 1 台が不在の時間が約 7 分になりました。** 文書にある「通常 60 秒未満」はフェイルオーバーそのものの時間で、**ANA が反転するまでの約 66 秒がそれに対応します。**

### iSCSI と NVMe/TCP で結果が分かれた理由

**iSCSI は透過的でした。** `dm-multipath` が 2 本目のパスに切り替え、**エラーは 1 度も出ず、コストは約 2.1 秒の停止だけ**でした。AWS がスループット容量のページで iSCSI を透過的と書いている内容と一致します。

**NVMe/TCP は透過的ではありませんでした。** ただし **原因は FSx for ONTAP 側ではなくホストのカーネル構成です。**

| 段階 | 起きたこと |
|---|---|
| 原因 | Amazon Linux 2023 のカーネルが **`CONFIG_NVME_MULTIPATH` 無効**でビルドされている |
| 帰結 1 | 1 つの namespace が **同じ `wwid` を持つ 2 つのデバイスノード**として現れる |
| 帰結 2 | アプリケーションはそのうち片方に紐づく。**切り替える先が存在しない** |
| 観測 | コントローラが落ちた側のデバイスへの書き込みが **412.741 秒ブロックしたのちエラー**になり、以後もコントローラが戻るまで失敗 |

**AWS が NFS / SMB / iSCSI を名指しして NVMe/TCP を名指ししていない理由が、ここに現れています。**

**「NVMe/TCP はフェイルオーバーできない」ではありません。** ネイティブ multipath が有効なカーネルなら 2 つのコントローラが 1 つのデバイスにまとまり、ANA に従って切り替わります。**ただしそれはこの検証で確認していません。** 確認したのは **AL2023 の既定のカーネルでは切り替わらない**ことです。

**NVMe/TCP を使うなら、カーネルの `CONFIG_NVME_MULTIPATH` を構築前に確認してください。** 無効なら、iSCSI を選ぶか、ネイティブ multipath が有効なディストリビューションを選ぶ判断になります。

**なお AWS の NVMe/TCP の手順は controller loss timeout を 1800 秒に指示しています。** 検証環境の断が 423.8 秒だったことと合わせると、**この値はコントローラが戻るまで待つための設定です。** 待てるかどうかはアプリケーション側の要件です。

**LIF を管理面から落とす方法は試していません。** Amazon FSx for ONTAP が管理する LIF の状態を変更する操作であり、検証の副作用が読み切れないため行いませんでした。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `network interface show -vserver <svm> -data-protocol iscsi` で LIF の本数を確認する（**SVM を指定すること**） | パス数の計算の片方 |
| 2 | `iscsiadm --mode session \| wc -l` と `multipath -ll` を並べて記録する | セッション数とパス数の関係 |
| 3 | `multipath -ll` の prio 値でグループが 2 つに分かれているかを確認する | ALUA が効いているか |
| 4 | `grep replacement_timeout /etc/iscsi/iscsid.conf` | **既定は 120。5 にするかを判断する** |
| 5 | `wc -c /etc/multipath.conf` | **0 バイトか、`mpathconf` が作った内容か。どちらに従ったかを記録する** |
| 6 | Windows で `Get-MSDSMGlobalDefaultLoadBalancePolicy` と `(Get-MPIOSetting).PathVerificationState` | **既定は None と Disabled** |
| 7 | Windows で `mpclaim -s -d 0` を実行し、パス総数と Active/Optimized の内訳を記録する | パス数と ALUA |
| 8 | 接続スクリプトを**2 回**流し、セッション数が増えるかを確認する | **冪等でないこと** |
| 9 | `grep CONFIG_NVME_MULTIPATH /boot/config-$(uname -r)` | **NVMe/TCP で multipath が成立するか** |
| 10 | NVMe/TCP 接続後、`nvme list` で同じ `wwid` のデバイスが複数出ていないかを確認する | multipath が効いていない兆候 |
| 11 | `lun mapping show -fields reporting-nodes` | Selective LUN Map が絞っている範囲 |
| 12 | 検証環境でスループット容量を変更し、**両プロトコルに負荷を掛けた状態で** 1 秒間隔の direct write の成否と所要時間を記録する | **フェイルオーバー時に I/O が継続するか。第 2 世代は変更間に 6 時間のクールダウンがあり、1 環境で 1 回しか測れません** |
| 13 | 同時に `nvme ana-log` とコントローラの `state` を 2 秒間隔で記録する | **ANA が反転した時点** |

手順 8 と 12 は**検証環境で行ってください。** 手順 8 は本番でパス数を倍にします。**手順 12 はプローブを先に動かし、記録先を確認してから変更を要求してください。** やり直しは 6 時間後です。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| フェイルオーバーはストレージ側が面倒を見る | **I/O を継続させるのはホスト側の multipath です** |
| multipath は任意 | **AWS のドキュメントは自動フェイルオーバーのために必須としています** |
| パスは多いほうが安全 | NetApp は **AFF/FAS で 1 LUN に 4 パス超は問題を起こしうる**としています |
| AWS の 8 セッションが常に正しい | **第 1 世代の 4,000 MBps を前提にした計算です。** 第 2 世代では再計算が必要です |
| iSCSI の LIF は 1 ファイルシステムに 2 本 | **SVM 単位で 2 本です。** SVM を増やすと増えます |
| iSCSI と NVMe/TCP は別の LIF を使う | **同じ LIF が両方の service を持っています** |
| 接続スクリプトは何度流しても同じ | **冪等ではありません。** 16 → 24 に増えました |
| Windows の MPIO 設定は実行した時点で効く | **再起動が必要と警告されます** |
| `mpathconf --enable` が NetApp 推奨の設定を作る | **NetApp は 0 バイトのファイルを推奨しています。** `mpathconf` は 334 バイトを作りました |
| NVMe/TCP なら multipath は自動 | **Amazon Linux 2023 ではカーネルで無効です。** 同じ namespace が 2 デバイスに見えます |
| `/sys/module/nvme_core/parameters/multipath` を見れば分かる | **AL2023 にはこのファイルがありません** |
| フェイルオーバーは iSCSI でも I/O エラーになる | **1,161 サンプルで失敗 0 でした。** 約 2.1 秒の停止のみ |
| NVMe/TCP も iSCSI と同様に透過的 | **AL2023 では透過的ではありませんでした。** 423.8 秒の断です。原因はカーネルの `CONFIG_NVME_MULTIPATH` 無効 |
| NVMe/TCP はフェイルオーバーできない | **カーネル構成の問題です。** ネイティブ multipath が有効な環境での挙動はこの検証では未確認 |
| `storage failover takeover` でフェイルオーバーを試せる | **`storage failover show` が空テーブルを返します。** 誘発手段はスループット容量の変更だけです |
| スループット容量の変更 = 60 秒未満のフェイルオーバー | **全体で約 22 分でした。** ファイルサーバーを直列に置き換えるためです。60 秒未満はフェイルオーバー単体の時間で、ANA の反転は約 66 秒でした |

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| デプロイタイプ | パス数・ALUA・冪等性・既定値は `SINGLE_AZ_2`。**フェイルオーバーの実測は `MULTI_AZ_2`**（どちらも第 2 世代、1 HA ペア） |
| スループット容量 | 384 MBps |
| Linux クライアント | Amazon Linux 2023、kernel 6.18.44-99.149.amzn2023.x86_64 |
| Windows クライアント | Windows Server 2022 Datacenter |
| iSCSI LIF | 2 本（SVM あたり、ノードごとに 1 本） |
| 検証日 | 2026-09-05 |

> **注意**: 上記はこの環境での実測であり、一般的なサービス上限や本番環境での再現を保証するものではありません。**パス数は LIF 本数とセッション数の設定で変わります。**

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| multipath が自動フェイルオーバーに必要であること、`replacement_timeout` を 5 にすること、`mpathconf --enable`、1 ノード・1 AZ あたり 8 セッション、WWID が `3600a0980` + serial hex であること | [AWS: Provisioning iSCSI for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-luns-linux.html) |
| Windows の MPIO 機能、`New-MSDSMSupportedHW`、`Set-MPIOSetting`、round robin、ポータルあたり 8 接続、`CheckiSCSI.ps1` | [AWS: Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) |
| NVMe/TCP の手順、`nvme connect-all -l 1800`、`/sys/module/nvme_core/parameters/multipath` の確認、前提クライアントが RHEL 9.3 であること、iSCSI と NVMe/TCP が同じ LIF を使うこと | [AWS: Provisioning NVMe/TCP for Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/provision-nvme-linux.html) |
| ONTAP が iSCSI で ALUA、NVMe で ANA を使うこと。1 ノードあたり 8 パスを超えないこと。LUN あたり最低 2 パス。Selective LUN Map と portset でパスを絞ること | [NetApp: Multipathing](https://docs.netapp.com/us-en/ontap/san-config/host-support-multipathing-concept.html) |
| 0 バイトの `/etc/multipath.conf` が推奨であること、推奨パラメータの一覧、AFF/FAS で 1 LUN に 4 パス超が問題を起こしうること | [NetApp: Linux SAN host configuration](https://docs.netapp.com/us-en/ontap-sanhost/hu-ol-9x.html) |
| Selective LUN Map が新しい LUN マップで既定で有効であること | [NetApp: Selective LUN Map](https://docs.netapp.com/us-en/ontap/san-admin/selective-lun-map-concept.html) |
| スループット容量の変更に伴うフェイルオーバーが NFS / SMB / iSCSI に透過的であること。ファイルサーバーが直列に置き換わること。フェイルオーバーの試験手段がスループット容量の変更であること | [AWS: Managing throughput capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html) |
| フェイルオーバーの契機が 4 つあること、通常 60 秒未満で完了すること、**透過的な対象として NFS と SMB のみを挙げていること**（上のページは iSCSI も挙げています） | [AWS: Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| 第 2 世代のスループット上限（Multi-AZ 6,144 MBps、Single-AZ 73,728 MBps） | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| NVMe/TCP が iSCSI に比べ MPIO の構成を単純にすること | [AWS: FSx for ONTAP supports NVMe-over-TCP](https://aws.amazon.com/about-aws/whats-new/2024/07/amazon-fsx-netapp-ontap-nvme-over-tcp) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [Multi-AZ が動かすのはアドレスではなくルート](multi-az-moves-a-route-not-an-address.md) — フェイルオーバーで書き換わるものと、動かないアドレス
- [igroup の外側にある 2 つの制御](igroups-are-not-the-only-access-control.md) — portset でパス数を絞る方法
- [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](protocol-choice-is-bounded-before-you-choose.md) — LIF とポートの前提
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 3 つ目の制御面としてのホスト
- [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) — Selective LUN Map と `lun move`
- [スループットは 1 つの設定値では決まらない](../../performance/notes/where-throughput-is-determined-and-shared.md) — 8 セッションの根拠になっている帯域
- [ブロックストレージ横断リソースマップ](../../../reference/block-storage-resource-map.md) — 資料間の食い違いの一覧
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
