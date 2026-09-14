---
title: SMB の落ち方は端末ごとに違う — 同じ原因が 3 つの別の症状として出るので、症状から原因を引けない
lifecycle: [build, operate]
domains: [client-access, multiprotocol-identity]
evidence: documented
source: https://docs.aws.amazon.com/us_en/fsx/latest/ONTAPGuide/attach-windows-client.html
lang: ja
---

# SMB の落ち方は端末ごとに違う

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)

---

## 結論

**同じ原因が、端末ごとに別の症状として出ます。** そのため**症状から原因を逆引きできません。**
確認する順序を固定してください。

| 原因 | Windows での見え方 | macOS での見え方 | WSL2 での見え方 |
|---|---|---|---|
| **名前が解決していない** | ネットワークパスが見つからない | サーバーに接続できない | `mount error: could not resolve address` |
| **経路が無い / SG で落ちている** | 長く待って失敗 | 長く待って失敗 | 長く待って `Connection timed out` |
| **資格情報が違う** | 資格情報を再入力する画面 | 認証ダイアログが再表示される | `mount error(13): Permission denied` |
| **共有名が違う** | ネットワーク名が見つからない | 共有の一覧に出ない | `mount error(2): No such file or directory` |
| **SMB のバージョン交渉が合わない** | プロトコルエラー | 接続できない | `mount error(95): Operation not supported` |

**1 行目と 2 行目が最も紛らわしいです。** どちらも「繋がらない」に見え、**IP でマウントすると 1 行目だけが
消えます。** だから IP で試して通ったことを「経路は正常」と読むのは正しく、
**「設定は正常」と読むのは誤りです。**

> **区分**: `documented` — AWS / Microsoft / Apple のドキュメントと、Linux の `mount.cifs` の
> エラー番号に基づきます（2026-09-13 に確認）。
> **上の表のエラー文言は、当方の 3 端末での実測ではまだ埋まっていません。**
> `examples/client-access/probe-endpoint.sh` と `probe-endpoint.ps1` が失敗時の文言をそのまま
> 記録するので、測定後にここを実測値に置き換えます。**現時点では想定される対応として読んでください。**

---

## 確認する順序

**症状から入らず、この順序で潰してください。** 上から順に、原因を 1 つずつ消していきます。

| # | 確認 | 通ったら次へ / 落ちたら |
|---|---|---|
| 1 | `nslookup <svm-dns-name>` | 落ちたら **Client VPN の DNS サーバー設定**（[詳細](../../../reference/comparison/endpoint-reachability-options.md#client-vpn-を検証の既定にする理由)） |
| 2 | `nc -vz <smb-ip> 445` | 落ちたら経路かセキュリティグループ。**445 だけでなく NFS 側の 111 / 635 / 4045-4046 も別に確認してください** |
| 3 | IP でマウントする | 通ったら原因は 1 で、経路と資格情報は正常です |
| 4 | 共有名を一覧する（Windows は `net view \\<ip>`） | 落ちたら共有が無いか、共有 ACL で見えていません |
| 5 | 資格情報を変えてマウントする | 通ったら資格情報。**Windows は資格情報マネージャーに古い値を保持します**（[詳細](where-endpoint-credentials-live.md)） |
| 6 | SMB のバージョンを明示してマウントする | 通ったら交渉の問題です |

**手順 5 で Windows だけ挙動が違います。** 資格情報マネージャーに古いエントリが残っていると、
**入力し直しても古い値が使われます。** `cmdkey /list` で確認し、`cmdkey /delete` で消してから
再試行してください。

---

## 端末ごとに固有の落とし穴

| 端末 | 落とし穴 |
|---|---|
| **Windows** | 資格情報マネージャーが古い値を保持します。**445 はローカルでも待ち受けているため、ポートの状態を `netstat` で見ると自分の待ち受けと混ざります** |
| **macOS** | Finder のダイアログはエラーの区別が粗く、原因の切り分けに向きません。**`mount_smbfs` をターミナルから実行すると文言が出ます。** AWS は Mac には SMB を推奨しており、既定共有は `C$` です |
| **WSL2** | ネットワーク境界が先に来ます（[詳細](wsl2-network-boundary.md)）。**`mount.cifs` は `sudo` を必要とし、`credentials=` ファイルのモードが 600 でないと警告します** |

**macOS の行が診断コストに直結します。** Finder で「接続できません」と出た時点では、
上の表の 5 つの原因のどれか分かりません。**ターミナルから実行し直すのが最短です。**

---

## ストレージ側が原因の場合

**端末を疑い切ったあとに残る 3 つです。** どれも既にこのリポジトリに記録があります。

| 原因 | 症状 | 参照 |
|---|---|---|
| **SVM が SMB を提供できない状態にある** | すべての端末で一様に失敗します | [SMB を提供できない SVM がある](../../multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md)（`verified`） |
| **監査ログの宛先が枯渇している** | **アクセスが止まります。枯渇した瞬間ではありません** | [監査宛先が枯渇するとクライアントアクセスは止まる](../../security-governance/notes/audit-log-space-and-client-access.md)（`verified`） |
| **NTFS ACL で拒否されている** | 特定のユーザーだけ失敗します | [セキュリティスタイルが権限評価のモデルを決める](../../multiprotocol-identity/notes/security-style-and-permission-evaluation.md) |

**2 行目は端末側からは原因が見えません。** 「昨日まで動いていた」「全員が同時に失敗した」の 2 つが
揃ったら、端末の調査より先にここを見てください。

---

## workgroup と AD 参加で変わること

**AWS は SMB マウントの前提として、SVM が AD に参加しているか、または workgroup を使っていることを
挙げています。** どちらでも端末からマウントできます。

| 構成 | 端末側で変わること | 使えなくなるもの |
|---|---|---|
| **AD 参加** | ドメインユーザーでマウントします | — |
| **workgroup** | SVM 上のローカル SMB ユーザーでマウントします | **SMB3 Witness、SMB3 の継続的可用性共有、SQL over SMB、フォルダリダイレクト、移動プロファイル、グループポリシー、ボリュームシャドウコピーサービス** |

**右列は実在する一覧です。** 形式的な注記ではありません。いずれかが要るなら workgroup は選べません。
AD 参加側の権限評価は
[Domain — マルチプロトコルと ID](../../multiprotocol-identity/README.md) にあります。

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 症状を見れば原因が分かる | **端末ごとに別の文言になります。** 確認の順序を固定するほうが速いです |
| IP で通ったので設定は正常 | **経路と資格情報は正常です。** 名前解決だけが落ちています |
| Windows で資格情報を入力し直せば新しい値が使われる | **資格情報マネージャーの古いエントリが優先されます** |
| Finder のエラーで切り分けられる | 区別が粗いので、**`mount_smbfs` をターミナルから実行してください** |
| 全員が同時に失敗したなら端末の問題ではない | **監査宛先の枯渇でも同じ形になります。** ストレージ側を先に見てください |
| SMB を使うには Active Directory が必要 | **workgroup でも使えます。** ただし上の一覧が使えなくなります |
| 445 が開いていれば SMB は成立する | 成立しますが、**NFS を併用するなら 111 / 635 / 4045-4046 を別に開ける必要があります** |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| SMB マウントの前提が AD 参加または workgroup であること | [AWS: Mounting volumes on Microsoft Windows clients](https://docs.aws.amazon.com/us_en/fsx/latest/ONTAPGuide/attach-windows-client.html) |
| macOS に SMB を推奨すること、`mount -t smbfs` の形、既定共有が `C$` であること | [AWS: Mounting volumes on macOS clients](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/attach-mac-client.html) |
| workgroup モードの SMB サーバーを FSx for ONTAP で作れること | [AWS: Creating an SMB server in a workgroup](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-smb-server-workgroup.html) |
| workgroup モードで使えなくなる機能の一覧、および作成後にローカルユーザーが必要であること | [NetApp: Create SMB servers on the ONTAP SVM with specified workgroups](https://docs.netapp.com/us-en/ontap/smb-config/create-server-workgroup-task.html) |
| SMB 共有の管理と共有 ACL | [AWS: Managing SMB shares](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-smb-shares.html) |
| Client VPN で DNS サーバーを指定しない場合にローカルの DNS が使われること | [AWS: Client VPN endpoint での DNS の動作](https://aws.amazon.com/premiumsupport/knowledge-center/client-vpn-how-dns-works-with-endpoint/) |
| NFS のマウントと SMB のロックに必要なポートが 2049 だけではないこと | [repost.aws: Multiprotocol access without Active Directory integration](https://www.repost.aws/articles/ARTG4-JD8UQ_igrHwSoxytOA/fsx-for-netapp-ontap-fsxn-multiprotocol-access-without-active-directory-integration) |

---

## 関連ドキュメント

- [Domain — クライアントアクセス](../README.md) — このモジュールのハブ
- [端末からデータに届く経路の決定木](../../../reference/decision-trees/client-access-route.md) — 確認の順序の全体像
- [WSL2 のネットワーク境界](wsl2-network-boundary.md) — WSL2 で先に来る問題
- [端末側の資格情報の置き場所](where-endpoint-credentials-live.md) — 手順 5 の詳細
- [SMB を提供できない SVM がある](../../multiprotocol-identity/notes/smb-service-lost-on-cifs-server-delete.md) — ストレージ側の原因
- [監査宛先が枯渇するとクライアントアクセスは止まる](../../security-governance/notes/audit-log-space-and-client-access.md) — 全員が同時に失敗する形
- [SMB のユーザー管理と監査は 2 つの選択で決まる](../../../reference/decision-trees/smb-identity-and-audit.md) — workgroup と AD 参加の判断
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — クライアントアクセス](../README.md)
