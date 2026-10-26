"""オブジェクトストア (S3) バケット削除パターン

SVM 上のオブジェクトストアバケットを削除する。ONTAP のリリースにより削除
エンドポイントが 2 系統あるため、GET で存在する側を判定してから DELETE する
（client.resolve_s3_bucket_endpoint が担う）。

- DELETE /protocols/s3/buckets/{svm.uuid}/{uuid}
- DELETE /protocols/s3/services/{svm.uuid}/buckets/{uuid}
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
from .base import DeletePattern

logger = logging.getLogger(__name__)


class S3BucketDelete(DeletePattern):
    """SVM 上のオブジェクトストアバケットを削除する"""

    name = "s3bucket_delete"

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        if not self.svm_uuid:
            self._targets = []
            return self._targets
        records = self.client.list_s3_buckets(self.svm_uuid)
        self._targets = [
            {
                "uuid": r["uuid"],
                "name": r.get("name"),
                "kind": "s3-bucket",
                "svm_uuid": self.svm_uuid,
            }
            for r in records
            if r.get("uuid")
        ]
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            response = self.client.delete_s3_bucket(self.svm_uuid, target["uuid"])
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def confirm_gone(self) -> bool:
        # 削除後は両エンドポイントとも 404 になる。resolve は両方 404 のとき例外を
        # 投げる（＝どちらにも存在しない）ので、それを「消えた」と解釈する。
        for target in self._targets:
            try:
                path = self.client.resolve_s3_bucket_endpoint(
                    self.svm_uuid, target["uuid"]
                )
            except OntapClientError as err:
                if err.status_code == 404:
                    continue
                raise
            if not self._is_absent(path):
                return False
        return True
