---
title: ONTAP 9.17.1 から 9.20.1 の新機能と FSx for ONTAP での確認状況 — リリースノートの記載と、FSx for ONTAP で使えることは別に確かめる
lifecycle: [assess, design, operate]
domains: [security-governance, performance]
evidence: documented
source: https://docs.netapp.com/us-en/ontap/release-notes/index.html
lang: ja
---
# ONTAP 9.17.1 から 9.20.1 の新機能と FSx for ONTAP での確認状況

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)

---

## このページの位置づけ

NetApp の What's new in ONTAP に載る機能のうち、Amazon FSx for NetApp ONTAP（以下 FSx for ONTAP）に関係しうるものを版ごとに並べ、**FSx for ONTAP で使えることを確かめた行と、まだ確かめていない行を分けて**記録します。設計や構築で「この機能は使えるか」を調べるときの、最初に読む表です。

> **区分**: `documented` — 「機能」と「条件」の列は NetApp のリリースノートの記載です。「状態」の列にある確認の結果は、リンク先のノートの区分に従います。**リリースノートに載っていることは、FSx for ONTAP で使えることの根拠になりません。** FSx for ONTAP が提供する ONTAP の版と、管理者ロール `fsxadmin` で使えるコマンドは、別に確かめる必要があります。

## 読み方

- 出典は NetApp の What's new in ONTAP の 4 ページ（[9.17.1](https://docs.netapp.com/us-en/ontap/release-notes/whats-new-9171.html)、[9.18.1](https://docs.netapp.com/us-en/ontap/release-notes/whats-new-9181.html)、[9.19.1](https://docs.netapp.com/us-en/ontap/release-notes/whats-new-9191.html)、[9.20.1](https://docs.netapp.com/us-en/ontap/release-notes/index.html)）です。2026-11-23 に 4 ページとも全文を読みました。
- 「条件」の列は、リリースノートが書く対象製品や構成を写したものです。空欄は、条件の記載がないことを表します。
- 「状態」が「未確認」の行は、確かめていません。「確認」の行は、環境（世代、ONTAP の完全な版、日付）をリンク先のノートに記録しています。
- 確認した環境は、ap-northeast-1 の第 1 世代（`SINGLE_AZ_1`）の ONTAP 9.19.1P4 が中心です。第 2 世代と第 3 世代は、まだ確かめていません。
- 9.20.1 を FSx for ONTAP が提供しているかは、確認していません。
- 取り直しの手順は、[ファイルシステムを作り直すたびの世代と版の確認](../playbooks/04-build/checklists/rebuild-version-and-generation-checks.md)にあります。

---

## ONTAP 9.17.1

| 領域 | 機能 | 条件 | FSx for ONTAP での確認 | 状態 |
|---|---|---|---|---|
| NAS / S3 | ONTAP S3 の NAS バケットで CopyObject を使える | ONTAP S3 の NAS バケット | FSx for ONTAP の S3 Access Points と ONTAP S3 サーバーは別の仕組み。S3 Access Points の側で同等の操作ができるかを確認する | 未確認 |
| NAS / S3 | NAS バケットをボリュームにリンクする（ジャンクションパスの変更に追従） | ONTAP CLI で作成する NAS バケット | 同上 | 未確認 |
| NAS / S3 | マルチプロトコル環境の CreateMultipartUpload でタグとメタデータを使える | S3 と NAS のマルチプロトコル | 同上 | 未確認 |
| セキュリティ | ARP/AI のスナップショット更新 | | ARP/AI の設定項目と既定値を読み取る | 未確認 |
| セキュリティ | ARP/AI が SAN ボリュームに対応する | SAN | FSx for ONTAP の LUN で有効化できるか | 未確認 |
| セキュリティ | ARP が Hyper-V、KVM、OpenStack に対応する | 9.17.1P5 以降 | 対象のワークロードが FSx for ONTAP にあるか | 未確認 |
| セキュリティ | HTTP Strict Transport Security（HSTS） | | 管理 Web サービスの設定を読み取る | 未確認 |
| セキュリティ | LAG への IPsec ハードウェアオフロード、IPsec のポスト量子事前共有鍵 | | FSx for ONTAP で IPsec を設定できるか、ハードウェアオフロードの対象か | 未確認 |
| セキュリティ | RBAC の一時的な権限昇格（JIT） | | `fsxadmin` から設定できるか | 未確認 |
| セキュリティ | SAML の IdP として Entra を使う、IdP のグループをロールに対応づける | | 同上 | 未確認 |
| セキュリティ | クロスクラスターの要求を、実行側のクラスターでも監査する | ピア接続したクラスター | SnapMirror のピアで監査ログを取れるか | 未確認 |
| セキュリティ | OpenStack Barbican の鍵管理サービスに対応 | NVE の鍵 | OpenStack を使わない構成では対象外の可能性が高い。FSx for ONTAP の外部鍵管理の選択肢を確認する | 未確認 |
| データ保護 | SnapMirror active sync の NVMe アクセス、ONTAP Cloud Mediator | 2 ノードのクラスター | FSx for ONTAP が SnapMirror active sync を提供するか | 未確認 |
| ストレージ管理 | 新規 SVM の新規ボリュームで File System Analytics（FSA）が既定で有効になる | NAS プロトコル用のクラスター | 新規ボリュームの FSA の有無を読み取る | 未確認 |
| ストレージ管理 | `volume file async-delete show` がクライアント起点の非同期削除を表示する | FlexGroup | FlexGroup で表示を確認する | 未確認 |

## ONTAP 9.18.1

| 領域 | 機能 | 条件 | FSx for ONTAP での確認 | 状態 |
|---|---|---|---|---|
| ネットワーク | IPsec ハードウェアオフロードの IPv6 対応 | | FSx for ONTAP の IPsec の対応範囲 | 未確認 |
| ネットワーク | SSL のポスト量子暗号アルゴリズム | SSL FIPS モードが無効なとき | 管理エンドポイントで使えるか | 未確認 |
| ネットワーク | バックエンドのクラスターネットワークの TLS 暗号化、HA ペア間通信の暗号化 | | マネージドサービスの内部構成なので、利用者が設定できるかを確認する | 未確認 |
| SAN | NVMe コピーオフロード | NVMe | FSx for ONTAP の NVMe/TCP で使えるか | 未確認 |
| S3 | S3 スナップショットの時点復元（単一オブジェクト、複数、バケット全体） | ONTAP S3 | S3 Access Points での扱いを確認する | 未確認 |
| S3 | FlexCache ボリューム上の NAS バケット | クラスターの全ノードが 9.18.1 以降 | FlexCache 上で S3 Access Points を使えるか。別プロジェクトの記録を先に読む | 未確認 |
| セキュリティ | FlexGroup の ARP/AI 対応 | | FlexGroup で ARP/AI を有効にできるか | 未確認 |
| セキュリティ | 新規ボリュームで ARP/AI が 12 時間の猶予後に既定で有効になる | AFF A、AFF C、ASA、ASA r2。FSx for ONTAP は記載にない | 新規ボリュームの ARP/AI の状態を読み取る | 確認。第 1 世代の 9.19.1P4 で `disabled`。[ノート](../domains/data-protection/notes/new-volumes-start-with-arp-disabled-on-first-generation.md) |
| ストレージ管理 | FabricPool のスキャナーを動的な熱追跡に置き換え、大きなアグリゲートで負荷を下げる | FabricPool | FSx for ONTAP のキャパシティプールで挙動が変わるか | 未確認 |
| ストレージ管理 | SVM とその配下のボリュームに同時に QoS ポリシーを割り当てる（2 階層） | | `fsxadmin` から設定できるか | 未確認 |
| ストレージ管理 | SVM-DR の関係にあるオリジンボリュームの SVM FlexCache を作成する | | FSx for ONTAP で SVM-DR を使えるか | 未確認 |
| ストレージ管理 | `storage aggregate show-space` の論理参照容量の数え方が変わる | | `fsxadmin` が実行できるコマンドかを確認する | 未確認 |
| データ保護 | MetroCluster の FlexGroup に対する SnapMirror cloud | MetroCluster | FSx for ONTAP に MetroCluster の構成はないため、対象外の可能性が高い | 未確認 |

## ONTAP 9.19.1

| 領域 | 機能 | 条件 | FSx for ONTAP での確認 | 状態 |
|---|---|---|---|---|
| NAS | 小さな NAS ディレクトリ（2 MB 以下、約 25,000 ファイル）の一覧取得に、より多くの CPU を割り当てる | 設定不要 | 多数のクライアントが同じディレクトリを一覧したときの挙動 | 未確認 |
| ネットワーク | SVM ごとに NFSv4.2 を有効化・無効化する | | SVM の NFS 設定で個別に切り替えられるか | 確認（9.19.1P4、第 1 世代）。[ノート](../domains/multiprotocol-identity/notes/nfsv42-is-switched-independently-of-nfsv41.md) |
| ネットワーク | システム定義のフェイルオーバーグループポリシーが、フェイルオーバー先を拡張する | NAS データ LIF | LIF のフェイルオーバー先の範囲を読み取る | 一部確認。フェイルオーバーグループの変更権限は `readonly`。方針の切り替えは未確認 |
| ネットワーク | TCP の PRR（既定で有効）と RACK（既定で無効、約 25 Gbps の輻輳したネットワーク向け） | | RACK の設定を `fsxadmin` が変更できるか | 一部確認。設定のコマンド名を特定できていない |
| SAN | iSCSI と NVMe/TCP の LIF の自動フェイルオーバー | AFF と ASA | FSx for ONTAP の SAN LIF での挙動 | 未確認 |
| SAN | iSCSI の Foreign LUN Import | | FSx for ONTAP で使えるか | 未確認 |
| S3 | 条件付き書き込み・条件付き削除を強制する | ONTAP S3 | S3 Access Points の側で同等の操作ができるか | 未確認 |
| S3 | S3 ユーザーに 2 本目のアクセスキーを発行する | ONTAP S3 | 同上 | 未確認 |
| セキュリティ | NFS over TLS（TLS 1.3）、LIF ごとの相互 TLS 認証 | | 有効化できるか | 確認。`fsxadmin` から使えない（9.19.1P4、権限 `none`） |
| セキュリティ | TLS オフロード | 対応する Ethernet カード | FSx for ONTAP が該当のカードを備えるか | 未確認 |
| セキュリティ | ARP/AI が SnapMirror synchronous と SnapMirror active sync に対応する | FAS、AFF、AFX、ASA r2 | FSx for ONTAP が SnapMirror synchronous を提供するか | 未確認 |
| セキュリティ | System Manager が ARP のワークロード特性（基準値と急増の統計）を表示しなくなる | CLI と REST では引き続き参照できる | 画面の変更なので、FSx for ONTAP では CLI と REST で参照できるかを確認する | 未確認 |
| セキュリティ | WebAuthn の `-rp-domains` | System Manager の多要素認証 | 設定できるか | 未確認 |
| データ保護 | SnapMirror synchronous でタンパープルーフスナップショットのロック、スケジュールスナップショットの複製 | | 提供の有無。ロックは取り消せないため、使い捨ての環境で、保持期間を人が指定してから行う | 未確認 |
| データ保護 | SnapMirror cloud が 100 個の S3 バケットまで対応する | | FSx for ONTAP が SnapMirror cloud を提供するか | 未確認 |
| データ保護 | SnapMirror active sync の NAS 対応、AIX の透過フェイルオーバー | AFF の 2 ノード、AFX の 4 ノード | 提供の有無 | 未確認 |
| ストレージ管理 | `volume show-space` の出力にディレクトリが加わる | | 出力を比べる | 確認。項目 `dir-l0-blk-cnt` が返る（9.19.1P4） |
| ストレージ管理 | QoS の自動上限引き上げの既定値を変更できる | 9.18.1 以前では変更できない | `fsxadmin` が変更できるか | 確認（9.19.1P2）。[ノート](../domains/performance/notes/qos-burst-defaults-are-user-modifiable.md) |
| System Manager | SVM 管理者向けのダッシュボード | | FSx for ONTAP が System Manager を公開するか | 未確認 |
| アップグレード | 事前チェックのエラーと警告を分けて表示する | | FSx for ONTAP では AWS が更新を行うため、利用者に見える範囲を確認する | 未確認 |
| SAN | FC の直接接続、AFF のアクティブ/アクティブマルチパス | FC、AFF | FSx for ONTAP に FC 接続はないため、対象外の可能性が高い | 未確認 |

## ONTAP 9.20.1

| 領域 | 機能 | 条件 | FSx for ONTAP での確認 | 状態 |
|---|---|---|---|---|
| NAS | 約 2,500 万ファイルまでを含むディレクトリで、ディレクトリサイズの上限を最大 4 GB まで扱えるようにする | AFF と FAS。ボリュームごとに有効化 | FSx for ONTAP が対象に含まれるか | 未確認 |
| NAS | SMB の正規化名クエリ | Windows 11 24H2 以降のクライアント | クライアントの組み合わせを確認する | 未確認 |
| NAS | VMware の NFS データストアで自動的に領域を回収する | NetApp NFS Plug-in for VMware VAAI、ESXi 9.0 以降 | FSx for ONTAP を NFS データストアにした環境で確認する | 未確認 |
| NAS | LDAP 接続の SVM で、SID から UNIX の UID と GID を自動変換する | 既定で無効、SVM ごとに設定 | AWS Managed Microsoft AD と組み合わせた環境で設定できるか | 未確認 |
| FPolicy | NFSv4.2 に FPolicy を拡張する | 外部エンジンが protobuf 形式 | FSx for ONTAP の FPolicy の対応範囲 | 未確認 |
| FPolicy | S3 オブジェクトに FPolicy を拡張する | | 同上。S3 Access Points での扱いを確認する | 未確認 |
| S3 | 新規バケットの既定サイズを設定できる | | S3 Access Points の側での扱いを確認する | 未確認 |
| S3 | FlexVol オリジンの FlexCache ボリューム上の NAS バケット、CopyObject と UploadPartCopy | マルチパートアップロードは不可 | FlexCache 上の S3 Access Points の記録と照らす | 未確認 |
| S3 | CRC-64NVME チェックサム | NAS バケット | S3 Access Points の側での扱いを確認する | 未確認 |
| S3 | オブジェクトを含むバケットの削除（保持期間つきの回復期間） | ONTAP S3 | 保持期間を伴う操作のため、使い捨ての環境で、期間を人が指定してから行う | 未確認 |
| S3 | S3 NAS バケットを持つ SVM の移行 | FlexVol | SVM の移行が FSx for ONTAP で使えるか | 未確認 |
| セキュリティ | ARP/AI のスナップショット応答ポリシーを SVM またはボリュームごとに設定する | 9.20.1 への更新後は、定期スナップショットの最大数が 6 から 2、保持が 12 時間から 7 時間に変わる（変更済みの場合を除く） | 設定項目と既定値を読み取る。更新で既定値が変わる点を、運用手順に反映する | 未確認 |
| セキュリティ | データ SVM で外部鍵管理を有効にすると、ボリューム暗号鍵を自動で移行する | | FSx for ONTAP の鍵管理の構成を確認する | 未確認 |
| セキュリティ | MAV の承認者に IdP、AD、LDAP のグループを指定できる | | FSx for ONTAP で MAV を使えるか | 未確認 |
| セキュリティ | SNMPv3 の SHA-512 認証 | | SNMPv3 を設定できるか | 未確認 |
| セキュリティ | 管理接続の洪水に備えた、送信元 IP ごとの公平なキューイング | 既定で無効 | 管理エンドポイントの設定を読み取る | 未確認 |
| データ保護 | SnapMirror cloud が元のボリュームにその場で復元する | FlexVol | 提供の有無 | 未確認 |
| データ保護 | SnapMirror active sync の上限を HA ペアあたり 600 ボリュームに増やす、NAS でタンパープルーフスナップショットを使える | | 提供の有無。ロックを伴う操作は、使い捨ての環境で、保持期間を人が指定してから行う | 未確認 |
| データ保護 | SVM-DR の宛先ボリュームで、一部の volume modify を管理者権限で行える。FlexGroup の構成要素で Quick Resync を使える | | SVM-DR の提供の有無 | 未確認 |
| データ保護 | 非 SnapLock のソースから SnapLock for SnapVault の宛先へ複製する | | SnapLock は削除できなくなる機能。人が保持期間を指定するまで試さない | 未確認 |
| データ保護 | FC 経由の SnapMirror 複製、Broadcom の HBA の FC-SP-3 | FC、AFF と FAS | FSx for ONTAP に FC 接続はないため、対象外の可能性が高い | 未確認 |
| ストレージ効率 | データ削減率を、削減可能なデータだけで計算する | 9.19.1 以前は削減不可のデータも含む | 同じボリュームの表示値が、版の違いで変わるかを比べる | 未確認 |
| ストレージ効率 | Automatic Dedupe Scheduler の最適化 | AFF。既定で有効 | FSx for ONTAP が対象に含まれるか | 未確認 |
| ストレージ効率 | QAT 非対応の系統から対応の系統へボリュームを移した後の読み取り遅延を下げる | QAT | 対象外の可能性がある。FSx for ONTAP のハードウェア構成を確認する | 未確認 |
| ストレージ管理 | FlexCache の上限を 1 ノードあたり 2,500、HA ペアあたり 5,000 に増やす | 1 ボリュームあたり構成要素 1 つ | FSx for ONTAP の上限の記載と照らす | 未確認 |
| ストレージ管理 | FlexCache ボリュームの指標（オリジンとの間のデータ量とメタデータ量） | 9.20 以降のキャッシュ側とオリジン側の両方 | REST の統計に項目が加わるかを読み取る | 未確認 |
| ストレージ管理 | NVFAIL を FlexCache で使える | | 同上 | 未確認 |
| ストレージ管理 | 非同期削除の性能向上、FlexGroup の回収可能容量の計算 | 詳細は NetApp 担当への問い合わせとされている | 公開情報では詳細が分からないため、実測の対象にする | 未確認 |
| ストレージ管理 | FlexGroup のストレージプロファイル（バランス型と高性能型） | | `fsxadmin` から選べるか | 未確認 |
| ストレージ管理 | FlexGroup の容量リバランスと SMB マルチチャネルの併用 | | 同上 | 未確認 |
| ストレージ管理 | File System Analytics のスキャンが atime を保持する | | FSA の動作を確認する | 未確認 |
| ストレージ管理 | クラスター内のリバランス（配置の制御と Space Performance Rebalance） | REST API | FSx for ONTAP のボリューム配置は AWS の管理範囲のため、利用者が使えるかを確認する | 未確認 |
| ストレージ管理 | MetroCluster IP の SVM 容量制限 | MetroCluster | FSx for ONTAP に MetroCluster の構成はないため、対象外の可能性が高い | 未確認 |
| SAN | SCSI-3 永続予約の登録数を LUN あたり 182 から 256 に増やす、コピーオフロードの性能向上、ASA r2 から ASA または AFF への SVM 移行 | ASA r2、ASA、AFF | 前 2 つは FSx for ONTAP の SAN で確認する。SVM 移行は対象外の可能性が高い | 未確認 |
| System Manager | 証明書とパスワードの期限切れ警告、AutoSupport の警告 | | 画面の変更なので、FSx for ONTAP では対象外の可能性がある | 未確認 |

---

## 先読み機能の記載

NetApp の会議資料に、積極的な先読み（aggressive readahead）と連番ファイルをまたぐ先読み（cross-file sequential readahead）に関するスライドがあります。4 ページを全文で読んだ範囲では、これらに当たる記載は、どの版の What's new にもありませんでした。ONTAP のドキュメントにある `-aggressive-readahead-mode`（`none` / `file_prefetch`）は FabricPool のボリューム向けで、9.13.1 と 9.14.1 に入った別の機能です。**スライドの機能と同じとは書きません。** 公式な名称と対象製品が分かった時点で、その名前で検索し直します。FSx for ONTAP で使えるかは、現時点で根拠がありません。

## 更新のしかた

- 確かめた行は、状態の欄を「確認」に変え、環境と日付を書いたノートへのリンクを置きます。
- 新しい版の What's new が出たら、全文を読み、版ごとの節を足します。
- 保持期間を伴う機能の行は、人が保持期間を指定するまで実行しません。
- 追跡用の Issue は [#424](https://github.com/Yoshiki0705/FSx-for-ONTAP-Adoption-Playbook/issues/424) です。このページが正本で、Issue の表は更新しません。

---

[🏠 リポジトリトップ](../../../README.md) | [Reference](README.md)
