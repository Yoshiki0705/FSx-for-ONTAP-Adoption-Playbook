"""Lambda エントリーポイント

イベントで file_system_id を必須とし、安全ゲート（allowlist / keep-list / dry-run）を
通してから、オーケストレーターで削除計画の提示（dry-run）または実行（confirm=true）を
行う。ONTAP 認証失敗時は即座に中断する（再試行は fsxadmin ロックの危険があるため）。

Event 例:
    {
      "file_system_id": "fs-0123456789abcdef0",   # 必須
      "svm_uuid": "....",                          # 任意（絞り込み）
      "svm_name": "....",                          # 任意（SnapMirror 絞り込み）
      "parent_volume_name": "...",                 # 任意（FlexClone の親）
      "split_clones": false,                       # 任意（クローンを split するか）
      "secret_id": "...",                          # 任意（env ONTAP_SECRET_ID を上書き）
      "confirm": false                             # true のときだけ削除を実行
    }

環境変数:
    ONTAP_OPS_ALLOWLIST  削除を許可するファイルシステム ID（カンマ/空白区切り）
    ONTAP_OPS_KEEP_LIST  保護するファイルシステム ID（多重防御）
    ONTAP_SECRET_ID      ONTAP fsxadmin 認証情報シークレット（イベントで上書き可）
    ONTAP_VERIFY_SSL     "false" のときのみ TLS 検証を無効化（既定: 有効）
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
from .shared.safety import SafetyViolation, assert_in_scope, is_dry_run

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


def handler(event: dict[str, Any] | None, context: Any = None) -> dict[str, Any]:
    """Lambda ハンドラ本体"""
    event = event or {}

    file_system_id = event.get("file_system_id")
    if not file_system_id:
        return {"status": "error", "error": "file_system_id is required"}

    # 1) 安全ゲート: allowlist / keep-list。どの変更呼び出しよりも前に通す。
    try:
        assert_in_scope(file_system_id)
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

    kwargs = {
        "svm_uuid": event.get("svm_uuid"),
        "svm_name": event.get("svm_name"),
        "parent_volume_name": event.get("parent_volume_name"),
        "split_clones": bool(event.get("split_clones", False)),
    }

    dry_run = is_dry_run(event)

    # 3) dry-run は計画のみ。confirm:true のときだけ実行。
    try:
        if dry_run:
            steps = orchestrator.plan(client, **kwargs)
            return {
                "status": "dry_run",
                "file_system_id": file_system_id,
                "plan": steps,
            }
        steps = orchestrator.execute(client, **kwargs)
        return {
            "status": "executed",
            "file_system_id": file_system_id,
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
