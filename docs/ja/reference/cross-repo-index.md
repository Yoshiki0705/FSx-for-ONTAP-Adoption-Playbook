---
title: プロジェクト間の引用索引 — どの主張をどのリポジトリから引いているか
lifecycle: [assess, design]
domains: [performance, block-storage, data-utilization]
evidence: documented
source: https://github.com/Yoshiki0705/S3-Burst-on-ONTAP-Files
lang: ja
---

# プロジェクト間の引用索引

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## 結論

**このリポジトリは、実測環境を持つ他のプロジェクトの数値を引用します。転記はしますが、再測定はしません。**

同じ実装や同じ測定を 2 か所に置くと、片方だけが更新されて古い側が新しい側を上書きします。だから **分担は「環境を持っているプロジェクトが数値を持ち、このリポジトリは判断の指針を持って引用する」** です。

**そして引用は静かに腐ります。** 引用先のファイルが移動しても、主張が撤回されても、こちら側の記述は何も変わらないまま残ります。**だから引用を表にして、引用先に主張がまだ存在するかをゲートで検証します。**

| ゲート | 何を検証するか | ネットワーク |
|---|---|---|
| `make cross-repo` | 本文に現れる sibling repo へのリンクが下の表に載っているか。表の行の引用元ファイルが実在し、実際にそのリンクを含むか | 不要 |
| `make cross-repo-external` | 引用先のパスが今も存在し、**確認する文字列**がまだ含まれているか | 必要 |

---

## 分担の原則

| 種類 | どこが持つか | このリポジトリの役割 |
|---|---|---|
| 性能の実測値 | 測定環境を作ったプロジェクト | 条件付きで引用し、設計判断に翻訳する |
| 業種別ユースケースの実装 | [FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns) | [業種別リソースマップ](industry-resource-map.md) から索引し、読む順序を示す |
| 監査ログの外部連携 | [FSx-for-ONTAP-Observability-integrations](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations) | 何が見えて何が見えないかを書く |
| サイバーレジリエンスの実装パターン | [FSx-for-ONTAP-Cyber-Resilience-Patterns](https://github.com/Yoshiki0705/FSx-for-ONTAP-Cyber-Resilience-Patterns) | 選択肢の比較と判断基準 |
| 最小構成を動かす手順 | **このリポジトリ**（[`examples/`](../../../examples/)） | 保守する |
| エビデンス階層と公開物の規約 | **このリポジトリ**（[`AGENTS.md`](../../../AGENTS.md)） | 保守する |

**sibling repo 側の規約をここから一方的に変えることはしません。** 提案は Issue で出します。逆方向の依頼も同じで、[cross-repo finding](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/new?template=cross-repo-finding.yml) のテンプレートがあります。

---

## 引用表

**この表の形式はゲートが読みます。** 列を増やす・順序を変える・行を表の外に書くと `make cross-repo` が失敗します。

- **引用元** — このリポジトリ内の相対パス。その本文が引用先へのリンクを実際に含んでいること
- **確認する文字列** — 引用先にまだ存在すべき短い literal。**主張そのものを指す文字列にしてください。** 見出しやファイル名だと、主張が撤回されてもゲートが通ります
  > **この文字列が検出できないもの**: probe は**その文字列が引用先に存在するか**しか見ません。**引用元の中で記述が古くなり、同じファイルの本文が別のことを言っている状態は検出できません。**
  > 実例があります。`Finalize は意図的に未実施` を probe にしていた行は、引用先のステータス行にその文が残ったまま、同じファイルの本文が「承認を得て実行」に更新されていました。**ゲートは「probe 現存」と報告し続け、気づいたのは相手側から指摘を受けたときです。**
  > **引用元が自己矛盾している可能性は、ゲートでは拾えません。** 逆リンクを依頼するときなどに、引用している主張が今も本文と一致しているかを併せて訊いてください。

**この表の後半 10 行は、ゲートを入れた時点で既に存在していた引用です。** 仕組みが無かった間に積まれ、登録も検証もされていませんでした。**引用が 8 ファイル分あることに誰も気づいていなかった、というのがこのゲートの最初の成果です。**

<!-- cross-repo-table:start -->

| 引用元 | リポジトリ | パス | 確認する文字列 | 何を引いているか |
|---|---|---|---|---|
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `EC2 の 1 フローあたり全二重 5 Gbps` | FSx for ONTAP の単一接続が当たっているのは EC2 の 1 フロー上限であること |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `500 MiBps に一致する` | Amazon EFS の 499.79 MB/s は 1 フロー上限ではなくクライアント単位のクォータに一致すること。**近い値を同じ原因に束ねない** |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `45% 違った` | 同一構成・同一パラメータで 2 回測って 45% 振れ、違いはキャッシュに何が残っていたかだけだったこと |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `0.18 倍` | 8 台・128 接続で、同じファイルを共有した場合と重ならない領域を読んだ場合の差 |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `既定 65,536 のままだと` | 既定 65,536 のままだと `rsize` が 64 KiB に切り下がるため、測定前に引き上げていること |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/throughput-protocol-matrix-plan.md` | `コマンドラインでは渡せない` | 測定に使った器具と、パラメータがコマンドラインから渡せない制約 |

| `docs/ja/reference/comparison/throughput-levers.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `3,551〜5,149 MB/s` | 接続数を上げたときの実測値と、それが追加料金なしで最も大きく動いた手段だったこと |
| `docs/ja/reference/comparison/throughput-levers.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `観測したチャネル数は 4 であり` | SMB Multichannel のチャネル数が設定を上げても 4 で止まったこと |
| `docs/en/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-authorization-model.en.md` | `There is no subtraction across them` | The two authorization layers are independent, with no subtraction across them |
| `docs/en/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/en/saas-to-fsx-ontap-migration.md` | `always requires an agent and Basic mode` | An FSx for ONTAP destination always needs an agent and Basic mode in AWS DataSync |
| `docs/en/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/saas-to-fsx-ontap-migration.md` | `常にエージェントと Basic モードが必要です` | FSx for ONTAP を宛先にすると AWS DataSync でエージェントと Basic モードが必要になること |
| `docs/ja/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-authorization-model.md` | `層をまたいだ引き算は起きません` | IAM とファイル権限の 2 層が独立で、層をまたいだ引き算が起きないこと |
| `docs/ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/snaplock-audit-log-console-guardrails.md` | `デフォルト 0 年 / 最小 0 年 / 最大 30 年` | 保持期間の欄が監査ログ用ではなく、既定 0 年のまま 6 か月削除できなかった実測 |
| `docs/ja/playbooks/02-design/notes/how-end-users-reach-the-data.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/file-portal-amplify-gen2.md` | `作らずに済むかもしれません` | ブラウザ UI を自作する前に AWS Transfer Family で足りるかを先に判定すること |
| `docs/ja/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/saas-to-fsx-ontap-migration.md` | `常にエージェントと Basic モードが必要です` | FSx for ONTAP を宛先にすると AWS DataSync でエージェントと Basic モードが必要になること |
| `docs/ja/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/en/saas-to-fsx-ontap-migration.md` | `always requires an agent and Basic mode` | An FSx for ONTAP destination always needs an agent and Basic mode in AWS DataSync |
| `docs/ja/reference/limits/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-object-size-limits-verification.md` | `5 GB → 50 GB` | オブジェクトサイズ上限の記載変更に対して、実際にエラーになるサイズを実測で確定したこと |
| `docs/ja/reference/recent-updates.md` | `VMware-Migration-EC2-ONTAP` | `docs/ja/atx-fsxn-ga-verification.md` | `承認を得て実行` | AWS Transform の FSx for ONTAP 対応 GA スコープの実機確認と、Finalize を承認のうえ実行した結果（split の所要時間と不可逆性） |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `NFSv2 と NFSv3 は非対応` | Amazon EFS が NFSv3 に対応しないこと。NFSv3 が要件なら EFS が選択肢から外れる根拠 |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `NFSv4.2 は対応プロトコルとして挙げられていない` | Amazon EFS の NFSv4.2 非対応。**列挙に無いことが根拠**で、非対応と明記されているわけではありません |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `Windows を実行する EC2 インスタンスからの EFS のマウントは非対応` | Amazon EFS が Windows から使えないこと。**「EFS は SMB 非対応」の唯一の根拠でもあり、SMB 非対応を独立の主張として書かない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | ``EFS は `nconnect` にも非対応`` | Amazon EFS が `nconnect` に対応しないこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `実効オプションではなく接続数で判定した` | `nconnect` の可否を実効オプションで判定できないこと。EFS でも `nconnect=16` は実効オプションに現れます |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `倍率 2.97 は **1,500 ÷ 500 = 3.0** に一致しており` | Amazon EFS のマウントヘルパー使用時の倍率がクォータ比に一致し、フロー数には比例しないこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `12,173 MiB/s = **102 Gbps**` | FSx for ONTAP のネットワーク上限が単一のデータ LIF ではないことの裏取り。**単一接続の値から外挿しない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `観測したチャネル数は 4 であり` | SMB Multichannel のチャネル数が設定を上げても 4 で止まったこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `そうなったのかは**確認していない**` | チャネル数が 4 で止まる理由が未確認であること。**上の行だけを引くと 4 が製品の上限だと読めるため、2 行で 1 組** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `キャッシュの温度が揃っていない` | NFS 16 接続の列と SMB Multichannel の列が同条件でないこと。**この 2 列から SMB と NFS の優劣を取らない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/performance-testing-guide.md` | `2,200 MB/s → 267 MB/s` | ボリューム使用率の上昇で書き込みが落ちること |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/performance-testing-guide.md` | ``測定ファイルを `rm` しても空きは戻らない`` | 削除では容量が戻らないこと。**上の行だけを引くと回復手順を誤るため、2 行で 1 組** |
| `docs/ja/reference/file-protocol-resource-map.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/throughput-iops-concurrency.md` | `性能仕様表には NVMe キャッシュの列が**ありません**` | 性能仕様表とデプロイタイプの節が食い違っていること。**列の不在を「非対応」と読むか「記載なし」と読むかで結論が変わる** |
| `docs/ja/reference/file-protocol-resource-map.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/throughput-iops-concurrency.md` | `ONTAP に直接聞いて決着させました` | 食い違いを ONTAP への直接確認で決着させたこと。**上の行だけだと「表に列が無い」で終わり、どう確定させたかが落ちるため 2 行で 1 組** |
| `docs/ja/reference/file-protocol-resource-map.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/errata-fpolicy-s3ap-coverage.md` | `書き込みが S3 Access Point 経由で届く場合には成り立たない` | FPolicy による遮断が S3 Access Point 経由の書き込みには成り立たないこと |
| `docs/ja/reference/file-protocol-resource-map.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/support-matrix-fsx-ontap-flexcache-s3ap.md` | `ONTAP バージョンだけでは判断できない` | マネージドサービス上の機能可否が ONTAP のバージョンだけでは決まらないこと |
| `docs/ja/reference/decision-trees/file-storage-selection.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/decision-trees/choosing-this-architecture.md` | `S3 Access Point のみでよい。ファンアウトは不要` | 利用拠点が Origin と同一なら FlexCache のファンアウトが不要であること。この決定木の終端 5 から送り出す先 |
| `docs/ja/reference/fsx-ontap-fit-conditions.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification-status.md` | `公開ドキュメントに記載を見つけられていない。「できない」ではない` | 供出元の「未確認」の定義。**`cannot` と読み替えないことの根拠** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `8 台の 11,194.7 MiB/s は 94 Gbps である` | 同じファイルを 8 台で読んだときのポート実測。**重ならない領域の表と 2 行で 1 組**  |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `4 台と 8 台で止まった` | 重ならない領域では 4 台で頭打ちになること。**同一ファイル側の行だけを引くと逆の結論になる** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `同一ファイル側の伸びは、ONTAP のメモリが重なりを供給した結果である` | 伸びの原因。2 つの表を片方だけ引いてはいけない理由 |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `クライアントを 4.5 倍の型に変えても 0.6% しか動かない` | 15 分の持続書き込みがクライアント律速ではないこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `SMB は NFS の 72.1%` | 同一環境・同一物理ポートでの NFS との比。**どちらが公表値に近いかを優劣の根拠にしない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/limits/smb-multichannel-enablement.md` | `ONTAP 9 の SMB Multichannel は無効で出荷される` | SMB Multichannel が ONTAP で既定無効であること。**すべての SMB 数値の前提** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/limits/smb-multichannel-enablement.md` | `成功したという応答は、その接続に適用された証拠ではない` | 有効化が既に張られた接続に届かないこと（Tree Connect） |

<!-- cross-repo-table:end -->

---

## まだ probe を張れていない引用

**引用表に載せられるのは、引用先のファイルに文字列が存在するものだけです。** 相手側の成果物が
未コミットの間は probe を張れず、**張ると `make cross-repo` が落ちます。** 落ちるのが正しい挙動なので、
「通すために probe を緩める」のではなく、ここに保留として書きます。

| 引用元 | 根拠の所在 | 待っているもの |
|---|---|---|
| `docs/ja/domains/observability/notes/cross-account-is-a-network-problem.md` | [Issue #71 の回答](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/issues/71)（公開 URL、恒久） | Observability 側の実装ファイルのコミット。**回答時点で約 67 件が未コミットでした** |

**Issue のコメントは公開されていて消えませんが、ファイルではないので probe の対象にできません。**
つまりこの引用は、**索引に載っていても撤回を検出できない**状態です。

**待っているのはコミットではなくマージです。** 相手の成果物が既定ブランチ以外に載っている間、probe は「文字列が消えた」ではなく **「ファイルが存在しない」** で落ちます。**これは撤回と区別がつきません。** 既定ブランチにマージされてから引用表へ移し、probe を張ってください。

## 引用を足すときの手順

| # | 手順 | なぜ |
|---|---|---|
| 1 | 引用先の主張を読み、**条件（世代・容量・IOPS・キャッシュ・クライアント型・並列度・測定日）を確認する** | 条件のない数値は設計に使えません |
| 2 | 本文に引用先ファイルへのリンクを書く。`blob/main` のパスまで指す | 行番号を指すと編集で外れます |
| 3 | 上の表に 1 行足す。**確認する文字列は主張を指すもの**にする | 見出しだと主張の撤回を検出できません |
| 4 | 条件を本文に併記する。引用先だけに置かない | 読者が引用先を開かずに誤用します |
| 5 | `make cross-repo` を実行する | リンクと表の対応 |
| 6 | `make cross-repo-external` を実行する | 引用先に主張がまだあるか |
| 7 | 引用先が未測定としている範囲も書く | **引用は都合のよい部分だけを取り出せます** |

---

## よくある誤解

| 誤解 | 実際 |
|---|---|
| 引用しておけば数値の責任は引用先にある | **条件を併記しない引用は、読者に誤用させます。** 責任は分かれません |
| リンクが 200 を返すなら引用は生きている | **ファイルが存在することと、主張がまだそこにあることは別です。** だから文字列で検証します |
| 同じ検証をこちらでもやれば確実 | **2 か所で測ると数字が 2 つになり、古い側が参照され続けます** |
| 分担は各リポジトリの `AGENTS.md` に書けばよい | **同じ規約を 10 か所に置くと片方だけ更新されます。** ここに一元化し、sibling には Issue で提案します |
| 引用先が環境を消していたら引用できない | 引用できます。**再現手順が残っているかを確認して、それも併記してください** |

---

## 関連ドキュメント

- [業種別リソースマップ](industry-resource-map.md) — 業種から入ったときの索引
- [ブロックストレージ横断リソースマップ](block-storage-resource-map.md) — 一次情報の索引と資料間の食い違い
- [知見の分類ポリシー](../evidence-policy.md) — エビデンス階層の定義
- [Reference](README.md)

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
