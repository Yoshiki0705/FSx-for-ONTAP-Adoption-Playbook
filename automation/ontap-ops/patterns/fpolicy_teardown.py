"""FPolicy 撤去パターン

SVM 上の FPolicy を撤去する。順序は lakehouse の configure_fpolicy.py の
delete_fpolicy_config() で実証済みのもの。

    ポリシーを無効化 -> ポリシー削除 -> イベント削除 -> エンジン削除

この順序は依存関係に沿う。ポリシーはイベントとエンジンを参照するため先に消し、
有効なまま削除できないので先に無効化する。
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
from .base import DeletePattern

logger = logging.getLogger(__name__)


class FPolicyTeardown(DeletePattern):
    """SVM 上の全 FPolicy ポリシー/イベント/エンジンを撤去する"""

    name = "fpolicy_teardown"

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        if not self.svm_uuid:
            self._targets = []
            return self._targets

        policies = self._list("policies")
        events = self._list("events")
        engines = self._list("engines")

        targets: list[dict[str, Any]] = []
        targets += [{"kind": "fpolicy-policy", "name": r.get("name")} for r in policies]
        targets += [{"kind": "fpolicy-event", "name": r.get("name")} for r in events]
        targets += [{"kind": "fpolicy-engine", "name": r.get("name")} for r in engines]
        self._targets = targets
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        # configure_fpolicy.py と同じ順序: ポリシー(無効化->削除) -> イベント -> エンジン。
        results: list[dict[str, Any]] = []
        for target in self._by_kind("fpolicy-policy"):
            name = target["name"]
            try:
                self.client.patch(
                    f"/protocols/fpolicy/{self.svm_uuid}/policies/{name}",
                    body={"enabled": False},
                )
            except OntapClientError:
                # 既に無効の場合がある。無視して削除へ進む。
                pass
            response = self.client.delete(
                f"/protocols/fpolicy/{self.svm_uuid}/policies/{name}"
            )
            results.append({**target, "result": self._poll_if_job(response)})

        for target in self._by_kind("fpolicy-event"):
            response = self.client.delete(
                f"/protocols/fpolicy/{self.svm_uuid}/events/{target['name']}"
            )
            results.append({**target, "result": self._poll_if_job(response)})

        for target in self._by_kind("fpolicy-engine"):
            response = self.client.delete(
                f"/protocols/fpolicy/{self.svm_uuid}/engines/{target['name']}"
            )
            results.append({**target, "result": self._poll_if_job(response)})

        return results

    def confirm_gone(self) -> bool:
        for kind, endpoint in (
            ("fpolicy-policy", "policies"),
            ("fpolicy-event", "events"),
            ("fpolicy-engine", "engines"),
        ):
            for target in self._by_kind(kind):
                path = f"/protocols/fpolicy/{self.svm_uuid}/{endpoint}/{target['name']}"
                if not self._is_absent(path):
                    return False
        return True

    def _list(self, kind: str) -> list[dict[str, Any]]:
        try:
            result = self.client.get(f"/protocols/fpolicy/{self.svm_uuid}/{kind}")
        except OntapClientError as err:
            if err.status_code == 404:
                return []
            raise
        return result.get("records", [])

    def _by_kind(self, kind: str) -> list[dict[str, Any]]:
        return [t for t in self._targets if t["kind"] == kind and t.get("name")]
