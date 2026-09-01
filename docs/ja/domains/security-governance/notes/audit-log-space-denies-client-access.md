---
title: 監査ログの空き容量不足はクライアントアクセスを止める。そして枯渇を監視する経路が塞がれている
lifecycle: [design, build, operate]
domains: [security-governance]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# 監査ログの空き容量不足はクライアントアクセスを止める。そして枯渇を監視する経路が塞がれている

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

---

## 結論

**ファイルアクセス監査を有効にすると、監査ログを書けなくなった時点で SMB / NFS アクセスが失敗し得ます。** 既定値がそう設定されています。

```text
FsxIdEXAMPLE::> vserver audit show -vserver <svm> -instance
      Strict Guarantee of Auditing: true      ← 監査を保証する。書けなければアクセスを失敗させる
          Log Files Rotation Limit: 0         ← 本数の上限なし
            Log Retention Duration: 0s        ← 期間による削除もしない
```

**この 3 つが同時に既定であることが問題です。** 保持の上限が無いのでログは増え続け、埋まった時点で保証設定が効いてアクセスが止まります。監査を「記録を増やすだけの追加機能」として有効化すると、後から可用性の問題として現れます。

**さらに、枯渇を監視する経路の片方が塞がれています。** 監査は宛先ボリュームとは別に、ONTAP が内部で作るステージングボリューム（`MDV_AUD_*`）を使います。**FSx for ONTAP では `fsxadmin` からこのボリュームが見えません。**

| 領域 | 空き容量の確認 |
|---|---|
| 監査ログの宛先ボリューム | **できる**（`volume show`、CloudWatch のボリュームメトリクス） |
| ステージングボリューム `MDV_AUD_*` | **できない** |

AWS のドキュメントは「ステージングボリュームに十分な空き容量を確保する必要があります」と利用者に責任を置いていますが、**FSx for ONTAP ではその確認手段が提供されていません。**

> **Evidence**: `verified`（2026-09-01、`ap-northeast-1`、ONTAP `9.18.1P3D1`）。
> 既定値と可視性は 2 つのファイルシステムで確認しました。**容量枯渇時のアクセス失敗そのものは
> 実測していません**（意図的にボリュームを埋める操作は行っていません）。挙動は NetApp の
> ドキュメント記載で、本ノートでは既定値がその条件を満たしていることを確認した位置づけです。

---

## ステージングボリュームの不可視性

```text
FsxIdEXAMPLE::> volume show -volume MDV_AUD* -fields vserver,volume,aggregate,size,state
There are no entries matching your query.

FsxIdEXAMPLE::> volume show -volume *MDV*
There are no entries matching your query.

FsxIdEXAMPLE::> vserver show -type admin
There are no entries matching your query.
```

監査を有効化した SVM がある状態で 0 件です。`volume show` の全件にも現れません。管理 vserver 自体が参照できないため、そこを経由した確認もできません。

**ステージングボリュームはアグリゲート単位で作られ、監査対象ボリュームを持つアグリゲートごとに必要です。** NetApp の KB には、アグリゲートに 2 GB の空きが無いと監査設定の作成自体が失敗する旨の記載があります。したがって**アグリゲートの空き容量が間接的な代理指標**になります。

| 監視できるもの | 代理として何を示すか |
|---|---|
| 監査宛先ボリュームの使用率 | 直接の枯渇要因の 1 つ |
| アグリゲートの空き容量 | ステージング領域が確保できる余地 |

**どちらも「ステージングが今どれだけ埋まっているか」ではありません。** 余裕を厚めに取る以外の対処が、現状の可視性ではできません。

---

## 保持設定 — 2 つの方式は排他

```text
FsxIdEXAMPLE::> vserver audit modify -vserver <svm> -rotate-limit 10 -retention-duration 90d
Error: Field "-retention-duration" cannot be used with field "-rotate-limit".
```

| 方式 | パラメータ | 設定できた値 |
|---|---|---|
| 期間で保持 | `-retention-duration` | `90d` → `90d 0h 0m 0s` |
| 本数で保持 | `-rotate-limit` | `10` |

**同時に指定できません。** 期間だけを指定すると本数に上限が無く、**設計時に容量の上界を押さえられません。** 逆に本数だけを指定すると、アクセス量が増えた期間は保持期間が短くなります。

3 か月の棚卸し要件のように期間が規程で決まっている場合は `-retention-duration 90d` が要件に一致しますが、**容量の上界は別途「宛先ボリュームのサイズ」と「宛先ボリュームの使用率監視」で担保することになります。**

---

## 設計時に決めておくこと

| 項目 | 推奨 | 理由 |
|---|---|---|
| 宛先ボリューム | **監査専用に 1 本**。他用途と共有しない | 他用途の書き込みで埋まると、監査ではなくアクセスが止まります |
| 保持 | 要件に合わせて `-retention-duration` か `-rotate-limit` を**明示** | 既定はどちらも無制限です |
| `-rotate-size` | 100 MB 程度 | 1 ファイルの肥大を避け、回収と解析を扱いやすくします |
| 宛先ボリュームの監視 | 使用率のアラームを**有効化と同時に**入れる | 埋まってから気づくと、その時点でアクセスが止まっています |
| アグリゲートの空き | 併せて監視 | ステージング領域の代理指標 |
| `-strict-guarantee` | **既定 `true` のまま**を基本にする | 後述 |

`-strict-guarantee false` にすれば容量枯渇時もアクセスは継続しますが、**監査ログの欠落を許容することになります。** コンプライアンス目的で監査を入れているなら、記録の欠落は監査そのものの前提を崩します。どちらを取るかは監査要件の性質で決まり、**容量管理で守るほうが筋が通る**場面が多いはずです。可用性が優先される要件では `false` が選択肢になりますが、その場合は「監査ログは欠落し得る」ことを設計文書に明記してください。

---

## 監査ログの取り出し

宛先ボリューム上に EVTX が置かれます。**syslog 転送はできません**（AWS の記載）。取り出す経路を実測した結果です。

| 経路 | 結果 |
|---|---|
| ONTAP REST のファイル API | 通る。マウント不要。`byte_offset` と `length` の明示が必要 |
| S3 Access Point 経由（`ListObjectsV2` → `GetObject`） | 通る。**ただし条件あり**（下記） |
| SMB / NFS でマウントしてコピー | 一般的な方法 |

S3 Access Point を使う場合の条件が 2 つあります。

1. **宛先ボリュームのセキュリティスタイルと、アクセスポイントに固定した ID が整合していること。** NTFS スタイルのボリュームに UNIX ID のアクセスポイントを張ると、呼び出し元が管理者権限でも `AccessDenied` になりました。同一アクセスポイントのままセキュリティスタイルを `unix` に変更したら `ListObjectsV2` と `GetObject` が通りました。原因は名前マッピングの不在です
2. **同一 SVM に ONTAP のオブジェクトストアサーバーがあるとアクセスポイントを作成できません。** 作成が `FAILED` になり、既存サーバーの削除を求められます

層の仕組みは
[S3 Access Point の権限設計 — 評価順序と、絞り込みを担う 2 つの層](access-point-authorization-layers.md)
にあります。

> **運用に関する補足**: アクセスポイントの作成が `FAILED` で終わった後、アタッチメントを削除しても
> ボリューム側に FSx for ONTAP 管理のオブジェクトストア関連付けが残り、**ONTAP からボリュームを
> 削除できなくなりました。** エラーが指すバケットは ONTAP 側から参照できません（advanced 特権でも
> 現れない）。`aws fsx delete-volume` を使うと削除できました。監査用ボリュームを作り直す運用では
> ここで詰まります。

---

## 自環境での確認手順

| # | 手順 | 確認できること |
|---|---|---|
| 1 | `vserver audit show -instance` で 3 つの既定値を読む | `Strict Guarantee` / `Rotation Limit` / `Retention Duration` の現状 |
| 2 | `volume show -volume *MDV*` を実行する | ステージングボリュームが見えないこと。**見えないのが正常です** |
| 3 | 宛先ボリュームの使用量を数日測り、増加ペースを出す | 保持期間に必要な容量。**有効化前の見積もりでは足りません** |
| 4 | 宛先ボリュームの使用率アラームを入れる | 埋まる前に気づけること |
| 5 | 保持方式を明示して設定し、`show` で反映を確認する | 既定の無制限から抜けたこと |

---

## 未確認

- **枯渇時のアクセス失敗の実際の挙動**。ボリュームを意図的に埋める操作は行っていません。エラーの内容、影響範囲（当該ボリュームのみか SVM 全体か）、復旧手順は測っていません
- **ステージングボリュームの実サイズと増加ペース**。参照できないため測れません
- **`-strict-guarantee false` にした場合の欠落の仕方**。どのレコードが落ちるか、落ちたことが分かるかを測っていません

---

## 参照した一次情報

- AWS: [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html)
- NetApp: [Troubleshoot ONTAP auditing and staging volume space issues](https://docs.netapp.com/us-en/ontap/nas-audit/troubleshoot-auditing-staging-volume-concept.html)
- NetApp KB: [What happens if the destination volume or staging volume is out of space in NAS auditing](https://kb.netapp.com/onprem/ontap/da/NAS/What_happens_if_the_destination_volume_or_staging_volume_is_out_of_space_in_NAS_auditing)

---

## 関連

- [SMB ログオン監査 — 4624 は記録される](smb-logon-audit-event-coverage.md)
- [ローカルユーザーの棚卸しに使える情報は監査ログにしかない](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)
