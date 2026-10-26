"""Lambda エントリーポイント

イベントで file_system_id を必須とし、安全ゲート（allowlist / keep-list / dry-run /
maintenance）を通してから、2 つの処理のどちらかを行う。

1. teardown（既定）: オーケストレーターで削除計画の提示（dry-run）または実行
   （confirm=true）を行う。allowlist のみで許可し、keep-list の FS は決して teardown
   しない（assert_in_scope）。
2. maintenance（event["operation"] 指定時）: ソース側 SnapMirror 解放・vserver peer
   削除・recovery-queue purge といった外科的な単発操作、または読み取り専用の
   maintenance_plan プレビュー。allowlist か maintenance リストのどちらかにあれば
   許可する（assert_maintenance_allowed）。FS/SVM/volume そのものは消さない。

ONTAP 認証失敗時は即座に中断する（再試行は fsxadmin ロックの危険があるため）。

Event 例（teardown）:
    {
      "file_system_id": "fs-0123456789abcdef0",   # 必須
      "svm_uuid": "....",                          # 任意（絞り込み）
      "svm_name": "....",                          # 任意（SnapMirror 絞り込み）
      "parent_volume_name": "...",                 # 任意（FlexClone の親）
      "split_clones": false,                       # 任意（クローンを split するか）
      "secret_id": "...",                          # 任意（env ONTAP_SECRET_ID を上書き）
      "confirm": false                             # true のときだけ削除を実行
    }

Event 例（maintenance）: 下の MAINTENANCE_OPERATIONS を参照。
    { "file_system_id": "...", "operation": "purge_recovery_queue",
      "svm_name": "svm1", "volume": "vol_clone" }

環境変数:
    ONTAP_OPS_ALLOWLIST          teardown を許可するファイルシステム ID
    ONTAP_OPS_KEEP_LIST          保護するファイルシステム ID（多重防御）
    ONTAP_OPS_MAINTENANCE_FSIDS  maintenance 操作を許可するファイルシステム ID
    ONTAP_SECRET_ID              ONTAP fsxadmin 認証情報シークレット（イベントで上書き可）
    ONTAP_VERIFY_SSL             "false" のときのみ TLS 検証を無効化（既定: 有効）
"""

from __future__ import annotations

import logging
import os
from typing import Any

from . import orchestrator
from .shared.fsx_helpers import (
    SecretVerificationError,
    get_management_ip,
    resolve_and_verify_secret,
)
from .shared.ontap_client import OntapClient, OntapClientConfig, OntapClientError
from .shared.safety import (
    SafetyViolation,
    assert_in_scope,
    assert_maintenance_allowed,
    is_dry_run,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ONTAP の認証失敗を表す HTTP ステータス。即中断の対象。
_AUTH_FAILURE_STATUS = {401, 403}


def _build_client(file_system_id: str, secret_id: str) -> OntapClient:
    """検証済みシークレットと探索した管理 IP から ONTAP クライアントを組む"""
    verified_secret = resolve_and_verify_secret(secret_id, file_system_id)
    management_ip = get_management_ip(file_system_id)
    verify_ssl = os.environ.get("ONTAP_VERIFY_SSL", "true").lower() != "false"
    config = OntapClientConfig(
        management_ip=management_ip,
        secret_name=verified_secret,
        verify_ssl=verify_ssl,
    )
    return OntapClient(config)


# --- maintenance 操作の surface ---
#
# teardown（plan/execute）とは別の、外科的な単発操作。live teardown で debug 用に
# 散らばっていた event["diagnose"]/event["action"] の分岐は、この最小の documented な
# 集合に集約した。各操作は FS/SVM/volume そのものは消さず、関係レコードや recovery
# queue といった「teardown を阻む実体」だけを外す。すべて assert_maintenance_allowed
# ゲートの後ろで動く。
#
# | operation                | 必須フィールド                    | 何をするか |
# |--------------------------|-----------------------------------|-----------|
# | maintenance_plan         | (任意) parent_volume_name,        | 読み取り専用。teardown を阻みがちな
# |                          |        svm_name                   | 実体（recovery queue / ソース側
# |                          |                                   | SnapMirror / vserver peer / CLI の
# |                          |                                   | 不可視クローン）を 1 回で可視化する。 |
# | purge_recovery_queue     | svm_name, volume                  | recovery queue の DEL ボリュームを
# |                          |                                   | purge し、親の "has clones" を解消。 |
# | snapmirror_release_source| source_path                       | ソース側に残る SnapMirror 関係を
# |                          |                                   | 解放（ソースボリュームを削除可能に）。|
# | snapmirror_delete        | destination_path                  | destination-path 指定で関係を削除
# |                          |                                   | （relationship-id は不可）。 |
# | delete_vserver_peer      | svm_name, peer_vserver            | 生き残った vserver peer を外し、
# |                          |                                   | MISCONFIGURED な SVM を解放する。 |


def _maintenance_plan(client: OntapClient, event: dict[str, Any]) -> dict[str, Any]:
    """読み取り専用 maintenance プレビュー（唯一の diagnostic surface）

    teardown を阻みがちな実体を 1 回で可視化する。削除は一切しない。debug 用の
    生ダンプを多数並べる代わりに、これ 1 本に集約している。
    """
    parent = event.get("parent_volume_name")
    svm_name = event.get("svm_name")
    preview: dict[str, Any] = {
        "recovery_queue": client.list_recovery_queue(),
        "vserver_peers": client.list_vserver_peers(),
    }
    if parent:
        preview["cli_clones_of_parent"] = client.list_volume_clones_cli(parent)
    if svm_name:
        preview["snapmirror_source_destinations"] = (
            client.list_snapmirror_destinations_by_source(source_vserver=svm_name)
        )
    return preview


def _dispatch_maintenance(
    client: OntapClient, operation: str, event: dict[str, Any]
) -> dict[str, Any]:
    """maintenance 操作 1 件を実行し、結果 dict を返す

    未知の operation は ValueError。各操作は冪等寄り（既に無ければ ONTAP 側が
    "doesn't exist" 等を返す）で、呼び出し側が結果を見て判断できる形で返す。
    """
    if operation == "maintenance_plan":
        return _maintenance_plan(client, event)

    if operation == "purge_recovery_queue":
        result = client.purge_recovery_queue(
            vserver=event["svm_name"], volume=event["volume"]
        )
        return {"result": result}

    if operation == "snapmirror_release_source":
        result = client.release_snapmirror_source(
            source_path=event["source_path"],
            destination_path=event.get("destination_path"),
            relationship_id=event.get("relationship_id"),
        )
        return {"result": result}

    if operation == "snapmirror_delete":
        result = client.delete_snapmirror_by_destination(event["destination_path"])
        return {"result": result}

    if operation == "delete_vserver_peer":
        result = client.delete_vserver_peer(
            vserver=event["svm_name"], peer_vserver=event["peer_vserver"]
        )
        return {"result": result}

    raise ValueError(f"unknown maintenance operation: {operation}")


def handler(event: dict[str, Any] | None, context: Any = None) -> dict[str, Any]:
    """Lambda ハンドラ本体"""
    event = event or {}

    file_system_id = event.get("file_system_id")
    if not file_system_id:
        return {"status": "error", "error": "file_system_id is required"}

    operation = event.get("operation")
    is_teardown = operation is None

    # 1) 安全ゲート。
    #    - teardown（plan/execute: dry_run か confirm の本処理）は allowlist のみ
    #      （assert_in_scope）。keep-list の FS は決して teardown しない。
    #    - maintenance 操作（recovery-queue purge、SnapMirror release/delete、
    #      vserver peer 削除）と read-only の maintenance_plan は、FS/SVM/volume を
    #      消さないので allowlist か maintenance リストのどちらかで許可
    #      （assert_maintenance_allowed）。
    try:
        if is_teardown:
            assert_in_scope(file_system_id)
        else:
            assert_maintenance_allowed(file_system_id)
    except SafetyViolation as err:
        logger.warning("Safety gate refused %s: %s", file_system_id, err)
        return {
            "status": "refused",
            "file_system_id": file_system_id,
            "reason": str(err),
        }

    secret_id = event.get("secret_id") or os.environ.get("ONTAP_SECRET_ID")
    if not secret_id:
        return {
            "status": "error",
            "error": "secret_id must be supplied via event or ONTAP_SECRET_ID",
        }

    # 2) シークレット検証 + クライアント構築。
    try:
        client = _build_client(file_system_id, secret_id)
    except SecretVerificationError as err:
        logger.warning("Secret verification failed: %s", err)
        return {
            "status": "refused",
            "file_system_id": file_system_id,
            "reason": str(err),
        }
    except ValueError as err:
        return {"status": "error", "file_system_id": file_system_id, "error": str(err)}

    try:
        if not is_teardown:
            # 3a) maintenance 操作を 1 件実行する。
            try:
                payload = _dispatch_maintenance(client, operation, event)
            except KeyError as err:
                return {
                    "status": "error",
                    "file_system_id": file_system_id,
                    "error": f"missing required field for {operation}: {err}",
                }
            except ValueError as err:
                return {
                    "status": "error",
                    "file_system_id": file_system_id,
                    "error": str(err),
                }
            return {
                "status": "maintenance",
                "file_system_id": file_system_id,
                "operation": operation,
                **payload,
            }

        # 3b) teardown。dry-run は計画のみ。confirm:true のときだけ実行。
        kwargs = {
            "svm_uuid": event.get("svm_uuid"),
            "svm_name": event.get("svm_name"),
            "parent_volume_name": event.get("parent_volume_name"),
            "split_clones": bool(event.get("split_clones", False)),
        }
        if is_dry_run(event):
            steps = orchestrator.plan(client, **kwargs)
            return {
                "status": "dry_run",
                "file_system_id": file_system_id,
                "plan": steps,
            }
        steps = orchestrator.execute(client, **kwargs)
        # status="executed" は「実行した」であって「全部消えた」ではない。各パターンの
        # confirmed と result を集約し、1 つでも未確認・エラーがあれば all_confirmed を
        # False にして呼び出し側が成功と誤読しないようにする。
        all_confirmed = all(s.get("confirmed") for s in steps)
        had_errors = any(
            r.get("result") == "error" for s in steps for r in s.get("results", [])
        )
        return {
            "status": "executed",
            "file_system_id": file_system_id,
            "all_confirmed": all_confirmed and not had_errors,
            "steps": steps,
        }
    except OntapClientError as err:
        # 認証失敗は即中断。再試行しない（fsxadmin ロックの危険）。
        if err.status_code in _AUTH_FAILURE_STATUS:
            logger.error(
                "ONTAP authentication failed (HTTP %s); aborting without retry "
                "to avoid fsxadmin lockout: %s",
                err.status_code,
                err.ontap_message,
            )
            return {
                "status": "auth_failure",
                "file_system_id": file_system_id,
                "error": err.ontap_message,
                "note": "aborted immediately; not retried (fsxadmin lock hazard)",
            }
        logger.error("ONTAP operation failed: %s", err.ontap_message)
        return {
            "status": "error",
            "file_system_id": file_system_id,
            "error": err.ontap_message,
        }
