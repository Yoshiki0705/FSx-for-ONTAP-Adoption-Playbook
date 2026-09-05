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

> **区分**: `verified`（検証日 2026-09-05、`ap-northeast-1`、`SINGLE_AZ_2` 第 2 世代 1 HA ペア、ONTAP 9.18.1P5、Amazon Linux 2023 と Windows Server 2022）— パス数・ALUA の分かれ方・冪等でないこと・各既定値。
> **フェイルオーバーの所要時間は測れていません（`documented`）。** ホスト側からパス障害を誘発する試みが 2 回失敗し、パスが落ちなかったため測定になっていません。詳細は [測れなかったこと](#測れなかったこと) にあります。
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

## 測れなかったこと

**フェイルオーバーの所要時間は測れていません。** ホスト側からパス障害を誘発する試みが 2 回失敗しました。

| 試み | 結果 |
|---|---|
| Windows のファイアウォールで 1 つのポータル宛の TCP 3260 を outbound で遮断 | **パス数は 16 のまま。** 確立済みの iSCSI セッションは影響を受けませんでした。20 秒間の書き込み 40 回で失敗 0 |
| そのポータルへの接続に対する `Disconnect-IscsiTarget` | **セッション数は 16 のまま** |

**80 回の書き込みで失敗が 0 でしたが、パスが落ちていないので、これはフェイルオーバーの証拠ではありません。** 「何も壊れていない間、書き込みが通り続けた」ことの証拠です。

**LIF を管理面から落とす方法は試していません。** Amazon FSx が管理する LIF の状態を変更する操作であり、検証の副作用が読み切れないため行いませんでした。

**AWS のドキュメントは、スループット容量の変更に伴うフェイルオーバーが NFS / SMB / iSCSI に透過的であると記載しています。** NVMe/TCP は名指しされていません。**未記載を非対応と読み替えないでください。**

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
| 12 | 検証環境で LIF を落とすかネットワークを切り、I/O が継続するかと所要時間を測る | **このノートで測れなかった部分。検証環境で行ってください** |

手順 8 と 12 は**検証環境で行ってください。** 手順 8 は本番でパス数を倍にします。

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
| このノートでフェイルオーバー時間が分かる | **測れていません。** 誘発の試みが 2 回失敗しました |

---

## 検証環境

| 項目 | 値 |
|---|---|
| ONTAP バージョン | 9.18.1P5 |
| リージョン | `ap-northeast-1` |
| デプロイタイプ | `SINGLE_AZ_2`（第 2 世代、1 HA ペア） |
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
| スループット容量の変更に伴うフェイルオーバーが NFS / SMB / iSCSI に透過的であること | [AWS: Managing throughput capacity](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/managing-throughput-capacity.html) |
| 第 2 世代のスループット上限（Multi-AZ 6,144 MBps、Single-AZ 73,728 MBps） | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |
| NVMe/TCP が iSCSI に比べ MPIO の構成を単純にすること | [AWS: FSx for ONTAP supports NVMe-over-TCP](https://aws.amazon.com/about-aws/whats-new/2024/07/amazon-fsx-netapp-ontap-nvme-over-tcp) |

---

## 関連ドキュメント

- [Domain — ブロックストレージ](../README.md) — このモジュールのハブ
- [ブロックプロトコルの選択肢は世代と HA ペア数で先に狭まる](protocol-choice-is-bounded-before-you-choose.md) — LIF とポートの前提
- [LUN と igroup は AWS の API の外側にある](block-objects-are-outside-the-aws-api.md) — 3 つ目の制御面としてのホスト
- [LUN の並べ方が決めているのは復旧の粒度](lun-layout-decides-recovery-granularity.md) — Selective LUN Map と `lun move`
- [スループットは 1 つの設定値では決まらない](../../performance/notes/where-throughput-is-determined-and-shared.md) — 8 セッションの根拠になっている帯域
- [ブロックストレージ横断リソースマップ](../../../reference/block-storage-resource-map.md) — 資料間の食い違いの一覧
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — ブロックストレージ](../README.md)
