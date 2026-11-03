---
title: FlexCache CLI 手順 (NFS編) – 簡易版
lifecycle: [design, build]
domains: [performance, client-access, data-protection]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html
lang: ja
---

# FlexCache CLI 手順 (NFS編) – 簡易版

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

> **対象読者と位置づけ**
>
> 既存の「FlexCache CLI 手順 (SMB編) – 簡易版」に対応する NFS 版です。マニュアルを順に追うのが面倒な担当者が、Origin を Amazon FSx for NetApp ONTAP、Cache を別クラスタに置く FlexCache を NFS で最短経路に組むための手順を示します。SMB 版の NetBIOS 名・Active Directory ドメイン参加・CIFS 共有の節を、NFS サービスと export policy、junction path マウントに置き換えています。
>
> **証拠の扱い**
>
> この文書は `documented` です。コマンドの形は AWS の FlexCache ガイド、NetApp の公開 ONTAP 手順、TR-4743 / TR-4571 に沿いますが、特定環境での成立・性能・状態は示しません。IP、SVM 名、cluster 名、volume 名、サイズはすべて置換用の placeholder です。実値、実行結果、性能値は非公開の記録にだけ書き留めます。本番適用の前に自環境で検証してください。

## 結論

この手順は、Origin（FSx for ONTAP）の NFS volume に対する Cache volume を別クラスタの Cache SVM に作成し、NFSv3 でアクセスするまでの最短経路です。本線は **NFSv3 + write-around（既定）+ FlexGroup auto-provision** に絞ります。write-back、NFSv4.x、SMB 併用は補足に短く記します。

FlexCache は読み取り主体で変更が少ないワークロードに向きます。Origin 側の変更は Cache の refresh を要し、cache miss と write は Origin への回線に律速されるため、効果は経路とアクセスパターンで決まります（TR-4743）。この簡易版は到達性・export policy・peering が整った前提の作成手順であり、Origin/Cache の identity 確認と逆操作の記録を省略しません。

| 判定 | この手順での意味 |
|---|---|
| `documented` | 公開資料から確認できる前提または操作の形。実環境での成立・性能を示さない。 |
| placeholder | IP・名前・サイズは環境に合わせて置換する。実値は公開しない。 |
| 停止 | identity・state・peer・経路が記録した値と一致しない場合、その場で止める。 |

> **作成境界**
>
> `cluster peer create`、`vserver peer create/accept`、`volume flexcache create` は mutation です。実行は、両クラスタの peering が `Available` / `peered`、intercluster LIF 間の疎通が全組み合わせで成立、Origin/Cache の identity と逆操作が非公開の記録にある場合に限ります。一つでも欠ける・矛盾する場合は実行せず停止します。

## 対象環境（置換用）

SMB 版の機種名を一般化し、Cache 側を任意の第 2 クラスタとして記述します。実値は非公開の記録にだけ保存します。

| 項目 | Origin ストレージ | Cache ストレージ |
|---|---|---|
| ストレージ | Amazon FSx for NetApp ONTAP | `<cache-cluster-model>`（任意の ONTAP クラスタ） |
| ONTAP バージョン | `<origin-ontap-version>`（9.7 以降を想定） | `<cache-ontap-version>`（9.7 以降を想定） |
| SVM | `<origin-svm>` | `<cache-svm>` |
| 利用プロトコル | NFS（NFSv3 本線） | NFS（NFSv3 本線） |
| Origin volume | `<origin-volume>` | — |
| Cache volume | — | `<cache-volume>`（FlexGroup） |
| NFS データ LIF | `<origin-nfs-lif>` | `<cache-nfs-lif-1>` / `<cache-nfs-lif-2>` |
| Intercluster LIF | `<origin-intercluster-lif-1>` / `<origin-intercluster-lif-2>` | `<cache-intercluster-lif-1>` / `<cache-intercluster-lif-2>` |
| Gateway / NTP / DNS | 環境既定 | `<cache-gateway-ip>` / `<cache-ntp-ip>` / `<cache-dns-ip>` |

### 前提（事前に完了している作業）

- **FSx for ONTAP（Origin）**: ファイルシステム作成、SVM 作成、volume 作成（UNIX セキュリティスタイル）、NFS サービス有効化、export policy によるアクセス許可、NFS データ LIF。
- **Cache クラスタ**: 初期セットアップ、データ用 aggregate 作成、SVM 作成、FlexCache 用 intercluster LIF 作成、NFS データ LIF 作成。
- **ネットワーク**: 両クラスタの intercluster LIF 間で TCP 11104 / 11105 疎通、Cache SVM から Origin への経路、NFS client から Cache への TCP 2049 経路。

FlexCache の利用要件（TR-4743、ONTAP マニュアル）: Origin/Cache とも ONTAP 9.5 以上。Origin volume は FlexVol でも FlexGroup でもよい（9.7 以降）。**Cache volume は常に FlexGroup** になる。Origin は NFSv3 / NFSv4 / SMB を使えるが、Cache へのアクセスは 9.7 以前では NFSv3 のみ、**NFSv4 は 9.10.1 以降**でサポートされる。SMB Cache は 9.8 以降。

## 1. Origin（FSx for ONTAP）側の事前確認

read-only で現状を確認します。cluster management endpoint に `fsxadmin` で SSH し、advanced 権限へ移行します。

```text
::> set advanced

# 1.1 volume 一覧
::*> volume show -vserver *

# 1.2 対象 volume のセキュリティスタイル（NFS は unix を想定）
::*> volume show -vserver <origin-svm> -volume <origin-volume> -fields security-style

# 1.3 NFS サービスの状態
::*> vserver nfs show -vserver <origin-svm>

# 1.4 DNS 設定
::*> dns show -vserver *

# 1.5 ONTAP バージョン
::*> version

# 1.6 export policy とルール（どの client を許可するか）
::*> vserver export-policy show -vserver <origin-svm>
::*> vserver export-policy rule show -vserver <origin-svm> -policyname *

# 1.7 ルーティング
::*> route show -vserver *

# 1.8 FlexCache 用 intercluster LIF
::*> network interface show -role intercluster
```

security-style が unix でない、NFS サービスが無効、export policy が Cache SVM からのアクセスを許可しない、intercluster LIF が存在しない場合は停止し、各 owner に返します。Origin volume のセキュリティスタイルは Cache 側に引き継がれ、**Cache 側では変更できません**。NFS 本線では Origin を unix で用意します。

## 2. Cache クラスタの設定

### 2.1 設定確認

```text
::*> route show -vserver *
::*> dns show -vserver *
::*> export-policy rule show -vserver *
::*> cluster time-service ntp server show
```

export policy にルールが無い場合は、NFS client の範囲に限定して追加します。`0.0.0.0/0` は検証限定で、本番では client CIDR に絞ります。

```text
::*> export-policy rule create -vserver <cache-svm> -policyname default \
  -clientmatch <nfs-client-cidr> -rorule sys -rwrule sys -superuser sys -protocol nfs
```

Admin SVM 名は `vserver show -vserver *` の `type` 欄が `admin` のものです。

### 2.2 ゲートウェイ・NTP・DNS

```text
# 2.2.1 ゲートウェイ
::*> route add -vserver <admin-svm> -destination 0.0.0.0/0 -gateway <cache-gateway-ip>
::*> route show -vserver *

# 2.2.2 NTP（時刻合わせには数分かかる）
::*> cluster time-service ntp server create -server <cache-ntp-ip>
::*> cluster time-service ntp server show
::*> cluster date show

# 2.2.3 DNS
::*> dns create -vserver <admin-svm> -domains <dns-domain> -name-servers <cache-dns-ip>
::*> dns create -vserver <cache-svm> -domains <dns-domain> -name-servers <cache-dns-ip>
::*> dns show -vserver *
```

### 2.3 intercluster LIF 間の疎通確認

Cache 側の 2 つの intercluster LIF から、Origin 側の 2 つの intercluster LIF へ、全組み合わせで疎通します。

```text
::*> network ping -lif <cache-intercluster-lif-1> -vserver <admin-svm> -destination <origin-intercluster-lif-1>
::*> network ping -lif <cache-intercluster-lif-1> -vserver <admin-svm> -destination <origin-intercluster-lif-2>
::*> network ping -lif <cache-intercluster-lif-2> -vserver <admin-svm> -destination <origin-intercluster-lif-1>
::*> network ping -lif <cache-intercluster-lif-2> -vserver <admin-svm> -destination <origin-intercluster-lif-2>
```

**4 組すべてで疎通する必要があります。** どれか 1 つでも IP がダウンしていると FlexCache 作成がエラーになります（SMB 版と同じ制約）。1 つでも失敗したら停止します。

### 2.4 NFS サービスの有効化（Cache SVM）

SMB 版の CIFS サーバ作成と AD ドメイン参加は、NFS 版では不要です。代わりに Cache SVM で NFS を有効にします。

```text
::*> vserver nfs create -vserver <cache-svm> -v3 enabled -access true
::*> vserver nfs show -vserver <cache-svm>
```

NFSv4.x も使う場合は補足を参照してください。本線は v3 です。

## 3. FlexCache の設定

プロンプト名で実行する ONTAP を表します（Cache 側は `Cache::*>`、Origin 側は `FSx-for-ONTAP::*>`）。

### 3.1 クラスタピアの作成

```text
Cache::*> cluster peer create -address-family ipv4 \
  -peer-addrs <origin-intercluster-lif-1>,<origin-intercluster-lif-2> -applications flexcache
  Enter the passphrase:
  Confirm the passphrase:
  # ここで入力した passphrase を次の手順でも入力する。peer を張るための 1 回限りの値。

FSx-for-ONTAP::*> cluster peer create -address-family ipv4 \
  -peer-addrs <cache-intercluster-lif-1>,<cache-intercluster-lif-2> -applications flexcache
  Enter the passphrase:
  Confirm the passphrase:

Cache::*> cluster peer show
FSx-for-ONTAP::*> cluster peer show
```

passphrase は private channel で受け渡し、shell history・stdout・ログ・公開物に残しません。`cluster peer show` が両側で `Available` にならない場合は停止します。

### 3.2 SVM ピアの作成

```text
Cache::*> vserver peer create -vserver <cache-svm> -peer-vserver <origin-svm> \
  -applications flexcache -peer-cluster <origin-cluster-name>

FSx-for-ONTAP::*> vserver peer accept -vserver <origin-svm> -peer-vserver <cache-svm>

Cache::*> vserver peer show
FSx-for-ONTAP::*> vserver peer show
```

両側で peer state が `peered`、applications に `flexcache` が含まれることを確認します。片側だけ `peered`、applications 不足、identity 不一致の場合は停止します。

### 3.3 FlexCache volume の作成

AWS は FlexCache volume が FlexGroup であることを要求するため、`-auto-provision-as flexgroup` を使います。SMB 版の `-aggr-list` 明示に代えて、FSx for ONTAP では aggregate を明示せず auto-provision を本線にします。

```text
Cache::*> volume flexcache create \
  -vserver <cache-svm> \
  -volume <cache-volume> \
  -auto-provision-as flexgroup \
  -size <cache-size> \
  -origin-vserver <origin-svm> \
  -origin-volume <origin-volume> \
  -junction-path /<cache-volume> \
  -space-guarantee none

Cache::*> volume flexcache show
Cache::*> volume flexcache show -vserver <cache-svm> -volume <cache-volume> -instance
```

意味: Cache SVM `<cache-svm>` に、Origin SVM `<origin-svm>` の `<origin-volume>` に対する Cache volume `<cache-volume>`（FlexGroup）を作成し、`<cache-size>` で thin provisioning、`/<cache-volume>` にマウントします。security style は Origin（unix）を継承し、Cache 側では指定・変更できません。`volume flexcache show` が Cache を表示し、Origin/Cache identity が記録した値と一致するまで次へ進みません。

## 4. その他作業

### 4.1 NFS export とマウント

SMB 版の CIFS 共有作成に代えて、NFS では junction path を export policy 経由で公開し、client からマウントします。

```text
# Cache volume に export policy を適用（2.1 で作成した policy を使う）
Cache::*> volume modify -vserver <cache-svm> -volume <cache-volume> -policy default
Cache::*> volume show -vserver <cache-svm> -volume <cache-volume> -fields policy,junction-path
```

```bash
# NFS client 側（NFSv3）
sudo mount -t nfs -o vers=3 <cache-nfs-lif-1>:/<cache-volume> /mnt/<cache-volume>
findmnt -T /mnt/<cache-volume> -o TARGET,SOURCE,FSTYPE,OPTIONS
```

mount source と FSTYPE が想定と一致することを確認します。一致しない場合はマウントを解除し停止します。

### 4.2 キャッシュのウォームアップ（任意）

バッチ処理前などにヒット率を上げたい場合は prepopulate を使います。`-path-list` には FlexVol 内のディレクトリ構造を直接指定し、junction path や共有名は含めません。

```text
Cache::> set advanced
Cache::*> flexcache prepopulate start \
  -cache-volume <cache-volume> -cache-vserver <cache-svm> -path-list /<dir1>,/<dir2>
```

本来はブロック単位でキャッシュされますが、`-path-list` 指定時は該当ファイル・ディレクトリ全体がキャッシュされます。

## 補足

### write-back（既定は write-around）

本線の write-around では、Cache への write は Origin へ転送され、Origin がコミットしてから完了します（TR-4743 の NFS Write 動作）。write-back は Cache 側で先に確定させる書き込みモードで、ONTAP 9.15.1 で導入されましたが、**Origin/Cache 双方で 9.17.1P1 以降が強く推奨**され、9.15.1 は本番非推奨です。write-back を選ぶと、FlexGroup を単一 constituent にする推奨などの制約が加わります。AWS が FlexCache=FlexGroup を要求するため、構成は「単一 constituent の FlexGroup」になります。write-back は別承認のうえ、バージョン前提を満たしてから検討してください。

### NFSv4.x

Cache への NFSv4 アクセスは ONTAP 9.10.1 以降でサポートされます。NFSv4.x を使う場合は Cache SVM で `-v4.0 enabled` / `-v4.1 enabled` を有効にし、client 側の `vers=4.x` でマウントします。ACL やロックの扱いは v3 と異なるため、本線（v3）と分けて検証します。

### invalidation と整合性

FlexCache は delegation、ロック、negative lookup cache、disconnected mode で整合性を保ちます。Origin 側の変更は該当ブロックの委任を無効化し、Cache は次アクセス時に再取得します。ネットワーク切断時は、切断された Cache では既にキャッシュ済みのデータのみアクセスでき、再接続後に Origin 側の更新をファイル単位で反映します（TR-4743）。sizing は Cache を 90% で FIFO 追い出しする前提で見積もります。これらは結論の注記であり、個別環境での挙動は検証して確定してください。

## 停止条件

次のいずれかで直ちに停止します。

- Origin volume の security-style が unix でない、または NFS サービスが無効。
- export policy が NFS client / Cache SVM からのアクセスを許可しない。
- intercluster LIF 4 組のいずれかで疎通が成立しない。
- `cluster peer show` が片側でも `Available` にならない。
- SVM peer が片側のみ `peered`、applications に `flexcache` が無い、identity 不一致。
- `volume flexcache show` に Cache が出ない、または Origin/Cache identity が記録した値と違う。
- passphrase・実値が shell history・stdout・ログ・公開物に出た。

## Related documents

- [GCP / FSx for ONTAP のピアリングとレプリケーション未解決項目](gcp-to-fsx-ontap-peering-and-replication-open-items.md) — 本手順を GCNV を Cache 側に置く文脈へ適用する際の、GCNV 管理面インターフェースの未解決項目
- [GCP / FSx for ONTAP の read-only 事前確認とサンプル検証](gcp-to-fsx-ontap-preflight-and-sample-validation.md)
- [Evidence policy](../evidence-policy.md)
- [AWS: Creating a FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/create-flexcache.html)
- [NetApp: Create ONTAP FlexCache volumes](https://docs.netapp.com/us-en/ontap/flexcache/create-volume-task.html)
- [NetApp: FlexCache accelerate data access concept](https://docs.netapp.com/us-en/ontap/flexcache/accelerate-data-access-concept.html)
- [NetApp TR-4743: FlexCache in ONTAP](https://docs.netapp.com/us-en/ontap-technical-reports/nas-containers.html)
- [NetApp TR-4571: ONTAP FlexGroup volumes](https://docs.netapp.com/us-en/ontap-technical-reports/flexgroup-volumes.html)

<!-- lang-switcher:start -->
🌐 [日本語](flexcache-cli-nfs-simplified.md) | [English](../../en/reference/flexcache-cli-nfs-simplified.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
