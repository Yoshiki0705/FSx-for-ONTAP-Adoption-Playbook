"""SnapMirror リレーションシップ削除パターン

DP/オリジンボリュームに紐づく SnapMirror リレーションシップを削除する。宛先
ボリュームは残るが複製は止まる。ボリューム削除より前に実行して依存を断つ。

ONTAP REST: DELETE /snapmirror/relationships/{uuid}

ソース側解放
-----------
構造化 REST の /snapmirror/relationships は宛先側視点で、ソースボリュームの削除を
阻む「ソース側に残る関係」を取りこぼすことがある。svm_name が与えられたときは、
CLI passthrough の list-destinations（source-vserver 指定）でソース側の宛先を
列挙し、各関係をソース側解放（POST /private/cli/snapmirror/release）する。これに
よりソースボリュームが削除可能になる。宛先のデータは消さない。
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
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
        # svm_name があればソース側に残る関係も解放対象に加える（構造化 REST の宛先
        # 側視点では見えない、ソースボリュームを阻む関係）。
        if self.svm_name:
            targets.extend(self._resolve_source_side())
        self._targets = targets
        return self._targets

    def _resolve_source_side(self) -> list[dict[str, Any]]:
        """ソース側から見た宛先を列挙し、ソース側解放の target に変換する

        CLI passthrough: GET /private/cli/snapmirror/list-destinations
            ?source-vserver=<svm_name>

        Returns:
            list[dict]: kind="snapmirror-source-release" の target。
                source-path / destination-path を保持する。
        """
        dests = self.client.list_snapmirror_destinations_by_source(
            source_vserver=self.svm_name
        )
        source_targets: list[dict[str, Any]] = []
        for d in dests:
            source_path = d.get("source-path")
            if not source_path:
                continue
            source_targets.append(
                {
                    "kind": "snapmirror-source-release",
                    "source": source_path,
                    "destination": d.get("destination-path"),
                    "relationship_id": d.get("relationship-id"),
                }
            )
        return source_targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            if target.get("kind") == "snapmirror-source-release":
                results.append(self._release_source(target))
                continue
            try:
                response = self.client.delete_snapmirror(target["uuid"])
            except OntapClientError as err:
                if self._is_already_absent_error(err):
                    # 既に無いリレーションシップは冪等に成功扱いとし、残りを続行する。
                    results.append({**target, "result": "absent"})
                    continue
                raise
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def _release_source(self, target: dict[str, Any]) -> dict[str, Any]:
        """ソース側の関係を解放する（冪等）。宛先データは消さない。"""
        try:
            response = self.client.release_snapmirror_source(
                source_path=target.get("source")
            )
        except OntapClientError as err:
            if self._is_already_absent_error(err):
                return {**target, "result": "absent"}
            raise
        final = self._poll_if_job(response)
        return {**target, "result": final}

    def confirm_gone(self) -> bool:
        """全 target の不在を読み戻しで確認する

        構造化リレーションシップ（kind=snapmirror）は
        GET /snapmirror/relationships/{uuid} が 404 か。ソース側解放
        （kind=snapmirror-source-release）は list-destinations を source-vserver で
        再取得し、その source-path がもう現れないこと。target があるのに確認を
        スキップして True を返す vacuous-true は避ける。
        """
        structured = [t for t in self._targets if t.get("kind") == "snapmirror"]
        source_rel = [
            t for t in self._targets if t.get("kind") == "snapmirror-source-release"
        ]
        for t in structured:
            if not self._is_absent(f"/snapmirror/relationships/{t['uuid']}"):
                return False
        if source_rel:
            remaining = {
                d.get("source-path")
                for d in self.client.list_snapmirror_destinations_by_source(
                    source_vserver=self.svm_name
                )
            }
            for t in source_rel:
                if t.get("source") in remaining:
                    return False
        return True

    def _matches_svm(self, record: dict[str, Any]) -> bool:
        source_svm = record.get("source", {}).get("svm", {}).get("name")
        dest_svm = record.get("destination", {}).get("svm", {}).get("name")
        return self.svm_name in (source_svm, dest_svm)
