"""SVM 削除パターン

非 root ボリュームがすべて削除済みであることを前提に、SVM を削除する。

ONTAP REST: DELETE /svm/svms/{uuid}
"""

from __future__ import annotations

import logging
from typing import Any

from .base import DeletePattern

logger = logging.getLogger(__name__)


class SvmDelete(DeletePattern):
    """対象 SVM を削除する（非 root ボリュームが残っていれば対象から外す）"""

    name = "svm_delete"

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        if not self.svm_uuid:
            self._targets = []
            return self._targets

        # 非 root ボリュームが残っていると SVM 削除は失敗する。残存を計画に記録する。
        remaining = [
            r
            for r in self.client.list_volumes(svm_uuid=self.svm_uuid)
            if not (r.get("name") or "").endswith("_root")
        ]
        svm = self.client.get_svm(self.svm_uuid)
        self._targets = [
            {
                "uuid": self.svm_uuid,
                "name": svm.get("name"),
                "kind": "svm",
                "remaining_non_root_volumes": [r.get("name") for r in remaining],
            }
        ]
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            response = self.client.delete_svm(target["uuid"])
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def confirm_gone(self) -> bool:
        return all(self._is_absent(f"/svm/svms/{t['uuid']}") for t in self._targets)
