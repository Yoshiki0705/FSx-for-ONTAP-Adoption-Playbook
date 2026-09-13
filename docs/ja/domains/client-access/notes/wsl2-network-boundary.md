---
title: WSL2 のネットワーク境界 — ホストが VPN に繋がっていることは WSL2 から届くことを意味しない
lifecycle: [assess, design, build]
domains: [client-access]
evidence: documented
source: https://learn.microsoft.com/en-us/windows/wsl/networking
lang: ja
---

# WSL2 のネットワーク境界

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

---

## 結論

**WSL2 は Windows ホストと同じネットワークにいません。** 既定では仮想化されたネットワークインター
フェースと NAT を持つため、**ホストが VPN に接続していても WSL2 から同じ経路が使えるとは限りません。**

境界は 2 つあります。**どちらも「Linux だから Linux 端末と同じ」を崩します。**

| 境界 | 何が変わるか |
|---|---|
| **ネットワーク** | 既定は NAT。ホストの VPN 経路を共有するかはモードとバージョンに依存します |
| **カーネル** | WSL2 は Microsoft のカスタムカーネルを使います。`iscsi_tcp` のようなモジュールを増やすにはカーネルのビルドが必要です |

**mirrored モードにすれば解決する、とは書けません。** Microsoft の WSL リポジトリに
`WSL 2 mirrored networking breaks NFS mounts ("Connection timed out")` という Issue があり、
**未解決です。** 一方を直すともう一方が壊れる可能性があるため、**どちらのモードでも自環境で確認して
ください。**

> **区分**: `documented` — Microsoft のドキュメントと WSL リポジトリの Issue に基づきます（2026-09-13 に確認）。
> **自環境での再現は未実施です。** NAT モードと mirrored モードのどちらで NFS / SMB が成立するかは、
> `examples/client-access/probe-endpoint.sh` を両モードで実行する測定項目に入っています。
> **測るまで、どちらのモードを推奨するとも書きません。**

---

## 2 つのモードと、どちらでも確認が必要な理由

| モード | ネットワークの見え方 | 既知の懸念 |
|---|---|---|
| **NAT（既定）** | WSL2 が独自のアドレスを持ちます。ホストの VPN インターフェースは WSL2 には現れません | ホストの VPN 経路が WSL2 から使えるかが構成依存 |
| **mirrored**（Windows 11 で opt-in） | ホストのインターフェースが WSL2 にも現れ、`localhost` で相互に到達できます | **NFS マウントが失敗するという未解決の報告があります** |

**mirrored モードは `/etc/wsl.conf` か Windows 側の `.wslconfig` で有効にします。**
Linux 側から見えるのは前者だけなので、`probe-endpoint.sh` が `nat_or_unset` と報告した場合、
それは「NAT だと確認した」ではなく「Linux 側の設定ファイルに記述が無い」という意味です。
**Windows 側の `.wslconfig` を必ず併せて確認してください。**

---

## 実務上とれる 3 つの形

**どれが優れているという話ではありません。** 端末の構成と、何を WSL2 でやりたいかで決まります。

| 形 | 向く状況 | 引き換えに負うもの |
|---|---|---|
| **ファイルとオブジェクトは WSL2、ブロックは Windows 側** | 開発は WSL2、LUN は Windows のディスクとして使いたい | 2 つの OS にまたがる手順書になります |
| **すべて Windows 側で行い、WSL2 からは `/mnt/` 経由で読む** | WSL2 に何も設定したくない | Windows のマウントを経由するため、パーミッションの表現が Windows 側のものになります |
| **WSL2 を mirrored モードにして Linux の道具で完結させる** | Linux のツールチェーンをそのまま使いたい | **NFS マウントの既知の報告があり、モードの変更は WSL 全体に効きます** |

**2 行目は見落とされがちですが、多くの場合これで足ります。** WSL2 から NFS を張る必要が本当にあるかを
先に問うと、境界の問題自体が消える場合があります。

---

## 自環境での確認手順

**ホスト側と WSL2 側を別々に見てください。** 片方だけでは境界の状態が分かりません。

| # | 手順 | 確認できること |
|---|---|---|
| 1 | Windows 側で `wsl.exe --version` | WSL のバージョン。mirrored モードが使えるか |
| 2 | Windows 側で `type %USERPROFILE%\.wslconfig` | **mirrored モードは主にここで設定されます。** Linux 側から見えません |
| 3 | WSL2 側で `cat /etc/wsl.conf` | Linux 側の設定。無くても mirrored の可能性があります |
| 4 | WSL2 側で `ip addr` と `ip route`、Windows 側で `route print` を並べる | 同じ経路を見ているか |
| 5 | VPN 接続中に、Windows 側と WSL2 側の両方から `nc -vz <nfs-ip> 2049` 相当を試す | **境界がどちらにあるか。** ホストで通り WSL2 で通らなければネットワーク境界です |
| 6 | WSL2 側で `modprobe iscsi_tcp; echo $?` | カーネル境界。ブロックが使えるか |
| 7 | 両方で `examples/client-access/probe-endpoint.sh` / `probe-endpoint.ps1` を実行する | 同じ形の JSON で並べられます |

**手順 5 が判定の中心です。** ホストで通って WSL2 で通らないなら、マウントオプションを変えても直りません。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| WSL2 は Windows と同じネットワークにいる | **既定は NAT です。** ホストのインターフェースは現れません |
| ホストが VPN に繋がっていれば WSL2 からも届く | **モードと構成に依存します。** 手順 5 で確認してください |
| mirrored モードにすれば解決する | **NFS マウントが壊れるという未解決の報告があります。** 解決策として選ぶ前に確認してください |
| `/etc/wsl.conf` に何も無いので NAT モードだ | **Windows 側の `.wslconfig` が優先される場合があります。** Linux 側からは見えません |
| WSL2 は Linux なので `open-iscsi` を入れれば iSCSI が使える | **カーネルにモジュールが無い場合、パッケージだけでは足りません** |
| WSL2 から NFS を張るのが唯一の方法 | **Windows 側でマウントして `/mnt/` 経由で読む形で足りる場合があります。** 先に必要性を問うと境界の問題が消えます |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| WSL2 が仮想化されたネットワークインターフェースと NAT を持ち、mirrored モードでホストと `localhost` で相互到達になること | [Microsoft: Accessing network applications with WSL](https://learn.microsoft.com/en-us/windows/wsl/networking) |
| mirrored モードで NFS マウントが `Connection timed out` になる未解決の報告 | [microsoft/WSL Issue #12508](https://github.com/microsoft/WSL/issues/12508) |
| WSL2 がカスタムカーネルを使い、モジュールを増やすにはビルドが必要であること | [Microsoft: How to use the Microsoft Linux kernel v6 on WSL2](https://learn.microsoft.com/en-us/community/content/wsl-user-msft-kernel-v6) |
| WSL2 が仮想化ゲストとしてホストのデバイスを扱えないこと | [Microsoft: Troubleshooting Windows Subsystem for Linux](https://learn.microsoft.com/en-us/windows/wsl/troubleshooting) |

---

## 関連ドキュメント

- [Domain — クライアントアクセス](../README.md) — このモジュールのハブ
- [端末の種類がプロトコルを先に狭める](the-endpoint-narrows-the-protocol.md) — WSL2 の △ の位置
- [端末別にできることの比較](../../../reference/comparison/client-endpoint-capabilities.md) — 端末ごとの可否
- [端末からデータに届く経路の決定木](../../../reference/decision-trees/client-access-route.md) — 判断の順序
- [SMB の落ち方は端末ごとに違う](how-smb-fails-per-endpoint.md) — WSL2 で SMB を張る場合
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)
