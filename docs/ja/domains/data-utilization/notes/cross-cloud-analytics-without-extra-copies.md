---
title: クロスクラウド分析でコピーを増やさない — 書き込みパスはローカルに寄せ、クロスクラウドは読み取り側に置く
lifecycle: [design]
domains: [data-utilization, cost]
evidence: documented
source: https://aws.amazon.com/jp/blogs/news/fresher-insights-faster-decisions-talabats-near-real-time-analytics-across-aws-and-google-cloud/
lang: ja
---

# クロスクラウド分析でコピーを増やさないにはどうするか

書き込みパスはローカルに寄せ、クロスクラウド依存は読み取り側に置きます。同じ原則を ONTAP のデータモビリティにあてはめたとき、構成ごとに公式ドキュメントの記載と実機の公開記録がどこまであるかを分けます。

## このノートで学べること

- クロスクラウド・クロスリージョン分析で、エグレスと遅延と障害点を増やす構造と、それを避ける設計原則（書き込みはローカル・短く、クロスクラウドは読み取り側）
- その原則を ONTAP のデータモビリティ（SnapMirror / FlexCache）にあてはめたときに、FSx for ONTAP 内・オンプレミス連携で引ける範囲
- 他クラウドの ONTAP ベースサービス（Google Cloud NetApp Volumes, Azure NetApp Files）と FSx for ONTAP で組む FlexCache について、向きごとの公式ドキュメントの記載と、公開できる実機記録がないこと

## このノートが答えないこと

- 特定のエグレス単価やリージョン間転送料の実額（[課金の構造](../../cost/notes/provisioned-versus-consumed.md)と各社の料金ページ）
- 他クラウドの ONTAP サービスと組む FlexCache の実機挙動（読み取り性能、書き込み、Origin 更新時の整合）。公開できる実機記録がないため、本文は公式ドキュメントの記載だけを扱います

## 前提レベル

advanced

## 本文

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)

---

### 結論

**クロスクラウドやクロスリージョンでデータを分析するとき、コピーを増やすほどコスト・遅延・障害点が積み上がります。** 公開事例が共通して行き着く設計原則は 1 つです。

**書き込みパスはローカルで短く保ち、クラウドやリージョンをまたぐ依存は読み取り側に置く。**

**書き込み経路にクロスクラウドの依存を入れると、相手側の書き込み API の可用性と遅延に、自分の取り込みが結合します。** 読み取り側の問題が書き込み側の障害に化けます。クロスクラウドの難しさは、リトライが効き・キャッシュでき・取り込みに影響しない読み取り側に寄せるのが扱いやすい形です。

> **Evidence**: `documented` — 設計原則は AWS 公開事例（複数クラウドにまたがるニアリアルタイム分析）の記載に基づきます（2026-11-02 に確認）。ONTAP のデータモビリティにあてはめた範囲のうち、FSx for ONTAP 内とオンプレミス連携は公式ドキュメントと sibling の実測に基づきます。他クラウドの ONTAP サービスとの FlexCache は、各社の公式ドキュメントの記載（2026-11-03 に確認、[出典](#参照した公式ドキュメント)）に基づく `documented` で、**実機で通した公開記録はありません**（後述）。

---

### 原則の出どころ

**ある公開事例では、AWS 上のオペレーション基盤と他クラウド上の分析基盤をまたいでいました。** 最初はストリーミングの書き込みを相手クラウドのテーブルへ直接書く設計を試し、取り込みが相手側の書き込み API に結合して脆くなりました。作り直した形は、**データの物理コピーを片側に 1 つ保持し、両方のクラウドからそれぞれのツールでそのまま読み取る**というものです。「どちらのクラウドか」が分岐ではなくアクセスパスの選択になりました。

**この教訓はストレージ製品を問いません。** コピーを増やすたびに、そのコピーの権限・保持・削除・転送料を別に管理することになります。コピーを増やさない設計の価値はコストだけではない、という点は [コピーを増やさずにデータへ届く](reaching-data-without-copies.md) と同じです。

---

### ONTAP のデータモビリティへのあてはめ

**同じ原則を ONTAP の仕組みで実現する手段が 2 つあります。** ただし「引ける範囲」を正確に分けます。

| 手段 | 何をするか | 書き込み/読み取りの位置づけ |
|---|---|---|
| **SnapMirror** | ボリュームを別のファイルシステムへ非同期に複製する | 書き込みは Origin（ローカル）。宛先は読み取り。**宛先は break せずに S3 Access Point で読める**（[別ノート](serving-a-replication-destination-over-s3.md)） |
| **FlexCache** | 必要な分だけ Origin から取得する疎なキャッシュ | 読み取りを Cache 側（遠い側）に近づける。既定は書き込みを Origin が確認する。**Cache には S3 Access Point を付けられず、NFS / SMB で読みます**（[機構](reaching-data-without-copies.md#flexcache-が効く条件)） |

**どちらも「書き込みはローカル、クロスな依存は読み取り側」という原則に沿います。** SnapMirror は書き込みを Origin に閉じ、複製先で読ませます。FlexCache は読み取りを遠い側へ運び、キャッシュミスと書き込み確認だけが Origin への依存になります。機構はこの 2 つのノートにあるので再説明しません。

![データモビリティの 3 つの枠。上の枠は、オンプレミスの NetApp ONTAP を Origin に FlexCache で FSx for ONTAP の Cache へ必要分を取得し、Cache は NFS / SMB で読む（Cache に S3 Access Points は付けられない）。中の枠は、SnapMirror で FSx for ONTAP の宛先へ複製し、宛先に付けた S3 Access Points から break せず S3 API で読む。下の枠は他クラウドの ONTAP サービスで、公式ドキュメントに記載はあるが実機の公開記録がないため線は引かず、その旨を注記する。](../../../../_assets/images/ai-hpc-cross-cloud-mobility.svg)

図 1: FlexCache は読み取りを近づけ、S3 API で読ませるなら SnapMirror の宛先を使う。他クラウドの ONTAP サービスとの FlexCache は、公式ドキュメントに記載はあるが実機の公開記録がないため、線を引かない。

---

### 構成ごとの確認状況

**ここが最も取り違えやすいところです。** ONTAP のデータモビリティは「どの ONTAP 同士か」で、確認の根拠が違います。

| 構成 | 確認状況 |
|---|---|
| FSx for ONTAP ⇄ FSx for ONTAP（同一アカウント / クロスリージョン） | SnapMirror・FlexCache ともに公式ドキュメントに記載。sibling の実測あり |
| オンプレミスの NetApp ONTAP ⇄ FSx for ONTAP | 公式ドキュメントに FlexCache の 3 構成として記載。[reaching-data-without-copies](reaching-data-without-copies.md#flexcache-が効く条件) に出典 |
| **他クラウドの ONTAP サービス（Google Cloud NetApp Volumes, Azure NetApp Files）と FSx for ONTAP の FlexCache** | **相手クラウドの公式ドキュメントに記載があり、向きごとに違います。実機で通した公開記録は、このリポジトリにも Spoke にもありません。** 向きごとの記載は次の項に分けます |

#### 他クラウドの ONTAP サービスとの FlexCache の記載

**AWS の FSx for ONTAP のドキュメントが挙げる FlexCache の構成は 3 通りで、他クラウドの ONTAP サービスを含みません。** 3 通りは、オンプレミスの NetApp ONTAP を Origin に FSx for ONTAP を Cache にする構成、その逆向き、FSx for ONTAP 同士です（2026-11-03 に確認）。Google Cloud NetApp Volumes（GCNV）と Azure NetApp Files（ANF）のドキュメントは、自サービスの側から FlexCache を説明していて、記載は向きごとに違います。

| Origin → Cache | 区分 | 相手クラウド側のドキュメントの記載（2026-11-03 に確認） |
|---|---|---|
| FSx for ONTAP → GCNV | `documented`（FSx for ONTAP の名指しなし） | Cache の Origin は ONTAP クラスタ上の FlexVol または FlexGroup、と書かれています。Origin ボリュームではアクセス時刻の更新を無効にする必要があります。FlexCache は 2025-09-24 のリリースノートで allow-listed GA（許可リストへの登録が要る一般提供）とされています |
| GCNV → FSx for ONTAP | `documented`（条件つき。FSx for ONTAP の名指しなし） | Origin になれるのは Flex Unified の ONTAP-mode ボリュームだけです（2026-04-17 に GA）。ほかの GCNV ボリュームは Cache にしかなれません。ONTAP-mode のプールを外部の ONTAP クラスタとピアリングする手順が書かれています |
| FSx for ONTAP → ANF | `documented`（FSx for ONTAP の名指しあり） | 構成手順のページが、Cache の Origin としてオンプレミスの ONTAP、Cloud Volumes ONTAP、Amazon FSx for NetApp を挙げています（概要のページはオンプレミスと Cloud Volumes ONTAP だけを挙げています）。Cache は 2026-05 に GA です。Origin 側の ONTAP は 9.15.1 以降が条件で、Cache ボリュームは REST API でしかサポートされていません |
| ANF → FSx for ONTAP | 記載なし | 下の出典のページには、ANF を Origin にできるとも、できないとも書かれていません。ANF は Cache 側としてだけ説明されています |

**表の `documented` は、相手クラウドのドキュメントがそう書いているという意味で、FSx for ONTAP で動くことを示すものではありません。** 4 構成はどれも、AWS のドキュメントが挙げる対応構成の外にあります。ANF → FSx for ONTAP の「記載なし」は、非対応という意味でもありません。

**実機で通した公開記録は、このリポジトリにも Spoke にもありません。** S3-Burst の確認状況表は、FSx for ONTAP を Origin にした GCNV / ANF の Cache 可否を「未確認（ただし各クラウド側の要件は判明。2026-09-20 に調査）」、逆向きを「GCNV は条件つきで documented（2026-09-20）。ANF は未確認」と記録しています（[確認状況表](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification-status.md)）。GCNV との手順の未解決項目は [GCNV ⇄ FSx for ONTAP のピアリングとレプリケーションの未解決項目](../../../reference/gcp-to-fsx-ontap-peering-and-replication-open-items.md) に整理しています。

**他クラウド ONTAP サービス同士のネットワーク到達性**（マネージドな相互接続か、相互接続プロバイダ経由か）と、その上で ONTAP のレプリケーション/キャッシュが成立するかは別の問いです。到達性の検証と未解決項目は [GCNV ⇄ FSx for ONTAP の事前確認とサンプル検証](../../../reference/gcp-to-fsx-ontap-preflight-and-sample-validation.md) にあります。**ネットワークが届くことと、ONTAP のレプリケーション/キャッシュがその経路で機能することを混同しないでください。**

**だから、クロスクラウドのデータモビリティを ONTAP で設計するときは、FSx for ONTAP 内とオンプレミス連携に閉じる範囲と、他クラウドの ONTAP サービスを相手にする範囲を分けてください。後者は上の記載を出発点にして、自環境で通してから設計の前提に置きます。** 公式ドキュメントの記載を「FSx for ONTAP で動く」と読み替えないことが、このリポジトリの区分の目的です（[知見の分類ポリシー](../../../evidence-policy.md)）。

---

### 参照した公式ドキュメント

**以下は 2026-11-03 に読んだページです。** ページは更新されうるので、設計の根拠にする前に最新の記載を確認してください。

| 提供元 | ページ | この項で使った記載 |
|---|---|---|
| AWS | [Using FlexCache](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-flexcache.html) | FSx for ONTAP で使える FlexCache の 3 構成 |
| Google Cloud | [FlexCache overview](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/overview) | ONTAP-mode 以外の GCNV ボリュームは Cache にしかなれない |
| Google Cloud | [Create a FlexCache volume](https://docs.cloud.google.com/netapp/volumes/docs/configure-and-use/volumes/cache-ontap-volumes/create-flexcache-volume) | Origin は ONTAP クラスタ上の FlexVol または FlexGroup。Origin ボリュームのアクセス時刻更新を無効にする条件 |
| Google Cloud | [Peer clusters and SVMs](https://docs.cloud.google.com/netapp/volumes/docs/ontap/peer-clusters-svms) | ONTAP-mode のプールと外部の ONTAP クラスタのピアリング手順 |
| Google Cloud | [Release notes](https://docs.cloud.google.com/netapp/volumes/docs/release-notes) | FlexCache の allow-listed GA（2025-09-24）、ONTAP-mode の GA（2026-04-17） |
| Microsoft | [Configure a cache volume](https://learn.microsoft.com/en-us/azure/azure-netapp-files/configure-cache-volumes) | Cache の Origin に挙げられているもの。この記載は 2025-11-06 の編集で入り、2026-11-03 に読んだ版にも含まれる（[編集履歴](https://github.com/MicrosoftDocs/azure-docs/commits/main/articles/azure-netapp-files/configure-cache-volumes.md)で確認） |
| Microsoft | [Understand cache volumes](https://learn.microsoft.com/en-us/azure/azure-netapp-files/cache-volumes) | Origin の例としてオンプレミスと Cloud Volumes ONTAP だけを挙げる概要 |
| Microsoft | [Cache volume requirements](https://learn.microsoft.com/en-us/azure/azure-netapp-files/cache-requirements) | Origin 側の ONTAP 9.15.1 以降、REST API のみ |
| Microsoft | [What's new](https://learn.microsoft.com/en-us/azure/azure-netapp-files/whats-new) | キャッシュボリュームのプレビュー（2025-11）と GA（2026-05） |

---

### データ主権・リージョン制約が効く場面

**ライフサイエンス・公共・金融では、クロスクラウド/クロスリージョンの「どこにコピーが落ちるか」が規制の問題になります。** エグレスコストより先に、データの所在が許されるかが制約になります。

- **コピーを増やさない設計は、データ主権の観点でも整理しやすくなります。** 物理コピーが 1 か所に閉じるなら、「どのリージョン・どのクラウドにデータが存在するか」を 1 点に絞って説明できます。
- ただし **これはガバナンスの設計の出発点であって、法務・コンプライアンス・規制の判断ではありません。** どのデータがどこに置けるかの最終判断は、各組織の規制要件に照らして行ってください。区分の考え方は [知見の分類ポリシー](../../../evidence-policy.md) に準じます。

---

### よくある誤解

| 誤解 | 実際 |
|---|---|
| クロスクラウド分析は相手クラウドにテーブルを作って書き込むのが素直 | **書き込みにクロスクラウド依存を入れると取り込みが相手の API に結合して脆くなります。** 書き込みはローカルに寄せます |
| コピーを複数持てば各クラウドで速く読める | コピーごとに権限・保持・削除・転送料が増えます。片側に 1 コピーで両方から読む形が扱いやすい |
| ネットワークが相手クラウドに届けば FlexCache も組める | **ネットワーク到達性と ONTAP のキャッシュ/複製の成立は別の問いです。** 他クラウドの ONTAP サービスとの FlexCache は、公式ドキュメントの記載が向きごとに違い、実機の公開記録もありません（[構成ごとの確認状況](#構成ごとの確認状況)） |
| SnapMirror 宛先を分析に使うには break が要る | **要りません。** 宛先を mount すれば読み取りで S3 Access Point を取り付けられます（[別ノート](serving-a-replication-destination-over-s3.md)） |
| コピーが 1 か所ならデータ主権は自動的に満たされる | 整理はしやすくなりますが、**どこに置けるかの最終判断は規制要件に照らす必要があり、ガバナンスの設計はその判断ではありません** |

---

### 関連ドキュメント

- [Domain — データ活用](../README.md) — このモジュールのハブ
- [コピーを増やさずにデータへ届く](reaching-data-without-copies.md) — SnapMirror / FlexCache / FlexClone の機構・権限・制約
- [SnapMirror の宛先は break せずに S3 API で読める](serving-a-replication-destination-over-s3.md) — 複製先を読み取りで分析に使う
- [AI・HPC ワークロードのデータ層に FSx for ONTAP を経由させるかを決める](../../../reference/decision-trees/ai-workload-data-layer.md) — クロスクラウドの分岐を含む決定木
- [課金は「確保した量」と「使った量」に分かれる](../../cost/notes/provisioned-versus-consumed.md) — コピーと転送料のコスト構造
- [知見の分類ポリシー](../../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../../README.md) | [Domain — データ活用](../README.md)
