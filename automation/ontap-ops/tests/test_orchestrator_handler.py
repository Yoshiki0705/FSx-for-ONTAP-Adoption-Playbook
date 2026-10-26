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


class TestOrchestratorMultiSvm(unittest.TestCase):
    """When no svm_uuid is given, the orchestrator discovers every SVM and runs the
    per-SVM patterns once per SVM, keeping the DESIGN.md dependency order."""

    def _multi_svm_client(self):
        svm_a, svm_b = "svm-a", "svm-b"
        return RecordingClient(
            {
                # Discovery: two SVMs on the file system.
                "/svm/svms": {
                    "records": [
                        {"uuid": svm_a, "name": "svmA"},
                        {"uuid": svm_b, "name": "svmB"},
                    ]
                },
                # Cluster-wide reads.
                "/snapmirror/relationships": {"records": []},
                "/storage/flexcache/flexcaches": {"records": []},
                "/storage/volumes": {
                    "records": [
                        {
                            "uuid": "clone-eda",
                            "name": "eda_demo_vol_clone",
                            "svm": {"uuid": svm_a, "name": "svmA"},
                            "clone": {
                                "is_flexclone": True,
                                "parent_volume": {"name": "eda_demo_vol"},
                            },
                        },
                    ]
                },
                # S3: discovered cluster-wide in one pass. The stuck bucket is backed
                # by a FLEXGROUP volume and lives on svm-a; the cluster-wide record
                # carries its own svm.uuid/name and backing volume.name.
                "/protocols/s3/buckets": {
                    "records": [
                        {
                            "uuid": "b-oss",
                            "name": "fg_oss_1779804873",
                            "svm": {"uuid": svm_a, "name": "svmA"},
                            "volume": {"name": "fg_oss_1779804873", "uuid": "vol-fg"},
                        }
                    ]
                },
                f"/protocols/audit/{svm_a}": {"enabled": True},
                f"/protocols/fpolicy/{svm_a}/policies": {"records": [{"name": "pol"}]},
                f"/protocols/fpolicy/{svm_a}/events": {"records": []},
                f"/protocols/fpolicy/{svm_a}/engines": {"records": []},
                f"/protocols/fpolicy/{svm_a}/persistent-stores": {
                    "records": [{"name": "fpolicy_persistent_store"}]
                },
                f"/svm/svms/{svm_a}": {"name": "svmA"},
                f"/svm/svms/{svm_b}": {"name": "svmB"},
            }
        )

    def test_plan_fans_out_per_svm_in_dependency_order(self):
        client = self._multi_svm_client()
        steps = orchestrator.plan(client)
        names = [s["pattern"] for s in steps]
        # snapmirror (1), flexclone (1), s3 cluster-wide (1), then audit/fpolicy once
        # per SVM (2 each), flexcache (1), volume (1), svm_delete once per SVM (2).
        self.assertEqual(
            names,
            [
                "snapmirror_release",
                "flexclone_split_delete",
                "s3bucket_delete",
                "audit_redirect",
                "audit_redirect",
                "fpolicy_teardown",
                "fpolicy_teardown",
                "flexcache_delete",
                "volume_delete",
                "svm_delete",
                "svm_delete",
            ],
        )
        # Discovery used GET /svm/svms.
        self.assertIn("/svm/svms", client.paths("GET"))

    def test_plan_is_read_only_across_svms(self):
        client = self._multi_svm_client()
        orchestrator.plan(client)
        self.assertEqual(client.paths("DELETE"), [])
        self.assertEqual(client.paths("POST"), [])
        self.assertEqual(client.paths("PATCH"), [])

    def test_plan_discovers_the_known_stuck_objects(self):
        client = self._multi_svm_client()
        steps = orchestrator.plan(client)
        by_pattern: dict[str, list] = {}
        for s in steps:
            by_pattern.setdefault(s["pattern"], []).extend(s["targets"])
        # FlexClone discovered FS-wide (no parent given).
        clone_names = [t.get("name") for t in by_pattern["flexclone_split_delete"]]
        self.assertIn("eda_demo_vol_clone", clone_names)
        # S3 bucket discovered per SVM.
        bucket_names = [t.get("name") for t in by_pattern["s3bucket_delete"]]
        self.assertIn("fg_oss_1779804873", bucket_names)
        # FPolicy persistent store discovered and present as a target.
        fpolicy_kinds = {t.get("kind") for t in by_pattern["fpolicy_teardown"]}
        self.assertIn("fpolicy-persistent-store", fpolicy_kinds)

    def test_targets_carry_svm_identity_for_traceability(self):
        client = self._multi_svm_client()
        steps = orchestrator.plan(client)
        for s in steps:
            for t in s["targets"]:
                # Every per-SVM target carries its svm uuid for traceability.
                if s["pattern"] in (
                    "s3bucket_delete",
                    "audit_redirect",
                    "fpolicy_teardown",
                    "svm_delete",
                ):
                    self.assertIn("svm_uuid", t)
                    self.assertIsNotNone(t["svm_uuid"])
                    # svm_name resolved from discovery.
                    self.assertIn("svm_name", t)

    def test_single_svm_scope_keeps_one_of_each_pattern(self):
        """When svm_uuid IS given, the single-SVM behavior (one of each) is kept."""
        client = RecordingClient(
            {
                "/snapmirror/relationships": {"records": []},
                "/storage/volumes": {"records": []},
                "/protocols/s3/buckets": {"records": []},
                f"/protocols/audit/{SVM}": {},
                f"/protocols/fpolicy/{SVM}/policies": {"records": []},
                f"/protocols/fpolicy/{SVM}/events": {"records": []},
                f"/protocols/fpolicy/{SVM}/engines": {"records": []},
                f"/protocols/fpolicy/{SVM}/persistent-stores": {"records": []},
                "/storage/flexcache/flexcaches": {"records": []},
                f"/svm/svms/{SVM}": {"name": "svm1"},
            }
        )
        steps = orchestrator.plan(client, svm_uuid=SVM, svm_name="svm1")
        self.assertEqual([s["pattern"] for s in steps], EXPECTED_ORDER)
        # No discovery call when scope is explicit.
        self.assertNotIn("/svm/svms", client.paths("GET"))


class TestHandlerMaintenanceGate(unittest.TestCase):
    """Maintenance operations are gated by assert_maintenance_allowed, not
    assert_in_scope: allowed when the FS is in the maintenance list OR the
    allowlist, refused otherwise. Teardown (no operation) stays on the allowlist,
    and the keep-list still protects a FS from teardown."""

    def _client(self):
        # The maintenance ops the handler dispatches read/write via the recorded
        # verbs; empty GET responses are fine for a shape assertion.
        return RecordingClient(
            {
                "/private/cli/volume/recovery-queue": {"records": []},
                "/private/cli/vserver/peer": {"records": []},
            }
        )

    def test_maintenance_allowed_when_fs_in_maintenance_list(self):
        client = self._client()
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": FS}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "purge_recovery_queue",
                    "svm_name": "svm1",
                    "volume": "vol_clone",
                    "secret_id": "s",
                }
            )
        self.assertEqual(result["status"], "maintenance")
        self.assertEqual(result["operation"], "purge_recovery_queue")
        # The POST body carries the attributes (not the query), per the CLI rule.
        self.assertIn(
            (
                "POST",
                "/private/cli/volume/recovery-queue/purge",
                {"vserver": "svm1", "volume": "vol_clone"},
            ),
            client.calls,
        )

    def test_maintenance_allowed_when_fs_in_allowlist(self):
        client = self._client()
        env = {"ONTAP_OPS_ALLOWLIST": FS}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "maintenance_plan",
                    "secret_id": "s",
                }
            )
        self.assertEqual(result["status"], "maintenance")
        self.assertEqual(result["operation"], "maintenance_plan")
        # maintenance_plan is read-only: no DELETE/POST/PATCH issued.
        self.assertEqual(client.paths("DELETE"), [])
        self.assertEqual(client.paths("POST"), [])
        self.assertEqual(client.paths("PATCH"), [])

    def test_maintenance_refused_when_fs_in_neither_list(self):
        env = {"ONTAP_OPS_ALLOWLIST": OTHER_FS}
        with mock.patch.dict(os.environ, env, clear=True):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "delete_vserver_peer",
                    "svm_name": "svm1",
                    "peer_vserver": "peer1",
                }
            )
        self.assertEqual(result["status"], "refused")

    def test_maintenance_list_does_not_permit_teardown(self):
        """A FS only in the maintenance list is refused for teardown (no operation)."""
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": FS}
        with mock.patch.dict(os.environ, env, clear=True):
            result = handler_module.handler({"file_system_id": FS, "secret_id": "s"})
        # Teardown uses assert_in_scope (allowlist), which is empty here.
        self.assertEqual(result["status"], "refused")

    def test_keep_list_still_protects_teardown_even_if_in_maintenance(self):
        """keep-list refuses teardown even when the FS is also in the maintenance
        list; maintenance membership never opens a teardown path."""
        env = {
            "ONTAP_OPS_ALLOWLIST": FS,
            "ONTAP_OPS_KEEP_LIST": FS,
            "ONTAP_OPS_MAINTENANCE_FSIDS": FS,
        }
        with mock.patch.dict(os.environ, env, clear=True):
            result = handler_module.handler({"file_system_id": FS, "secret_id": "s"})
        self.assertEqual(result["status"], "refused")

    def test_unknown_operation_is_an_error(self):
        client = self._client()
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": FS}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "cli_vol",  # a removed debug dump name
                    "secret_id": "s",
                }
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("unknown maintenance operation", result["error"])

    def test_snapmirror_delete_body_shape(self):
        client = self._client()
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": FS}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "snapmirror_delete",
                    "destination_path": "svmB:dst_vol",
                    "secret_id": "s",
                }
            )
        self.assertEqual(result["status"], "maintenance")
        # delete is keyed on destination-path in the BODY (relationship-id not used).
        self.assertIn(
            (
                "POST",
                "/private/cli/snapmirror/delete",
                {"destination-path": "svmB:dst_vol"},
            ),
            client.calls,
        )

    def test_delete_vserver_peer_query_shape(self):
        client = self._client()
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": FS}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "delete_vserver_peer",
                    "svm_name": "svm1",
                    "peer_vserver": "peer1",
                    "secret_id": "s",
                }
            )
        # Collection DELETE is query-based (attribute match in the query string).
        self.assertIn(
            "/private/cli/vserver/peer?vserver=svm1&peer-vserver=peer1",
            client.paths("DELETE"),
        )

    def test_missing_required_field_is_an_error(self):
        client = self._client()
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": FS}
        with (
            mock.patch.dict(os.environ, env, clear=True),
            mock.patch.object(handler_module, "_build_client", lambda *a, **k: client),
        ):
            result = handler_module.handler(
                {
                    "file_system_id": FS,
                    "operation": "purge_recovery_queue",
                    "svm_name": "svm1",  # missing "volume"
                    "secret_id": "s",
                }
            )
        self.assertEqual(result["status"], "error")
        self.assertIn("missing required field", result["error"])


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
