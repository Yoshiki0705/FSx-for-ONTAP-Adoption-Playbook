"""ONTAP REST API クライアント

FSx for NetApp ONTAP の REST API を呼び出す共通 Python クライアント。
Secrets Manager 認証、urllib3 PoolManager、TLS 検証、リトライ機能を備える。

既存リポジトリ FSx-for-ONTAP-Agentic-Access-Aware-RAG の検証済みパターンを
Python で再実装したもの。

SOURCE
------
This file is ported from the Serverless Spoke
(`fsxn-s3ap-serverless-patterns/shared/ontap_client.py`). The generic request layer,
Secrets Manager auth, production TLS default, `is_unsafe_path` path-traversal guard,
`delete_flexcache`, `delete_snapmirror`, the SnapMirror state controls and
`wait_ontap_job` come from there verbatim. The deletion shortcuts this module adds
(`delete_volume`, `delete_svm`, S3 bucket delete with endpoint detection, audit
destination removal, and clone resolution) are the only additions, grouped under
"ONTAP-ops deletion shortcuts" at the end.

Key patterns preserved:
- Secrets Manager authentication
- urllib3 PoolManager with TLS verification (default enabled)
- urllib3.Timeout(connect=10.0, read=30.0)
- urllib3.Retry(total=3, backoff_factor=0.5)
- OntapClientError exception class (status_code, response_body attributes)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import boto3
import urllib3

logger = logging.getLogger(__name__)

# Caller-supplied names reach request paths: a share name, a volume name, a
# relationship UUID. A value carrying a `..` segment redirects the request to a
# different endpoint, so a "delete this share" call can arrive at a cluster
# resource instead. Callers are expected to percent-encode each segment, but the
# check belongs here as well rather than in every call site — the portal handler
# learned this the same way and put it in the one function all its requests go
# through.
_UNSAFE_PATH_CHARS = re.compile(r"[\x00-\x1f\x7f\\]")


def is_unsafe_path(path: str) -> bool:
    """True if an assembled request path must not be sent.

    A `..` inside a name is fine ("my..share"); a whole segment of `..` is not.
    The query string is excluded from the traversal check because a value there
    cannot change which endpoint is addressed.
    """
    if _UNSAFE_PATH_CHARS.search(path):
        return True
    route = path.split("?", 1)[0]
    return any(segment == ".." for segment in route.split("/"))


class OntapClientError(Exception):
    """ONTAP REST API エラー"""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_body: str | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body

    @property
    def ontap_message(self) -> str:
        """The message ONTAP returned, or this exception's own message.

        ONTAP reports failures as {"error": {"message": ..., "code": ...}}. Callers
        that surface errors to a person want that text, not the HTTP status line.
        """
        if self.response_body:
            try:
                parsed = json.loads(self.response_body)
            except (json.JSONDecodeError, TypeError):
                parsed = None
            if isinstance(parsed, dict):
                message = parsed.get("error", {})
                if isinstance(message, dict) and message.get("message"):
                    return str(message["message"])
        return str(self)


class OntapClientConfig:
    """OntapClient 設定データクラス

    Attributes:
        management_ip: ONTAP クラスタ管理 IP アドレス
        secret_name: Secrets Manager のシークレット名
        verify_ssl: TLS 検証の有効/無効 (デフォルト: True)
        ca_cert_path: CA 証明書ファイルパス (オプション)
        connect_timeout: 接続タイムアウト秒数 (デフォルト: 10.0)
        read_timeout: 読み取りタイムアウト秒数 (デフォルト: 30.0)
        retry_total: リトライ回数 (デフォルト: 3)
        backoff_factor: リトライバックオフ係数 (デフォルト: 0.5)
    """

    def __init__(
        self,
        management_ip: str,
        secret_name: str,
        verify_ssl: bool = True,
        ca_cert_path: str | None = None,
        connect_timeout: float = 10.0,
        read_timeout: float = 30.0,
        retry_total: int = 3,
        backoff_factor: float = 0.5,
    ):
        self.management_ip = management_ip
        self.secret_name = secret_name
        self.verify_ssl = verify_ssl
        self.ca_cert_path = ca_cert_path
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.retry_total = retry_total
        self.backoff_factor = backoff_factor

    def to_dict(self) -> dict:
        """設定を辞書に変換"""
        return {
            "management_ip": self.management_ip,
            "secret_name": self.secret_name,
            "verify_ssl": self.verify_ssl,
            "ca_cert_path": self.ca_cert_path,
            "connect_timeout": self.connect_timeout,
            "read_timeout": self.read_timeout,
            "retry_total": self.retry_total,
            "backoff_factor": self.backoff_factor,
        }

    @classmethod
    def from_dict(cls, data: dict) -> OntapClientConfig:
        """辞書から設定を復元"""
        return cls(**data)


class OntapClient:
    """ONTAP REST API クライアント

    Secrets Manager から認証情報を取得し、urllib3 PoolManager を使用して
    ONTAP REST API を呼び出す。TLS 検証、タイムアウト、リトライを設定可能。

    Usage:
        config = OntapClientConfig(
            management_ip="10.0.0.1",
            secret_name="fsxn/ontap-credentials",
        )
        client = OntapClient(config)
        volumes = client.list_volumes()
    """

    BASE_API_PATH = "/api"

    def __init__(
        self,
        config: OntapClientConfig,
        session: boto3.Session | None = None,
    ):
        self._config = config
        self._session = session or boto3.Session()
        self._pool: urllib3.PoolManager | None = None
        self._credentials: dict | None = None

    def _get_credentials(self) -> dict:
        """Secrets Manager から認証情報を取得

        Returns:
            dict: {"username": str, "password": str}

        Raises:
            OntapClientError: Secrets Manager からの取得に失敗した場合
        """
        if self._credentials is not None:
            return self._credentials

        try:
            sm_client = self._session.client("secretsmanager")
            response = sm_client.get_secret_value(
                SecretId=self._config.secret_name,
            )
            self._credentials = json.loads(response["SecretString"])
            return self._credentials
        except Exception as e:
            raise OntapClientError(
                f"Failed to retrieve credentials from Secrets Manager (secret: {self._config.secret_name}): {e}"
            ) from e

    def _get_pool(self) -> urllib3.PoolManager:
        """urllib3 PoolManager を初期化（TLS 検証、タイムアウト、リトライ設定）

        Returns:
            urllib3.PoolManager: 設定済みの PoolManager

        Notes:
            - verify_ssl=True (デフォルト): TLS 検証有効
            - verify_ssl=False: TLS 検証無効（lab/PoC 用途のみ、警告ログ出力）
            - ca_cert_path: カスタム CA 証明書パス
        """
        if self._pool is not None:
            return self._pool

        timeout = urllib3.Timeout(
            connect=self._config.connect_timeout,
            read=self._config.read_timeout,
        )
        retry = urllib3.Retry(
            total=self._config.retry_total,
            backoff_factor=self._config.backoff_factor,
        )

        if self._config.verify_ssl:
            if self._config.ca_cert_path:
                self._pool = urllib3.PoolManager(
                    timeout=timeout,
                    retries=retry,
                    cert_reqs="CERT_REQUIRED",
                    ca_certs=self._config.ca_cert_path,
                )
            else:
                self._pool = urllib3.PoolManager(
                    timeout=timeout,
                    retries=retry,
                    cert_reqs="CERT_REQUIRED",
                )
        else:
            logger.warning(
                "TLS verification is disabled. "
                "This should only be used for lab/PoC environments. "
                "Set verify_ssl=True for production use."
            )
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            self._pool = urllib3.PoolManager(
                timeout=timeout,
                retries=retry,
                cert_reqs="CERT_NONE",
            )

        return self._pool

    def _make_headers(self) -> dict:
        """認証ヘッダーを生成"""
        creds = self._get_credentials()
        return urllib3.make_headers(
            basic_auth=f"{creds['username']}:{creds['password']}",
        )

    def _request(
        self,
        method: str,
        path: str,
        params: dict | None = None,
        body: dict | None = None,
    ) -> dict:
        """ONTAP REST API リクエストを実行

        Args:
            method: HTTP メソッド (GET, POST, PATCH, DELETE)
            path: API パス (例: /storage/volumes)
            params: クエリパラメータ
            body: リクエストボディ (JSON)

        Returns:
            dict: レスポンスボディ (JSON パース済み)

        Raises:
            OntapClientError: 非 2xx レスポンスの場合、または path が不正な場合
        """
        if is_unsafe_path(path):
            logger.warning("Refused ONTAP request with unsafe path: %r", path[:200])
            raise OntapClientError(
                "Invalid characters in request path",
                status_code=400,
            )

        pool = self._get_pool()
        headers = self._make_headers()
        headers["Content-Type"] = "application/json"
        headers["Accept"] = "application/json"

        url = f"https://{self._config.management_ip}{self.BASE_API_PATH}{path}"

        kwargs: dict[str, Any] = {
            "method": method,
            "url": url,
            "headers": headers,
        }

        if params:
            # urllib3 uses 'fields' for query parameters on GET
            if method == "GET":
                kwargs["fields"] = params
            else:
                # For non-GET with params, append to URL
                query_string = "&".join(f"{k}={v}" for k, v in params.items())
                kwargs["url"] = f"{url}?{query_string}"

        if body is not None:
            kwargs["body"] = json.dumps(body).encode("utf-8")

        try:
            response = pool.request(**kwargs)
        except urllib3.exceptions.MaxRetryError as e:
            raise OntapClientError(
                f"Max retries exceeded for {method} {path}: {e}"
            ) from e
        except urllib3.exceptions.TimeoutError as e:
            raise OntapClientError(f"Request timeout for {method} {path}: {e}") from e
        except Exception as e:
            raise OntapClientError(f"Request failed for {method} {path}: {e}") from e

        response_body = response.data.decode("utf-8")

        if response.status < 200 or response.status >= 300:
            raise OntapClientError(
                f"ONTAP API error: {method} {path} returned {response.status}",
                status_code=response.status,
                response_body=response_body,
            )

        if not response_body:
            return {}

        try:
            return json.loads(response_body)
        except json.JSONDecodeError:
            return {"raw": response_body}

    # --- 汎用 REST メソッド ---

    def get(self, path: str, params: dict | None = None) -> dict:
        """GET リクエスト"""
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict | None = None) -> dict:
        """POST リクエスト"""
        return self._request("POST", path, body=body)

    def patch(self, path: str, body: dict | None = None) -> dict:
        """PATCH リクエスト"""
        return self._request("PATCH", path, body=body)

    def delete(self, path: str) -> dict:
        """DELETE リクエスト"""
        return self._request("DELETE", path)

    # --- ショートカットメソッド ---

    def list_volumes(self, svm_uuid: str | None = None) -> list[dict]:
        """ボリューム一覧取得

        Args:
            svm_uuid: SVM UUID でフィルタ (オプション)

        Returns:
            list[dict]: ボリューム情報のリスト
        """
        params = {"fields": "name,uuid,size,type,svm,nas,style"}
        if svm_uuid:
            params["svm.uuid"] = svm_uuid
        result = self.get("/storage/volumes", params=params)
        return result.get("records", [])

    def get_volume(self, volume_uuid: str) -> dict:
        """ボリューム詳細取得

        Args:
            volume_uuid: ボリューム UUID

        Returns:
            dict: ボリューム詳細情報
        """
        return self.get(
            f"/storage/volumes/{volume_uuid}",
            params={"fields": "name,uuid,size,type,svm,nas,style,snapshot_policy"},
        )

    def list_cifs_shares(self, svm_uuid: str) -> list[dict]:
        """CIFS 共有一覧取得

        Args:
            svm_uuid: SVM UUID

        Returns:
            list[dict]: CIFS 共有情報のリスト
        """
        result = self.get(
            "/protocols/cifs/shares",
            params={
                "svm.uuid": svm_uuid,
                "fields": "svm,name,path,volume,acls",
            },
        )
        return result.get("records", [])

    def list_nfs_exports(self, svm_uuid: str) -> list[dict]:
        """NFS エクスポートポリシー一覧取得

        Args:
            svm_uuid: SVM UUID

        Returns:
            list[dict]: NFS エクスポートポリシー情報のリスト
        """
        result = self.get(
            "/protocols/nfs/export-policies",
            params={
                "svm.uuid": svm_uuid,
                "fields": "name,rules",
            },
        )
        return result.get("records", [])

    def get_svm(self, svm_uuid: str) -> dict:
        """SVM 詳細取得

        Args:
            svm_uuid: SVM UUID

        Returns:
            dict: SVM 詳細情報
        """
        return self.get(
            f"/svm/svms/{svm_uuid}",
            params={"fields": "name,uuid,ip_interfaces,cifs,nfs,s3"},
        )

    def list_svms(self) -> list[dict]:
        """ファイルシステム上の SVM 一覧取得

        ONTAP REST: GET /svm/svms (fields=name,uuid)

        オーケストレーターが明示の svm_uuid なしで呼ばれたとき、per-SVM scope の
        パターンを全 SVM に対して回すために使う。display extra（state 等）は
        この ONTAP バージョンが fields で拒否するため name,uuid のみに絞る。

        Returns:
            list[dict]: SVM の生レコード（name, uuid）
        """
        result = self.get("/svm/svms", params={"fields": "name,uuid"})
        return result.get("records", [])

    def get_file_security(
        self,
        svm_uuid: str,
        volume_uuid: str,
        path: str,
    ) -> dict:
        """ファイルセキュリティ（ACL）情報取得

        Args:
            svm_uuid: SVM UUID
            volume_uuid: ボリューム UUID
            path: ファイルパス

        Returns:
            dict: ファイルセキュリティ情報（ACL 含む）
        """
        return self.get(
            f"/protocols/file-security/permissions/{svm_uuid}/{volume_uuid}/{path}",
        )

    # --- FlexCache 操作メソッド ---

    def list_flexcaches(
        self,
        name: str | None = None,
        svm_name: str | None = None,
    ) -> list[dict]:
        """FlexCache ボリューム一覧取得

        Args:
            name: FlexCache 名でフィルタ (オプション)
            svm_name: SVM 名でフィルタ (オプション)

        Returns:
            list[dict]: FlexCache ボリューム情報のリスト
        """
        params: dict[str, str] = {
            "fields": "name,uuid,svm,size,path,origins",
        }
        if name:
            params["name"] = name
        if svm_name:
            params["svm.name"] = svm_name
        result = self.get("/storage/flexcache/flexcaches", params=params)
        return result.get("records", [])

    def get_flexcache(self, uuid: str) -> dict:
        """FlexCache ボリューム詳細取得

        Args:
            uuid: FlexCache UUID

        Returns:
            dict: FlexCache 詳細情報
        """
        return self.get(
            f"/storage/flexcache/flexcaches/{uuid}",
            params={"fields": "name,uuid,svm,size,path,origins,prepopulate"},
        )

    def create_flexcache(
        self,
        name: str,
        svm_name: str,
        origin_volume: str,
        origin_svm: str,
        size_gb: int,
        junction_path: str | None = None,
        aggregate_name: str | None = None,
        prepopulate_dir_paths: list[str] | None = None,
    ) -> dict:
        """FlexCache ボリューム作成

        Args:
            name: FlexCache ボリューム名
            svm_name: キャッシュ SVM 名
            origin_volume: オリジンボリューム名
            origin_svm: オリジン SVM 名
            size_gb: サイズ (GB)
            junction_path: ジャンクションパス (デフォルト: /{name})
            aggregate_name: アグリゲート名 (オプション)
            prepopulate_dir_paths: Prepopulate 対象ディレクトリ (オプション)

        Returns:
            dict: 作成結果（job UUID 含む）

        Raises:
            OntapClientError: 作成失敗時
        """
        body: dict[str, Any] = {
            "name": name,
            "svm": {"name": svm_name},
            "origins": [
                {
                    "volume": {"name": origin_volume},
                    "svm": {"name": origin_svm},
                }
            ],
            "size": size_gb * 1024 * 1024 * 1024,  # GB → bytes
        }

        if junction_path:
            body["path"] = junction_path
        else:
            body["path"] = f"/{name}"

        if aggregate_name:
            body["aggregates"] = [{"name": aggregate_name}]

        if prepopulate_dir_paths:
            body["prepopulate"] = {"dir_paths": prepopulate_dir_paths}

        logger.info(
            "Creating FlexCache: %s (origin: %s/%s)", name, origin_svm, origin_volume
        )
        return self.post("/storage/flexcache/flexcaches", body=body)

    def delete_flexcache(self, uuid: str) -> dict:
        """FlexCache ボリューム削除

        Args:
            uuid: FlexCache UUID

        Returns:
            dict: 削除結果（job UUID 含む）

        Raises:
            OntapClientError: 削除失敗時
        """
        logger.info("Deleting FlexCache: %s", uuid)
        return self.delete(f"/storage/flexcache/flexcaches/{uuid}")

    def prepopulate_flexcache(
        self,
        uuid: str,
        dir_paths: list[str],
        exclude_dir_paths: list[str] | None = None,
    ) -> dict:
        """FlexCache Prepopulate 実行

        指定ディレクトリのデータを事前にキャッシュにフェッチする。
        ONTAP 9.13.1+ が必要。

        Args:
            uuid: FlexCache UUID
            dir_paths: Prepopulate 対象ディレクトリパスのリスト
            exclude_dir_paths: 除外ディレクトリパスのリスト (オプション)

        Returns:
            dict: Prepopulate ジョブ結果
        """
        body: dict[str, Any] = {"dir_paths": dir_paths}
        if exclude_dir_paths:
            body["exclude_dir_paths"] = exclude_dir_paths

        logger.info("Prepopulating FlexCache %s: %s", uuid, dir_paths)
        return self.patch(
            f"/storage/flexcache/flexcaches/{uuid}",
            body={"prepopulate": body},
        )

    # --- SnapMirror 操作メソッド ---
    #
    # These carry only the request path, the payload and the field mapping. Input
    # validation, the confirm gate on the destructive ones, the audit log line and
    # the camelCase response shaping stay with the caller: whether a particular
    # operation needs a human to confirm it is a property of the surface exposing
    # it, not of the protocol.
    #
    # Field selections are the ones verified against a live cluster. Notably
    # `last_transfer_size` is NOT a field on the relationships endpoint -- ONTAP
    # 9.17 rejects the whole request with 'The value "last_transfer_size" is
    # invalid for field "fields"' and the list comes back empty. Per-transfer byte
    # counts come from list_snapmirror_transfers() instead.

    # Minimal field set that every ONTAP version accepts on this endpoint. Display
    # extras (state, healthy, policy.name, lag_time, last_transfer_type) are omitted
    # because some versions reject them on /snapmirror/relationships with
    # 'The value "<field>" is invalid for field "fields"' and return an empty list;
    # a teardown only needs the uuid and the source/destination identity.
    RELATIONSHIP_FIELDS = (
        "uuid,source.path,source.svm.name,destination.path,destination.svm.name"
    )
    TRANSFER_FIELDS = "state,bytes_transferred,end_time,total_duration"

    def list_snapmirror_relationships(self, max_records: int = 100) -> list[dict]:
        """SnapMirror リレーションシップ一覧取得

        ONTAP REST: GET /snapmirror/relationships

        Returns:
            list[dict]: リレーションシップの生レコード
        """
        result = self.get(
            "/snapmirror/relationships",
            params={
                "fields": self.RELATIONSHIP_FIELDS,
                "max_records": str(max_records),
            },
        )
        return result.get("records", [])

    def list_snapmirror_transfers(
        self,
        relationship_uuid: str,
        max_records: int = 20,
    ) -> list[dict]:
        """1 つのリレーションシップの転送履歴取得

        ONTAP REST: GET /snapmirror/relationships/{uuid}/transfers
        """
        result = self.get(
            f"/snapmirror/relationships/{relationship_uuid}/transfers",
            params={"fields": self.TRANSFER_FIELDS, "max_records": str(max_records)},
        )
        return result.get("records", [])

    def set_snapmirror_state(self, relationship_uuid: str, state: str) -> dict:
        """SnapMirror の state を変更

        ONTAP REST: PATCH /snapmirror/relationships/{uuid}

        `paused` で quiesce、`snapmirrored` で resume/resync、`broken_off` で break。
        break と resync は宛先のデータを不可逆に変えるため、呼び出し側で確認を取ること。
        """
        return self.patch(
            f"/snapmirror/relationships/{relationship_uuid}",
            body={"state": state},
        )

    def quiesce_snapmirror(self, relationship_uuid: str) -> dict:
        """転送を一時停止 (state=paused)"""
        return self.set_snapmirror_state(relationship_uuid, "paused")

    def resume_snapmirror(self, relationship_uuid: str) -> dict:
        """一時停止した転送を再開 (state=snapmirrored)"""
        return self.set_snapmirror_state(relationship_uuid, "snapmirrored")

    def break_snapmirror(self, relationship_uuid: str) -> dict:
        """リレーションシップを break して宛先を書き込み可能にする

        break 後、宛先はソースから乖離します。呼び出し側で確認を取ること。
        """
        return self.set_snapmirror_state(relationship_uuid, "broken_off")

    def resync_snapmirror(self, relationship_uuid: str) -> dict:
        """break したリレーションシップを再同期する

        break 後に宛先へ書き込まれた変更は破棄されます。呼び出し側で確認を取ること。
        """
        return self.set_snapmirror_state(relationship_uuid, "snapmirrored")

    def update_snapmirror_now(self, relationship_uuid: str) -> dict:
        """スケジュールを待たず即時転送を開始

        ONTAP REST: POST /snapmirror/relationships/{uuid}/transfers
        """
        return self.post(f"/snapmirror/relationships/{relationship_uuid}/transfers")

    def abort_snapmirror_transfer(
        self, relationship_uuid: str, transfer_uuid: str
    ) -> dict:
        """進行中の転送を中断

        ONTAP REST: PATCH /snapmirror/relationships/{uuid}/transfers/{transfer_uuid}
        """
        return self.patch(
            f"/snapmirror/relationships/{relationship_uuid}/transfers/{transfer_uuid}",
            body={"state": "aborted"},
        )

    def delete_snapmirror(self, relationship_uuid: str) -> dict:
        """リレーションシップを削除

        ONTAP REST: DELETE /snapmirror/relationships/{uuid}

        宛先ボリュームは残りますが複製は止まります。呼び出し側で確認を取ること。
        """
        return self.delete(f"/snapmirror/relationships/{relationship_uuid}")

    def wait_ontap_job(
        self,
        job_uuid: str,
        timeout_seconds: int = 300,
        poll_interval: int = 5,
    ) -> dict:
        """ONTAP 非同期ジョブの完了を待機

        Args:
            job_uuid: ジョブ UUID
            timeout_seconds: タイムアウト秒数 (デフォルト: 300)
            poll_interval: ポーリング間隔秒数 (デフォルト: 5)

        Returns:
            dict: ジョブ最終状態

        Raises:
            OntapClientError: タイムアウトまたはジョブ失敗時
        """
        import time

        start_time = time.time()
        while True:
            elapsed = time.time() - start_time
            if elapsed > timeout_seconds:
                raise OntapClientError(
                    f"ONTAP job {job_uuid} timed out after {timeout_seconds}s"
                )

            job = self.get(f"/cluster/jobs/{job_uuid}")
            state = job.get("state", "unknown")

            if state == "success":
                logger.info("ONTAP job %s completed successfully", job_uuid)
                return job
            elif state in ("failure", "error"):
                error_msg = job.get("message", "Unknown error")
                raise OntapClientError(
                    f"ONTAP job {job_uuid} failed: {error_msg}",
                    response_body=json.dumps(job),
                )

            logger.debug(
                "ONTAP job %s state: %s (%.0fs elapsed)",
                job_uuid,
                state,
                elapsed,
            )
            time.sleep(poll_interval)

    # --- ONTAP-ops deletion shortcuts (added for automation/ontap-ops) ---
    #
    # These are the only additions over the ported Serverless Spoke client. Each
    # is the thin request layer for one deletion the AWS FSx control plane cannot
    # perform; the confirm gate, the audit line and the 202 job polling stay with
    # the pattern that calls them (see patterns/). Endpoints are the ones recorded
    # in DESIGN.md from NetApp documentation. None of these touch SnapLock /
    # Object-Lock / retention — the family guard stays authoritative.

    def unmount_volume(self, volume_uuid: str) -> dict:
        """ボリュームをアンマウント（ジャンクションパスを外す）

        ONTAP REST: PATCH /storage/volumes/{uuid}  body={"nas": {"path": ""}}

        マウント済みのボリューム（FlexCache 含む）は、そのままでは削除できない。
        削除前にこの呼び出しでジャンクションを外す。202 を返すことがあるため、
        呼び出し側で wait_ontap_job によるポーリングが必要。
        """
        logger.info("Unmounting volume (clearing junction path): %s", volume_uuid)
        return self.patch(f"/storage/volumes/{volume_uuid}", body={"nas": {"path": ""}})

    def delete_volume(self, volume_uuid: str) -> dict:
        """ボリューム削除

        ONTAP REST: DELETE /storage/volumes/{uuid}

        202 を返すため、呼び出し側で wait_ontap_job によるポーリングが必要。
        """
        logger.info("Deleting volume: %s", volume_uuid)
        return self.delete(f"/storage/volumes/{volume_uuid}")

    def delete_svm(self, svm_uuid: str) -> dict:
        """SVM 削除

        ONTAP REST: DELETE /svm/svms/{uuid}

        非 root ボリュームがすべて削除済みであることが前提。202 を返すため
        呼び出し側でポーリングする。
        """
        logger.info("Deleting SVM: %s", svm_uuid)
        return self.delete(f"/svm/svms/{svm_uuid}")

    def list_s3_buckets(self, svm_uuid: str) -> list[dict]:
        """オブジェクトストア (S3) バケット一覧取得

        ONTAP REST: GET /protocols/s3/buckets（SVM UUID でフィルタ）

        Returns:
            list[dict]: バケットの生レコード（name, uuid, svm, volume）
        """
        result = self.get(
            "/protocols/s3/buckets",
            params={
                "svm.uuid": svm_uuid,
                "fields": "name,uuid,svm,volume",
            },
        )
        return result.get("records", [])

    def list_all_s3_buckets(self) -> list[dict]:
        """クラスタ全体のオブジェクトストア (S3) バケット一覧取得

        svm.uuid で絞らず、クラスタ上の全 SVM のバケットを 1 回の GET で発見する。
        per-SVM の list_s3_buckets は、バケットを背後で支えるボリュームがどの SVM に
        紐づくかを呼び出し側が知っている前提だが、FLEXGROUP ボリュームを背後に持つ
        バケットのように、削除をブロックしている実体が per-SVM の列挙に現れないことが
        ある。クラスタ全体の列挙は svm.uuid/svm.name と volume.name/volume.uuid を
        各バケットに添えて返すので、任意の SVM 上のバケットをその SVM の文脈つきで
        発見・削除できる。

        この ONTAP クラスタは fields に "state" を拒否するため追加しない。

        ONTAP REST: GET /protocols/s3/buckets
            （fields=name,uuid,svm.uuid,svm.name,volume.name,volume.uuid）

        Returns:
            list[dict]: バケットの生レコード（name, uuid, svm, volume を含む）
        """
        result = self.get(
            "/protocols/s3/buckets",
            params={"fields": "name,uuid,svm.uuid,svm.name,volume.name,volume.uuid"},
        )
        return result.get("records", [])

    def resolve_s3_bucket_endpoint(self, svm_uuid: str, bucket_uuid: str) -> str:
        """どの S3 バケット削除エンドポイントが存在するかを GET で判定

        ONTAP のリリースにより次の 2 系統が存在する。先に `/protocols/s3/buckets`
        側を GET で確認し、404 なら `/protocols/s3/services` 側にフォールバックする。
        これにより DELETE を誤ったパスへ送らない。

        - DELETE /protocols/s3/buckets/{svm.uuid}/{uuid}
        - DELETE /protocols/s3/services/{svm.uuid}/buckets/{uuid}

        Returns:
            str: 削除に使うべきパス（上記のいずれか）
        """
        buckets_path = f"/protocols/s3/buckets/{svm_uuid}/{bucket_uuid}"
        services_path = f"/protocols/s3/services/{svm_uuid}/buckets/{bucket_uuid}"
        try:
            self.get(buckets_path)
            return buckets_path
        except OntapClientError as err:
            if err.status_code == 404:
                self.get(services_path)
                return services_path
            raise

    def delete_s3_bucket(self, svm_uuid: str, bucket_uuid: str) -> dict:
        """オブジェクトストア (S3) バケット削除

        存在するエンドポイントを resolve_s3_bucket_endpoint で判定してから DELETE。
        202 を返すため呼び出し側でポーリングする。
        """
        path = self.resolve_s3_bucket_endpoint(svm_uuid, bucket_uuid)
        logger.info(
            "Deleting S3 bucket %s on SVM %s via %s", bucket_uuid, svm_uuid, path
        )
        return self.delete(path)

    def get_audit_config(self, svm_uuid: str) -> dict:
        """SVM の監査 (audit) 設定取得

        ONTAP REST: GET /protocols/audit/{svm.uuid}
        """
        return self.get(f"/protocols/audit/{svm_uuid}")

    def disable_audit(self, svm_uuid: str) -> dict:
        """SVM の NAS 監査を無効化（宛先ボリュームを解放する前段）

        ONTAP REST: PATCH /protocols/audit/{svm.uuid}  body={"enabled": false}
        """
        logger.info("Disabling NAS audit on SVM %s", svm_uuid)
        return self.patch(f"/protocols/audit/{svm_uuid}", body={"enabled": False})

    def delete_audit(self, svm_uuid: str) -> dict:
        """SVM の NAS 監査設定削除

        ONTAP REST: DELETE /protocols/audit/{svm.uuid}
        """
        logger.info("Deleting NAS audit config on SVM %s", svm_uuid)
        return self.delete(f"/protocols/audit/{svm_uuid}")

    def delete_object_store_audit(self, svm_uuid: str) -> dict:
        """SVM のオブジェクトストア監査設定削除

        ONTAP REST: DELETE /protocols/audit/{svm.uuid}/object-store
        """
        logger.info("Deleting object-store audit config on SVM %s", svm_uuid)
        return self.delete(f"/protocols/audit/{svm_uuid}/object-store")

    def list_clones_of(self, parent_volume_name: str) -> list[dict]:
        """指定した親ボリュームの FlexClone 一覧取得

        FlexClone はボリュームの一種で、clone.parent_volume などが設定されている。
        ONTAP REST: GET /storage/volumes?clone.parent_volume.name={name}
        """
        result = self.get(
            "/storage/volumes",
            params={
                "clone.parent_volume.name": parent_volume_name,
                "fields": "name,uuid,svm,clone",
            },
        )
        return result.get("records", [])

    def list_clones(self) -> list[dict]:
        """ファイルシステム全体の FlexClone 一覧取得

        親ボリューム名が渡されないときに、クローンを FS 全体から発見するために使う。
        GET /storage/volumes で clone を要求し、呼び出し側が clone.is_flexclone ==
        true のものだけを残す。display extra（state 等）はこの ONTAP バージョンが
        fields で拒否するため追加しない。

        ONTAP REST: GET /storage/volumes?fields=name,uuid,svm,clone

        Returns:
            list[dict]: clone 情報を含むボリュームの生レコード
        """
        result = self.get(
            "/storage/volumes",
            params={"fields": "name,uuid,svm,clone"},
        )
        return result.get("records", [])

    def split_clone(self, volume_uuid: str) -> dict:
        """FlexClone を親から split する

        ONTAP REST: PATCH /storage/volumes/{uuid} body={"clone":{"split_initiated":true}}

        split は親との依存を断つ。split 完了後にクローンボリュームを削除できる。
        202 を返すため呼び出し側でポーリングする。クローンを split せず直接削除する
        選択肢もある（flexclone_split_delete パターンを参照）。
        """
        logger.info("Splitting FlexClone: %s", volume_uuid)
        return self.patch(
            f"/storage/volumes/{volume_uuid}",
            body={"clone": {"split_initiated": True}},
        )

    def list_fpolicy_persistent_stores(self, svm_uuid: str) -> list[dict]:
        """SVM の FPolicy persistent store 一覧取得

        各 SVM は persistent store を最大 1 つ持つ。これを支えるボリューム
        （fpolicy_persistent_store）を解放するには、ポリシー/イベント/エンジンを
        消したあとに persistent store を消す必要がある。

        ONTAP REST: GET /protocols/fpolicy/{svm.uuid}/persistent-stores
        """
        result = self.get(
            f"/protocols/fpolicy/{svm_uuid}/persistent-stores",
            params={"fields": "name,volume"},
        )
        return result.get("records", [])

    def delete_fpolicy_persistent_store(self, svm_uuid: str, name: str) -> dict:
        """SVM の FPolicy persistent store 削除

        ポリシー/イベント/エンジンの削除後に実行する。順序を守らないと、まだ参照
        されている persistent store の削除が失敗する。

        ONTAP REST: DELETE /protocols/fpolicy/{svm.uuid}/persistent-stores/{name}
        """
        logger.info("Deleting FPolicy persistent store %s on SVM %s", name, svm_uuid)
        return self.delete(f"/protocols/fpolicy/{svm_uuid}/persistent-stores/{name}")

    # --- CLI passthrough maintenance operations (/api/private/cli) ---
    #
    # These wrap the ONTAP private CLI passthrough for surgical teardown blockers
    # that structured REST does not expose: a stale clone stuck in the volume
    # recovery queue, a source-side SnapMirror relationship pinning a source
    # volume, and a surviving vserver peer that blocks an SVM. Each was verified
    # against a live cluster during a teardown.
    #
    # The passthrough has one firm rule, learned the hard way and encoded here so
    # every call site inherits it:
    #   - GET takes query parameters (fields=..., filters as query keys).
    #   - POST must carry its attributes in the request BODY. Query filtering on a
    #     POST is rejected with "POST on a REST API does not support filtering on an
    #     attribute".
    #   - A collection DELETE can be query-based (attribute match in the query).
    #
    # None of these touch SnapLock / Object-Lock / retention; the family guard
    # stays authoritative.

    def list_recovery_queue(self) -> list[dict]:
        """Volume Recovery Queue（pending-delete ボリューム）一覧取得

        ONTAP CLI passthrough: GET /private/cli/volume/recovery-queue
        （GET なのでクエリ。ここでは全件を読む。）

        削除保留中（volume type DEL）のボリュームを返す。親の削除を
        "has one or more clones" で阻む stale clone は、`volume show` と構造化 REST
        には現れず、ここと `volume clone show` にだけ現れることがある。

        Returns:
            list[dict]: recovery queue のレコード（vserver, volume などを含む）
        """
        result = self.get("/private/cli/volume/recovery-queue")
        return result.get("records", result if isinstance(result, list) else [])

    def purge_recovery_queue(self, vserver: str, volume: str) -> dict:
        """Volume Recovery Queue の pending-delete ボリュームを完全破棄する

        ONTAP CLI passthrough: POST /private/cli/volume/recovery-queue/purge
            body={"vserver": <svm>, "volume": <volume>}

        POST なので属性は **body** に入れる（クエリ指定は passthrough が拒否する）。
        これにより、親の削除を "has one or more clones" で阻んでいた stale clone
        （recovery queue 内の DEL ボリューム）を取り除き、親を削除可能にする。

        202 を返すことがあるため、呼び出し側で _poll_if_job / wait_ontap_job が必要。
        """
        logger.info("Purging recovery-queue volume %s on vserver %s", volume, vserver)
        return self.post(
            "/private/cli/volume/recovery-queue/purge",
            body={"vserver": vserver, "volume": volume},
        )

    def list_volume_clones_cli(self, parent_volume_name: str) -> list[dict]:
        """`volume clone show` 相当（親ボリューム名でクローンを引く）

        ONTAP CLI passthrough: GET /private/cli/volume/clone?parent-volume=<name>

        GET なのでクエリ。構造化 REST（GET /storage/volumes?clone.parent_volume...）
        に現れないクローン（recovery queue 内の DEL クローン等）を拾う最後の手段。

        Returns:
            list[dict]: clone のレコード（volume, vserver, parent-volume を含む）
        """
        result = self.get(
            "/private/cli/volume/clone",
            params={"parent-volume": parent_volume_name},
        )
        return result.get("records", result if isinstance(result, list) else [])

    def list_snapmirror_destinations_by_source(
        self,
        source_path: str | None = None,
        source_vserver: str | None = None,
    ) -> list[dict]:
        """ソース側から見た SnapMirror の宛先一覧（source-side relationships）

        ONTAP CLI passthrough:
            GET /private/cli/snapmirror/list-destinations?source-path=<svm:vol>
            または ?source-vserver=<svm>
            （fields=relationship-id,source-path,destination-path）

        GET なのでクエリ。ソースボリュームの削除を阻むソース側の関係を見つけるために
        使う（構造化 REST の /snapmirror/relationships は宛先側視点で、ソース側の
        解放対象を取りこぼすことがある）。source_path か source_vserver のいずれかを渡す。

        Returns:
            list[dict]: relationship-id, source-path, destination-path を含むレコード
        """
        params = {"fields": "relationship-id,source-path,destination-path"}
        if source_path:
            params["source-path"] = source_path
        if source_vserver:
            params["source-vserver"] = source_vserver
        result = self.get("/private/cli/snapmirror/list-destinations", params=params)
        return result.get("records", result if isinstance(result, list) else [])

    def release_snapmirror_source(
        self,
        source_path: str | None = None,
        destination_path: str | None = None,
        relationship_id: str | None = None,
    ) -> dict:
        """SnapMirror のソース側解放（source-side release）

        ONTAP CLI passthrough: POST /private/cli/snapmirror/release
            body に source-path を入れる、または relationship-id + destination-path、
            または relationship-info-only=true（関係情報のみ解放しボリュームは残す）。

        POST なので属性は **body** に入れる（クエリ指定は passthrough が拒否する）。
        ソースボリュームを削除可能にするため、ソース側に残る関係レコードを外す。
        destination_path が無ければ relationship-info-only=true を立て、宛先には
        触れずソース側の情報だけを解放する。
        """
        body: dict[str, Any] = {}
        if source_path:
            body["source-path"] = source_path
        if relationship_id:
            body["relationship-id"] = relationship_id
        if destination_path:
            body["destination-path"] = destination_path
        else:
            body["relationship-info-only"] = True
        logger.info("Releasing source-side SnapMirror: %s", body)
        return self.post("/private/cli/snapmirror/release", body=body)

    def delete_snapmirror_by_destination(self, destination_path: str) -> dict:
        """SnapMirror を宛先パスで削除する

        ONTAP CLI passthrough: POST /private/cli/snapmirror/delete
            body={"destination-path": <svm:vol>}

        POST なので属性は **body** に入れる。この CLI の delete は destination-path
        でのみ指定でき、relationship-id は受け付けない（検証済み）。構造化 REST の
        DELETE /snapmirror/relationships/{uuid} が使えない（宛先側に関係が無い等）
        ケースの補完。
        """
        logger.info("Deleting SnapMirror by destination-path: %s", destination_path)
        return self.post(
            "/private/cli/snapmirror/delete",
            body={"destination-path": destination_path},
        )

    def list_vserver_peers(self) -> list[dict]:
        """vserver peer 一覧取得

        ONTAP CLI passthrough: GET /private/cli/vserver/peer

        GET なのでクエリ。生き残った SVM peer が SVM を MISCONFIGURED / 削除不可に
        する場合があり、その特定に使う。

        Returns:
            list[dict]: vserver, peer-vserver などを含むレコード
        """
        result = self.get("/private/cli/vserver/peer")
        return result.get("records", result if isinstance(result, list) else [])

    def delete_vserver_peer(self, vserver: str, peer_vserver: str) -> dict:
        """vserver peer をクエリ指定で削除する

        ONTAP CLI passthrough:
            DELETE /private/cli/vserver/peer?vserver=<svm>&peer-vserver=<peer>

        コレクション DELETE はクエリベースでよい（属性一致の DELETE）。生き残った
        SVM peer に阻まれて削除できない SVM を解放する。値は percent-encode する。

        注意: SVM そのものの削除は AWS FSx API 側で行い、ONTAP REST では実装しない。
        ここが外すのは peer 関係だけで、SVM は消さない。
        """
        from urllib.parse import quote

        logger.info("Deleting vserver peer %s -> %s", vserver, peer_vserver)
        return self.delete(
            f"/private/cli/vserver/peer?vserver={quote(vserver)}"
            f"&peer-vserver={quote(peer_vserver)}"
        )
