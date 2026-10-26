"""FlexClone split/削除パターン

FlexClone は clone.parent_* が設定されたボリューム。親との依存を断ってから消す。
二通りある。

- split してからクローンボリュームを削除する（親を残したい場合）
- クローンボリュームを直接削除する（split 不要。親は影響を受けない）

既定は直接削除（split=False）。split=True のとき split を先に実行して完了を待つ。
いずれも DELETE /storage/volumes/{uuid} でボリュームとして削除する。

recovery-queue フォールバック
-----------------------------
親が has_flexclone を報告するのに、構造化 REST（GET /storage/volumes?clone.*）で
クローンボリュームが 1 件も引けないことがある。削除保留中（volume type DEL）の
stale clone が recovery queue に残っているとこの状態になり、親の削除が
"has one or more clones" で失敗する。このとき `volume clone show`
（GET /private/cli/volume/clone?parent-volume=<name>）で CLI 側のクローン名を引き、
recovery queue から名前指定で purge して依存を外す。parent_volume_name が
与えられたときにだけ実行する（どの親を見るかが一意に決まるため）。
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
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
        if self.parent_volume_name:
            # 親ボリューム名が与えられた場合は、その親のクローンだけに絞る。
            records = self.client.list_clones_of(self.parent_volume_name)
        else:
            # 親が指定されない場合は FS 全体のボリュームからクローンを発見する。
            # clone.is_flexclone == true のものだけを残す。
            records = [
                r
                for r in self.client.list_clones()
                if (r.get("clone") or {}).get("is_flexclone")
            ]
        targets: list[dict[str, Any]] = [
            {
                "uuid": r["uuid"],
                "name": r.get("name"),
                "kind": "flexclone",
                "split": self.split,
                "svm_uuid": (r.get("svm") or {}).get("uuid"),
                "svm_name": (r.get("svm") or {}).get("name"),
                "parent_volume_name": (r.get("clone") or {})
                .get("parent_volume", {})
                .get("name"),
            }
            for r in records
            if r.get("uuid")
        ]
        # recovery-queue フォールバック: 構造化 REST でクローンが引けないのに親が
        # has_flexclone を報告するケース。親名が与えられているときにだけ、CLI の
        # `volume clone show` で見える stale clone を purge 対象として計画に加える。
        if self.parent_volume_name and not targets:
            targets.extend(self._resolve_recovery_queue_clones())
        self._targets = targets
        return self._targets

    def _resolve_recovery_queue_clones(self) -> list[dict[str, Any]]:
        """`volume clone show` で見える stale clone を recovery-queue purge 対象にする

        構造化 REST に出ないクローンを CLI passthrough で引き、各クローン名を
        recovery queue から purge するための target（kind="recovery-queue-clone"）に
        変換する。1 件も見つからなければ空リスト。
        """
        cli_clones = self.client.list_volume_clones_cli(self.parent_volume_name)
        recovery: list[dict[str, Any]] = []
        for c in cli_clones:
            volume = c.get("volume") or c.get("clone-volume")
            vserver = c.get("vserver")
            if not volume or not vserver:
                continue
            recovery.append(
                {
                    "kind": "recovery-queue-clone",
                    "name": volume,
                    "vserver": vserver,
                    "parent_volume_name": self.parent_volume_name,
                }
            )
        return recovery

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            if target.get("kind") == "recovery-queue-clone":
                results.append(self._purge_recovery_clone(target))
                continue
            try:
                if self.split:
                    split_response = self.client.split_clone(target["uuid"])
                    self._poll_if_job(split_response)
                delete_response = self.client.delete_volume(target["uuid"])
            except OntapClientError as err:
                if self._is_already_absent_error(err):
                    # split / delete のどちらで「既に無い」が返っても冪等に成功扱いとし、
                    # 残りを続行する。
                    results.append({**target, "result": "absent"})
                    continue
                raise
            final = self._poll_if_job(delete_response)
            results.append({**target, "result": final})
        return results

    def _purge_recovery_clone(self, target: dict[str, Any]) -> dict[str, Any]:
        """recovery queue の stale clone を名前指定で purge する（冪等）"""
        try:
            response = self.client.purge_recovery_queue(
                target["vserver"], target["name"]
            )
        except OntapClientError as err:
            if self._is_already_absent_error(err):
                return {**target, "result": "absent"}
            raise
        final = self._poll_if_job(response)
        return {**target, "result": final}

    def confirm_gone(self) -> bool:
        return all(
            self._is_absent(f"/storage/volumes/{t['uuid']}")
            for t in self._targets
            if t.get("kind") != "recovery-queue-clone"
        )
