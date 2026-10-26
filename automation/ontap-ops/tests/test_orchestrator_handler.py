"""Orchestrator ordering and handler gate behavior."""

from __future__ import annotations

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _bootstrap  # noqa: F401  (loads the ontap_ops package by path)
from fake_client import RecordingClient
from ontap_ops import handler as handler_module
from ontap_ops import orchestrator

SVM = "svm-uuid-1"
FS = "fs-0123456789abcdef0"
OTHER_FS = "fs-aaaaaaaaaaaaaaaaa"

# The dependency order DESIGN.md fixes.
EXPECTED_ORDER = [
    "snapmirror_release",
    "flexclone_split_delete",
    "s3bucket_delete",
    "audit_redirect",
    "fpolicy_teardown",
    "flexcache_delete",
    "volume_delete",
    "svm_delete",
]


def _empty_client():
    # Every list endpoint returns no records, so plan() runs read-only to completion.
    return RecordingClient(
        {
            "/snapmirror/relationships": {"records": []},
            "/storage/volumes": {"records": []},
            "/protocols/s3/buckets": {"records": []},
            f"/protocols/audit/{SVM}": {},
            f"/protocols/fpolicy/{SVM}/policies": {"records": []},
            f"/protocols/fpolicy/{SVM}/events": {"records": []},
            f"/protocols/fpolicy/{SVM}/engines": {"records": []},
            "/storage/flexcache/flexcaches": {"records": []},
            f"/svm/svms/{SVM}": {"name": "svm1"},
        }
    )


class TestOrchestratorPlan(unittest.TestCase):
    def test_plan_follows_design_order(self):
        client = _empty_client()
        steps = orchestrator.plan(client, svm_uuid=SVM, svm_name="svm1")
        self.assertEqual([s["pattern"] for s in steps], EXPECTED_ORDER)

    def test_plan_issues_no_mutations(self):
        client = _empty_client()
        orchestrator.plan(client, svm_uuid=SVM, svm_name="svm1")
        # A plan reads only; no DELETE/POST/PATCH may have been issued.
        self.assertEqual(client.paths("DELETE"), [])
        self.assertEqual(client.paths("POST"), [])
        self.assertEqual(client.paths("PATCH"), [])


class TestHandlerGates(unittest.TestCase):
    def test_handler_refuses_outside_allowlist(self):
        with mock.patch.dict(os.environ, {"ONTAP_OPS_ALLOWLIST": OTHER_FS}, clear=True):
            result = handler_module.handler({"file_system_id": FS})
        self.assertEqual(result["status"], "refused")
        # Refused before any client was built: no secret needed to reach this.

    def test_handler_requires_file_system_id(self):
        result = handler_module.handler({})
        self.assertEqual(result["status"], "error")

    def test_handler_keep_list_refuses(self):
        env = {"ONTAP_OPS_ALLOWLIST": FS, "ONTAP_OPS_KEEP_LIST": FS}
        with mock.patch.dict(os.environ, env, clear=True):
            result = handler_module.handler({"file_system_id": FS})
        self.assertEqual(result["status"], "refused")

    def test_handler_dry_run_plan(self):
        """Dry-run returns an ordered plan built from read-only GETs, no deletions."""
        client = _empty_client()
        # Bypass real AWS/ONTAP wiring: inject the recording client, skip secret/IP.
        with (
            mock.patch.dict(os.environ, {"ONTAP_OPS_ALLOWLIST": FS}, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "svm_uuid": SVM,
                    "svm_name": "svm1",
                    "secret_id": "s",
                }
            )
        self.assertEqual(result["status"], "dry_run")
        self.assertEqual([s["pattern"] for s in result["plan"]], EXPECTED_ORDER)
        self.assertEqual(client.paths("DELETE"), [])

    def test_handler_auth_failure_aborts_without_retry(self):
        """A 401/403 from ONTAP aborts immediately (fsxadmin lock hazard), no retry."""
        from ontap_ops.shared.ontap_client import OntapClientError

        class _AuthFailClient:
            pass

        def _raise_auth(*_a, **_k):
            raise OntapClientError("Invalid ONTAP credentials", status_code=401)

        with (
            mock.patch.dict(os.environ, {"ONTAP_OPS_ALLOWLIST": FS}, clear=True),
            mock.patch.object(
                handler_module, "_build_client", lambda *a, **k: _AuthFailClient()
            ),
            mock.patch.object(orchestrator, "plan", _raise_auth),
        ):
            result = handler_module.handler({"file_system_id": FS, "secret_id": "s"})
        self.assertEqual(result["status"], "auth_failure")
        self.assertIn("not retried", result["note"])


if __name__ == "__main__":
    unittest.main()
