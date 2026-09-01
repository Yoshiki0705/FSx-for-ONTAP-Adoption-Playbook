---
title: 監査宛先の枯渇ではアクセスは止まらず記録も失われない。止める条件は観測できないステージング側にある
lifecycle: [design, build, operate]
domains: [security-governance]
evidence: verified
verified_on: 2026-09-01
ontap_version: 9.18.1P3D1
region: ap-northeast-1
lang: ja
---

# 監査宛先の枯渇ではアクセスは止まらず記録も失われない。止める条件は観測できないステージング側にある

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — セキュリティ・ガバナンス](../README.md)

---

## 結論

**監査宛先ボリュームを満杯にしても、監査対象ボリュームへの SMB アクセスは止まりませんでした。** そして **満杯の間に発生した監査レコードも失われませんでした。** 空きを回復させたら、順序とタイムスタンプを保ったまま宛先に書き出されました。

**ドキュメントの「クライアントアクセスが失敗する」は誤りではありません。条件が宛先ではないということです。** 監査は宛先ボリュームとは別に、ONTAP が内部で作るステージングボリューム（`MDV_AUD_*`）へ先に書きます。アクセスが止まるのはそちらが枯渇したときで、**FSx for ONTAP ではステージングボリュームが `fsxadmin` から見えません。**

| 領域 | 空き容量の確認 | 枯渇したときの影響 |
|---|---|---|
| 監査ログの宛先ボリューム | **できる**（`volume show`、CloudWatch のボリュームメトリクス） | **アクセスは継続。レコードはステージングに滞留** |
| ステージングボリューム `MDV_AUD_*` | **できない** | アクセス失敗（NetApp のドキュメント記載。本ノートでは未実測） |

**この構造が監視設計を決めます。** 障害を起こす側は観測できず、観測できる側は満杯になっても即座には障害になりません。**つまり宛先ボリュームの使用率は「それ自体が障害の原因」ではなく「観測できないステージング滞留の唯一の前兆」として監視します。** この因果を取り違えると、宛先を大きくすれば安全という誤った結論になります。宛先を大きくしても、滞留が解消しなければステージングは埋まります。

そして既定値が滞留を起こしやすい側に寄っています。

```text
FsxIdEXAMPLE::> vserver audit show -vserver <svm> -instance
      Strict Guarantee of Auditing: true      ← 監査を保証する。書けなければアクセスを失敗させる
          Log Files Rotation Limit: 0         ← 本数の上限なし
            Log Retention Duration: 0s        ← 期間による削除もしない
```

**保持の上限が無いので宛先は必ず埋まります。** 埋まっても即座には止まりませんが、そこから先はステージング滞留が始まり、観測できない領域で残り時間が減っていきます。

> **Evidence**: `verified`（2026-09-01、`ap-northeast-1`、ONTAP `9.18.1P3D1`）。
> 枯渇の挙動は、**他の検証に影響しないよう専用に作成した使い捨て SVM** で測りました。
> 100 MB の宛先ボリューム、`-strict-guarantee` は既定の `true`、監査対象ボリュームには SACL を
> 設定済み。宛先は圧縮も重複排除も効かない乱数データで埋めています（**同一内容を書くと重複排除で
> 潰れて埋まりません**）。**ステージング枯渇そのものは実測していません** — ステージングは参照できず、
> アグリゲート単位で 2 GB 確保されるため、SMB 操作で埋めるのは現実的な時間では不可能でした。

---

## 宛先枯渇時の実測

宛先ボリュームを 99%（空き 8〜12 KB、クライアントからの書き込みが `There is not enough space on the disk` で失敗する状態）にしてから、監査対象ボリュームへ Windows クライアントでアクセスしました。

| 操作 | 結果 |
|---|---|
| 新規 SMB セッションの確立（4624 の書き込みを要する） | **成功** |
| ディレクトリ一覧 | **成功** |
| ファイル作成 | **成功** |
| 読み出し | **成功** |
| 削除 | **成功** |

**5 操作すべてが通りました。** 監査保証が有効でも、宛先が満杯であることだけではアクセスは止まりません。

### 滞留したレコードの回収

満杯中（`14:45:56`）のアクセスで発生したレコードは、その時点では宛先に現れませんでした。**宛先の空きを回復させたあと、13 件すべてが書き出されました。**

| 確認したこと | 結果 |
|---|---|
| 満杯中に生成されたレコードの、その時点での宛先への出現 | **無し**（直後のローテーションファイルは 0 件、`_last.evtx` は 0 バイト） |
| 空き回復後の出現 | **13 件すべて**（`4624` ×1、`4656` ×5、`4663` ×5、`4660` ×1、`4634` ×1） |
| タイムスタンプ | **満杯中の実時刻を保持**（`14:45:56.144` 〜 `14:46:06.884`） |
| 順序 | 保持 |

**「アクセスは通ったが記録は落ちた」ではありません。** レコードはステージングに保持され、書ける状態になってから宛先へ流れました。**逆に言えば、滞留している間その分だけステージングを消費し続けます。**

> **監査要件への含意**: 宛先が満杯の期間について、**監査ログにその場では穴が空いて見えます。**
> 「この時刻のアクセス記録が無い」ことを欠落と判断する前に、宛先の空き容量の履歴を確認してください。
> 空きを回復させれば埋まる可能性があります。**ただしステージングが先に枯渇した場合にどうなるかは
> 本ノートでは未実測です。**

### クライアントより後に飢える監査

**クライアントの書き込みが `ENOSPC` で失敗している状態でも、監査サブシステムは 68 KB のローテーションファイルを書けていました。** 順序はクライアントが先です。宛先ボリュームを共用していると、監査が止まる前に**その共用相手の書き込みが先に失敗します。**

これが宛先を専用ボリュームにする実務上の理由です。共用していると、監査の容量問題が無関係なアプリケーションの障害として現れます。

---

## 観測できる信号

**監査固有の EMS イベントはありませんでした。** 出るのは標準のボリューム満杯イベントだけです。

```text
FsxIdEXAMPLE::> event log show -message-name *audit*
There are no entries matching your query.

FsxIdEXAMPLE::> event log show -severity ALERT|EMERGENCY|ERROR
ALERT  monitor.volume.full: Volume "auditdest@vserver:..." is full
       (using or reserving 99% of space and 4% of inodes).
ERROR  monitor.volume.nearlyFull: Volume auditdest@vserver:... is nearly full
       (using or reserving 95% of space and 4% of inodes).
ALERT  wafl.vol.full: Insufficient space on volume auditdest@vserver:... to perform
       operation. 1.01MB was requested but only 1.00MB was available.
```

| 監視対象 | 何を示すか |
|---|---|
| 宛先ボリュームの使用率（95% / 99% の EMS、CloudWatch のボリュームメトリクス） | **ステージング滞留が始まる前兆。これが唯一の実用的な検知点です** |
| アグリゲートの空き容量 | ステージング領域が確保できる余地 |
| `event log show -message-name *audit*` | **何も出ません。** 監査の健全性を問い合わせる経路として使えません |

**「監査が書けているか」を直接問える経路がありません。** 宛先ボリュームの使用率を、監査の健全性の代理として監視することになります。

---

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
| 宛先ボリュームの監視 | 使用率のアラームを**有効化と同時に**入れる | **観測できないステージング滞留の唯一の前兆です。** 埋まった時点では止まりませんが、そこから残り時間が減り始めます |
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

1. **宛先ボリュームのセキュリティスタイルと、アクセスポイントに固定した ID が整合していること。** NTFS スタイルのボリュームに UNIX ID のアクセスポイントを張ると、呼び出し元が管理者権限でも `AccessDenied` になりました。同一アクセスポイントのままセキュリティスタイルを `unix` に変更したら `ListObjectsV2` と `GetObject` が通りました。原因は名前マッピングの不在です。

   **この失敗は S3 側のエラーからは原因が分かりませんが、ONTAP の EMS には出ます。** 同一クラスタの `event log show` に次が記録されていました（**この行は別のワークロードのものです。私の呼び出しに対応する 1 件として特定したわけではありません**）。`AccessDenied` の切り分けでは、IAM ではなくこの経路を確認してください。

   ```text
   ERROR secd.nfsAuth.noNameMap: vserver (<svm>) Cannot map UNIX name to CIFS name.
     Error: Get user credentials procedure failed
     [ 0 ms] Determined UNIX id 0 is UNIX user 'root'
     [    0] Trying to map 'root' to Windows user 'root' using implicit mapping
     [    0] Could not find Windows name 'root'
     [    0] Unable to map 'root'. No default Windows user defined.
   **[    0] FAILURE: Name mapping for UNIX user 'root' failed. No mapping found
   ```

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

- **ステージング枯渇時の挙動**。本ノートで測ったのは宛先の枯渇だけです。ステージングは参照できず、アグリゲート単位で 2 GB 確保されるため、SMB 操作で埋めるのは現実的な時間では不可能でした。**エラーの内容、影響範囲（当該ボリュームのみか SVM 全体か）、復旧手順、そのときレコードが落ちるかは測っていません**
- **滞留が続いた場合にレコードが落ち始める点**。今回は数分で空きを回復させたため、13 件すべてが回収されました。**滞留が長時間続いた場合に古いレコードから落ちるのか、ステージング枯渇まで保持されるのかは測っていません**
- **ステージングボリュームの実サイズと増加ペース**。参照できないため測れません
- **`-strict-guarantee false` にした場合の欠落の仕方**。どのレコードが落ちるか、落ちたことが分かるかを測っていません
- **NFS でも同じ順序になるか**。宛先枯渇時のアクセス継続は SMB でのみ測りました

---

## 参照した一次情報

- AWS: [Auditing file access](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/file-access-auditing.html)
- NetApp: [Troubleshoot ONTAP auditing and staging volume space issues](https://docs.netapp.com/us-en/ontap/nas-audit/troubleshoot-auditing-staging-volume-concept.html)
- NetApp KB: [What happens if the destination volume or staging volume is out of space in NAS auditing](https://kb.netapp.com/onprem/ontap/da/NAS/What_happens_if_the_destination_volume_or_staging_volume_is_out_of_space_in_NAS_auditing)

---

## 関連

- [SMB ログオン監査 — 4624 は記録される](smb-logon-audit-event-coverage.md)
- [ローカルユーザーの棚卸しに使える情報は監査ログにしかない](../../multiprotocol-identity/notes/local-user-inventory-without-last-logon.md)
