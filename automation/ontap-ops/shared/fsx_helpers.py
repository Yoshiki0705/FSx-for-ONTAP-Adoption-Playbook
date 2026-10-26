"""FSx 側のヘルパー — ファイルシステム記述、管理エンドポイント探索、シークレット検証

AWS FSx の describe-file-systems で管理 LIF を特定し、Secrets Manager の
シークレットが対象ファイルシステム用であることをタグ/説明で確認する。名前推測は
しない。同名の管理ユーザー (fsxadmin) を複数のファイルシステムが共有するため、
名前でシークレットを選ぶと取り違えて認証が「到達するが拒否される」形で失敗し、
原因を誤認しやすい。
"""

from __future__ import annotations

import logging

import boto3

logger = logging.getLogger(__name__)


class SecretVerificationError(Exception):
    """シークレットが対象ファイルシステム用であると確認できなかった"""


def describe_file_system(
    file_system_id: str, session: boto3.Session | None = None
) -> dict:
    """1 つのファイルシステムを describe する

    Args:
        file_system_id: 対象のファイルシステム ID
        session: boto3 セッション (省略時は既定)

    Returns:
        dict: FileSystem レコード

    Raises:
        ValueError: ファイルシステムが見つからない場合
    """
    session = session or boto3.Session()
    fsx = session.client("fsx")
    response = fsx.describe_file_systems(FileSystemIds=[file_system_id])
    file_systems = response.get("FileSystems", [])
    if not file_systems:
        raise ValueError(f"File system not found: {file_system_id}")
    return file_systems[0]


def get_management_ip(file_system_id: str, session: boto3.Session | None = None) -> str:
    """ファイルシステムの ONTAP 管理エンドポイント IP を返す

    OntapConfiguration.Endpoints.Management.IpAddresses[0] から取得する。
    この IP は VPC 内からのみ到達可能。

    Args:
        file_system_id: 対象のファイルシステム ID
        session: boto3 セッション (省略時は既定)

    Returns:
        str: 管理エンドポイントの IP アドレス

    Raises:
        ValueError: 管理エンドポイントが見つからない場合
    """
    fs = describe_file_system(file_system_id, session=session)
    try:
        addresses = fs["OntapConfiguration"]["Endpoints"]["Management"]["IpAddresses"]
    except (KeyError, TypeError) as err:
        raise ValueError(
            f"No ONTAP management endpoint on file system {file_system_id}"
        ) from err
    if not addresses:
        raise ValueError(f"Empty management IP list on file system {file_system_id}")
    return addresses[0]


def _file_system_id_from_secret(secret: dict) -> str | None:
    """シークレットのメタデータから FileSystemId を読む

    タグ (`FileSystemId`) を優先し、無ければ説明文 (Description) に含まれる
    fs-xxxx を探す。どちらも無ければ None。
    """
    for tag in secret.get("Tags", []) or []:
        if tag.get("Key") == "FileSystemId":
            return tag.get("Value")

    description = secret.get("Description", "") or ""
    for token in description.replace(",", " ").split():
        if token.startswith("fs-"):
            return token
    return None


def resolve_and_verify_secret(
    secret_id: str,
    file_system_id: str,
    session: boto3.Session | None = None,
) -> str:
    """シークレットが対象ファイルシステム用であることを検証する

    シークレットは呼び出し側が明示的に渡す (env ONTAP_SECRET_ID またはイベント)。
    使用前に、そのシークレットの `FileSystemId` タグ（または説明文中の fs-xxxx）が
    対象の file_system_id と一致することを確認する。一致しなければ中断する。
    名前から推測して選ぶことは絶対にしない。

    Args:
        secret_id: Secrets Manager のシークレット ID/ARN（明示指定）
        file_system_id: 対象ファイルシステム ID
        session: boto3 セッション (省略時は既定)

    Returns:
        str: 検証済みのシークレット ID（そのまま OntapClientConfig に渡す）

    Raises:
        SecretVerificationError: タグ/説明に紐づく FileSystemId が一致しない、
            または取得できない場合
    """
    session = session or boto3.Session()
    sm = session.client("secretsmanager")
    secret = sm.describe_secret(SecretId=secret_id)

    tagged_fs_id = _file_system_id_from_secret(secret)
    if tagged_fs_id is None:
        raise SecretVerificationError(
            f"Secret {secret_id} has no FileSystemId tag or description reference; "
            "refusing to use it (name-guessing is not allowed)."
        )
    if tagged_fs_id != file_system_id:
        raise SecretVerificationError(
            f"Secret {secret_id} is bound to {tagged_fs_id}, not the target "
            f"{file_system_id}; aborting to avoid a cross-file-system credential mix-up."
        )

    logger.info(
        "Secret %s verified as bound to file system %s", secret_id, file_system_id
    )
    return secret_id
