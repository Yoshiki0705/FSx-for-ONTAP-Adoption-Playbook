---
title: 端末の種類がプロトコルを先に狭める — Mac にブロックの選択肢が無いことは設計の制約であって設定の問題ではない
lifecycle: [assess, design]
domains: [client-access, block-storage]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-from-on-premises.html
lang: ja
---

# 端末の種類がプロトコルを先に狭める

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

---

## 結論

**端末が決まっている場合、使えるストレージ形態も決まっています。** 設計の余地は残った範囲だけです。

| 端末 | ファイル | ブロック | オブジェクト |
|---|---|---|---|
| Windows | ○ | ○ | ○ |
| WSL2 の Linux | ○ | **△ 既定カーネルに依存** | ○ |
| Mac | ○ | **× イニシエータが同梱されていません** | ○ |

**Mac × ブロックの × が最も設計を動かします。** LUN を扱う作業を Mac の担当者に割り当てられず、
その作業を別の場所（VPC 内のインスタンス、VDI、サーバー）に寄せる設計になります。

**AWS が列挙しているブロックの手順は 3 つで、macOS はその中にありません。**
iSCSI for Linux、iSCSI for Windows、NVMe/TCP for Linux です。

> **区分**: `documented` — AWS / NetApp / Microsoft のドキュメントと、macOS 側の一次情報の不在に基づきます（2026-09-13 に確認）。
> **`documented` に留めた理由**: 手元の Mac で `which iscsiadm` と `/usr/sbin` の走査を行い、
> イニシエータが無いことを 2026-09-13 に確認しています。**ただしこれは端末の状態の観察で、
> ファイルシステムの挙動の再現ではないため、`verified` が要求する `region` が意味を持ちません。**
> 区分は出どころで決まるので、観察したことを本文に書いて `documented` のままにしています。

---

## × と △ の根拠

**「できない」は主張です。根拠の性質を分けます。**

| 主張 | 根拠 | 出典の性質 |
|---|---|---|
| macOS に iSCSI イニシエータが同梱されていない | AWS のブロック手順 3 つに macOS が無く、サードパーティのイニシエータ実装が存在し、当方の Mac にコマンドが無い | **AWS 公式（手順の不在）＋ コミュニティ ＋ 自環境の観察。** Apple による「非対応」の明示的な記述は見つけていません |
| WSL2 の既定カーネルに `iscsi_tcp` が無い | WSL2 はカスタムカーネルを使い、モジュールを増やすにはカーネルのビルドが必要という Microsoft の記述がある | **未検証。** Windows 実機での確認が測定項目に入っています |
| Windows Server と NVMe/TCP の組み合わせが使えない | Windows のサポート範囲はネイティブ NVMe ディスクに限られる | **NetApp KB。** [ブロックプロトコルとレイアウトの選択](../../../reference/decision-trees/block-protocol-and-layout.md) に記録済み |

**AWS が明示的に「非対応」と書いているものは、この 3 行の中に 1 つもありません。**
機能は追加されるので、採用を決める前に現行のドキュメントを確認してください。

---

## 端末が選べない場合の読み方

**多くの場合、端末は既に配備されています。** その場合この表は「何を諦めるか」の一覧です。

| 状況 | 結論 |
|---|---|
| 端末が Mac で固定 | ブロックが必要な処理を Mac 以外に寄せます。ファイルとオブジェクトはそのまま使えます |
| Windows と Mac の混在 | **ファイルは共通に出せます。** ブロックは Windows だけに限定するか、使わないかの判断です |
| WSL2 で開発している | ファイルとオブジェクトは WSL2 から、ブロックは Windows ホスト側から張る構成が素直です |
| Chromebook / iPad を含む | マウントの仕組みが無いため、ブラウザ経路を用意しない限り届きません |

**「Mac でも iSCSI を使う」を選ぶ場合、サードパーティのイニシエータを入れる判断になります。**
このリポジトリでは検証していません。**本番に入れる前に、フェイルオーバー時の挙動を自分で測ってください。**
パスがフェイルオーバーの仕組みそのものである理由は
[パスはフェイルオーバーの仕組みそのもの](../../block-storage/notes/paths-are-the-failover-mechanism.md) にあります。

---

## AWS の手順ページが前提にしている端末

**3 つのページはどれも EC2 インスタンスを前提に書かれています。** そのまま実機に当てると 2 か所ずれます。

| ページ | 前提 | 実機とのずれ |
|---|---|---|
| [macOS](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html) | **EC2 Mac インスタンス** | 到達経路を自分で設計します。**NFS の節は Amazon Linux 2 インスタンスの手順が書かれています** |
| [Windows iSCSI](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) | **EC2 の Windows Server 2019 AMI** | MPIO の有効化コマンドがクライアント SKU では通らず、`InitiatorPortalAddress` に渡すアドレスが VPN では接続ごとに変わります |
| [Linux](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-linux-client.html) | EC2 の Linux | WSL2 ではネットワーク境界が先に来ます（[詳細](wsl2-network-boundary.md)） |

**1 行目の後半は AWS のドキュメントの記述どおりです。** macOS ページの NFS の手順は
「macOS を実行する EC2 Mac インスタンス」ではなく「Amazon Linux 2 を実行する EC2 インスタンス」を
作るよう書かれています。**Mac で NFS を使うつもりでこのページをたどると、手順が別の OS の話に移ります。**

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | 端末の一覧を OS とバージョンで棚卸しする | どの行に当たるか |
| 2 | Mac: `which iscsiadm; ls /usr/sbin \| grep -i iscsi` | イニシエータの不在。**自環境でコマンドと実行ファイルの有無を確認します** |
| 3 | WSL2: `modprobe iscsi_tcp; echo $?` と `lsmod \| grep iscsi` | ブロックが使えるかどうか |
| 4 | Windows: `Get-WindowsOptionalFeature -Online -FeatureName MultiPathIO` と `Get-Service MSiSCSI` | MPIO の有効化手段と iSCSI サービスの状態 |
| 5 | `examples/client-access/probe-endpoint.sh` または `probe-endpoint.ps1` を各端末で実行する | 上記を同じ形の JSON で並べられます |

**手順 2 と 3 を飛ばして設計に入ると、端末の担当者に不可能な作業を割り当てることになります。**

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| AWS が macOS を対応クライアントに挙げているので Mac で全部できる | **対応しているのはファイルプロトコルです。** ブロックの手順は存在しません |
| AWS の macOS ページがあるので実機の Mac からそのまま使える | **ページは EC2 Mac インスタンスを前提にしています** |
| WSL2 は Linux なのでネイティブ Linux 端末と同じ | **ブロックは既定カーネルに依存し、ネットワークの境界が増えます** |
| Windows なら AWS の iSCSI 手順をそのまま使える | **Windows Server の EC2 前提です。** 2 か所を読み替える必要があります |
| Mac にサードパーティのイニシエータを入れれば同じ | 動くかもしれませんが、**このリポジトリでは検証していません。** フェイルオーバーの挙動は自分で測ってください |
| 端末の制約は VDI にすれば消える | **VDI の中の OS に移るだけです。** 消えるのは端末側の運用です |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| AWS が列挙するブロックの手順が Linux iSCSI / Windows iSCSI / Linux NVMe/TCP の 3 つで、macOS が無いこと | [AWS: Accessing your FSx for ONTAP data](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/accessing-data-from-on-premises.html) |
| macOS が対応クライアントに含まれること、対応する NFS / SMB / iSCSI のバージョン | [AWS: Supported clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/supported-clients-fsx.html) |
| macOS 手順が EC2 Mac インスタンスを前提とし、SMB を推奨し、NFS の節が Amazon Linux 2 インスタンスの手順であること | [AWS: Mounting volumes on macOS clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html) |
| Windows の iSCSI 手順が Windows Server 2019 の EC2 を前提とし、`Install-WindowsFeature Multipath-IO` と `InitiatorPortalAddress` を使うこと | [AWS: Provisioning iSCSI for Windows](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/mount-iscsi-windows.html) |
| WSL2 でカーネルモジュールを増やすにはカーネルのビルドが要ること | [Microsoft: How to use the Microsoft Linux kernel v6 on WSL2](https://learn.microsoft.com/en-us/community/content/wsl-user-msft-kernel-v6) |
| macOS にイニシエータが同梱されておらず、サードパーティ実装が使われていること | [Apple Support Communities](https://discussions.apple.com/thread/250425330) · [iscsi-osx/iSCSIInitiator](https://github.com/iscsi-osx/iSCSIInitiator) |

---

## 関連ドキュメント

- [Domain — クライアントアクセス](../README.md) — このモジュールのハブ
- [端末別にできることの比較](../../../reference/comparison/client-endpoint-capabilities.md) — 同じ表の詳細版
- [端末からデータに届く経路の決定木](../../../reference/decision-trees/client-access-route.md) — 判断の順序
- [WSL2 のネットワーク境界](wsl2-network-boundary.md) — △ の中身
- [ブロックプロトコルとレイアウトの選択](../../../reference/decision-trees/block-protocol-and-layout.md) — LUN 側の設計
- [パスはフェイルオーバーの仕組みそのもの](../../block-storage/notes/paths-are-the-failover-mechanism.md) — ブロックを選んだ後の可用性
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)
