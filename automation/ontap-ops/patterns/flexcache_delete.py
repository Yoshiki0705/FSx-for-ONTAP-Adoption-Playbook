"""FlexCache 削除パターン

キャッシュ側の FlexCache ボリュームを削除する。オリジンボリュームは残る（依存なし）。

ONTAP REST: DELETE /storage/flexcache/flexcaches/{uuid}
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
from .base import DeletePattern

logger = logging.getLogger(__name__)


class FlexCacheDelete(DeletePattern):
    """SVM 上の FlexCache ボリュームを削除する"""

    name = "flexcache_delete"

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        records = self.client.list_flexcaches(
            svm_name=self._svm_name() if self.svm_uuid else None
        )
        self._targets = [
            {"uuid": r["uuid"], "name": r.get("name"), "kind": "flexcache"}
            for r in records
            if r.get("uuid")
        ]
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            self._unmount(target["uuid"])
            try:
                response = self.client.delete_flexcache(target["uuid"])
            except OntapClientError as err:
                if self._is_already_absent_error(err):
                    # 既に無い FlexCache は冪等に成功扱いとし、残りを続行する。
                    results.append({**target, "result": "absent"})
                    continue
                raise
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def _unmount(self, uuid: str) -> None:
        """削除前にジャンクションを外す（マウント済み FlexCache は削除不可）。
        既に外れている/無い場合は黙って続行。"""
        try:
            self._poll_if_job(self.client.unmount_volume(uuid))
        except OntapClientError as err:
            if not self._is_already_absent_error(err):
                raise

    def confirm_gone(self) -> bool:
        return all(
            self._is_absent(f"/storage/flexcache/flexcaches/{t['uuid']}")
            for t in self._targets
        )

    def _svm_name(self) -> str | None:
        """svm_uuid から SVM 名を解決する（list_flexcaches が名前フィルタのため）"""
        svm = self.client.get_svm(self.svm_uuid)
        return svm.get("name")
