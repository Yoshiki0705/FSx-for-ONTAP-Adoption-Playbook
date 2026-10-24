---
title: GCP と Amazon FSx for NetApp ONTAP の到達性とサンプルデータを安全に確認する
lifecycle: [assess, build, operate]
domains: [data-protection, client-access, security-governance]
evidence: documented
source: https://cloud.google.com/netapp/volumes/docs/migrate/ontap/prerequisites-ontap-netapp-volumes
lang: ja
---

# GCP と Amazon FSx for NetApp ONTAP の到達性とサンプルデータを安全に確認する

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

## 結論

この手順は、GCP と Amazon FSx for NetApp ONTAP の間で、既存のネットワークと専用の検証ボリュームを変更前に確認し、GCP の Linux クライアントから NFS 経由でサンプルデータを検証するためのものです。クラスターピアリング、SVM ピアリング、SnapMirror の開始・停止・Reverse Resync はこの文書の実行対象に含めません。これらの管理面操作は [別の open-items 文書](gcp-to-fsx-ontap-peering-and-replication-open-items.md)で扱います。

| 判定 | 意味 |
|---|---|
| `documented` | 公開ドキュメントに基づく手順または前提 |
| `verified` | 環境、日付、実行 ID が記録された実測 |
| `field-observation` | 一度観測したが、この文書では再現していない結果 |
| `open` | 根拠または実行インターフェースが不足しており、公開手順として確定していない状態 |

> **Evidence: documented**
>
> GCP と外部 ONTAP 間の通信には、GCP 側の経路、AWS 側の戻り経路、ファイアウォール、NFS export policy がすべて揃っている必要があります。出典は [Google Cloud: ONTAP と Google Cloud NetApp Volumes の通信前提](https://cloud.google.com/netapp/volumes/docs/migrate/ontap/prerequisites-ontap-netapp-volumes)です。

## はじめかた

| 段階 | 目的 | 主な担当 | 必要な権限 | 出力と停止条件 |
|---|---|---|---|---|
| 1 | 対象と所有者の確定 | AWS / GCP 担当 | AWS/GCP の読み取り権限 | 対象不一致なら停止 |
| 2 | 経路と NFS 到達性の確認 | ネットワーク担当 | VPC、VPN、Cloud Router の読み取り権限 | 戻り経路・2049/TCP 不通なら停止 |
| 3 | NFS マウントの安全確認 | GCP Linux 担当 | GCP Compute Engine の操作権限 | NFS 以外の mount は停止 |
| 4 | サンプル検証 | GCP Linux 担当 | 専用検証ディレクトリへの書き込み | 件数・manifest 不一致なら停止 |
| 5 | DP read-only 確認 | AWS / GCP 担当 | AWS/GCP の読み取り権限 | 書き込み可能なら停止 |
| 6 | 片付け | 作成者 | 作成した一時資源の所有権 | 共有資源は削除せずレビュー |

所要時間は環境、ファイルサイズ、ネットワーク帯域に依存する**計画上の目安**です。サービスの処理時間や本番見積りではありません。

## 前提条件と担当者

### 対象台帳

実行前に、次の値を run ledger に記録します。公開文書には実値を記録しません。

| 項目 | 値の形式 | 担当 |
|---|---|---|
| GCP project / region | `<gcp-project-id>` / `<gcp-region>` | GCP 担当 |
| GCP VPC / Cloud VPN / Cloud Router | `<gcp-vpc>` / `<vpn-name>` / `<router-name>` | GCP ネットワーク担当 |
| AWS account / region / VPC | `<aws-account>` / `<aws-region>` / `<aws-vpc-id>` | AWS 担当 |
| AWS VGW / VPN | `<vgw-id>` / `<vpn-id>` | AWS ネットワーク担当 |
| FSx for ONTAP file system / SVM | `<file-system-id>` / `<fsx-svm-name>` | AWS ストレージ担当 |
| NFS endpoint / export | `<nfs-endpoint>` / `<export-path>` | AWS ストレージ担当 |
| GCP Linux client | `<gce-instance>` | GCP 担当 |

### 停止条件

対象の所有者、リージョン、SVM、ボリューム、接続先、または run ID が台帳と一致しない場合は停止します。共有 VPN、Cloud Router、VGW、route table、security rule を削除・変更する場合は、run-created と確認できない限り停止し、所有者に戻します。

> **Evidence: documented**
>
> この手順は、対象リソースの読み取り確認を先に実施し、共有資源の所有権を推測しない前提で書いています。削除やルート変更の成功レスポンスだけでは、変更後の状態を証明できません。

## ネットワーク到達性と戻り経路

### GCP 側の確認

GCP 担当は、Cloud VPN トンネルと Cloud Router の BGP 状態を確認します。値は例です。

```bash
set -euo pipefail
GCP_PROJECT_ID="<gcp-project-id>"
GCP_REGION="<gcp-region>"
VPN_NAME="<vpn-name>"
ROUTER_NAME="<cloud-router-name>"
AWS_PREFIX="<aws-vpc-cidr>"

gcloud config set project "$GCP_PROJECT_ID"
gcloud compute vpn-tunnels list \
  --regions "$GCP_REGION" \
  --filter="name:$VPN_NAME" \
  --format='table(name,status,router,peerIp)'
gcloud compute routers get-status "$ROUTER_NAME" \
  --region "$GCP_REGION" \
  --format=json
```

`ESTABLISHED` / `UP` と、AWS VPC CIDR の BGP learned route が必要です。Cloud Shell など GCP VPC 外の環境から行ったテストは、VPC 内クライアントの疎通証拠にしません。

### AWS 側の確認

AWS 担当は、VGW、VPN、FSx for ONTAP の NFS サブネットの route table を確認します。

```bash
set -euo pipefail
AWS_REGION="<aws-region>"
VPC_ID="<aws-vpc-id>"
NFS_SUBNET_ID="<nfs-subnet-id>"
VGW_ID="<vgw-id>"
GCP_CIDR="<gcp-client-cidr>"

aws ec2 describe-vpn-connections \
  --region "$AWS_REGION" \
  --vpn-connection-ids "<vpn-id>" \
  --query 'VpnConnections[].VgwTelemetry'
aws ec2 describe-route-tables \
  --region "$AWS_REGION" \
  --filters "Name=association.subnet-id,Values=$NFS_SUBNET_ID" \
  --query 'RouteTables[].{RouteTable:RouteTableId,Routes:Routes}'
```

戻り経路は GCP クライアント CIDR を宛先とし、VGW、VPN、または事前承認済みの VPC peering/TGW を next hop とします。GCP 側の learned route だけでは AWS 側の戻り経路を証明できません。

### セキュリティと NFS 経路

NFS endpoint の 2049/TCP を GCP クライアント CIDR から許可する security group、NACL、export policy を確認します。変更が必要な場合は、変更対象、所有者、現在値、作成者、rollback を ledger に記録し、変更前に承認します。export policy は ONTAP 管理面の設定なので、AWS API だけで確認できない場合は、この手順を `open` として停止します。

GCP クライアントからの実測は次の条件で行います。

```bash
set -euo pipefail
NFS_ENDPOINT="<nfs-endpoint>"
timeout 5 bash -c "</dev/tcp/$NFS_ENDPOINT/2049"
```

成功しなければ、NFS mount や書き込みへ進みません。

## NFS サンプルデータとハッシュ検証

### 安全なマウント

GCP の Linux クライアントで、まず mount root だけを確認します。fixture directory を作る前に確認してください。

```bash
set -euo pipefail
SAMPLE_MOUNT="/mnt/gcp-fsx-sample"
NFS_ENDPOINT="<nfs-endpoint>"
EXPORT_PATH="<export-path>"

mountpoint -q "$SAMPLE_MOUNT"
findmnt -T "$SAMPLE_MOUNT" -o TARGET,SOURCE,FSTYPE,OPTIONS
SOURCE="$(findmnt -n -T "$SAMPLE_MOUNT" -o SOURCE)"
FSTYPE="$(findmnt -n -T "$SAMPLE_MOUNT" -o FSTYPE)"
test "$FSTYPE" = nfs || test "$FSTYPE" = nfs4
test "$SOURCE" = "$NFS_ENDPOINT:$EXPORT_PATH"
```

`mountpoint` が失敗する、FSTYPE が local filesystem、SOURCE が台帳と一致しない、既存の run directory または marker がある場合は停止します。

### Fixture と manifest

この手順の新規 fixture は、過去の 48 ファイル観測と同一だったことを証明していません。過去の観測を `verified` として公開するには、実行日時・run ID・環境・元の hash manifest を別の証拠記録で回収できる必要があります。回収できない場合、過去の結果は本文で `open` とし、以下の fixture は再現用手順として扱います。

次の Python 標準ライブラリ処理で 48 ファイルを作成します。

```bash
set -euo pipefail
RUN_ID="<run-id>"
FIXTURE_ROOT="$SAMPLE_MOUNT/gcp-fsx-ontap-$RUN_ID"
python3 - "$FIXTURE_ROOT" <<'PY'
from pathlib import Path
import hashlib
import sys

root = Path(sys.argv[1])
if root.exists():
    raise SystemExit(f"refusing existing fixture: {root}")
root.mkdir(parents=True)
manifest = []
for index in range(1, 49):
    name = f"sample-{index:03d}.txt"
    seed = f"gcp-fsx-ontap-sample-{index:03d}"
    payload = hashlib.sha256(seed.encode("ascii")).hexdigest().encode("ascii") + b"\n"
    path = root / name
    path.write_bytes(payload)
    manifest.append((hashlib.sha256(payload).hexdigest(), name))
(root / "manifest.sha256").write_text(
    "".join(f"{digest}\t{name}\n" for digest, name in sorted(manifest)),
    encoding="ascii",
)
PY

test "$(find "$FIXTURE_ROOT" -type f -name 'sample-*.txt' -printf '%f\n' | wc -l)" -eq 48
```

### DP ボリューム検証

複製先が DP/read-only と台帳に記録されている場合のみ、同じ manifest を比較します。実際の mount source とボリューム役割が一致しない場合は停止します。

```bash
set -euo pipefail
FIXTURE_ROOT="<verified-dp-mount>/gcp-fsx-ontap-<run-id>"
MANIFEST="$FIXTURE_ROOT/manifest.sha256"

ACTUAL="$(find "$FIXTURE_ROOT" -type f -name 'sample-*.txt' -printf '%f\n' | sort)"
EXPECTED="$(printf 'sample-%03d.txt\n' $(seq 1 48) | sort)"
test "$ACTUAL" = "$EXPECTED"
( cd "$FIXTURE_ROOT" && sha256sum -c <(awk -F '\t' '{print $1 "  " $2}' "$MANIFEST") )
touch "$FIXTURE_ROOT/.write-test" 2>&1 && exit 1 || true
```

`touch` の失敗が `Read-only file system` 以外なら、DP read-only の証拠として採用せず停止します。48 件の hash、failed、missing、extra、read-only 結果は private run ledger に記録します。公開文書には実 ID、実パス、hash の個別値を載せません。

## 片付けと停止条件

作成者は run ledger を参照し、次の順に片付けます。

1. fixture directory と一時 mount を解除する。既存 mount は削除しない。
2. run-created の一時 client がある場合だけ停止・削除する。
3. run-created の security rule、route、BGP advertisement を、直前の fresh read で同一内容か確認してから戻す。
4. shared または pre-existing の VPN、Cloud Router、VGW、peering、route table、SVM、volume は残し、所有者レビューへ送る。
5. 未完了 replication、active transfer、依存関係が残る場合は停止する。relationship を break/delete する操作は、対象、方向、所有者、現在状態、確認文を再提示してから実行する。

この文書の作成・検証では、上記の mutation は実行しません。

## 関連文書

- [Evidence policy](../evidence-policy.md)
- [Localization workflow](../../agent/localization.md)
- [S3 Access Points の制約](../domains/data-utilization/notes/s3-access-point-constraints.md)
- [データ保護](../domains/data-protection/)
- [クライアントアクセス](../domains/client-access/)
- [GCP-to-FSx for ONTAP peering と replication の未解決項目](gcp-to-fsx-ontap-peering-and-replication-open-items.md)

## Evidence と未解決事項

> **Evidence: documented**
>
> NFS、VPN、Cloud Router、VGW、route table、security group、export policy の確認順序は、各 provider の公開資料と本リポジトリの手順規約に基づきます。環境固有の結果は、この文書だけでは証明しません。

> **Status: open**
>
> このスレッドで確認された 48 ファイルの SHA-256 結果は、公開 checkout から参照できる正式な run record がないため、ここでは再現手順と分離しています。run ID、環境、日付、48/48、failed=0、missing=0、DP read-only の記録が揃えば verified に昇格できます。

<!-- lang-switcher:start -->
🌐 [日本語](gcp-to-fsx-ontap-preflight-and-sample-validation.md) | [English](../../en/reference/gcp-to-fsx-ontap-preflight-and-sample-validation.md) | [🏠 リポジトリトップ](../../../README.md)
<!-- lang-switcher:end -->
