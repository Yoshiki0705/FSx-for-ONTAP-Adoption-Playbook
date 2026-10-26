"""fsx_helpers tests.

The Secrets Manager resolve-and-verify path and the FSx describe path are both driven
by stubbed boto3 sessions built with unittest.mock, so the suite needs no moto, no live
cluster, and no AWS account. resolve_and_verify_secret() reads the secret metadata with
secretsmanager describe_secret (Tags / Description); get_management_ip() reads
fsx describe_file_systems. Each stub session returns exactly the shape the real API
returns, and the same four secret outcomes are asserted: resolves on a matching
FileSystemId tag, aborts on a mismatched tag, falls back to the description reference,
and refuses a secret with no binding at all (no name-guessing).
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _bootstrap  # noqa: F401  (loads the ontap_ops package by path)
from ontap_ops.shared.fsx_helpers import (
    SecretVerificationError,
    describe_file_system,
    get_management_ip,
    resolve_and_verify_secret,
)

FS = "fs-0123456789abcdef0"
OTHER_FS = "fs-abcdef0123456789a"


def _sm_session(describe_secret_response):
    """A boto3-like session whose secretsmanager client returns a canned describe.

    describe_secret is a MagicMock so the test can also assert it was called with the
    secret id supplied to resolve_and_verify_secret().
    """
    sm_client = mock.MagicMock()
    sm_client.describe_secret.return_value = describe_secret_response

    session = mock.MagicMock()

    def _client(name):
        assert name == "secretsmanager", f"unexpected client: {name}"
        return sm_client

    session.client.side_effect = _client
    # Expose the client so tests can inspect calls.
    session.sm_client = sm_client
    return session


def _fsx_session(describe_file_systems_response):
    """A boto3-like session whose fsx client returns a canned describe_file_systems."""
    fsx_client = mock.MagicMock()
    fsx_client.describe_file_systems.return_value = describe_file_systems_response

    session = mock.MagicMock()

    def _client(name):
        assert name == "fsx", f"unexpected client: {name}"
        return fsx_client

    session.client.side_effect = _client
    session.fsx_client = fsx_client
    return session


class TestResolveAndVerifySecret(unittest.TestCase):
    def test_matching_tag_resolves(self):
        session = _sm_session(
            {"ARN": "arn:x", "Tags": [{"Key": "FileSystemId", "Value": FS}]}
        )
        result = resolve_and_verify_secret("ontap-fsxadmin", FS, session=session)
        self.assertEqual(result, "ontap-fsxadmin")
        session.sm_client.describe_secret.assert_called_once_with(
            SecretId="ontap-fsxadmin"
        )

    def test_mismatched_tag_aborts(self):
        session = _sm_session({"Tags": [{"Key": "FileSystemId", "Value": OTHER_FS}]})
        with self.assertRaises(SecretVerificationError):
            resolve_and_verify_secret("ontap-fsxadmin-other", FS, session=session)

    def test_description_fallback_resolves(self):
        session = _sm_session({"Description": f"fsxadmin credentials for {FS}"})
        result = resolve_and_verify_secret("ontap-desc", FS, session=session)
        self.assertEqual(result, "ontap-desc")

    def test_no_binding_refused(self):
        # No FileSystemId tag or description reference -> refuse (no name-guessing).
        session = _sm_session({"Name": "ontap-unbound"})
        with self.assertRaises(SecretVerificationError):
            resolve_and_verify_secret("ontap-unbound", FS, session=session)


class TestFsxDescribe(unittest.TestCase):
    def test_get_management_ip_reads_first_address(self):
        session = _fsx_session(
            {
                "FileSystems": [
                    {
                        "FileSystemId": FS,
                        "OntapConfiguration": {
                            "Endpoints": {
                                "Management": {
                                    "IpAddresses": ["10.0.1.100", "10.0.2.100"]
                                }
                            }
                        },
                    }
                ]
            }
        )
        self.assertEqual(get_management_ip(FS, session=session), "10.0.1.100")
        session.fsx_client.describe_file_systems.assert_called_once_with(
            FileSystemIds=[FS]
        )

    def test_describe_file_system_not_found_raises(self):
        session = _fsx_session({"FileSystems": []})
        with self.assertRaises(ValueError):
            describe_file_system(FS, session=session)

    def test_get_management_ip_missing_endpoint_raises(self):
        session = _fsx_session(
            {"FileSystems": [{"FileSystemId": FS, "OntapConfiguration": {}}]}
        )
        with self.assertRaises(ValueError):
            get_management_ip(FS, session=session)


if __name__ == "__main__":
    unittest.main()
