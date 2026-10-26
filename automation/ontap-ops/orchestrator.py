"""削除オーケストレーター

1 つのファイルシステム上で、依存順に削除パターンを実行する。DESIGN.md の順序:

    snapmirror_release, flexclone_split_delete, s3bucket_delete, audit_redirect,
    fpolicy_teardown, flexcache_delete -> volume_delete (非 root) -> svm_delete

dry-run（既定）は読み取り専用の GET から「何を消すか」の順序付き計画を返す。
confirm=True のときだけ各パターンの delete() を実行し、202 はジョブ完了まで待ち、
各削除後に confirm_gone() で読み戻して消えたことを確認する。
"""

from __future__ import annotations

import logging
from typing import Any

from .patterns.audit_redirect import AuditRedirect
from .patterns.flexcache_delete import FlexCacheDelete
from .patterns.flexclone_split_delete import FlexCloneSplitDelete
from .patterns.fpolicy_teardown import FPolicyTeardown
from .patterns.s3bucket_delete import S3BucketDelete
from .patterns.snapmirror_release import SnapMirrorRelease
from .patterns.svm_delete import SvmDelete
from .patterns.volume_delete import VolumeDelete
from .shared.ontap_client import OntapClient

logger = logging.getLogger(__name__)


def _discover_svm_scopes(
    client: OntapClient,
    svm_uuid: str | None,
) -> list[dict[str, str | None]]:
    """per-SVM パターンを回す SVM scope の一覧を返す

    明示の svm_uuid があればそれ 1 つに絞る（従来の単一 SVM 動作）。無ければ
    ファイルシステム上の全 SVM を GET /svm/svms で発見し、1 件ずつ回す。

    Returns:
        list[dict]: {"uuid": ..., "name": ...}。name は追跡用（取れないこともある）。
    """
    if svm_uuid:
        return [{"uuid": svm_uuid, "name": None}]
    return [
        {"uuid": r.get("uuid"), "name": r.get("name")}
        for r in client.list_svms()
        if r.get("uuid")
    ]


def build_pattern_order(
    client: OntapClient,
    svm_uuid: str | None = None,
    svm_name: str | None = None,
    parent_volume_name: str | None = None,
    split_clones: bool = False,
) -> list:
    """DESIGN.md の依存順でパターンのインスタンス列を組み立てる

    依存を断つ順（SnapMirror -> クローン -> S3 -> 監査 -> FPolicy -> FlexCache）の
    あとに、非 root ボリューム削除、最後に SVM 削除。

    svm_uuid が与えられた場合は従来どおり単一 SVM を対象にする。与えられない場合は
    GET /svm/svms で全 SVM を発見し、per-SVM scope のパターン（監査 / FPolicy /
    SVM 削除）を SVM ごとに 1 インスタンスずつ展開する。cluster-wide の
    パターン（SnapMirror / FlexClone / FlexCache / ボリューム）は 1 回のまま。
    依存順は維持する。

    S3 バケットは、明示の svm_uuid が無いときは cluster-wide の 1 パスで発見する
    （list_all_s3_buckets）。per-SVM の列挙は、FLEXGROUP ボリュームを背後に持つ
    バケットのように、ボリューム削除をブロックしている実体を取りこぼすことがあるため、
    任意の SVM 上のバケットを確実に拾う。明示の svm_uuid があるときは従来どおり
    その SVM の per-SVM 列挙に絞る。各 target は自分の svm.uuid を保持し、削除は
    その svm.uuid へ送られる。
    """
    scopes = _discover_svm_scopes(client, svm_uuid)

    ordered: list = []
    # 1) SnapMirror: cluster-wide。svm_name が明示されていれば絞り込む。
    ordered.append(SnapMirrorRelease(client, svm_uuid=svm_uuid, svm_name=svm_name))
    # 2) FlexClone: parent 指定時はその親、無ければ FS 全体から発見する（1 回）。
    ordered.append(
        FlexCloneSplitDelete(
            client,
            svm_uuid=svm_uuid,
            parent_volume_name=parent_volume_name,
            split=split_clones,
        )
    )
    # 3) S3 バケット: 明示 svm_uuid があればその per-SVM、無ければ cluster-wide の
    #    1 パス。cluster-wide は全 SVM のバケットを 1 回で発見し、各 target が自分の
    #    svm.uuid を持つので、任意の SVM のバケットを正しいパスで削除できる。
    if svm_uuid:
        ordered.append(S3BucketDelete(client, svm_uuid=svm_uuid))
    else:
        ordered.append(S3BucketDelete(client, cluster_wide=True))
    # 4-5) per-SVM: 監査 -> FPolicy を SVM ごとに回す（真に per-SVM の設定）。
    for scope in scopes:
        ordered.append(AuditRedirect(client, svm_uuid=scope["uuid"]))
    for scope in scopes:
        ordered.append(FPolicyTeardown(client, svm_uuid=scope["uuid"]))
    # 6-7) cluster-wide: FlexCache -> 非 root ボリューム（svm_uuid=None なら全件）。
    ordered.append(FlexCacheDelete(client, svm_uuid=svm_uuid))
    ordered.append(VolumeDelete(client, svm_uuid=svm_uuid))
    # 8) per-SVM: SVM 削除を SVM ごとに回す（依存順の最後）。
    for scope in scopes:
        ordered.append(SvmDelete(client, svm_uuid=scope["uuid"]))
    return ordered


def _svm_name_map(client: OntapClient, svm_uuid: str | None) -> dict[str, str | None]:
    """svm uuid -> name の対応を作る（トレーサビリティの注記用）

    明示の svm_uuid があり名前が不要な場合でも空 dict でよい。無指定時は
    発見した全 SVM の名前を引けるようにする。
    """
    if svm_uuid:
        return {}
    return {r["uuid"]: r.get("name") for r in client.list_svms() if r.get("uuid")}


def _annotate_targets(
    pattern,
    targets: list[dict[str, Any]],
    name_map: dict[str, str | None],
) -> list[dict[str, Any]]:
    """各 target に svm_uuid / svm_name を補って追跡可能にする

    per-SVM パターンのインスタンスは self.svm_uuid を持つので、target が svm_uuid を
    持たない場合はパターンの scope で補う。svm_name は発見済みの map から引く。
    cluster-wide パターン（svm_uuid=None）の target は変更しない。
    """
    pattern_scope = getattr(pattern, "svm_uuid", None)
    annotated: list[dict[str, Any]] = []
    for target in targets:
        uuid = target.get("svm_uuid") or pattern_scope
        if uuid:
            target = {**target, "svm_uuid": uuid}
            if "svm_name" not in target and uuid in name_map:
                target["svm_name"] = name_map[uuid]
        annotated.append(target)
    return annotated


def plan(
    client: OntapClient,
    svm_uuid: str | None = None,
    svm_name: str | None = None,
    parent_volume_name: str | None = None,
    split_clones: bool = False,
) -> list[dict[str, Any]]:
    """読み取り専用の計画を返す（dry-run）。1 件も削除しない。

    Returns:
        list[dict]: パターンごとの {pattern, targets} を依存順に並べたもの。
            targets は全 SVM にわたって集約され、各 target に svm uuid/name を含む。
    """
    ordered = build_pattern_order(
        client,
        svm_uuid=svm_uuid,
        svm_name=svm_name,
        parent_volume_name=parent_volume_name,
        split_clones=split_clones,
    )
    name_map = _svm_name_map(client, svm_uuid)
    result: list[dict[str, Any]] = []
    for pattern in ordered:
        targets = _annotate_targets(pattern, pattern.resolve_dependencies(), name_map)
        result.append({"pattern": pattern.name, "targets": targets})
    return result


def execute(
    client: OntapClient,
    svm_uuid: str | None = None,
    svm_name: str | None = None,
    parent_volume_name: str | None = None,
    split_clones: bool = False,
) -> list[dict[str, Any]]:
    """依存順に削除を実行する（confirm=True 時のみ呼ばれる想定）

    各パターンで resolve -> delete -> confirm_gone を行う。confirm_gone が False の
    場合は confirmed=False を記録して次に進む（呼び出し側が検知できるようにする）。

    Returns:
        list[dict]: パターンごとの {pattern, targets, results, confirmed}。
    """
    ordered = build_pattern_order(
        client,
        svm_uuid=svm_uuid,
        svm_name=svm_name,
        parent_volume_name=parent_volume_name,
        split_clones=split_clones,
    )
    name_map = _svm_name_map(client, svm_uuid)
    outcome: list[dict[str, Any]] = []
    for pattern in ordered:
        targets = _annotate_targets(pattern, pattern.resolve_dependencies(), name_map)
        if not targets:
            outcome.append(
                {
                    "pattern": pattern.name,
                    "targets": [],
                    "results": [],
                    "confirmed": True,
                }
            )
            continue
        results = pattern.delete()
        confirmed = pattern.confirm_gone()
        outcome.append(
            {
                "pattern": pattern.name,
                "targets": targets,
                "results": results,
                "confirmed": confirmed,
            }
        )
    return outcome
