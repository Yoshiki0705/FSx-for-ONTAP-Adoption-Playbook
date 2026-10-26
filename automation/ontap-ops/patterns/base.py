"""削除パターンの抽象基底クラス

各パターンは 3 段で動く。

1. resolve_dependencies(): 読み取り専用 GET で、消すべきオブジェクトを特定する。
   dry-run はここまでだけを実行し、消す対象の一覧（計画）を返す。
2. delete(): 実際に削除する。202 (非同期ジョブ) が返れば wait_ontap_job で完了を待つ。
3. confirm_gone(): GET が 404/空を返すこと（＝本当に消えたこと）を確認する。
   成功レスポンスは成功の証拠にならないため、読み戻しで判定する。
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

from ..shared.ontap_client import OntapClient, OntapClientError

logger = logging.getLogger(__name__)


class DeletePattern(ABC):
    """1 種類の ONTAP オブジェクト削除の共通契約

    Attributes:
        name: パターン名（計画やログで使う短い識別子）
        client: ONTAP REST クライアント
        svm_uuid: 対象 SVM UUID（パターンにより未使用）
    """

    name: str = "delete-pattern"

    def __init__(self, client: OntapClient, svm_uuid: str | None = None):
        self.client = client
        self.svm_uuid = svm_uuid
        self._targets: list[dict[str, Any]] = []

    @abstractmethod
    def resolve_dependencies(self) -> list[dict[str, Any]]:
        """読み取り専用 GET で削除対象を特定し、計画として返す

        Returns:
            list[dict]: 削除対象の記述（最低限 uuid と name を含む）。
                self._targets にも保持し、delete() から参照する。
        """

    @abstractmethod
    def delete(self) -> list[dict[str, Any]]:
        """resolve 済みの対象を削除する。202 はジョブ完了まで待つ

        Returns:
            list[dict]: 各対象の削除結果。
        """

    @abstractmethod
    def confirm_gone(self) -> bool:
        """削除対象が GET で 404/空になったことを確認する

        Returns:
            bool: すべて消えていれば True。
        """

    # --- 共通ヘルパー ---

    def _poll_if_job(self, response: dict[str, Any]) -> dict[str, Any]:
        """ONTAP の削除応答がジョブ (202) を含む場合、完了まで待つ

        ONTAP は非同期操作を {"job": {"uuid": ...}} 形式で返す。その uuid を
        wait_ontap_job でポーリングする。同期完了（ジョブ無し）ならそのまま返す。
        """
        job = response.get("job") if isinstance(response, dict) else None
        if isinstance(job, dict) and job.get("uuid"):
            # 非同期ジョブが「対象は既に無い」で失敗するのは、冪等な撤去では成功と
            # 同じ。delete が 202 を返したあとジョブ側で "doesn't exist" が出る経路は
            # 同期 try/except の外側なので、ここで吸収する。それ以外の失敗は送出する。
            try:
                return self.client.wait_ontap_job(job["uuid"])
            except OntapClientError as err:
                if self._is_already_absent_error(err):
                    return {"result": "absent", "job": job["uuid"]}
                raise
        return response

    def _is_absent(self, path: str) -> bool:
        """GET が 404 を返す（＝オブジェクトが無い）かを確認する

        Returns:
            bool: 404 なら True。レコードが返れば False。
        """
        try:
            result = self.client.get(path)
        except OntapClientError as err:
            if self._is_already_absent_error(err):
                return True
            raise
        # 一覧系エンドポイントは 200 + records:[] で「無い」を表すことがある。
        if isinstance(result, dict) and "records" in result:
            return not result.get("records")
        return False

    @staticmethod
    def _is_already_absent_error(err: OntapClientError) -> bool:
        """削除/取得の失敗が「対象が既に無い」を意味するかを判定する

        冪等な撤去では「存在しない」は成功と同じに扱う。ONTAP は不在を HTTP 404
        だけでなく、200/400/500 + メッセージ（"doesn't exist" / "does not exist" /
        "not found" / "no such" / "no entries" / "already deleted/removed"）でも返す
        ため、両方を拾う。非不在（"already has clones" 等）を成功扱いしないよう、
        不在を確実に表す語だけに限定している。
        """
        if err.status_code == 404:
            return True
        # ontap_message は error.message を取り出すが、ONTAP が別の形（本文直下や
        # 別キー）で返すと str(self) の汎用文（"ONTAP API error: ... returned 400"）に
        # 退化し、不在の語を取りこぼす。生の response_body も併せて走査する。
        # さらに ONTAP は "doesn't" に ASCII ではなく Unicode の右シングルクォート
        # (U+2019) を用いるため、アポストロフィを正規化してから照合する。
        haystack = " ".join(
            part.lower() for part in (err.ontap_message, err.response_body) if part
        )
        haystack = haystack.replace("\u2019", "'")
        # 不在だけを拾う。以前は裸の "already" / "does not have" も入れていたが、
        # "already has clones" / "already in use" / 権限の "... does not have ..."
        # のような非不在メッセージまで成功扱いにしてしまうため外した。不在を確実に
        # 表す語（existence/found/entries/no such）に限定する。
        return any(
            phrase in haystack
            for phrase in (
                "doesn't exist",
                "does not exist",
                "no longer exists",
                "not found",
                "no such",
                "no entries",
                "already deleted",
                "already removed",
            )
        )
