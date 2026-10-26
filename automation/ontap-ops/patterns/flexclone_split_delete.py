"""FlexClone split/削除パターン

FlexClone は clone.parent_* が設定されたボリューム。親との依存を断ってから消す。
二通りある。

- split してからクローンボリュームを削除する（親を残したい場合）
- クローンボリュームを直接削除する（split 不要。親は影響を受けない）

既定は直接削除（split=False）。split=True のとき split を先に実行して完了を待つ。
いずれも DELETE /storage/volumes/{uuid} でボリュームとして削除する。
"""

from __future__ import annotations

import logging
from typing import Any

from .base import DeletePattern

logger = logging.getLogger(__name__)


class FlexCloneSplitDelete(DeletePattern):
    """親ボリュームの FlexClone を split（任意）して削除する"""

    name = "flexclone_split_delete"

    def __init__(
        self,
        client,
        svm_uuid: str | None = None,
        parent_volume_name: str | None = None,
        split: bool = False,
    ):
        super().__init__(client, svm_uuid=svm_uuid)
        self.parent_volume_name = parent_volume_name
        self.split = split

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        if not self.parent_volume_name:
            self._targets = []
            return self._targets
        records = self.client.list_clones_of(self.parent_volume_name)
        self._targets = [
            {
                "uuid": r["uuid"],
                "name": r.get("name"),
                "kind": "flexclone",
                "split": self.split,
            }
            for r in records
            if r.get("uuid")
        ]
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            if self.split:
                split_response = self.client.split_clone(target["uuid"])
                self._poll_if_job(split_response)
            delete_response = self.client.delete_volume(target["uuid"])
            final = self._poll_if_job(delete_response)
            results.append({**target, "result": final})
        return results

    def confirm_gone(self) -> bool:
        return all(
            self._is_absent(f"/storage/volumes/{t['uuid']}") for t in self._targets
        )
