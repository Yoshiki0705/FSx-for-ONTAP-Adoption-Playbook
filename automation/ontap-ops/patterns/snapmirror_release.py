"""SnapMirror リレーションシップ削除パターン

DP/オリジンボリュームに紐づく SnapMirror リレーションシップを削除する。宛先
ボリュームは残るが複製は止まる。ボリューム削除より前に実行して依存を断つ。

ONTAP REST: DELETE /snapmirror/relationships/{uuid}
"""

from __future__ import annotations

import logging
from typing import Any

from .base import DeletePattern

logger = logging.getLogger(__name__)


class SnapMirrorRelease(DeletePattern):
    """対象ボリュームに関わる SnapMirror リレーションシップを削除する"""

    name = "snapmirror_release"

    def __init__(
        self,
        client,
        svm_uuid: str | None = None,
        svm_name: str | None = None,
    ):
        super().__init__(client, svm_uuid=svm_uuid)
        self.svm_name = svm_name

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        records = self.client.list_snapmirror_relationships()
        targets: list[dict[str, Any]] = []
        for r in records:
            if not r.get("uuid"):
                continue
            # svm_name が与えられていれば、source/destination のどちらかが一致する
            # ものだけに絞る。無ければ全件（単一ファイルシステムのクリーンアップ）。
            if self.svm_name and not self._matches_svm(r):
                continue
            targets.append(
                {
                    "uuid": r["uuid"],
                    "kind": "snapmirror",
                    "source": r.get("source", {}).get("path"),
                    "destination": r.get("destination", {}).get("path"),
                }
            )
        self._targets = targets
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            response = self.client.delete_snapmirror(target["uuid"])
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def confirm_gone(self) -> bool:
        return all(
            self._is_absent(f"/snapmirror/relationships/{t['uuid']}")
            for t in self._targets
        )

    def _matches_svm(self, record: dict[str, Any]) -> bool:
        source_svm = record.get("source", {}).get("svm", {}).get("name")
        dest_svm = record.get("destination", {}).get("svm", {}).get("name")
        return self.svm_name in (source_svm, dest_svm)
