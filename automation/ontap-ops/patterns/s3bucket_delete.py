"""オブジェクトストア (S3) バケット削除パターン

SVM 上のオブジェクトストアバケットを削除する。ONTAP のリリースにより削除
エンドポイントが 2 系統あるため、GET で存在する側を判定してから DELETE する
（client.resolve_s3_bucket_endpoint が担う）。

- DELETE /protocols/s3/buckets/{svm.uuid}/{uuid}
- DELETE /protocols/s3/services/{svm.uuid}/buckets/{uuid}

発見には 2 つの経路がある。

- per-SVM: client.list_s3_buckets(svm_uuid) で 1 つの SVM のバケットを列挙する
  （svm_uuid が与えられたとき）。
- cluster-wide: client.list_all_s3_buckets() で全 SVM のバケットを 1 回で列挙する
  （cluster_wide=True のとき）。FLEXGROUP ボリュームを背後に持つバケットのように、
  ボリューム削除をブロックしているバケットが呼び出し側の想定した SVM の列挙に
  現れないことがあるため、任意の SVM 上のバケットを確実に発見する。

いずれの経路でも、各 target は自分の svm.uuid を保持する。DELETE / confirm は
その svm.uuid を使う（self.svm_uuid ではない）ので、cluster-wide で見つけた
別 SVM のバケットも正しいパスへ削除要求が届く。
"""

from __future__ import annotations

import logging
from typing import Any

from ..shared.ontap_client import OntapClientError
from .base import DeletePattern

logger = logging.getLogger(__name__)

# バケット DELETE がこれらを返したら、AD 到達不能による FS 層の AccessDenied の
# 可能性がある（AD 参加 SVM で DC に届かないとき、要求が正しくても 403 になりうる）。
# これは最初のログイン 401（fsxadmin 認証失敗、ハンドラが即中断する）とは別物なので、
# パターン内で捕捉して記録し、他の target を続行する。ログインは既に成功している
# ため、これを再試行しても fsxadmin ロックにはつながらない。
_ACCESS_DENIED_STATUS = {401, 403}


class S3BucketDelete(DeletePattern):
    """SVM 上のオブジェクトストアバケットを削除する

    Attributes:
        cluster_wide: True のとき list_all_s3_buckets で全 SVM を 1 回で列挙する。
            False（既定）のときは svm_uuid の per-SVM 列挙（従来動作）。
    """

    name = "s3bucket_delete"

    def __init__(
        self,
        client,
        svm_uuid: str | None = None,
        cluster_wide: bool = False,
    ):
        super().__init__(client, svm_uuid=svm_uuid)
        self.cluster_wide = cluster_wide

    def resolve_dependencies(self) -> list[dict[str, Any]]:
        if self.cluster_wide:
            records = self.client.list_all_s3_buckets()
        elif self.svm_uuid:
            records = self.client.list_s3_buckets(self.svm_uuid)
        else:
            self._targets = []
            return self._targets

        targets: list[dict[str, Any]] = []
        seen: set[str] = set()
        for r in records:
            uuid = r.get("uuid")
            if not uuid or uuid in seen:
                # per-SVM と cluster-wide の両パスが走っても同じバケットを 2 度
                # 消さないよう uuid で重複排除する。
                continue
            seen.add(uuid)
            # 各 target は自分の svm.uuid を持つ。cluster-wide のレコードは
            # svm.uuid を含む。per-SVM のレコードが svm を欠く場合はこの scope の
            # svm_uuid で補う。どちらの DELETE もこの値を使う。
            bucket_svm = (r.get("svm") or {}).get("uuid") or self.svm_uuid
            volume_name = (r.get("volume") or {}).get("name")
            targets.append(
                {
                    "uuid": uuid,
                    "name": r.get("name"),
                    "kind": "s3-bucket",
                    "svm_uuid": bucket_svm,
                    "svm_name": (r.get("svm") or {}).get("name"),
                    "volume_name": volume_name,
                }
            )
        self._targets = targets
        return self._targets

    def delete(self) -> list[dict[str, Any]]:
        results = []
        for target in self._targets:
            bucket_svm = target["svm_uuid"]
            try:
                response = self.client.delete_s3_bucket(bucket_svm, target["uuid"])
            except OntapClientError as err:
                if err.status_code in _ACCESS_DENIED_STATUS:
                    # per-object の 403/401 は、ハンドラのグローバル認証中断とは別。
                    # ここで捕捉して記録し、他の target を続行する（全体を止めない）。
                    logger.warning(
                        "S3 bucket %s on SVM %s returned HTTP %s on delete; "
                        "recording as access_denied_possibly_ad_unreachable and "
                        "continuing with the remaining targets",
                        target["uuid"],
                        bucket_svm,
                        err.status_code,
                    )
                    results.append(
                        {
                            **target,
                            "result": "access_denied_possibly_ad_unreachable",
                            "svm": bucket_svm,
                            "status_code": err.status_code,
                        }
                    )
                    continue
                if self._is_already_absent_error(err):
                    # 既に無いバケットは冪等に成功扱いとし、残りを続行する。
                    results.append({**target, "result": "absent"})
                    continue
                raise
            final = self._poll_if_job(response)
            results.append({**target, "result": final})
        return results

    def confirm_gone(self) -> bool:
        # 削除後は両エンドポイントとも 404 になる。resolve は両方 404 のとき例外を
        # 投げる（＝どちらにも存在しない）ので、それを「消えた」と解釈する。
        # 各 target は自分の svm.uuid で確認する（self.svm_uuid ではない）。
        # AD 到達不能で削除できなかった target（403/401）は読み戻しも拒否されうるので、
        # confirm の対象から外す（delete の結果にその事実が記録されている）。
        for target in self._targets:
            bucket_svm = target["svm_uuid"]
            try:
                path = self.client.resolve_s3_bucket_endpoint(
                    bucket_svm, target["uuid"]
                )
            except OntapClientError as err:
                if err.status_code == 404:
                    continue
                if err.status_code in _ACCESS_DENIED_STATUS:
                    # 到達不能で確認不能。全体の確認を失敗にはしない。
                    continue
                raise
            if not self._is_absent(path):
                return False
        return True
