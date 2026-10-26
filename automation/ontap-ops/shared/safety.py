"""安全ゲート — allowlist / keep-list / dry-run

どの ONTAP・AWS 変更呼び出しよりも前に通す門。allowlist に無い、または keep-list に
含まれる file_system_id は、1 件の変更も行う前に拒否する。dry_run は既定で True。

allowlist は実運用のデータであり、コードに焼き込まない。デプロイ時に環境変数で渡す。
"""

from __future__ import annotations

import os

ALLOWLIST_ENV = "ONTAP_OPS_ALLOWLIST"
KEEP_LIST_ENV = "ONTAP_OPS_KEEP_LIST"
MAINTENANCE_ENV = "ONTAP_OPS_MAINTENANCE_FSIDS"


class SafetyViolation(Exception):
    """安全ゲートが入力を拒否した"""


def get_maintenance_list(env: dict[str, str] | None = None) -> list[str]:
    """env ONTAP_OPS_MAINTENANCE_FSIDS から保守許可リストを読む

    保守操作（read-only 診断、SnapMirror 関係の release/delete、vserver peer 削除、
    recovery-queue purge）は、ファイルシステム・SVM・ボリュームそのものを削除しない。
    keep-list の FS でも、宙ぶらりんの関係レコードだけを外す必要がある場合がある
    （例: 残す FS が、消す FS との SVM peer / SnapMirror 関係を保持している）。
    その FS をこのリストに入れると、保守操作だけを許可する。teardown（plan/execute、
    volume/svm/fs 削除）は従来どおり allowlist のみで、このリストでは一切許可しない。
    """
    env = env if env is not None else dict(os.environ)
    return _parse_id_list(env.get(MAINTENANCE_ENV))


def assert_maintenance_allowed(
    file_system_id: str, env: dict[str, str] | None = None
) -> None:
    """保守操作（非 teardown）が許可されているか検証する

    allowlist に入っているか、maintenance リストに入っていれば許可。どちらにも無ければ
    SafetyViolation。teardown は決して許可しない（呼び出し側が plan/execute に進むときは
    別途 assert_in_scope を通すこと）。
    """
    if not file_system_id:
        raise SafetyViolation("file_system_id is required")
    allowed = set(get_allowlist(env)) | set(get_maintenance_list(env))
    if file_system_id not in allowed:
        raise SafetyViolation(
            f"{file_system_id} is not permitted for maintenance; add it to "
            f"{MAINTENANCE_ENV} (surgical, non-teardown) or {ALLOWLIST_ENV}."
        )


def _parse_id_list(raw: str | None) -> list[str]:
    """カンマ/空白区切りの ID リストを正規化する"""
    if not raw:
        return []
    return [token for token in raw.replace(",", " ").split() if token]


def get_allowlist(env: dict[str, str] | None = None) -> list[str]:
    """env ONTAP_OPS_ALLOWLIST から許可リストを読む"""
    env = env if env is not None else dict(os.environ)
    return _parse_id_list(env.get(ALLOWLIST_ENV))


def get_keep_list(env: dict[str, str] | None = None) -> list[str]:
    """env ONTAP_OPS_KEEP_LIST から保護リストを読む"""
    env = env if env is not None else dict(os.environ)
    return _parse_id_list(env.get(KEEP_LIST_ENV))


def assert_in_scope(file_system_id: str, env: dict[str, str] | None = None) -> None:
    """file_system_id が削除対象として許可されているか検証する

    どの変更呼び出しよりも前に呼ぶこと。次のいずれかに該当すれば SafetyViolation。

    - allowlist が空（＝明示的な許可が無い）
    - file_system_id が allowlist に無い
    - file_system_id が keep-list に含まれる（多重防御。allowlist にあっても拒否）

    Raises:
        SafetyViolation: 対象外または保護対象の場合
    """
    if not file_system_id:
        raise SafetyViolation("file_system_id is required")

    allowlist = get_allowlist(env)
    keep_list = get_keep_list(env)

    if not allowlist:
        raise SafetyViolation(
            f"{ALLOWLIST_ENV} is empty; refusing every file system until it names "
            "the one(s) permitted for deletion."
        )
    if file_system_id in keep_list:
        raise SafetyViolation(
            f"{file_system_id} is in {KEEP_LIST_ENV}; refused as defense in depth "
            "even though it may appear in the allowlist."
        )
    if file_system_id not in allowlist:
        raise SafetyViolation(
            f"{file_system_id} is not in {ALLOWLIST_ENV}; refusing before any "
            "ONTAP or AWS mutating call."
        )


def is_dry_run(event: dict | None) -> bool:
    """dry_run の判定。既定は True。confirm:true のときだけ False。

    削除が起きるのは `confirm: true` が明示されたときだけ。`dry_run` を明示的に
    False にしても、`confirm` が真でなければ dry-run のまま。
    """
    event = event or {}
    confirm = bool(event.get("confirm", False))
    # confirm が真のときだけ実行。それ以外はすべて dry-run。
    return not confirm
