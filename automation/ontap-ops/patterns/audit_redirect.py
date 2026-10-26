"""監査宛先の解放パターン

SVM の監査 (audit) 設定は宛先ボリュームを掴んでいるため、そのボリュームを消す前に
監査を無効化してから設定を削除する。NAS 監査とオブジェクトストア監査の両系統を扱う。

- NAS 監査:  PATCH /protocols/audit/{svm.uuid} (enabled=false) -> DELETE /protocols/audit/{svm.uuid}
- object-store 監査: DELETE /protocols/audit/{svm.uuid}/object-store
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
from .base import DeletePattern

logger = logging.getLogger(__name__)


class AuditRedirect(DeletePattern):
    """SVM の監査宛先を無効化・削除して宛先ボリュームを解放する"""

    name = "audit_redirect"

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        if not self.svm_uuid:
            self._targets = []
            return self._targets

        targets: list[dict[str, Any]] = []
        try:
            config = self.client.get_audit_config(self.svm_uuid)
        except OntapClientError as err:
            if err.status_code == 404:
                config = {}
            else:
                raise
        if config:
            targets.append(
                {
                    "kind": "nas-audit",
                    "svm_uuid": self.svm_uuid,
                    "enabled": config.get("enabled"),
                }
            )
        # object-store 監査は GET /object-store が無い系統もあるため、存在確認は
        # 削除時に 404 を許容する形で扱う。計画には常に 1 件載せる。
        targets.append({"kind": "object-store-audit", "svm_uuid": self.svm_uuid})

        self._targets = targets
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results: list[dict[str, Any]] = []
        for target in self._targets:
            if target["kind"] == "nas-audit":
                results.append(self._delete_nas_audit(target))
            else:
                results.append(self._delete_object_store_audit(target))
        return results

    def _delete_nas_audit(self, target: dict[str, Any]) -> dict[str, Any]:
        # 宛先を解放する前に監査を止める。
        self.client.disable_audit(self.svm_uuid)
        response = self.client.delete_audit(self.svm_uuid)
        final = self._poll_if_job(response)
        return {**target, "result": final}

    def _delete_object_store_audit(self, target: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self.client.delete_object_store_audit(self.svm_uuid)
        except OntapClientError as err:
            if err.status_code == 404:
                return {**target, "result": "absent"}
            raise
        final = self._poll_if_job(response)
        return {**target, "result": final}

    def confirm_gone(self) -> bool:
        return self._is_absent(f"/protocols/audit/{self.svm_uuid}")
