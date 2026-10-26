"""ボリューム削除パターン

上流の依存（FlexCache / FlexClone / S3 バケット / 監査宛先 / FPolicy / SnapMirror）が
すべて解消された後に、非 root ボリュームを削除する。

ONTAP REST: DELETE /storage/volumes/{uuid}
"""

from __future__ import annotations

import logging
from typing import Any

from .base import DeletePattern

logger = logging.getLogger(__name__)

# SVM の root ボリュームは SVM 削除で消えるため、ここでは除外する。
_ROOT_VOLUME_STYLES = {"flexgroup_root"}


class VolumeDelete(DeletePattern):
    """SVM 上の非 root ボリュームを削除する"""

    name = "volume_delete"

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        records = self.client.list_volumes(svm_uuid=self.svm_uuid)
        targets: list[dict[str, Any]] = []
        for r in records:
            if not r.get("uuid"):
                continue
            if self._is_root(r):
                continue
            targets.append(
                {
                    "uuid": r["uuid"],
                    "name": r.get("name"),
                    "kind": "volume",
                }
            )
        self._targets = targets
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            response = self.client.delete_volume(target["uuid"])
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def confirm_gone(self) -> bool:
        return all(
            self._is_absent(f"/storage/volumes/{t['uuid']}") for t in self._targets
        )

    @staticmethod
    def _is_root(record: dict[str, Any]) -> bool:
        # root ボリュームは名前が _root 終わり、または style が root 系。
        name = record.get("name") or ""
        if name.endswith("_root"):
            return True
        return record.get("style") in _ROOT_VOLUME_STYLES
