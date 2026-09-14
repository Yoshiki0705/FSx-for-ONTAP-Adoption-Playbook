---
title: 端末別にできることの比較 — 端末を決めた時点で、ブロック・ファイル・オブジェクトのうち使える範囲が決まっている
lifecycle: [assess, design, build]
domains: [client-access, block-storage, multiprotocol-identity, data-utilization]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-clients-fsx.html
lang: ja
---

# 端末別にできることの比較

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md) | [Domain — クライアントアクセス](../../domains/client-access/README.md)

---

## 結論

**端末を決めた時点で、使えるストレージ形態が決まっています。** 設計の余地があるのは残った範囲だけです。

| 端末 | ファイル | ブロック | オブジェクト |
|---|---|---|---|
| **Windows** | ○ 標準機能 | ○ 標準機能 | ○ AWS CLI / SDK |
| **WSL2 の Linux** | ○ ディストリビューション次第 | **△ 既定カーネルに依存** | ○ AWS CLI / SDK |
| **Mac** | ○ 標準機能 | **× 同梱されていません** | ○ AWS CLI / SDK |
| Chromebook / iPad | **× マウントの仕組みがありません** | × | **△ ブラウザ経路のみ** |

**3 つの × が設計を動かします。**

1. **Mac にブロックの選択肢がありません。** LUN を触る作業を Mac の担当者に割り当てられません
2. **Chromebook と iPad はマウントできません。** ブラウザ経路を用意しない限り、この層は対象外です
3. **WSL2 のブロックはカーネル次第です。** 使える前提で設計すると、端末の WSL バージョンで結果が変わります

**そして 3 つすべてに共通する前提が 1 つあります。** どの端末もパブリックインターネットからは届きません。
経路の比較は [端末の到達経路の比較](endpoint-reachability-options.md) にあります。

> **区分**: `documented` — 各端末の可否は AWS / Microsoft / Apple / NetApp の公開情報に基づきます（2026-09-13 に確認）。
> **端末の実機での再現はまだ含みません。** 測定した項目は [Domain — クライアントアクセス](../../domains/client-access/README.md) のノート側に順次入ります。
> **性能値は含めません。** 端末経路で測ると VPN のトンネルと端末の NIC を測ることになります（[理由](../decision-trees/client-access-route.md#この決定木で帯域を測らない理由)）。

---

## 比較

| 観点 | Windows 端末 | WSL2 の Linux | Mac 端末 | ネイティブ Linux 端末 | WorkSpaces / AppStream | Chromebook / iPad |
|---|---|---|---|---|---|---|
| **SMB** | **標準機能**（エクスプローラ / `net use`） | `cifs-utils` 経由 | **標準機能**（Finder / `mount -t smbfs`）。**AWS は Mac には SMB を推奨** | `cifs-utils` 経由 | VDI の中の OS が決めます | **不可** |
| **NFS** | Services for NFS（機能追加が必要） | ディストリビューションの `nfs-common` | **標準機能**（`mount -t nfs`） | ディストリビューションの `nfs-common` | 同上 | **不可** |
| **iSCSI** | **標準機能**（iSCSI イニシエータ + MPIO） | **既定カーネルに `iscsi_tcp` があるかに依存** | **同梱されていません** | `open-iscsi` + `multipath-tools` | VDI のイメージ次第 | **不可** |
| **NVMe/TCP** | **ONTAP 側が Windows Server 未対応** | 同上（カーネル依存に加えて） | 手順が存在しません | カーネルに `CONFIG_NVME_MULTIPATH` が要る | イメージ次第 | **不可** |
| **S3 Access Points** | AWS CLI / SDK | AWS CLI / SDK | AWS CLI / SDK | AWS CLI / SDK | VDI の中から | **ブラウザ経路のみ** |
| **AD 参加の必要性** | **SMB は AD か workgroup のどちらでも可** | 同左 | 同左。ただし **AD 参加した Mac の検証はこのリポジトリにありません** | 同左 | VDI の設計に含まれます | — |
| **AWS の手順ページ** | [Windows 版](https://docs.aws.amazon.com/us_en/fsx/latest/ONTAPGuide/attach-windows-client.html) と [iSCSI 版](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html)。**どちらも EC2 の Windows Server を前提** | 専用ページはありません。[Linux 版](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-linux-client.html)を読み替えます | [macOS 版](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html)。**EC2 Mac インスタンスを前提** | [Linux 版](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-linux-client.html) | [WorkSpaces 版](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-workspaces.html) | ありません |
| **資格情報が残る場所** | Credential Manager、iSCSI の CHAP シークレット、`~/.aws/credentials` | `/etc/` 配下の credentials ファイル、`~/.aws/credentials`。**Windows 側とは別のファイルシステム** | キーチェーン、`~/.aws/credentials` | 同左 | VDI の中。端末には残りません | **端末に残りません**（ブラウザのセッション） |
| **主なトレードオフ** | **できることが最も多く、手順の前提が最もずれています。** AWS の手順が Server SKU 前提なので、クライアント SKU では読み替えが必要です | **Windows 端末があれば追加費用ゼロで Linux の道具が使えます。** 引き換えにネットワークとカーネルの境界が 2 つ増えます | **ファイルアクセスは素直で、ブロックの選択肢がありません。** AWS の手順も EC2 Mac 前提なので、実機からの経路は自分で設計します | **境界の問題が最も少ないです。** 引き換えに、端末として配備・管理する運用が必要です | **端末側の運用が消えます。** 引き換えに VDI の費用と、VDI 自体の運用が乗ります | **端末に何も入れません。** 引き換えにマウントの選択肢が全部消えます |

**表に「速い」を書いていないのは、端末経路では測る対象がストレージにならないためです。**

---

## × の根拠

**「できない」は主張なので、根拠の性質を分けて書きます。**

| 主張 | 根拠 | 出典の性質 |
|---|---|---|
| macOS に iSCSI イニシエータが同梱されていない | AWS が列挙するブロックの手順は Linux iSCSI / Windows iSCSI / Linux NVMe/TCP の 3 つで macOS が無く、サードパーティのイニシエータ実装が存在する | **AWS 公式（手順の不在）＋ コミュニティ。** Apple による「非対応」の明示的な記述は見つけていません |
| Chromebook / iPad でマウントできない | AWS の対応クライアントの列挙に含まれない | **AWS 公式（列挙に無いこと）。** 「非対応」と書かれているわけではありません |
| Windows Server と NVMe/TCP の組み合わせが使えない | Windows のサポート範囲はネイティブ NVMe ディスクに限られる | **NetApp KB。** [ブロックプロトコルとレイアウトの選択](../decision-trees/block-protocol-and-layout.md)に記録済み |
| `Install-WindowsFeature` がクライアント SKU で使えない | `ServerManager` モジュールに属する | **未確認。** Microsoft の一文としては確認しておらず、Windows 実機での確認を測定項目に入れています |
| WSL2 の既定カーネルに `iscsi_tcp` が無い | WSL2 はカスタムカーネルを使い、モジュールの追加にはカーネルのビルドが必要という報告が複数ある | **未確認。** 実機での確認を測定項目に入れています |

**「非対応」と「言及が無い」を混ぜないでください。** 上の 5 行のうち、AWS が明示的に非対応と書いているものは 1 つもありません。
機能は追加されるので、採用を決める前に現行のドキュメントを確認してください。

---

## 端末を選べる場合と選べない場合

**多くの場合、端末は選べません。** すでに配備されているものが前提です。その場合、この表は「何を諦めるか」の一覧として読んでください。

| 状況 | この表の読み方 |
|---|---|
| 端末が Mac で固定 | ブロックが必要な処理を、Mac ではない場所（EC2 / VDI / サーバー）に寄せる設計になります |
| 端末が Windows と Mac の混在 | **ファイルは共通に出せます。** ブロックは Windows だけに限定するか、両方で使わないかの判断です |
| WSL2 で開発している | ファイルとオブジェクトは WSL2 から、ブロックは Windows ホスト側から張る構成が素直です |
| Chromebook / iPad を含む | ブラウザ経路を用意しない限り、この層はデータに届きません |
| 端末を新たに選べる | **ネイティブ Linux 端末が境界の問題が最も少ないです。** ただし配備と管理の運用が新たに要ります |

---

## 選び方

**「どの端末が優れているか」ではありません。** 必要なストレージ形態から、使える端末が決まります。

| 必要なもの | 使える端末 | 注意 |
|---|---|---|
| ファイル共有だけ | **全部**（Chromebook / iPad を除く） | AD 参加か workgroup かは別の判断です |
| ブロック（LUN） | **Windows、ネイティブ Linux。** WSL2 は要確認 | Mac は選択肢に入りません |
| オブジェクト（S3 Access Points） | **全部** | インターフェースエンドポイントが要ります |
| 端末に何もインストールしない | **Chromebook / iPad / 任意のブラウザ**、または VDI | マウントの選択肢が消えます |
| 端末側の運用をしたくない | **WorkSpaces / AppStream** | VDI の費用と運用が乗ります |

**推奨案自身の制約も書きます。** ブロックが必要なら Windows かネイティブ Linux になりますが、
Windows は AWS の手順が Server SKU 前提でそのまま動かず、ネイティブ Linux は端末として配備・管理する運用が新たに発生します。
**どちらも「素直に動く」わけではありません。**

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 端末の一覧を OS とバージョンで棚卸しする | この表のどの列に当たるか |
| 2 | Windows: `Get-WindowsOptionalFeature -Online -FeatureName MultiPathIO` と `Get-Service MSiSCSI` | MPIO の有効化手段と iSCSI サービスの状態 |
| 3 | Mac: `which iscsiadm; ls /usr/sbin \| grep -i iscsi` | イニシエータの不在。**「無い」ことは自環境で確認するのが最も確実です** |
| 4 | WSL2: `wsl.exe --version`、`modprobe iscsi_tcp; echo $?`、`cat /etc/wsl.conf` | カーネルとネットワークモード |
| 5 | 各端末で `aws sts get-caller-identity` | AWS の資格情報が端末にどう置かれているか |
| 6 | 各端末で `mount` の出力を記録する | すでに何がマウントされているか |

**手順 3 と 4 が「× と △ の確認」です。** ここを飛ばして設計に入ると、端末の担当者に不可能な作業を割り当てることになります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| AWS が macOS を対応クライアントに挙げているので、Mac で全部できる | **対応しているのはファイルプロトコルです。** ブロックの手順は存在しません |
| AWS の macOS 手順があるので実機の Mac から使える | **手順は EC2 Mac インスタンスを前提に書かれています。** 実機からの経路は自分で設計します |
| WSL2 は Linux なので Linux 端末と同じ | **ネットワークとカーネルの境界が 2 つ増えます。** ブロックは既定カーネルに依存します |
| Windows なら AWS の iSCSI 手順をそのまま使える | **手順は Windows Server 2019 の EC2 を前提にしています。** MPIO の有効化コマンドと、渡すローカル IP の 2 か所が端末では変わります |
| Chromebook でも VPN を入れればマウントできる | **マウントの仕組みがありません。** VPN は経路の問題を解くだけです |
| VDI にすれば端末の制約が消える | **VDI の中の OS に移るだけです。** 消えるのは端末側の運用で、制約の表は VDI の OS の列を読むことになります |
| S3 Access Points は端末からインターネット経由で使える | **VPC 内のインターフェースエンドポイントが要ります。** ゲートウェイエンドポイントは VPN 経由の流入をルーティングしません |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| 対応クライアントの列挙、NFS v3 / v4.0 / v4.1 / v4.2、SMB 2.0 / 3.0 / 3.1.1、iSCSI、パブリックインターネットからのアクセスが非対応であること | [AWS: Supported clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-clients-fsx.html) |
| macOS への SMB 推奨、`mount -t smbfs` と `mount -t nfs` の形、EC2 Mac インスタンスを前提とした手順 | [AWS: Mounting volumes on macOS clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html) |
| Windows の SMB マウントに AD 参加または workgroup が必要であること | [AWS: Mounting volumes on Microsoft Windows clients](https://docs.aws.amazon.com/us_en/fsx/latest/ONTAPGuide/attach-windows-client.html) |
| Windows の iSCSI 手順が Windows Server 2019 の EC2 を前提とすること、`Install-WindowsFeature Multipath-IO`、NetApp Windows Host Utilities、`InitiatorPortalAddress` にローカル IP を渡すこと、iSCSI が HA ペア 6 組以下で使えること | [AWS: Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) |
| Linux クライアントの NFS マウントが既定で hard mount であること | [AWS: Mounting volumes on Linux clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-linux-client.html) |
| AWS が列挙するブロックの手順が 3 つで macOS が無いこと | [AWS: Accessing your FSx for ONTAP data](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-from-on-premises.html) |
| WorkSpaces と併用する手順 | [AWS: Using Amazon WorkSpaces with FSx for ONTAP](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-workspaces.html) |
| WSL2 の仮想化されたネットワークと mirrored モード | [Microsoft: Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking) |
| WSL2 でカーネルモジュールを増やすにはカーネルのビルドが要るという報告 | [Microsoft: How to use the Microsoft Linux kernel v6 on WSL2](https://learn.microsoft.com/en-us/community/content/wsl-user-msft-kernel-v6) |
| macOS にイニシエータが同梱されていないこと、サードパーティ実装の存在 | [Apple Support Communities](https://discussions.apple.com/thread/250425330) · [iscsi-osx/iSCSIInitiator](https://github.com/iscsi-osx/iSCSIInitiator) |
| Windows Server と NVMe/TCP の組み合わせが ONTAP 側で非対応であること | [ブロックプロトコルとレイアウトの選択](../decision-trees/block-protocol-and-layout.md)（NetApp KB を出典に記録済み） |
| ゲートウェイエンドポイントが VPN / Direct Connect / Transit Gateway / ピアリング経由の流入をルーティングしないこと | [S3 Access Point の権限設計](../../domains/security-governance/notes/access-point-authorization-layers.md)（`verified`） |

---

## 関連ドキュメント

- [比較マトリクス](README.md) — このモジュールのハブ
- [端末の到達経路の比較](endpoint-reachability-options.md) — 端末より先に決まる経路の比較
- [端末からデータに届く経路の決定木](../decision-trees/client-access-route.md) — この表を判断順に並べた決定木
- [Domain — クライアントアクセス](../../domains/client-access/README.md) — 端末側の罠のノート
- [ファイルストレージの選択肢の比較](file-storage-options.md) — サービスを選ぶ側の比較
- [ブロックストレージの選択肢の比較](block-storage-options.md) — ブロックにするかどうかの判断
- [単一接続で測った値はストレージの性能ではない](../../domains/performance/notes/a-single-connection-measures-the-client.md) — 端末で測った数値の扱い
- [知見の分類ポリシー](../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md) | [Domain — クライアントアクセス](../../domains/client-access/README.md)
