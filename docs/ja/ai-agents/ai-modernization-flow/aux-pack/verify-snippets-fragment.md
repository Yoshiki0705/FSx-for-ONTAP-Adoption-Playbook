# 検証スニペット（`verify-snippets.md` 貼り込み用）

[🏠 リポジトリトップ](../../../../../README.md) | [補助パック](README.md)

---

この断片は、[観点表の行](analysis-appendix-fragment.md) の各 `MP-FSXN-N` に対応する否定テスト手順と「正しいと言える観測」を文で書いたものです。AIMF Playbook の `verify-snippets.md` に追記してください。**検出コマンドの実行結果・件数は載せません。** 実機・実ソースに当てて回していないためです。否定テストは「壊して検出器が EXIT≠0 を返すことを確認する手順」を文で書いています。

---

## 否定テスト手順

- **MP-FSXN-1（大文字小文字）**: 実在するファイル名の 1 文字を別の大小に変えた参照（例: `seed/docs/index.json` に対する `seed/Docs/Index.json`）をソースに一時的に埋め込み、検出器が `git ls-files` の実名と一致しないことを検出して EXIT≠0 を返すことを確認します。確認後に埋め込んだ参照を戻します。正しいと言える観測は、綴り違いの参照が 1 件もなく、全参照が実名と厳密一致すること。**`test -e` を使う実装だと作業ホスト（macOS）で偽陰性になる**ので、否定テストが通らないときはまず検出器が `git ls-files` ベースかを確認します。
- **MP-FSXN-2（モード切替の綴り不一致）**: この観点は `hypothesis` です。否定テストは、保存側パスと返却 URL の組に意図的な綴り不一致を作り、突合スクリプトがそれを検出することを確かめる形になります。**FSx for ONTAP S3 経路での発火は実測していない**ので、検出器が動くことと観点が実環境で発火することは別です。
- **MP-FSXN-3（非対応 API）**: 非対応 API（例: `If-None-Match` による条件付き書き込み）の呼び出しをソースに一時的に足し、検出器が[対応表](https://docs.aws.amazon.com/fsx/latest/ONTAPGuide/access-points-for-fsxn-object-api-support.html)と突合して EXIT≠0 を返すことを確認します。正しいと言える観測は、使用している S3 API がすべて対応表に載っていること。対応表は partial list なので、「列挙に無い = 対応」とは読みません。
- **MP-FSXN-4（反映の方向非対称）**: 書き込み直後に待機 / retry なしで読む同期処理をソースに一時的に作り、検出器がそれを列挙することを確かめます。正しいと言える観測は、反対プロトコルからの読み取りがすべて待機 / retry を伴うこと。遅れの秒数は構成依存なので、特定の秒数を閾値に焼き込みません。
- **MP-FSXN-5（クロスプロトコルの排他ロック）**: ロックを取らずにクロスプロトコル共有対象へ書く経路をソースに一時的に作り、検出器がそれを列挙することを確かめます。正しいと言える観測は、クロスプロトコルで共有するファイルへの書き込みが `FileShare.None` / `fcntl` のロックを伴うこと。**ロックを取らない書き手が別プロトコルの保持者によって止められるかは未測定**なので、観点は「拒否されうる」までです。
- **MP-FSXN-6（撤去時の停滞）**: teardown スクリプトに ONTAP CLI の `volume delete` を一時的に足し、検出器が S3 Access Points を触るボリュームに対するその使用を EXIT≠0 で止めることを確認します。正しいと言える観測は、S3 Access Points を触ったボリュームの撤去がすべて `aws fsx delete-volume` を使っていること。

---

## Snapshot / FlexClone で integration データを戻す例

> **これは例であり、現時点では未検証です。** 実機で 1 回通してから `verified` にしてください。コマンドは ONTAP REST API / CLI の形を示すもので、このリポジトリで実行・測定していません。

Phase 3 の検証で integration データを破壊的に変えたあと、次の run を同一の初期状態から始めたい場合、本番相当データの Snapshot を取って FlexClone で配り、run ごとに作り直す形が使えます。

```bash
# 例（未検証）: integration ボリュームの Snapshot を取り、FlexClone で検証用ボリュームを作る。
# <cluster-mgmt> / <svm> / <volume> は環境値に置き換える。実値は書かない。
curl -ku <user>:<password> -X POST \
  "https://<cluster-mgmt>/api/storage/volumes/<volume-uuid>/snapshots" \
  -d '{"name": "integration-baseline"}'

# FlexClone で検証用ボリュームを作る（親の Snapshot を基点にする）。
curl -ku <user>:<password> -X POST \
  "https://<cluster-mgmt>/api/storage/volumes" \
  -d '{"name": "integration-run-clone", "clone": {"parent_volume": {"name": "<volume>"}, "parent_snapshot": {"name": "integration-baseline"}, "is_flexclone": true}}'
```

FlexClone でテストデータを配るときに決める 3 点（認可・資源・寿命）は Hub の該当ノートにあります。本文はここに複製しません。

- 認可と資源（ストレージ管理者を介さずに配れる範囲）: [ストレージ管理者なしのセルフサービス](../../../domains/security-governance/notes/self-service-without-storage-admin.md)
- 版と実験ブランチ（どの Snapshot を基点にするか）: [データセットの版と実験ブランチ](../../../domains/data-utilization/notes/dataset-versions-and-experiment-branches.md)

> **マスキングの要否は人が決めます。** 本番相当データを検証に使う可否は AIMF 側で人の判断（Tier 2 / HOLD）に残ります。このスニペットは配布の機構を示すだけで、マスキングするかどうかを決めません。

---

## 撤去の注意（MP-FSXN-6 と接続）

S3 Access Points を取り付けた、あるいは取り付けようとしたボリュームの teardown は、ONTAP CLI の `volume delete` ではなく `aws fsx delete-volume` を使ってください。ONTAP CLI の `volume delete` を前提にした手順書は、この経路で詰まります。根拠と実測は Hub の [撤去時の停滞](../../../domains/data-utilization/notes/s3-access-point-constraints.md#撤去時の停滞--aws-側からしか消せなくなるボリューム) にあります。

---

[🏠 リポジトリトップ](../../../../../README.md) | [補助パック](README.md)
