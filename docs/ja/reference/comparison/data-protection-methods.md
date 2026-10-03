---
title: データ保護方式の比較 — Snapshot / ボリュームバックアップ / AWS Backup / SnapMirror
lifecycle: [design]
domains: [data-protection, cost]
evidence: documented
source: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html
lang: ja
---

# データ保護方式の比較

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)

---

## 結論

**Snapshot、バックアップ、SnapMirror は、復旧点の置き場所と更新方法が違います。** 守る障害、必要な整合性、管理資格情報の分離を決めて組み合わせます。

- **Snapshot** は同一 volume 内の変更前状態へ戻す用途です。volume や file system の喪失からは独立しません。
- **ボリュームバックアップ / AWS Backup** は file system と論理的に分離した復旧点です。別リージョン・別アカウントへコピーできますが、復旧にはリストア先の file system と SVM が必要です。
- **SnapMirror** は別 file system の宛先 volume を更新する用途です。ソースの変更も次回更新で届くため、保持世代を別に設計します。

> **区分** — `documented`。範囲と制約は AWS / NetApp の一次情報に基づきます。
> **復旧時間の実測値は含みません。** RTO を名乗るには自環境でのリストア訓練が必要です。

---

## 比較

### 判定基準

| 判定 | 意味 |
|---|---|
| **Protected** | 通常の取得・更新が成功し、障害前の復旧点が保持されていれば、その方式の標準範囲で復旧できる |
| **Not protected** | その方式だけでは障害から独立した復旧点を持たない |
| **Conditional** | 配置、コピー先、資格情報分離、保持期間、アプリケーション連携の条件で判定が変わる |

資格情報侵害は、その方式の復旧点を削除または変更できる管理資格情報が侵害された場合を指します。
`Protected` も復旧訓練、権限、容量、依存サービスの確認を省略できるという意味ではありません。

### 障害シナリオ別の保護範囲

| 障害・要件 | Snapshot | ボリュームバックアップ / AWS Backup | SnapMirror replication |
|---|---|---|---|
| ファイルの誤削除・誤更新 | **Protected** — 変更前の Snapshot を保持 [S] | **Protected** — 変更前の backup を保持 [B] | **Conditional** — 更新前か、宛先 Snapshot が残る場合 [R] |
| volume の喪失 | **Not protected** — Snapshot も同じ volume に存在 [S] | **Conditional** — user-initiated / final backup を保持し、新規 volume へ復元 [B] | **Protected** — 別 volume への転送が完了 [R] |
| file system の喪失 | **Not protected** — file system と共に失う [S] | **Conditional** — user-initiated / final backup を保持し、復元先の file system と SVM がある [B] | **Protected** — 宛先が別 file system にあり利用可能 [R] |
| AZ の停止 | **Not protected** — AZ 独立性は Snapshot ではなく deployment type の責務 [A] | **Protected** — backup は複数 AZ に冗長保管。復元先は別途必要 [B] | **Conditional** — 宛先が停止 AZ の外にあり、切り替え可能 [R] |
| Region の停止 | **Not protected** — 同一 file system 内 [S] | **Conditional** — 別 Region への copy が完了し、復元先を用意できる [C] | **Conditional** — cross-Region 宛先と切り替え手順がある [R] |
| 管理資格情報 / アカウントの侵害 | **Not protected** — Snapshot 管理権限があれば削除可能 [D] | **Conditional** — 分離アカウントへの copy と独立した保持・復元権限がある [C] | **Not protected** — 継続更新する replica は offline copy ではない [C] [R] |
| アプリケーション整合性 | **Conditional** — アプリケーションの I/O 静止 / 連携が必要。複数 volume は consistency group で同時取得 [F] [G] | **Conditional** — backup 前の I/O 静止 / 連携が必要。標準 backup は crash-consistent [F] | **Conditional** — アプリケーション整合性を確保したソース Snapshot を転送 [R] [G] |
| ソース側の論理破損 | **Conditional** — 破損前の世代を検知まで保持 [S] | **Conditional** — 破損前の backup を検知まで保持 [B] | **Conditional** — 破損の転送前か、宛先に正常な Snapshot を保持 [R] |

出典記号は [S] Snapshot、[B] backup、[C] backup copy、[R] SnapMirror、[A] AZ 可用性、[D] Snapshot 削除、[F] backup consistency、[G] consistency group です。

### 方式ごとの用途と制約

| 方式 | 向いている状況 | 制約 | 一次情報 |
|---|---|---|---|
| Snapshot | 同一 volume 内のファイル・フォルダを変更前へ戻す | 同じ volume / file system に依存し、変更ブロックが容量を消費 | [AWS][S] |
| Amazon FSx volume backup | volume 単位の独立した復旧点を保持 | RW volume のみ。保存 Region 内の既存 file system / SVM へ新規 volume として復元 | [AWS][B] |
| AWS Backup | スケジュール、vault、cross-account copy を一元管理 | 権限、vault、copy rule の設計が増える。FSx for ONTAP backup と同じ file system consistency | [AWS][B] |
| SnapMirror | 別 file system に更新済み volume を用意 | 変更を追従。宛先は break まで read-only。FSx for ONTAP は volume-level の非同期 replication のみ | [AWS][R] |

**`DP`（データ保護）・ロードシェアリングミラー・FlexCache / SnapMirror の宛先 volume は backup できません。** backup は複製元で取得します。

[S]: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html
[B]: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html
[C]: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html
[R]: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html
[A]: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html
[D]: https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/manually-delete-snapshots.html
[F]: https://aws.amazon.com/fsx/netapp-ontap/features/
[G]: https://docs.netapp.com/us-en/ontap/consistency-groups/index.html

---

## レプリケーションとコピーは別の操作

**表の「複製」（SnapMirror）と「コピー」（ボリュームバックアップ / AWS Backup）は、別の操作です。** どちらも「別リージョンにデータを持つ」と言えてしまうので、要件を詰める前にここを揃えてください。分かれ目は**宛先に何が残るか**です。

| | SnapMirror の**レプリケーション（複製）** | ボリュームバックアップ / AWS Backup の**コピー** |
|---|---|---|
| 宛先に置かれるもの | **ボリューム**（宛先 SVM 上の `DP` ボリューム） | **バックアップ（リカバリポイント）。** ボリュームはありません |
| ソースの変更 | **追従します**（スケジュールごとに差分転送） | **追従しません**（取得時点の像） |
| 宛先を使うには | 関係を break して昇格 | **リストアが必要で、できるのは新規ボリューム** |
| 関係の継続 | **続きます** | **続きません**（1 回ごとに独立した成果物） |
| RPO を決めるもの | レプリケーションのスケジュール（5 分まで） | バックアップの間隔（目安 60 分） |
| 平常時に宛先で払うもの | ファイルシステムの容量とスループット | バックアップストレージのみ |
| スタンバイ系からアクティブ系へのデータの切り戻し | 逆向きに `snapmirror resync` | **経路がありません** |

**AWS 側の語も分かれています。** AWS Backup のコンソールとドキュメントはこの操作を一貫して「コピー」と呼び、画面にも Copy jobs / Copy rule / `Copy type` と出ます。FSx for ONTAP 側の API 名も `CopyBackup` です。レプリケーションは、Amazon S3 のクロスリージョンレプリケーションのように**宛先が実体として追従する機構**に使われる語です。

この違いは RTO に出ます。**レプリケーションなら宛先のボリュームを昇格するだけですが、コピーからはファイルシステムと SVM を作ってリストアするところから始まります。** 逆に SnapMirror を「バックアップ」と呼ぶのもずれます。宛先は追従するので、**ソースで消したファイルは次の転送のあと宛先の最新状態からも消えます**（宛先の Snapshot に残る範囲は別）。世代を残すのは Snapshot か SnapVault の役割です。

詳細は [バックアップコピーはリストアするまでファイルシステムを持たない](../../domains/data-protection/notes/backup-copies-across-regions-and-accounts.md#レプリケーションとコピーは別の操作) にあります。

---

## DR 設計を決めるこの制約

**「本番を SnapMirror で別リージョンへ複製し、複製先をバックアップする」という構成は成立しません。** 複製先は `DP` ボリュームで、バックアップ対象外です。

したがって **バックアップは複製元で取ります。** 別リージョンに世代を持ちたい場合は、複製先で別途 Snapshot を運用するか、複製元のバックアップを前提に組みます。

---

## SnapMirror のポリシー種別と保持・ラグ・扇形展開の上限

**SnapMirror のポリシー種別は、宛先に何を転送し、宛先側でどれだけ保持するかを決めます。** ここは AWS ドキュメントではなく ONTAP 一般の挙動なので、FSx for ONTAP で同じ値が通るかは、公式記載か実測がない限り未確認として扱ってください。FSx for ONTAP は volume-level の非同期レプリケーションのみに対応しており（この範囲は AWS 記載。表の [AWS][R] 参照）、SVM-DR や同期レプリケーションの可否はこの比較の対象外です。

| ポリシー種別 | 宛先に残るもの | 向いている状況 | トレードオフ |
|---|---|---|---|
| MirrorAllSnapshots（async-mirror 系） | ソースのアクティブファイルシステムと、ソース側 Snapshot を全転送 | ソースと同じ Snapshot 構成をそのまま宛先に持ちたい | 宛先の保持はソースの Snapshot ポリシーに従属し、**宛先独自の長期保持を持ちません** |
| Vault（vault 系・旧 SnapVault） | ラベル付き Snapshot を宛先の保持ルールで残す | 宛先で長期の世代保持（アーカイブ）をしたい | **アクティブファイルシステムの即時フェイルオーバー用途ではありません。** 復旧には宛先 Snapshot からのリストアが要ります |
| MirrorAndVault（mirror-vault 系） | アクティブファイルシステムの複製と、宛先独自の長期保持を 1 関係に同居 | DR と長期保持を 1 本の関係でまとめたい | 保持ルールの設計が増え、宛先容量もその保持ぶん要ります |

**システム定義のポリシー名**（`MirrorAllSnapshots` / `MirrorAndVault` / `MirrorLatest` ほか）は ONTAP の [snapmirror policy create](https://docs.netapp.com/us-en/ontap-cli/snapmirror-policy-create.html)（2026-09-20 に確認）に、種別ごとの意味（`async-mirror` / `vault` / `mirror-vault`）は NetApp KB [What are the SnapMirror policy types](https://kb.netapp.com/onprem/ontap/dp/SnapMirror/What_are_the_SnapMirror_policy_types_and_what_do_they_mean)（2026-09-20 に確認）に記載があります。カスタム保持ルールの定義は ONTAP の [Create a custom SnapMirror replication policy](https://docs.netapp.com/us-en/ontap/data-protection/create-custom-replication-policy-concept.html) にあります。この整理の出典 TR は **TR-4015（SnapMirror Asynchronous の構成ガイド）** です（NetApp ONTAP Technical Reports の「Data protection and disaster recovery」索引、2026-09-30 版の SnapMirror › SnapMirror Asynchronous 節に収録）。

### 保持の選び方

- **宛先で独自に世代を長く残す必要があるか** — 要るなら Vault か MirrorAndVault。宛先の保持はソース Snapshot ポリシーとは別に、ラベル付き保持ルールで決めます。
- **即時にフェイルオーバーできる最新のアクティブファイルシステムが要るか** — 要るなら MirrorAllSnapshots か MirrorAndVault。Vault 単独はアーカイブ寄りで、フェイルオーバー用途には別の宛先 Snapshot リストアが挟まります。
- **両方要るか** — MirrorAndVault を 1 本で使うか、用途別に関係を分けます。どちらも保持ルールと宛先容量の設計が前提です。

### 転送スケジュールとラグの監視

SnapMirror Async は転送スケジュールで更新間隔を決め、更新と更新の間はラグ（最終転送からの経過）が RPO に直結します。FSx for ONTAP では SnapMirror のラグ・転送時間・健全性を Amazon CloudWatch のメトリクス（`SnapMirrorLagTime` / `SnapMirrorTransferDuration` / `SnapMirrorHealthy`）で監視できます（この監視経路の実測は [Lakehouse 連携の設計考慮](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/ja/s3ap-flexcache-snapmirror-considerations.md) にあります。SnapMirror Async の最短スケジュールが 5 分であることも同記録にあります）。

### カスケードと扇形展開（fan-out）の上限

- **扇形展開（fan-out）** は 1 本のソース volume から複数の宛先へ、**カスケード**は宛先からさらに三次先へ保護を広げる構成です（[ONTAP data protection fan-out and cascade deployments](https://docs.netapp.com/us-en/ontap/data-protection/supported-deployment-config-concept.html)、2026-09-20 に確認）。
- 1 本のソース volume から扇形展開できる宛先 volume 数の上限は、**アレイのモデルによって 8 または 16** です（[ONTAP SnapMirror limitations](https://docs.netapp.com/us-en/ontap/data-protection/limitations-mirror-relationships-concept.html)、2026-09-20 に確認）。**これは ONTAP 一般の上限で、FSx for ONTAP で同じ値が適用されるかは未確認です**（AWS の該当記載を確認できていません）。

> **区分** — この節は ONTAP 一般の `documented` です。TR-4015 と上記 docs.netapp.com の各ページに基づきます。**FSx for ONTAP で同じ挙動・同じ上限になるかは、AWS の公式記載または実測がない限り未確認**として扱ってください。

### break なしで読める稼働中の宛先

**稼働中の SnapMirror 宛先の volume は、関係を break することも、クローンを作ることもなく、FSx for ONTAP S3 Access Points 経由で読めます**（[Lakehouse 連携の 2026-09-13 実測](https://github.com/Yoshiki0705/FSx-for-ONTAP-Lakehouse-Integrations/blob/main/docs/ja/s3ap-flexcache-snapmirror-considerations.md)）。ONTAP 側で宛先 DP volume を mount して S3 Access Points をアタッチすると、読み取りは通り、書き込みは拒否され、各転送の新規データが同一アクセスポイント経由で見えます。書き込みが要る場合は宛先 Snapshot のクローンを使います。**「宛先を読むには break が要る」という古い前提では設計しないでください。**

break と昇格が要るのは、宛先で本番サービスを引き継ぐ DR フェイルオーバーのときです。その手順は [VMware → EC2/FSx for ONTAP の DR runbook](https://github.com/Yoshiki0705/VMware-Migration-EC2-ONTAP/blob/main/docs/ja/dr-snapmirror-runbook.md) にあります（この runbook は break/昇格の手順書であって、「読むのに break が要る」という意味ではありません）。

> **DR 手順の順序に関する補足**: 読み取り提供（mount またはクローン）とフェイルオーバー（break → 昇格）は別の要件です。読むためだけに break すると、宛先がソースから切り離され、以後の転送が止まります。

### ONTAP で作ったボリュームが AWS の API に現れるまでの時間

ONTAP REST API でボリュームを作ると、それが Amazon FSx の API（`describe-volumes` など）に現れるまでに時間がかかり、**この時間の上限は分かっていません。** 姉妹プロジェクトの実測では 20 秒間隔・ギャップ無しの観測で数百秒から千数百秒を要し、別の回では千数百秒経ってもまだ未出現でした。**3 回の観測が一致しないため上限値として扱えません**（[S3-Burst の検証状況](https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files/blob/main/docs/ja/verification-status.md)）。AWS の記載は「数分」ですが、**特定の秒数を見込んだ設計にはせず、こちら側で制御できない反映待ちとしてポーリングで扱ってください。**

---

## リストアテスト

**取得の成功とリストアの可否は別物です。** バックアップのログが成功していても、業務に耐える水準で復旧できるかは、実際に戻してみるまで分かりません。FSx for ONTAP は Snapshot のポインタ管理により、データブロックを動かさずに FlexClone で複製できるため、本番に影響を与えずにリストアテストを実施できます（[AWS ブログ「そのデータ復旧できますか？」](https://aws.amazon.com/jp/blogs/news/feasibility-of-data-recovery-written-by-netapp-2024/)、サイバーレジリエンスシリーズ第 3 回。内容は引用の都合で要約しています）。

ランサムウェア被害を想定したリストアシナリオの要点は次のとおりです。

| 手順 | 内容 | 理由 |
|---|---|---|
| 1 | 被害前の Snapshot を特定する | 被害後の Snapshot から戻すと暗号化済みデータを復旧してしまう |
| 2 | その Snapshot から FlexClone で**別の場所に**復旧する | 被害を受けたボリュームは攻撃の調査対象なので、**上書きリストアはしない** |
| 3 | 恒久的に使うなら、split 前に必要容量を確認してから split する | クローンは親 Snapshot を共有するため、split で独立させると親ぶんの実容量が要る。見積りは ONTAP の `volume clone show -estimate` で取る |
| 4 | 一時的な確認だけなら、クローンを offline にして delete する | 残置するとクローンが親 Snapshot を保持し続け、親側の削除や保持を縛る |

> **これは手順の記載であって、実行ではありません。** 本リポジトリでこのリストアテストを実行してはいません。手順 3・4 の `volume clone show -estimate` / split / offline / delete は ONTAP 一般の操作で、FSx for ONTAP での所要時間や容量挙動は自環境での確認が要ります。

---

## 選び方

**上から順に確認してください。** 答えが決まった時点で必要な方式が決まります。

| # | 確認項目 | 判断への影響 |
|---|---|---|
| 1 | 守りたい障害はどこまでか（file / volume / file system / AZ / Region / 管理資格情報 / 論理破損） | 障害シナリオ表で `Not protected` の方式を単独採用しない |
| 2 | 複数 volume やデータベースでアプリケーション整合性が必要か | アプリケーションの I/O 静止 / 連携を必須とし、複数 volume は consistency group で同時取得する |
| 3 | ソース側の管理資格情報が侵害されても復旧点を残す必要があるか | 管理権限を分離したアカウントへの backup copy と保持制御を検討する |
| 4 | file system を削除しても残す必要があるか | user-initiated backup または final backup の保持を確認する |
| 5 | 別 Region に備える必要があるか | 分単位の RPO と切り戻しが要件なら SnapMirror、時点 copy と管理境界の分離が要件なら backup copy を起点にする |
| 6 | SnapMirror を使うか | backup は複製元で取得し、宛先 Snapshot の保持も決める |
| 7 | 経路に NAT があるか | SnapMirror のネットワーク経路を先に確認する |
| 8 | 保持したい世代数と期間 | 検知までの期間を含め、Snapshot / backup の保持と容量を設計する |
| 9 | リストアにかけられる時間（RTO） | Snapshot restore、backup restore、SnapMirror failover を同じ手順として扱わない |
| 10 | リストアと切り戻しを実際に試したか | 未実施なら RTO と復旧可能性は未確認のまま |

手順 10 を確認項目に入れているのは、**取得の成功監視と復旧可能性は別物**だからです。手順は [Snapshot があることと復旧できることは別](../../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md#自環境での確認手順) にあります。

---

## 不変性が必要な場合

上の 4 方式はいずれも**削除できます。** 保持期間中の削除そのものを禁止したい場合は WORM の領域で、別の判断になります。

| 観点 | SnapLock Compliance | SnapLock Enterprise |
|---|---|---|
| 向いている状況 | 保持期間中の削除を一切許容しない | 認可された管理者による例外を残したい |
| トレードオフ | **自分でも削除できません。** 保持期間ぶんの容量を確約することになります | 特権削除の運用と監査ログボリュームの管理が増えます |
| 前提条件 | — | **同一 SVM に監査ログボリューム**（最小保持 6 か月。**この間ボリューム・SVM・ファイルシステムのいずれも削除できません**） |

**モードは一度設定すると変更できません。** 詳細は [SnapLock は有効化とロックが別](../../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) にあります。

---

## 判断フロー

```mermaid
graph TD
    A[守りたい障害を決める] --> F{ファイル単位の誤操作}
    F -->|それだけ| S[Snapshot]
    F -->|それ以上も| V{ボリューム削除}
    V -->|備える| B[ボリュームバックアップ]
    V -->|さらに| FS{ファイルシステム削除}
    FS -->|備える| AB["AWS Backup<br/>削除後も保持される"]
    FS -->|さらに| R{リージョン障害}
    R -->|分単位の RPO と切り戻し| SM[SnapMirror で別リージョンへ]
    R -->|隔離された保管| BC["バックアップを別リージョンへコピー<br/>復旧時に FS と SVM を作る"]

    SM --> DP["複製先は DP ボリューム<br/>バックアップできない"]
    DP --> SRC["バックアップは複製元で取る"]

    A --> W{保持期間中の削除を<br/>禁止する必要があるか}
    W -->|禁止する| C["SnapLock Compliance<br/>自分でも削除できない"]
    W -->|例外を残す| E["SnapLock Enterprise<br/>監査ログボリュームが前提"]

    S --> T[リストアを実際に試す]
    B --> T
    AB --> T
    SM --> T
    T --> RTO["ここで初めて RTO を名乗れる"]
```

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| Snapshot があれば復旧できる | 同一ファイルシステム内にあります。**ボリューム削除には対応できません** |
| バックアップだけではリージョン障害に備えられない | **別リージョンへコピーできます**（2026 年 8 月以降）。リストア先はバックアップと同一リージョンのままなので、**そこに FS を作る時間が RTO に乗ります** |
| 別リージョンへコピーすれば、そこから直接リストアできる | リストアにはコピー先リージョンの**ファイルシステムと SVM が必要**です |
| SnapMirror の複製先をバックアップすればよい | **複製先はバックアップ対象外**です。複製元で取ります |
| 4 つのうちどれか 1 つを選ぶ | 守れる範囲が違います。**組み合わせる対象**です |
| どの方式でも同じ RTO を名乗れる | 世代で変わります。第 2 世代はリストア開始から数分で読めます |
| SnapLock は保護方式の 1 つ | 削除を禁止する仕組みで、復旧手段ではありません |
| Compliance にすれば安全側に振れる | **自分でも削除できません。** 保持期間ぶんの容量を確約します |
| バックアップの成功監視ができていれば復旧できる | 取得とリストアは別です。試していなければ RTO は推測値です |

---

## 参照した一次情報

| 論点 | 出典 |
|---|---|
| Snapshot の配置、誤削除からの復元、容量消費 | [AWS: Protecting your data with snapshots](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/snapshots-ontap.html) |
| backup の複数 AZ 保管、RW volume 制約、保持、同一 Region 内への restore、crash-consistent な性質 | [AWS: Protecting your data with volume backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/using-backups.html) / [AWS: FSx for ONTAP features](https://aws.amazon.com/fsx/netapp-ontap/features/) |
| cross-Region / cross-account copy と資格情報・KMS key 侵害への分離 | [AWS: Copying backups](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copy-backups.html) |
| SnapMirror の周期更新、in-Region / cross-Region、volume-level の対象範囲 | [AWS: Replicating your data using SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/scheduled-replication.html) |
| Multi-AZ の AZ 障害時 failover と backup の複数 AZ 保管 | [AWS: Availability, durability, and deployment options](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/high-availability-AZ.html) |
| 複数 volume の crash-consistent / application-consistent Snapshot | [NetApp: ONTAP consistency groups](https://docs.netapp.com/us-en/ontap/consistency-groups/index.html) |
| backup copy と SnapMirror の復旧経路の違い | [AWS: Choosing between backup copies and SnapMirror](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/copying-backups-same-account.html) |
| SnapLock の 2 つの保持モードと監査ログ volume の前提 | [AWS: How SnapLock works](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/how-snaplock-works.html) |
| Snapshot / backup の上限と自動 backup の保持期間 | [AWS: Quotas](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/limits.html) |

---

## 比較時点

2026-09-20 時点の情報です。**機能は変わります。** 設計に使う前に各出典の現行版を確認してください。

**この表は一度実際に変わりました。** 2026 年 8 月まで「バックアップのリストア先は同一リージョン」を「バックアップではリージョン障害に備えられない」と書いていましたが、別リージョンへのコピーが可能になり、前提が崩れました。しかも [ONTAP ユーザーガイドの Document History には項目がありません](../recent-updates.md#更新の追跡方法)。

---

## 関連ドキュメント

- [比較マトリクス](README.md) — このディレクトリのハブ
- [Snapshot があることと復旧できることは別](../../domains/data-protection/notes/snapshots-are-not-a-recovery-plan.md) — 各方式の守備範囲の詳細
- [バックアップコピーはリストアするまでファイルシステムを持たない](../../domains/data-protection/notes/backup-copies-across-regions-and-accounts.md) — 別リージョン・別アカウントへの経路と実測
- [SnapLock は有効化とロックが別](../../domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md) — 不可逆な選択
- [切り戻せる時点はクライアントが書き始めた瞬間に閉じる](../../playbooks/03-migrate/notes/where-the-rollback-window-closes.md) — SnapMirror の切り替えと切り戻し
- [課金は「確保した量」と「使った量」に分かれる](../../domains/cost/notes/provisioned-versus-consumed.md) — 各方式のコスト特性
- [移行方式 決定ツリー](../decision-trees/migration-method.md) — 移行方式の選択
- [知見の分類ポリシー](../../evidence-policy.md)

---

[🏠 リポジトリトップ](../../../../README.md) | [Reference](../README.md) | [比較マトリクス](README.md)
