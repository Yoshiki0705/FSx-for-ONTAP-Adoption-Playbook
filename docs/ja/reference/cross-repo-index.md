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
| `docs/ja/playbooks/02-design/notes/the-split-decides-what-cannot-be-revisited.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/multi-tenant-design.md` | `テナント ID をパーティションキーにする` | `retraction` | マルチテナントの分離パターン。**こちらは分割で何が固定されるかを持ち、パターンの比較は持ちません** |
| `docs/ja/playbooks/02-design/notes/the-split-decides-what-cannot-be-revisited.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/design-first-decisions.md` | `取り消せない。**保持期間を明示した指示がない限り有効化しない**` | `retraction` | ボリュームを作る前に決めることの順序。**同じ問いをボリューム側から扱っている文書**です |
| `docs/ja/playbooks/04-build/README.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/fsxadmin-limitations.md` | `一部の操作は AWS サポートへの連絡が必要` | `retraction` | 委任された管理者で実行できない操作の**存在**。**一覧はそちらが持ちます。** probe は一覧の中身ではなく存在を主張する文を指すので、**項目が増減しても動きません。** 発火するのは「サポートが必要な操作はもう無い」に変わったときで、そのときこちらの記述は根拠を失います |
| `docs/ja/reference/comparison/ontap-configuration-routes.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/fsxadmin-limitations.md` | `一部の操作は AWS サポートへの連絡が必要` | `retraction` | 同じ主張を、経路の比較の側から。**どの経路を選んでも越えられない上限がある**という位置づけ |
| `docs/ja/playbooks/01-assess/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/adoption-assessment.md` | `require metadata operations that fail on S3 AP` | `retraction` | 評価を成果物として構成する形。**適用しない条件の一覧を持っている点**が、こちらの棚卸し項目にない部分です |
| `docs/ja/playbooks/01-assess/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/poc-checklist.md` | `測ったあとに合否を決めると、出た数値が合格になる。` | `retraction` | PoC の合否基準を測定前に決めること。**測ったあとに決めると出た数値が合格になる**という主張の所在 |
| `docs/en/playbooks/01-assess/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/adoption-assessment.md` | `require metadata operations that fail on S3 AP` | `retraction` | 同上（EN 版） |
| `docs/en/playbooks/01-assess/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/poc-checklist.md` | `測ったあとに合否を決めると、出た数値が合格になる。` | `retraction` | 同上（EN 版） |
| `docs/ja/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-s3-vs-s3ap.md` | `片方にあって他方にない項目が、そのまま設計上の制約になる。` | `retraction` | S3 標準と FSx for ONTAP S3 AP の費用構造の対応。**繰り返し読むか 1 回だけかで向く選択が変わる**という判断の所在 |
| `docs/ja/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-performance-test-patterns.md` | `実際の請求ではない` | `retraction` | 測定環境そのものの費用。**単価の取得日とリージョンが付いていることが、この文書を引用できる理由**です |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-model.md` | `デプロイの月額コストを見積もる` | `retraction` | 監視 3 経路の費用比較と、見積りに必要な入力値の一覧 |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-validation.md` | `実際の AWS 請求データ` | `retraction` | 見積りと実請求の突き合わせ。**見積りの妥当性を確かめる側**で、見積り自体は上の行にあります |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/cost-estimation.md` | `scaling formulas` | `retraction` | 構成要素別の内訳と算定式。メタデータのみと全複製の比較 |
| `docs/ja/domains/cost/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/cost-measurement.md` | `Cost Explorer` | `retraction` | 実測の手順。**見積りではありません** — この区別が落ちると、実測値が見積りとして引用されます |
| `docs/en/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-s3-vs-s3ap.md` | `片方にあって他方にない項目が、そのまま設計上の制約になる。` | `retraction` | S3 標準と FSx for ONTAP S3 AP の費用構造の対応。**繰り返し読むか 1 回だけかで向く選択が変わる**という判断の所在（EN 版）|
| `docs/en/domains/cost/README.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/reference/comparison/finops-performance-test-patterns.md` | `実際の請求ではない` | `retraction` | 測定環境そのものの費用。**単価の取得日とリージョンが付いていることが、この文書を引用できる理由**です（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-model.md` | `デプロイの月額コストを見積もる` | `retraction` | 監視 3 経路の費用比較と、見積りに必要な入力値の一覧（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/ja/cost-validation.md` | `実際の AWS 請求データ` | `retraction` | 見積りと実請求の突き合わせ。**見積りの妥当性を確かめる側**で、見積り自体は上の行にあります（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/adoption-guide/cost-estimation.md` | `scaling formulas` | `retraction` | 構成要素別の内訳と算定式。メタデータのみと全複製の比較（EN 版）|
| `docs/en/domains/cost/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/ja/cost-measurement.md` | `Cost Explorer` | `retraction` | 実測の手順。**見積りではありません** — この区別が落ちると、実測値が見積りとして引用されます（EN 版）|
| `docs/ja/domains/data-protection/notes/snaplock-and-layered-ransomware-readiness.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/arp-configuration.md` | `まだ有効なボリュームを無効と表示する` | `retraction` | 説明側の 6 値だけを実装に写すと、遷移中のボリュームが有効なまま「無効」と表示されること。**こちらは文書の不一致を、そちらは実害の形を持っています。** probe は実害を述べた文を指します — `paused` という値そのものは列挙にも説明にも現れるので、**どちらの側が変わっても発火しません** |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `EC2 の 1 フローあたり全二重 5 Gbps` | `retraction` | FSx for ONTAP の単一接続が当たっているのは EC2 の 1 フロー上限であること |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `500〜592 MB/s に収まる` | `reread` | ファイルプロトコルの単一接続が 625 MBps に届かないこと。範囲の両端が単一接続の実測 3 行から出ているので、4 本目が足されれば動きます。**この行は「ブロックの 1 セッションが測られた時点で発火する見込み」と書いていました。測られましたが、発火しませんでした** — 引用先が行を足さない判断を測る前に決めていたためです（次の行の probe がその判断を指します）。**沈黙は「まだ測っていない」ではありませんでした** |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `行を足さず、範囲（500〜592 MB/s）も変えない` | `retraction` | ブロックの値を単一接続の 3 行に足さない、という測定前の判断。**上の行の probe が沈黙している理由そのものです。** これが消えたら、範囲が広がって上の probe が発火する可能性を検討してください |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `セッション数を帯域の割り算で決める形そのものが成立していない` | `retraction` | 必要セッション数を除数で割って出す算術が成立しないこと。**このノートが以前その算術に補正を足す指示を書いていた根拠を、正面から否定する主張です** |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `iSCSI の 1 本はその約 2 倍を運んだ` | `retraction` | ブロックの単一接続がファイル側の約 2 倍だったこと。**「ブロックが同じ位置に来るなら」という前提が偽だった根拠**で、以前の指示が逆向きだったことの出どころです |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `1 → 2 では逐次スループットが 1 バイトも動かない` | `retraction` | 線形性が成立しないこと。**セッションを増やせば比例して伸びるという前提を否定します** |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `1 接続でのプロトコル差は再現しなかった` | `retraction` | iSCSI と NVMe/TCP の単一接続に差が無いこと。**プロトコルの選択を単一接続のスループットで決めない根拠** |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `環境が違ったから single が動いたのではない` | `retraction` | 同じ構成の多重度 1 が測り直しで 1.92 倍動いた原因が、環境差ではないこと。**対照で排除された事実そのもの**で、これが消えると「別のファイルシステムだったから」という説明に戻れてしまい、**1 点の測定を計画の入力にしない根拠が失われます** |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `範囲 500〜592 MB/s は「これを超える多重度 1 の実測が無い」という意味ではない` | `retraction` | 引用先の表が動かないことが、測っていないことの証拠にならないという明示。**こちらが `500〜592 MB/s に収まる` を `reread` で引き続けられる理由**で、範囲の不変を「ブロックは未測定」と読み替えない歯止めです |
| `docs/ja/domains/block-storage/notes/paths-are-the-failover-mechanism.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `別の上限である` | `retraction` | 近い値を同じ原因に束ねないという訂正そのもの。**ブロックの値をファイルの値で代用しない根拠。** 幅を含まないので、行が増えても動きません |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `500 MiBps に一致する` | `retraction` | Amazon EFS の 499.79 MB/s は 1 フロー上限ではなくクライアント単位のクォータに一致すること。**近い値を同じ原因に束ねない。** クォータの固定値を指すので、行が増えても動きません |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `違いはキャッシュに何が残っていたか` | `retraction` | 同一構成・同一パラメータで 2 回測って 45% 振れ、違いはキャッシュに何が残っていたかだけだったこと。**probe は振れ幅ではなく原因を指します** — 振れ幅は導入部と該当節の 2 か所にあり、**こちらの記述が依拠しているのは原因の側**です |
| `docs/ja/domains/performance/notes/a-single-connection-measures-the-client.md` | `S3-Burst-on-ONTAP-Files` | `docs/ja/verification/perf-matrix-results.md` | `違いはデータを共有しているかどうかだけである` | `retraction` | 8 台・128 接続で、同じファイルを共有した場合と重ならない領域を読んだ場合の差。**probe は倍率ではなく原因の帰属を指します** — 倍率はブロック側との対比でも使われており、そちらだけが書き換わる形があります |
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
| `docs/ja/reference/limits/README.md` | `FSx-for-ONTAP-S3AccessPoints-Serverless-Patterns` | `docs/s3ap-object-size-limits-verification.md` | `上限は正確に 50 GiB = 53,687,091,200 バイト` | `retraction` | オブジェクトサイズ上限の記載変更に対して、実際にエラーになるサイズを実測で確定したこと。**probe は確定した値そのものを指します** — 記載変更を表す `5 GB → 50 GB` は目的の節と質問の節にあり、**実測結果が変わっても動きません** |
| `docs/ja/reference/recent-updates.md` | `VMware-Migration-EC2-ONTAP` | `docs/ja/atx-fsxn-ga-verification.md` | `約 3 分後に開始し 60 秒未満で完了` | `retraction` | AWS Transform の FSx for ONTAP 対応 GA スコープの実機確認と、Finalize を承認のうえ実行した結果（split の所要時間と不可逆性）。**probe は所要時間の実測を指します** — 「承認を得て実行」はステータス行・未解消項目の表・本文の 3 か所にあり、**不可逆性の記述も 3 か所あるため pin できません** |
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
| `docs/ja/domains/block-storage/notes/volume-rehost-changes-ownership-not-contents.md` | `FSx-for-ONTAP-Cyber-Resilience-Patterns` | `docs/ontap-native/fsxadmin-limitations.md` | `一部の操作は AWS サポートへの連絡が必要` | `retraction` | 委任された管理者で実行できない操作が**存在すること**。**`volume rehost` が FSx for ONTAP で実行できるかは AWS が文書化していないため、この一覧が判断の出発点になります。** 一覧はそちらが持ち、**probe は一覧の中身ではなく存在を指します** |

| `docs/ja/domains/data-utilization/notes/serving-a-replication-destination-over-s3.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/en/s3ap-flexcache-snapmirror-considerations.md` | `no break and no clone` | `retraction` | 稼働中の SnapMirror 宛先を break もクローンもなしに読めること。**この主張は 2026-09-13 に逆向きへ訂正された経緯があるため、probe が生きていても本文が現在の結論と一致しているかを併せて確認してください** |
| `docs/ja/domains/data-utilization/notes/serving-a-replication-destination-over-s3.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `docs/en/s3ap-flexcache-snapmirror-considerations.md` | `PERMISSION_DENIED` | `retraction` | 宛先への書き込みがエンジン層で拒否されること。**読めることだけを引くと書けると誤読されるため、上の行と 2 行で 1 組** |
| `docs/ja/domains/data-utilization/notes/reaching-data-without-copies.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `integrations/snapmirror-flexcache-multicloud/docs/en/research.md` | `the refusal is by volume kind` | `retraction` | FlexCache の Cache Volume に S3 Access Point を取り付けられないこと。**probe はエラー文字列ではなく再確認の記述を指します** — エラー文は表と根拠欄の 2 か所にあり、片方を書き換えても発火しないためです。指しているのは**拒否がボリュームの種別によるものだ**という、この制約の非自明な部分です — マウント済みで API が RW と報告する状態でも阻まれます |
| `docs/ja/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `verification-pack/fpolicy-event-source/evidence/2026-09-14/evidence-record.yaml` | `is an invalid value for field "protocol"` | `retraction` | FPolicy の event が `s3` を受け付けないことを ONTAP 9.18.1P5 で再確認した記録。**ONTAP が返すエラー文字列そのものなので、後の版が `s3` を受け付けるようになれば発火します。** 候補集合を指す `accepted:` の行ではなくこちらを取るのは、YAML のリストが整形で改行され得るためです |
| `docs/en/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-Lakehouse-Integrations` | `verification-pack/fpolicy-event-source/evidence/2026-09-14/evidence-record.yaml` | `is an invalid value for field "protocol"` | `retraction` | 同上（EN 版）|
| `docs/ja/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/verification-results-fpolicy-s3ap-and-session.md` | `raised no FPolicy notification` | `retraction` | S3 Access Point 経由の操作が FPolicy 通知を発火しないこと、およびその測定の手順・環境表・生の件数の所在。**結論だけを持っていて方法に到達できない状態を解消するための行です** |
| `docs/en/domains/security-governance/notes/access-point-authorization-layers.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/verification-results-fpolicy-s3ap-and-session.md` | `raised no FPolicy notification` | `retraction` | 同上（EN 版）|
| `docs/ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/verification-results-fpolicy-s3ap-and-session.md` | `no spontaneous disconnect` | `retraction` | 72 時間の連続観測で自発的な切断が 0 件だったこと。**1 回・1 構成の測定なので、一般化していないことも併せて転記しています** |
| `docs/ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/verification-results-fpolicy-s3ap-and-session.md` | `Immediate (observed at 0.3 s)` | `retraction` | 通知の遅延がサブ秒であること。**こちらは桁だけを判定として書き、正確な値はこの引用先に置いています** |
| `docs/ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/operational-notes-fpolicy.md` | `NOT used for routing FPolicy traffic` | `retraction` | NLB を FPolicy の経路に置けず、ヘルスチェック専用になること。**同じファイルの KeepAlive の記述は訂正が進行中で、そちらは引用していません**（[保留](#まだ-probe-を張れていない引用)）|
| `docs/ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/fpolicy-production-architecture-patterns.md` | `fails over to secondary servers` | `retraction` | 冗長化が ONTAP のネイティブなフェイルオーバーであること。**AWS 側のロードバランサでは代替できない根拠** |
| `docs/ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md` | `FSx-for-ONTAP-Observability-integrations` | `docs/en/fpolicy-production-architecture-patterns.md` | `~2 minute recovery gap` | `retraction` | 再起動時の欠落窓が分の桁であること。**取り込みに使う場合、この窓は読み込まれないファイルになります** |
<!-- cross-repo-table:end -->

---

### probe の沈黙が意味しないこと

**probe が動かないことは「相手側で何も起きていない」ではありません。** ゲートについては真で、世界については偽です。

引用先が測定を完了しても、**文字列が動かない場合があります。**

| 相手側で起きたこと | 文字列 | こちらのゲート |
|---|---|---|
| 主張が撤回された | 消える | **発火** |
| 範囲が広がった | 変わる | **発火** |
| **測ったが、その主張の範囲内に収まった** | **不変** | **沈黙** |
| **測ったが、その表に載せない判断になった** | **不変** | **沈黙** |

**下 2 行が問題です。** 4 通りのうち 2 通りで、測定が完了しても probe は沈黙します。**つまり probe は完了の合図として使えません。**

**下から 2 行目の実例があります。** ブロックの単一接続が測られ、`500〜592 MB/s に収まる` を引く行は
**「ブロックの 1 セッションが測られた時点で発火する見込み」と書いていました。測定は完了し、probe は
沈黙しました。** 引用先が、その値を単一接続の 3 行に足さないことを**測る前に**決めていたためです。
**そして沈黙している間に、こちらの記述は誤ったままでした** — 「ブロックが同じ位置に来るなら」という
前提で補正を足す指示を出しており、実測は約 2 倍で、指示の向きが逆でした。**発火の予想を書くと、
沈黙が「まだ起きていない」の確認に見えます。** 予想は書かず、沈黙の理由を指す probe を別に張る形に
変えました。

引用先のリポジトリからの指摘で判明しました。**こちらは「文がそのまま残る → 何も起きない」と書いており、それが誤りでした。** 完了は Issue で知らされる必要があり、**沈黙を「まだ測っていない」と読むと、待ち続けます。**

**probe が答えるのは 1 つだけです。「引いている主張がまだそこにあるか」。** 相手の進捗は答えません。

### probe が主張を名指していない 2 つの形

**「引用先に文字列が存在する」ことは、probe が機能していることではありません。** 存在したまま
何も守らなくなる形が 2 つあり、**規則が別なので互いを見つけられません。**

| 形 | 何が起きるか | 発火 |
|---|---|---|
| **見出しのみ** | 節が題を保ったまま中身が反対の所見に置き換わる | **しない** |
| **多重一致** | 2 か所以上にあり、片方を書き換えても残る | **しない** |

**この 2 集合は重なりませんでした。** 見出しのみを検出する規則を持つ側と多重一致を検出する規則を
持つ側が、それぞれ 6 件を報告し、**同じ行は 1 件もありませんでした。** つまり片方の規則しか持たない
状態は、見えない側の形については**規則が無いのと区別できません。**

判定は [`tools/probe_strength.py`](../../../tools/probe_strength.py) の 1 か所にあり、
**outbound（`make cross-repo-external`）と inbound（`make inbound-probes`）が同じ関数を読みます。**
2 つ目のコピーを作ると、両方が成功を報告しながら別の規則を強制する状態になります。

**強制の場所が方向で違います。**

| 方向 | 検査 | `make all` |
|---|---|---|
| inbound | pin されたファイルがこのツリーにあるのでオフライン | **入っています** |
| outbound | 引用先のファイルを取得するのでネットワークが必要 | **入っていません**（`make cross-repo-external` が opt-in）|

**outbound をコミットゲートに入れられないのは構造的な制約です。** 引用先のファイルはこちらに
ありません。**したがって弱い probe を登録した瞬間には止まらず、外部チェックを走らせたときに
止まります。** 登録の手順（[引用を足すときの手順](#引用を足すときの手順)）の手順 8 がその機会です。

**第 3 の形は規則で判定できません。** 1 回・本文にあっても主張を運んでいない文字列があり、
**検出器は報告しません。** `Cost Explorer` は 13 文字の製品名で、その文書が実測手順であることを
やめても残ります。**長さは基準になりません** — 8 文字でも特定の実測比を名指す文字列は強く、
13 文字の製品名は何も守りません。行ごとの判断になります。

**3 つの形は独立です。** 主張を名指していても多重一致でありえます。`0.18 倍` は特定の実測比なので
第 3 の形では強く、**2 か所にあったので再登録の対象になりました。** 片方の観点で合格したことは、
他方の観点について何も言いません。

### 引用先が自己矛盾している場合の沈黙

**上の[引用表の注記](#引用表)は、引用元がこちら側で自己矛盾する場合を扱っています。引用先が
自己矛盾する場合は別の盲点で、こちらのほうが検出できません。**

引用先のリポジトリが同じ主張について 2 つのファイルで違う値を持っているとき、**probe はどちらに
張っても沈黙します。** 正しい側に張れば文字列は存在し、誤った側に張れば**そちらの文字列も存在する**
からです。**ゲートは 2 つの値の食い違いを見ていません。**

実例があります。FPolicy の KeepAlive の間隔について、引用先の一方は測定に基づく値へ訂正済みで、
他方は訂正前の値のままでした。**桁が 1 桁違います。** 訂正済みの側に probe を張れば通り、訂正前の
側に張っても通ります。**「probe が通っているから引用先は整合している」は成り立ちません。**

| 引用先の状態 | probe |
|---|---|
| 主張が撤回された | **発火** |
| 主張が移動した | **発火** |
| **同じ主張について 2 つのファイルが違う値を持っている** | **沈黙**（どちらに張っても） |
| **引用していない別の主張が誤っている** | **沈黙** |

**したがって取れる手は 2 つだけです。** 争点になっている値を引用しない（[保留](#まだ-probe-を張れていない引用)に
検査できる解除条件つきで置く）か、逆リンクを依頼するときに**引用している主張が同じリポジトリの
他のファイルと一致しているかを併せて訊く**か。**ゲートを厚くしても解決しません。**

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
（`7 ms 対 2,171 ms`、`SMB は NFS の 72.1%`）や観測値そのもの（`12,173 MiB/s = **102 Gbps**`）は、
引用先が測定を足しても書き換わりません。**`reread` を広く付けると、その主張については撤回を検出
できなくなります。**

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

**保留には型が 3 つあり、解消のしかたが違います。** 型を取り違えると沈黙を進捗と読みます。

| 型 | 何を待っているか | 解消したときの動き |
|---|---|---|
| コミット待ち | 引用先の既定ブランチにファイルが現れること | 引用表へ移して probe を張る |
| **対象外** | **何も待っていません。** 転記しない方針の結果で、照合する文字列がそもそも存在しません | 解消しません。方針が変わらない限り恒久です |
| **訂正待ち** | 引用先の記述そのものが訂正されること。**ファイルは既に存在します** | 訂正の完了を確認してから引用表へ移す |

**そして「相手からの通知待ち」と書かないでください。** 通知は届かないことがあり、届かないことと
起きていないことを区別できません。**検査できる条件に書き換えられるなら、そうします。**

| 引用元 | 根拠の所在 | 型 | 検査できる解除条件 |
|---|---|---|---|
| `docs/ja/domains/observability/notes/cross-account-is-a-network-problem.md` | [Issue #71 の回答](https://github.com/Yoshiki0705/FSx-for-ONTAP-Observability-integrations/issues/71)（公開 URL、恒久） | コミット待ち | **未確定。** 回答時点で約 67 件が未コミットで、**どのファイルが根拠になるかを特定できていません。** 特定できた時点で 1 行の検査に書き換えます |
| `docs/ja/domains/data-utilization/notes/reaching-data-without-copies.md` | [Issue #162 の回答](https://github.com/Yoshiki0705/FSx-for-ONTAP-Agentic-Access-Aware-RAG/issues/162#issuecomment-5563205901)（公開 URL、恒久） | 対象外 | **ありません。** 実装のファイル名・関数名を転記しない方針で、**転記しないなら probe を張る対象がありません。** 二重管理を避けた結果としてゲートの外に出ます |
| `docs/ja/domains/data-utilization/notes/fpolicy-fits-by-how-writes-land.md`（**KeepAlive の間隔のみ**） | `FSx-for-ONTAP-Observability-integrations` の `docs/en/operational-notes-fpolicy.md` と `docs/en/verification-results-fpolicy-s3ap-and-session.md` | 訂正待ち | **`docs/en/operational-notes-fpolicy.md` に `6 second` が含まれないこと。** 2 文書が桁の違う 2 つの値を持っており、訂正されるまで**桁でも引用していません** |

**3 行目が保留しているのは 1 つの数値だけです。** 同じ引用先の他の主張（NLB の役割、欠落窓、
セッションの継続）は争点になっていないので、**上の引用表に probe を張ってあります。** 引用先の
ファイル単位で保留すると、争点になっていない主張の撤回も検出できなくなります。

**Issue のコメントは公開されていて消えませんが、ファイルではないので probe の対象にできません。**
つまりこの引用は、**索引に載っていても撤回を検出できない**状態です。

### 転記しない選択の代償

**上の 2 行目は、相手のコミットを待っているのではありません。** 実装の詳細（ファイル名・関数名・行）を
こちらへ転記しない方針を採ったので、**照合する文字列がそもそも存在しません。**

転記すれば probe を張れます。ただし**二重管理になり、相手がリファクタリングした時点で片方が腐ります。**
どちらを選んでも失うものがあり、ここでは**腐った記述が残るより、ゲートの外にあることが記録されている
ほうがましだと判断しました。** この判断は方針であって、ゲートの不足ではありません。

### 他リポジトリがこちらを pin している probe

**この索引は outbound だけを扱います。** 逆向き——**他リポジトリがこちらのファイルの文字列を pin
している**——は別の artefact になりました。

| 向き | 追跡 | ゲート |
|---|---|---|
| outbound（こちらが他所を pin） | この索引と [probe 契約](../../agent/cross-repo-probe-contract.txt) | `make cross-repo` / `make cross-repo-external` |
| **inbound（他所がこちらを pin）** | [inbound-probe-contract.txt](../../agent/inbound-probe-contract.txt) | **`make inbound-probes`** |
| 外部から引用されている見出し | [アンカー契約](../../agent/external-anchor-contract.txt) | `make anchors` |

**inbound の検査はネットワークを使いません。** pin されているファイルがこちらのツリーにあるので、
`make all` の中に入っています。**発見のほうだけがネットワークを要します**（`make inbound-probes-refresh`）。

**inbound には「存在すること」より強い規則が要ります。**

| 状態 | 相手のゲート | 意味 |
|---|---|---|
| 1 回・本文 | 緑 | 正常 |
| **0 回** | **赤** | **こちらの編集が、相手側では主張の撤回として報告されます** |
| **2 回以上** | **緑** | **片方を書き換えても鳴りません。probe が何も守らなくなります** |
| **見出しのみ** | **緑** | 節の題が残ったまま中身が入れ替わります |

**2 行目と 3 行目の非対称が要点です。** 消すと相手が赤くなって気づけますが、**増やすと誰も気づき
ません。** そして **probe について書くこと自体が 2 回目を作ります** — 引用元のリポジトリが、まさに
この現象を文書化している最中に踏んでいます。だから
[block-to-file-routes.md](comparison/block-to-file-routes.md) の注記は文字列を引用せず、所在だけを
指しています。

**網羅は下限です。** 発見は各 sibling が**公開している**契約を読み、sibling の一覧は本文中の
リポジトリ参照から導出します（固定の一覧を持ちません）。**契約ファイルの不在は probe の不在では
ありません。** 公開していない sibling は artefact の末尾に unknown として並ぶので、**どこまでが
検査済みでどこからが不明かは artefact を見てください** — 件数をここに書くと更新が人手に残ります。
**現状は大半が unknown です。**

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
| 3 | 上の表に 1 行足す。**確認する文字列は主張を指し、引用先に 1 回だけ現れ、見出しではないもの**にする | 見出しだと撤回を検出できず、2 か所にあると片方を書き換えられても発火しません |
| 4 | **役割を決める。** 集合の最小値・最大値を含むなら `reread`、それ以外は `retraction` | 発火の意味が 1 通りに読めなくなります |
| 5 | `python3 tools/check_cross_repo.py --write-contract` を実行する | **引用先が読むのは公開した契約で、この表ではありません** |
| 6 | 条件を本文に併記する。引用先だけに置かない | 読者が引用先を開かずに誤用します |
| 7 | `make cross-repo` を実行する | リンクと表の対応、および契約が表と一致すること |
| 8 | `make cross-repo-external` を実行する | 引用先に主張がまだあるか、**および probe が見出しのみ・多重一致でないか。** ネットワークが要るのでコミットゲートには入らず、**弱い probe が止まる唯一の機会がここです** |
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
