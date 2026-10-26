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
    """
    return [
        SnapMirrorRelease(client, svm_uuid=svm_uuid, svm_name=svm_name),
        FlexCloneSplitDelete(
            client,
            svm_uuid=svm_uuid,
            parent_volume_name=parent_volume_name,
            split=split_clones,
        ),
        S3BucketDelete(client, svm_uuid=svm_uuid),
        AuditRedirect(client, svm_uuid=svm_uuid),
        FPolicyTeardown(client, svm_uuid=svm_uuid),
        FlexCacheDelete(client, svm_uuid=svm_uuid),
        VolumeDelete(client, svm_uuid=svm_uuid),
        SvmDelete(client, svm_uuid=svm_uuid),
    ]


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
    """
    ordered = build_pattern_order(
        client,
        svm_uuid=svm_uuid,
        svm_name=svm_name,
        parent_volume_name=parent_volume_name,
        split_clones=split_clones,
    )
    result: list[dict[str, Any]] = []
    for pattern in ordered:
        targets = pattern.resolve_dependencies()
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
    outcome: list[dict[str, Any]] = []
    for pattern in ordered:
        targets = pattern.resolve_dependencies()
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
