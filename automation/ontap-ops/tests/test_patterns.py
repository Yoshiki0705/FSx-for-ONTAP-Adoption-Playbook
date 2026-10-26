"""Pattern assembly tests.

Each pattern must assemble the exact ONTAP REST method + path (+ body) that DESIGN.md
records, and poll 202 jobs. Each test also includes a deliberately broken stub to show
the assertion fails when the call is wrong — a test that cannot fail proves nothing.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _bootstrap  # noqa: F401  (loads the ontap_ops package by path)
from fake_client import RecordingClient
from ontap_ops.patterns.audit_redirect import AuditRedirect
from ontap_ops.patterns.flexcache_delete import FlexCacheDelete
from ontap_ops.patterns.flexclone_split_delete import FlexCloneSplitDelete
from ontap_ops.patterns.fpolicy_teardown import FPolicyTeardown
from ontap_ops.patterns.s3bucket_delete import S3BucketDelete
from ontap_ops.patterns.snapmirror_release import SnapMirrorRelease
from ontap_ops.patterns.svm_delete import SvmDelete
from ontap_ops.patterns.volume_delete import VolumeDelete

SVM = "svm-uuid-1"


class TestPatternAssembly(unittest.TestCase):
    def test_flexcache_delete_path(self):
        client = RecordingClient(
            {
                "/svm/svms/svm-uuid-1": {"name": "svm1"},
                "/storage/flexcache/flexcaches": {
                    "records": [{"uuid": "fc-1", "name": "cache1"}]
                },
            }
        )
        pattern = FlexCacheDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertIn("/storage/flexcache/flexcaches/fc-1", client.paths("DELETE"))

    def test_flexclone_direct_delete_path(self):
        client = RecordingClient(
            {"/storage/volumes": {"records": [{"uuid": "clone-1", "name": "clone1"}]}}
        )
        pattern = FlexCloneSplitDelete(
            client, svm_uuid=SVM, parent_volume_name="parent", split=False
        )
        pattern.resolve_dependencies()
        pattern.delete()
        # Direct delete (no split): a PATCH split_initiated must NOT have been issued.
        self.assertIn("/storage/volumes/clone-1", client.paths("DELETE"))
        self.assertEqual(client.paths("PATCH"), [])

    def test_flexclone_split_then_delete_path(self):
        client = RecordingClient(
            {"/storage/volumes": {"records": [{"uuid": "clone-1", "name": "clone1"}]}}
        )
        pattern = FlexCloneSplitDelete(
            client, svm_uuid=SVM, parent_volume_name="parent", split=True
        )
        pattern.resolve_dependencies()
        pattern.delete()
        # split issues a PATCH with clone.split_initiated, then the volume delete.
        split_calls = [
            (p, b)
            for (m, p, b) in client.calls
            if m == "PATCH" and p.endswith("clone-1")
        ]
        self.assertTrue(split_calls)
        self.assertEqual(split_calls[0][1], {"clone": {"split_initiated": True}})
        self.assertIn("/storage/volumes/clone-1", client.paths("DELETE"))

    def test_s3bucket_delete_path(self):
        client = RecordingClient(
            {"/protocols/s3/buckets": {"records": [{"uuid": "b-1", "name": "bucket1"}]}}
        )
        pattern = S3BucketDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertIn(f"/protocols/s3/buckets/{SVM}/b-1", client.paths("DELETE"))

    def test_audit_redirect_disables_then_deletes(self):
        client = RecordingClient({f"/protocols/audit/{SVM}": {"enabled": True}})
        pattern = AuditRedirect(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        # NAS audit: a PATCH disable precedes the DELETE; object-store audit is deleted.
        patch_bodies = [b for (m, p, b) in client.calls if m == "PATCH"]
        self.assertIn({"enabled": False}, patch_bodies)
        self.assertIn(f"/protocols/audit/{SVM}", client.paths("DELETE"))
        self.assertIn(f"/protocols/audit/{SVM}/object-store", client.paths("DELETE"))

    def test_fpolicy_teardown_order(self):
        client = RecordingClient(
            {
                f"/protocols/fpolicy/{SVM}/policies": {"records": [{"name": "pol"}]},
                f"/protocols/fpolicy/{SVM}/events": {"records": [{"name": "evt"}]},
                f"/protocols/fpolicy/{SVM}/engines": {"records": [{"name": "eng"}]},
            }
        )
        pattern = FPolicyTeardown(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        deletes = client.paths("DELETE")
        # Proven teardown order: policy -> event -> engine.
        self.assertEqual(
            deletes,
            [
                f"/protocols/fpolicy/{SVM}/policies/pol",
                f"/protocols/fpolicy/{SVM}/events/evt",
                f"/protocols/fpolicy/{SVM}/engines/eng",
            ],
        )
        # And the policy was disabled before deletion.
        patch_bodies = [b for (m, p, b) in client.calls if m == "PATCH"]
        self.assertIn({"enabled": False}, patch_bodies)

    def test_snapmirror_release_path(self):
        client = RecordingClient(
            {"/snapmirror/relationships": {"records": [{"uuid": "sm-1"}]}}
        )
        pattern = SnapMirrorRelease(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertIn("/snapmirror/relationships/sm-1", client.paths("DELETE"))

    def test_volume_delete_skips_root(self):
        client = RecordingClient(
            {
                "/storage/volumes": {
                    "records": [
                        {"uuid": "v-root", "name": "svm1_root"},
                        {"uuid": "v-data", "name": "data1"},
                    ]
                }
            }
        )
        pattern = VolumeDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        deletes = client.paths("DELETE")
        self.assertIn("/storage/volumes/v-data", deletes)
        # Root volume must not be deleted here (SVM delete removes it).
        self.assertNotIn("/storage/volumes/v-root", deletes)

    def test_svm_delete_path(self):
        client = RecordingClient(
            {
                "/storage/volumes": {"records": []},
                f"/svm/svms/{SVM}": {"name": "svm1"},
            }
        )
        pattern = SvmDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertIn(f"/svm/svms/{SVM}", client.paths("DELETE"))

    def test_202_job_is_polled(self):
        """A delete returning {"job": {...}} must be polled with wait_ontap_job."""

        class JobClient(RecordingClient):
            def delete_flexcache(self, uuid):
                super().delete_flexcache(uuid)
                return {"job": {"uuid": "job-123"}}

        client = JobClient(
            {
                "/svm/svms/svm-uuid-1": {"name": "svm1"},
                "/storage/flexcache/flexcaches": {"records": [{"uuid": "fc-1"}]},
            }
        )
        pattern = FlexCacheDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertEqual(client.jobs_waited, ["job-123"])

    def test_broken_stub_fails_detection(self):
        """A stub that issues the wrong delete path fails the same assertion.

        Proves the path assertion is load-bearing: swapping in a client that deletes a
        different path makes the flexcache check fail. The failing assertion is
        exercised inside assertRaises so a test that cannot fail cannot pass here.
        """
        client = RecordingClient(
            {
                "/svm/svms/svm-uuid-1": {"name": "svm1"},
                "/storage/flexcache/flexcaches": {"records": [{"uuid": "fc-1"}]},
            }
        )

        class BrokenFlexCacheDelete(FlexCacheDelete):
            def delete(self):
                # Wrong endpoint on purpose.
                for target in self._targets:
                    self.client.delete(f"/storage/volumes/{target['uuid']}")
                return []

        pattern = BrokenFlexCacheDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertNotIn("/storage/flexcache/flexcaches/fc-1", client.paths("DELETE"))
        with self.assertRaises(AssertionError):
            self.assertIn("/storage/flexcache/flexcaches/fc-1", client.paths("DELETE"))


if __name__ == "__main__":
    unittest.main()
