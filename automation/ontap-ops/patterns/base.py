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
            return self.client.wait_ontap_job(job["uuid"])
        return response

    def _is_absent(self, path: str) -> bool:
        """GET が 404 を返す（＝オブジェクトが無い）かを確認する

        Returns:
            bool: 404 なら True。レコードが返れば False。
        """
        try:
            result = self.client.get(path)
        except OntapClientError as err:
            if err.status_code == 404:
                return True
            raise
        # 一覧系エンドポイントは 200 + records:[] で「無い」を表すことがある。
        if isinstance(result, dict) and "records" in result:
            return not result.get("records")
        return False
