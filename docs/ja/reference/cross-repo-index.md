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
| `make cross-repo` | 本文に現れる sibling repo へのリンクが下の表に載っているか。表の行の引用元ファイルが実在し、実際にそのリンクを含むか。**公開している [probe 契約](../../agent/cross-repo-probe-contract.txt) がこの表と一致するか** | 不要 |
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
- **役割** — 発火が何を意味するか。`retraction` か `reread` のいずれかで、**他の値はゲートが拒否します。** 判定の基準は[発火の意味が 1 通りでない probe の扱い](#発火の意味が-1-通りでない-probe-の扱い)にあり、値は [probe 契約](../../agent/cross-repo-probe-contract.txt)として引用先へ公開されます
  > **この文字列が検出できないもの**: probe は**その文字列が引用先に存在するか**しか見ません。**引用元の中で記述が古くなり、同じファイルの本文が別のことを言っている状態は検出できません。**
  > 実例があります。`Finalize は意図的に未実施` を probe にしていた行は、引用先のステータス行にその文が残ったまま、同じファイルの本文が「承認を得て実行」に更新されていました。**ゲートは「probe 現存」と報告し続け、気づいたのは相手側から指摘を受けたときです。**
  > **引用元が自己矛盾している可能性は、ゲートでは拾えません。** 逆リンクを依頼するときなどに、引用している主張が今も本文と一致しているかを併せて訊いてください。

**この表の後半 10 行は、ゲートを入れた時点で既に存在していた引用です。** 仕組みが無かった間に積まれ、登録も検証もされていませんでした。**引用が 8 ファイル分あることに誰も気づいていなかった、というのがこのゲートの最初の成果です。**

<!-- cross-repo-table:start -->

| 引用元 | リポジトリ | パス | 確認する文字列 | 役割 | 何を引いているか |
|---|---|---|---|---|---|
| `docs/ja/playbooks/02-design/notes/the-split-decides-what-cannot-be-revisited.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/multi-tenant-design.md` | `分離レベル` | `retraction` | マルチテナントの分離パターン。**こちらは分割で何が固定されるかを持ち、パターンの比較は持ちません** |
| `docs/ja/playbooks/02-design/notes/the-split-decides-what-cannot-be-revisited.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/design-first-decisions.md` | `不可逆・作り直しになる操作` | `retraction` | ボリュームを作る前に決めることの順序。**同じ問いをボリューム側から扱っている文書**です |
| `docs/ja/playbooks/04-build/README.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/fsxadmin-limitations.md` | `AWS サポートリクエストが必要な操作` | `reread` | 委任された管理者で実行できない操作の存在。**一覧はそちらが持ちます** — サービスが操作を得ると一覧は縮み、発火は撤回ではなく読み直しの合図です |
| `docs/ja/reference/comparison/ontap-configuration-routes.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/fsxadmin-limitations.md` | `AWS サポートリクエストが必要な操作` | `reread` | 同じ主張を、経路の比較の側から。**どの経路を選んでも越えられない上限がある**という位置づけ |
| `docs/ja/playbooks/01-assess/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/adoption-assessment.md` | `Anti-Patterns` | `retraction` | 評価を成果物として構成する形。**適用しない条件の一覧を持っている点**が、こちらの棚卸し項目にない部分です |
| `docs/ja/playbooks/01-assess/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/poc-checklist.md` | `測定前の合否基準の決定` | `retraction` | PoC の合否基準を測定前に決めること。**測ったあとに決めると出た数値が合格になる**という主張の所在 |
| `docs/en/playbooks/01-assess/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/adoption-assessment.md` | `Anti-Patterns` | `retraction` | 同上（EN 版） |
| `docs/en/playbooks/01-assess/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/poc-checklist.md` | `測定前の合否基準の決定` | `retraction` | 同上（EN 版） |
| `docs/ja/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-s3-vs-s3ap.md` | `課金次元の対応` | `retraction` | S3 標準と FSx for ONTAP S3 AP の費用構造の対応。**繰り返し読むか 1 回だけかで向く選択が変わる**という判断の所在 |
| `docs/ja/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-performance-test-patterns.md` | `実際の請求ではない` | `retraction` | 測定環境そのものの費用。**単価の取得日とリージョンが付いていることが、この文書を引用できる理由**です |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-model.md` | `デプロイの月額コストを見積もる` | `retraction` | 監視 3 経路の費用比較と、見積りに必要な入力値の一覧 |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-validation.md` | `実際の AWS 請求データ` | `retraction` | 見積りと実請求の突き合わせ。**見積りの妥当性を確かめる側**で、見積り自体は上の行にあります |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/cost-estimation.md` | `scaling formulas` | `retraction` | 構成要素別の内訳と算定式。メタデータのみと全複製の比較 |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/cost-measurement.md` | `Cost Explorer` | `retraction` | 実測の手順。**見積りではありません** — この区別が落ちると、実測値が見積りとして引用されます |
| `docs/en/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-s3-vs-s3ap.md` | `課金次元の対応` | `retraction` | S3 標準と FSx for ONTAP S3 AP の費用構造の対応。**繰り返し読むか 1 回だけかで向く選択が変わる**という判断の所在（EN 版）|
| `docs/en/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-performance-test-patterns.md` | `実際の請求ではない` | `retraction` | 測定環境そのものの費用。**単価の取得日とリージョンが付いていることが、この文書を引用できる理由**です（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-model.md` | `デプロイの月額コストを見積もる` | `retraction` | 監視 3 経路の費用比較と、見積りに必要な入力値の一覧（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-validation.md` | `実際の AWS 請求データ` | `retraction` | 見積りと実請求の突き合わせ。**見積りの妥当性を確かめる側**で、見積り自体は上の行にあります（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/cost-estimation.md` | `scaling formulas` | `retraction` | 構成要素別の内訳と算定式。メタデータのみと全複製の比較（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/cost-measurement.md` | `Cost Explorer` | `retraction` | 実測の手順。**見積りではありません** — この区別が落ちると、実測値が見積りとして引用されます（EN 版）|
| `docs/ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/arp-configuration.md` | `paused` | `retraction` | 説明側の 6 値だけを実装に写すと `paused` のボリュームが有効なまま「無効」と表示されること。**こちらは文書の不一致を、そちらは実害の形を持っています** |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `EC2 の 1 フローあたり全二重 5 Gbps` | `retraction` | FSx for ONTAP の単一接続が当たっているのは EC2 の 1 フロー上限であること |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `500〜592 MB/s に収まる` | `reread` | ファイルプロトコルの単一接続が 625 MBps に届かず、625 で割る形が必要セッション数を約 5% 少なく出すこと。**範囲の両端が単一接続の実測 3 行から出ているので、4 本目が足されるだけで動きます** — ブロックの 1 セッションが測られた時点で発火する見込みです |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `別の上限である` | `retraction` | 近い値を同じ原因に束ねないという訂正そのもの。**ブロックの値をファイルの値で代用しない根拠。** 幅を含まないので、行が増えても動きません |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `500 MiBps に一致する` | `retraction` | Amazon EFS の 499.79 MB/s は 1 フロー上限ではなくクライアント単位のクォータに一致すること。**近い値を同じ原因に束ねない。** クォータの固定値を指すので、行が増えても動きません |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `45% 違った` | `retraction` | 同一構成・同一パラメータで 2 回測って 45% 振れ、違いはキャッシュに何が残っていたかだけだったこと |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `0.18 倍` | `retraction` | 8 台・128 接続で、同じファイルを共有した場合と重ならない領域を読んだ場合の差 |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `既定 65,536 のままだと` | `retraction` | 既定 65,536 のままだと `rsize` が 64 KiB に切り下がるため、測定前に引き上げていること |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/throughput-protocol-matrix-plan.md` | `コマンドラインでは渡せない` | `retraction` | 測定に使った器具と、パラメータがコマンドラインから渡せない制約 |

| `docs/ja/reference/comparison/throughput-levers.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `3,551〜5,149 MB/s` | `reread` | 接続数を上げたときの実測値と、それが追加料金なしで最も大きく動いた手段だったこと |
| `docs/ja/reference/comparison/throughput-levers.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `観測したチャネル数は 4 であり` | `retraction` | SMB Multichannel のチャネル数が設定を上げても 4 で止まったこと |
| `docs/en/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-authorization-model.en.md` | `There is no subtraction across them` | `retraction` | The two authorization layers are independent, with no subtraction across them |
| `docs/en/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/en/saas-to-fsx-ontap-migration.md` | `always requires an agent and Basic mode` | `retraction` | An FSx for ONTAP destination always needs an agent and Basic mode in AWS DataSync |
| `docs/en/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/saas-to-fsx-ontap-migration.md` | `常にエージェントと Basic モードが必要です` | `retraction` | FSx for ONTAP を宛先にすると AWS DataSync でエージェントと Basic モードが必要になること |
| `docs/ja/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-authorization-model.md` | `層をまたいだ引き算は起きません` | `retraction` | IAM とファイル権限の 2 層が独立で、層をまたいだ引き算が起きないこと |
| `docs/ja/domains/security-governance/notes/irreversible-operations-need-separate-approval.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/snaplock-audit-log-console-guardrails.md` | `デフォルト 0 年 / 最小 0 年 / 最大 30 年` | `retraction` | 保持期間の欄が監査ログ用ではなく、既定 0 年のまま 6 か月削除できなかった実測 |
| `docs/ja/playbooks/02-design/notes/how-end-users-reach-the-data.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/file-portal-amplify-gen2.md` | `作らずに済むかもしれません` | `retraction` | ブラウザ UI を自作する前に AWS Transfer Family で足りるかを先に判定すること |
| `docs/ja/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/saas-to-fsx-ontap-migration.md` | `常にエージェントと Basic モードが必要です` | `retraction` | FSx for ONTAP を宛先にすると AWS DataSync でエージェントと Basic モードが必要になること |
| `docs/ja/playbooks/03-migrate/notes/saas-source-migration-scoping.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/en/saas-to-fsx-ontap-migration.md` | `always requires an agent and Basic mode` | `retraction` | An FSx for ONTAP destination always needs an agent and Basic mode in AWS DataSync |
| `docs/ja/reference/limits/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-object-size-limits-verification.md` | `5 GB → 50 GB` | `retraction` | オブジェクトサイズ上限の記載変更に対して、実際にエラーになるサイズを実測で確定したこと |
| `docs/ja/reference/recent-updates.md` | `VMware-Migration-EC2-ONTAP` | `docs/ja/atx-fsxn-ga-verification.md` | `承認を得て実行` | `retraction` | AWS Transform の FSx for ONTAP 対応 GA スコープの実機確認と、Finalize を承認のうえ実行した結果（split の所要時間と不可逆性） |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `NFSv2 と NFSv3 は非対応` | `retraction` | Amazon EFS が NFSv3 に対応しないこと。NFSv3 が要件なら EFS が選択肢から外れる根拠 |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `NFSv4.2 は対応プロトコルとして挙げられていない` | `retraction` | Amazon EFS の NFSv4.2 非対応。**列挙に無いことが根拠**で、非対応と明記されているわけではありません |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `Windows を実行する EC2 インスタンスからの EFS のマウントは非対応` | `retraction` | Amazon EFS が Windows から使えないこと。**「EFS は SMB 非対応」の唯一の根拠でもあり、SMB 非対応を独立の主張として書かない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | ``EFS は `nconnect` にも非対応`` | `retraction` | Amazon EFS が `nconnect` に対応しないこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/protocol-matrix-efs-vs-ontap.md` | `実効オプションではなく接続数で判定した` | `retraction` | `nconnect` の可否を実効オプションで判定できないこと。EFS でも `nconnect=16` は実効オプションに現れます |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `倍率 2.97 は **1,500 ÷ 500 = 3.0** に一致しており` | `retraction` | Amazon EFS のマウントヘルパー使用時の倍率がクォータ比に一致し、フロー数には比例しないこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `12,173 MiB/s = **102 Gbps**` | `retraction` | FSx for ONTAP のネットワーク上限が単一のデータ LIF ではないことの裏取り。**単一接続の値から外挿しない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `観測したチャネル数は 4 であり` | `retraction` | SMB Multichannel のチャネル数が設定を上げても 4 で止まったこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `そうなったのかは**確認していない**` | `retraction` | チャネル数が 4 で止まる理由が未確認であること。**上の行だけを引くと 4 が製品の上限だと読めるため、2 行で 1 組** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `キャッシュの温度が揃っていない` | `retraction` | NFS 16 接続の列と SMB Multichannel の列が同条件でないこと。**この 2 列から SMB と NFS の優劣を取らない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/performance-testing-guide.md` | `2,200 MB/s → 267 MB/s` | `retraction` | ボリューム使用率の上昇で書き込みが落ちること |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/performance-testing-guide.md` | ``測定ファイルを `rm` しても空きは戻らない`` | `retraction` | 削除では容量が戻らないこと。**上の行だけを引くと回復手順を誤るため、2 行で 1 組** |
| `docs/ja/reference/file-protocol-resource-map.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/throughput-iops-concurrency.md` | `性能仕様表には NVMe キャッシュの列が**ありません**` | `retraction` | 性能仕様表とデプロイタイプの節が食い違っていること。**列の不在を「非対応」と読むか「記載なし」と読むかで結論が変わる** |
| `docs/ja/reference/file-protocol-resource-map.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/throughput-iops-concurrency.md` | `ONTAP に直接聞いて決着させました` | `retraction` | 食い違いを ONTAP への直接確認で決着させたこと。**上の行だけだと「表に列が無い」で終わり、どう確定させたかが落ちるため 2 行で 1 組** |
| `docs/ja/reference/file-protocol-resource-map.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/errata-fpolicy-s3ap-coverage.md` | `書き込みが S3 Access Point 経由で届く場合には成り立たない` | `retraction` | FPolicy による遮断が S3 Access Point 経由の書き込みには成り立たないこと |
| `docs/ja/reference/file-protocol-resource-map.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/support-matrix-fsx-ontap-flexcache-s3ap.md` | `ONTAP バージョンだけでは判断できない` | `retraction` | マネージドサービス上の機能可否が ONTAP のバージョンだけでは決まらないこと |
| `docs/ja/reference/decision-trees/file-storage-selection.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/decision-trees/choosing-this-architecture.md` | `S3 Access Point のみでよい。ファンアウトは不要` | `retraction` | 利用拠点が Origin と同一なら FlexCache のファンアウトが不要であること。この決定木の終端 5 から送り出す先 |
| `docs/ja/reference/fsx-ontap-fit-conditions.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification-status.md` | `公開ドキュメントに記載を見つけられていない。「できない」ではない` | `retraction` | 供出元の「未確認」の定義。**`cannot` と読み替えないことの根拠** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `8 台の 11,194.7 MiB/s は 94 Gbps である` | `retraction` | 同じファイルを 8 台で読んだときのポート実測。**重ならない領域の表と 2 行で 1 組**  |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `4 台と 8 台で止まった` | `retraction` | 重ならない領域では 4 台で頭打ちになること。**同一ファイル側の行だけを引くと逆の結論になる** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `同一ファイル側の伸びは、ONTAP のメモリが重なりを供給した結果である` | `retraction` | 伸びの原因。2 つの表を片方だけ引いてはいけない理由 |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `クライアントを 4.5 倍の型に変えても 0.6% しか動かない` | `retraction` | 15 分の持続書き込みがクライアント律速ではないこと |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `SMB は NFS の 72.1%` | `retraction` | 同一環境・同一物理ポートでの NFS との比。**どちらが公表値に近いかを優劣の根拠にしない** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/limits/smb-multichannel-enablement.md` | `ONTAP 9 の SMB Multichannel は無効で出荷される` | `retraction` | SMB Multichannel が ONTAP で既定無効であること。**すべての SMB 数値の前提** |
| `docs/ja/reference/comparison/file-storage-options.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/limits/smb-multichannel-enablement.md` | `成功したという応答は、その接続に適用された証拠ではない` | `retraction` | 有効化が既に張られた接続に届かないこと（Tree Connect） |
| `docs/ja/domains/data-utilization/notes/how-long-until-a-write-is-visible.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/cross-protocol-directions.md` | `正しい値は今回の p50 44 ms です` | `retraction` | 4 方向の反映速度と、NFS → S3 AP 方向の正しい値。**873 ms は CLI 起動コストを含む旧値で、引用してはいけない側** |
| `docs/ja/domains/data-utilization/notes/how-long-until-a-write-is-visible.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/s3ap-nfs-visibility.md` | `7 ms 対 2,171 ms` | `retraction` | 同一操作の観測値がクライアントのマウントオプションで 300 倍変わること。**「反映が遅い」の原因がストレージ側とは限らない根拠** |
| `docs/ja/domains/data-utilization/notes/how-long-until-a-write-is-visible.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/s3files-measured.md` | `削除と上書きは、新規作成と同じ桁です` | `retraction` | Amazon S3 Files のファイル → S3 方向が新規作成・削除・上書きのいずれも 60 秒級であること。**片方向だけの現象ではないこと** |
| `docs/ja/domains/data-utilization/notes/s3-access-point-constraints.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/s3ap-operations.md` | `同一実行内の対照がすべて成功しているため、手順の誤りではありません` | `retraction` | `UploadPartCopy` の `NoSuchKey` に同一実行内の `CopyObject` 対照があること。**切り分けの手順そのもの** |

<!-- cross-repo-table:end -->

---

### 発火の意味が 1 通りでない probe の扱い

**probe が発火したら撤回、とは読めません。** 主張に幅が含まれていると、**引用先が測定を 1 本足した
だけで文字列が変わります。** ゲートは行の追加と主張の撤回を区別できないので、発火を撤回と決めて
本文を自動で直すと、**拡張を撤回として記録します。**

だから**表の 役割 列**で意味を 1 つに固定します。値は 2 つだけです。

| 役割 | 付ける条件 | 発火の読み方 |
|---|---|---|
| `reread` | probe が**引用先の測定集合の最小値・最大値**を含む（`500〜592 MB/s に収まる`、`3,551〜5,149 MB/s`）| **「該当節を読み直せ」。** 集合に 1 本足されただけで文字列は書き換わり、所見は立ったままです |
| `retraction` | それ以外 | **主張が消えたか移動した。** こちら側の記述は根拠を失っています |

**基準を「幅を含むか」ではなく「集合の最小値・最大値か」に絞ってあります。** 特定の 2 点の比
（`0.18 倍`、`45% 違った`）や観測値そのもの（`12,173 MiB/s = **102 Gbps**`）は、引用先が測定を
足しても書き換わりません。**`reread` を広く付けると、その主張については撤回を検出できなくなります。**

**不在の主張は第 3 の形で、意図して `retraction` に置いています。** 「性能仕様表に列がない」
「公開ドキュメントに記載がない」は、真でなくなった瞬間にこちら側の指針が変わります。**これは
警告ではなく止まるべき事象なので、`reread` には入れません。**

`reread` と `retraction` に分けたのは、片方だけを残す案を却下した結果です。**「読み直せ」用だけに
すると撤回を検出できず、「撤回検出」用だけにすると幅の変化に気づけません。**

### 引用先が自分で検査するための probe 契約

**probe の検査はこちらでしか走りません。** つまり引用先から見ると、**自分の文言を変えたことで
他リポジトリの根拠が消えた事実は、こちらの CI が落ちるまで見えません。** 順序が逆です。

だから登録内容を [`docs/agent/cross-repo-probe-contract.txt`](../../agent/cross-repo-probe-contract.txt)
として公開します。**この表から生成し、`make cross-repo` が一致を検証します。**

| | |
|---|---|
| 形式 | `<repo>` TAB `<引用先パス>` TAB `<役割>` TAB `<確認する文字列>`、ソート済み |
| 生成 | `python3 tools/check_cross_repo.py --write-contract` |
| 引用元の列 | **入れません。** どのファイルが引いているかはこちら側の問題で、引用先が必要なのは「黙って書き換えてはいけない文字列の集合」です |
| 重複 | 同じ文字列を 2 ファイルから引いていても 1 行になります |

**手で書かないこと。** 生成せずに書くと、それが[ゲートの説明とゲートそのものの不一致](#ゲートの説明とゲートそのものの不一致)で
起きた失敗そのものになります。**生成物であることと、比較するゲートがあることの 2 つで、はじめて
第 2 のコピーが許容できます。**

### ゲートの説明とゲートそのものの不一致

**この表が登録内容です。** 散文で probe を列挙している場所は、**ゲートが変わっても追随しません。**

実際に起きました。分担を提案した issue の本文に probe 7 本を列挙しており、その後 2 本を差し替えた
時点で本文は現在のゲートの説明ではなくなりました。**列挙を実装だと読んだ相手が「壊れている」と
報告し、その文字列は一度も登録されていませんでした。** 直す対象はゲートではなく本文でした。

**規則: 他リポジトリへ probe の内容を散文で伝えるときは、この表への参照 1 行にする。** 現在の登録を
issue 本文や説明文へ転記すると同じ問題が再発します。**故障・撤回・未対応を他者へ報告する前に、
散文ではなく登録表を読んでください。**

**[probe 契約](#引用先が自分で検査するための-probe-契約)はこの規則の例外ではありません。** 転記では
なく生成物で、`make cross-repo` が表との一致を検証します。**追随しないから禁止しているのであって、
内容を渡すこと自体が問題なのではありません。**

## まだ probe を張れていない引用

**引用表に載せられるのは、引用先のファイルに文字列が存在するものだけです。** 相手側の成果物が
未コミットの間は probe を張れず、**張ると `make cross-repo` が落ちます。** 落ちるのが正しい挙動なので、
「通すために probe を緩める」のではなく、ここに保留として書きます。

| 引用元 | 根拠の所在 | 待っているもの |
|---|---|---|
| `docs/ja/domains/observability/notes/cross-account-is-a-network-problem.md` | [Issue #71 の回答](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/issues/71)（公開 URL、恒久） | Observability 側の実装ファイルのコミット。**回答時点で約 67 件が未コミットでした** |
| `docs/ja/domains/data-utilization/notes/reaching-data-without-copies.md` | [Issue #162 の回答](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/issues/162#issuecomment-5563205901)（公開 URL、恒久） | **何も待っていません。** 実装のファイル名・関数名を転記しない方針で、**転記しないなら probe を張る対象がありません。** 二重管理を避けた結果としてゲートの外に出ます |

**Issue のコメントは公開されていて消えませんが、ファイルではないので probe の対象にできません。**
つまりこの引用は、**索引に載っていても撤回を検出できない**状態です。

### 転記しない選択の代償

**上の 2 行目は、相手のコミットを待っているのではありません。** 実装の詳細（ファイル名・関数名・行）を
こちらへ転記しない方針を採ったので、**照合する文字列がそもそも存在しません。**

転記すれば probe を張れます。ただし**二重管理になり、相手がリファクタリングした時点で片方が腐ります。**
どちらを選んでも失うものがあり、ここでは**腐った記述が残るより、ゲートの外にあることが記録されている
ほうがましだと判断しました。** この判断は方針であって、ゲートの不足ではありません。

### この索引が捕まえない逆リンク

**外部から `docs/ja|en/domains/data-utilization/` へ向かうリンクが存在します**（[FSx-for-ONTAP-Agentic-Access-Aware-RAG](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG) の
8 言語 README）。**この索引は「こちらが引用しているもの」しか見ておらず、「こちらが引用されているもの」は
見ていません。** つまり**このディレクトリを動かすと、こちらのゲートは 1 つも鳴らずに相手のリンクが
切れます。** [外部から引用されているアンカー](../../../docs/agent/external-anchor-contract.txt) は
見出しを守りますが、**ディレクトリの移動は対象外**です。移動の予定はありません。

**待っているのはコミットではなくマージです。** 相手の成果物が既定ブランチ以外に載っている間、probe は「文字列が消えた」ではなく **「ファイルが存在しない」** で落ちます。**これは撤回と区別がつきません。** 既定ブランチにマージされてから引用表へ移し、probe を張ってください。

## 引用を足すときの手順

| # | 手順 | なぜ |
|---|---|---|
| 1 | 引用先の主張を読み、**条件（世代・容量・IOPS・キャッシュ・クライアント型・並列度・測定日）を確認する** | 条件のない数値は設計に使えません |
| 2 | 本文に引用先ファイルへのリンクを書く。`blob/main` のパスまで指す | 行番号を指すと編集で外れます |
| 3 | 上の表に 1 行足す。**確認する文字列は主張を指すもの**にする | 見出しだと主張の撤回を検出できません |
| 4 | **役割を決める。** 集合の最小値・最大値を含むなら `reread`、それ以外は `retraction` | 発火の意味が 1 通りに読めなくなります |
| 5 | `python3 tools/check_cross_repo.py --write-contract` を実行する | **引用先が読むのは公開した契約で、この表ではありません** |
| 6 | 条件を本文に併記する。引用先だけに置かない | 読者が引用先を開かずに誤用します |
| 7 | `make cross-repo` を実行する | リンクと表の対応、および契約が表と一致すること |
| 8 | `make cross-repo-external` を実行する | 引用先に主張がまだあるか |
| 9 | 引用先が未測定としている範囲も書く | **引用は都合のよい部分だけを取り出せます** |

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
