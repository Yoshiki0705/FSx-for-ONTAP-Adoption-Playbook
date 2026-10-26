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
from ontap_ops.shared.ontap_client import OntapClientError

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

    def test_flexclone_fs_wide_discovery_when_no_parent(self):
        """With no parent_volume_name, clones are discovered file-system-wide.

        The volumes-with-clone query returns a mix; only clone.is_flexclone == true
        rows become targets. A non-clone row and a clone with is_flexclone false are
        dropped. The svm uuid/name and parent name ride along for traceability.
        """
        client = RecordingClient(
            {
                "/storage/volumes": {
                    "records": [
                        {
                            "uuid": "clone-1",
                            "name": "eda_demo_vol_clone",
                            "svm": {"uuid": "svm-a", "name": "svmA"},
                            "clone": {
                                "is_flexclone": True,
                                "parent_volume": {"name": "eda_demo_vol"},
                            },
                        },
                        {
                            "uuid": "plain-1",
                            "name": "plain_vol",
                        },
                        {
                            "uuid": "notclone-1",
                            "name": "not_a_clone",
                            "clone": {"is_flexclone": False},
                        },
                    ]
                }
            }
        )
        pattern = FlexCloneSplitDelete(client, parent_volume_name=None, split=False)
        targets = pattern.resolve_dependencies()
        # Only the real FlexClone is a target; the FS-wide query was used.
        self.assertIn(
            ("/storage/volumes", {"fields": "name,uuid,svm,clone"}),
            [(p, b) for (m, p, b) in client.calls if m == "GET"],
        )
        self.assertEqual([t["uuid"] for t in targets], ["clone-1"])
        self.assertEqual(targets[0]["svm_uuid"], "svm-a")
        self.assertEqual(targets[0]["svm_name"], "svmA")
        self.assertEqual(targets[0]["parent_volume_name"], "eda_demo_vol")
        pattern.delete()
        self.assertIn("/storage/volumes/clone-1", client.paths("DELETE"))

    def test_flexclone_parent_filter_still_scopes_query(self):
        """A supplied parent_volume_name keeps the narrow per-parent query."""
        client = RecordingClient(
            {"/storage/volumes": {"records": [{"uuid": "clone-1", "name": "c1"}]}}
        )
        pattern = FlexCloneSplitDelete(client, parent_volume_name="parent")
        pattern.resolve_dependencies()
        get_bodies = [b for (m, p, b) in client.calls if m == "GET"]
        self.assertIn({"clone.parent_volume.name": "parent"}, get_bodies)

    def test_s3bucket_delete_path(self):
        client = RecordingClient(
            {"/protocols/s3/buckets": {"records": [{"uuid": "b-1", "name": "bucket1"}]}}
        )
        pattern = S3BucketDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertIn(f"/protocols/s3/buckets/{SVM}/b-1", client.paths("DELETE"))

    def test_s3bucket_cluster_wide_finds_bucket_on_other_svm(self):
        """Cluster-wide discovery finds a bucket on an SVM != a passed svm_uuid.

        The stuck bucket (fg_oss, backed by a FLEXGROUP volume) lives on svm-b, but
        the per-SVM pass would have looked at svm-a. Cluster-wide list_all_s3_buckets
        surfaces it, and the target carries svm-b (its own svm.uuid), the bucket name,
        uuid, and the backing volume.name for traceability.
        """
        client = RecordingClient(
            {
                "/protocols/s3/buckets": {
                    "records": [
                        {
                            "uuid": "b-oss",
                            "name": "fg_oss_1779804873",
                            "svm": {"uuid": "svm-b", "name": "svmB"},
                            "volume": {
                                "name": "fg_oss_1779804873",
                                "uuid": "vol-fg",
                            },
                        }
                    ]
                }
            }
        )
        # cluster_wide mode; no per-SVM scope is passed.
        pattern = S3BucketDelete(client, cluster_wide=True)
        targets = pattern.resolve_dependencies()
        # The cluster-wide list endpoint (no svm.uuid filter) was used.
        self.assertIn(
            (
                "/protocols/s3/buckets",
                {"fields": "name,uuid,svm.uuid,svm.name,volume.name,volume.uuid"},
            ),
            [(p, b) for (m, p, b) in client.calls if m == "GET"],
        )
        self.assertEqual(len(targets), 1)
        t = targets[0]
        self.assertEqual(t["uuid"], "b-oss")
        self.assertEqual(t["name"], "fg_oss_1779804873")
        # The target carries its OWN svm_uuid (svm-b), not any passed scope.
        self.assertEqual(t["svm_uuid"], "svm-b")
        self.assertEqual(t["svm_name"], "svmB")
        self.assertEqual(t["volume_name"], "fg_oss_1779804873")

    def test_s3bucket_delete_uses_each_targets_own_svm_uuid(self):
        """The DELETE path keys on the bucket's own svm.uuid, not self.svm_uuid.

        Two buckets on two different SVMs must each be deleted via their own SVM path,
        even though the pattern instance has no single scope (cluster-wide).
        """
        client = RecordingClient(
            {
                "/protocols/s3/buckets": {
                    "records": [
                        {
                            "uuid": "b-a",
                            "name": "bucket-a",
                            "svm": {"uuid": "svm-a", "name": "svmA"},
                        },
                        {
                            "uuid": "b-b",
                            "name": "bucket-b",
                            "svm": {"uuid": "svm-b", "name": "svmB"},
                        },
                    ]
                }
            }
        )
        pattern = S3BucketDelete(client, cluster_wide=True)
        pattern.resolve_dependencies()
        pattern.delete()
        deletes = client.paths("DELETE")
        self.assertIn("/protocols/s3/buckets/svm-a/b-a", deletes)
        self.assertIn("/protocols/s3/buckets/svm-b/b-b", deletes)

    def test_s3bucket_per_bucket_403_is_recorded_and_does_not_abort(self):
        """A per-bucket 403 is caught inside the pattern, recorded, and does not raise.

        On an AD-joined SVM with unreachable DCs, a bucket DELETE can return 403 at the
        FS layer even for a correct request. The pattern records that target as
        access_denied_possibly_ad_unreachable and CONTINUES with the others, rather
        than raising to the handler's global auth-abort (which is only for login 401).
        """

        class DenyFirstClient(RecordingClient):
            def delete_s3_bucket(self, svm_uuid, bucket_uuid):
                self.calls.append(
                    ("DELETE", f"/protocols/s3/buckets/{svm_uuid}/{bucket_uuid}", None)
                )
                if bucket_uuid == "b-denied":
                    raise OntapClientError(
                        "AccessDenied", status_code=403, response_body=None
                    )
                return {}

        client = DenyFirstClient(
            {
                "/protocols/s3/buckets": {
                    "records": [
                        {
                            "uuid": "b-denied",
                            "name": "ad-joined-bucket",
                            "svm": {"uuid": "svm-ad", "name": "svmAD"},
                        },
                        {
                            "uuid": "b-ok",
                            "name": "plain-bucket",
                            "svm": {"uuid": "svm-ok", "name": "svmOK"},
                        },
                    ]
                }
            }
        )
        pattern = S3BucketDelete(client, cluster_wide=True)
        pattern.resolve_dependencies()
        # Must NOT raise; the 403 is handled inside the pattern.
        results = pattern.delete()
        by_uuid = {r["uuid"]: r for r in results}
        self.assertEqual(
            by_uuid["b-denied"]["result"], "access_denied_possibly_ad_unreachable"
        )
        self.assertEqual(by_uuid["b-denied"]["svm"], "svm-ad")
        self.assertEqual(by_uuid["b-denied"]["status_code"], 403)
        # The other bucket was still deleted (run continued).
        self.assertIn("/protocols/s3/buckets/svm-ok/b-ok", client.paths("DELETE"))

    def test_s3bucket_cluster_wide_dedups_by_uuid(self):
        """A bucket listed twice (e.g. per-SVM + cluster-wide) is a single target."""
        client = RecordingClient(
            {
                "/protocols/s3/buckets": {
                    "records": [
                        {
                            "uuid": "b-dup",
                            "name": "dup",
                            "svm": {"uuid": "svm-a", "name": "svmA"},
                        },
                        {
                            "uuid": "b-dup",
                            "name": "dup",
                            "svm": {"uuid": "svm-a", "name": "svmA"},
                        },
                    ]
                }
            }
        )
        pattern = S3BucketDelete(client, cluster_wide=True)
        targets = pattern.resolve_dependencies()
        self.assertEqual([t["uuid"] for t in targets], ["b-dup"])
        pattern.delete()
        self.assertEqual(client.paths("DELETE"), ["/protocols/s3/buckets/svm-a/b-dup"])

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
                f"/protocols/fpolicy/{SVM}/persistent-stores": {
                    "records": [{"name": "ps1"}]
                },
            }
        )
        pattern = FPolicyTeardown(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        deletes = client.paths("DELETE")
        # Proven teardown order: policy -> event -> engine -> persistent-store.
        # The persistent store backs the fpolicy_persistent_store volume, so it must
        # be deleted last, after everything that references it.
        self.assertEqual(
            deletes,
            [
                f"/protocols/fpolicy/{SVM}/policies/pol",
                f"/protocols/fpolicy/{SVM}/events/evt",
                f"/protocols/fpolicy/{SVM}/engines/eng",
                f"/protocols/fpolicy/{SVM}/persistent-stores/ps1",
            ],
        )
        # And the policy was disabled before deletion.
        patch_bodies = [b for (m, p, b) in client.calls if m == "PATCH"]
        self.assertIn({"enabled": False}, patch_bodies)

    def test_fpolicy_persistent_store_only_after_engines(self):
        """Persistent store is deleted strictly after any engine delete.

        Even when policies/events are empty, if an engine and a store both exist the
        engine delete must precede the store delete. Guards the ordering contract
        against a future reorder.
        """
        client = RecordingClient(
            {
                f"/protocols/fpolicy/{SVM}/policies": {"records": []},
                f"/protocols/fpolicy/{SVM}/events": {"records": []},
                f"/protocols/fpolicy/{SVM}/engines": {"records": [{"name": "eng"}]},
                f"/protocols/fpolicy/{SVM}/persistent-stores": {
                    "records": [{"name": "ps1"}]
                },
            }
        )
        pattern = FPolicyTeardown(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        deletes = client.paths("DELETE")
        engine_idx = deletes.index(f"/protocols/fpolicy/{SVM}/engines/eng")
        store_idx = deletes.index(f"/protocols/fpolicy/{SVM}/persistent-stores/ps1")
        self.assertLess(engine_idx, store_idx)

    def test_fpolicy_no_persistent_store_when_none(self):
        """No persistent-store delete is issued when the SVM has none."""
        client = RecordingClient(
            {
                f"/protocols/fpolicy/{SVM}/policies": {"records": [{"name": "pol"}]},
                f"/protocols/fpolicy/{SVM}/events": {"records": []},
                f"/protocols/fpolicy/{SVM}/engines": {"records": []},
                f"/protocols/fpolicy/{SVM}/persistent-stores": {"records": []},
            }
        )
        pattern = FPolicyTeardown(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        pattern.delete()
        store_deletes = [p for p in client.paths("DELETE") if "persistent-stores" in p]
        self.assertEqual(store_deletes, [])

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


class TestDeleteIsIdempotent(unittest.TestCase):
    """An "already absent" delete is recorded as absent and the loop continues.

    A partial prior teardown may have already deleted an object. ONTAP reports that
    as HTTP 404 OR as 200/400/500 with a message like "doesn't exist". The per-target
    delete must record such a target as absent and keep going to the next target, not
    abort the whole run. Each case drives both a message-phrase error and a 404 error,
    and asserts the SECOND target is still deleted.
    """

    @staticmethod
    def _absent_message_error() -> OntapClientError:
        # ontap_message reads error.message from response_body; this makes the phrase
        # "doesn't exist" reach _is_already_absent_error without a 404 status.
        return OntapClientError(
            "delete failed",
            status_code=400,
            response_body='{"error": {"message": "volume \\"x\\" doesn\'t exist"}}',
        )

    @staticmethod
    def _absent_404_error() -> OntapClientError:
        return OntapClientError("not found", status_code=404, response_body=None)

    def _assert_absent_then_continue(
        self, pattern, results, first_path, second_path, client
    ):
        by = {r.get("uuid"): r for r in results}
        # The already-absent first target is recorded as absent (idempotent success).
        self.assertEqual(by[first_path]["result"], "absent")
        # The loop continued: the second target was still deleted.
        self.assertIn(second_path, client.paths("DELETE"))

    def test_volume_delete_absent_message_continues(self):
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        "/storage/volumes": {
                            "records": [
                                {"uuid": "v-gone", "name": "gone"},
                                {"uuid": "v-live", "name": "live"},
                            ]
                        }
                    },
                    raise_on={("DELETE", "/storage/volumes/v-gone"): make_err()},
                )
                pattern = VolumeDelete(client, svm_uuid=SVM)
                pattern.resolve_dependencies()
                results = pattern.delete()  # must not raise
                self._assert_absent_then_continue(
                    pattern,
                    results,
                    "v-gone",
                    "/storage/volumes/v-live",
                    client,
                )

    def test_flexcache_delete_absent_continues(self):
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        f"/svm/svms/{SVM}": {"name": "svm1"},
                        "/storage/flexcache/flexcaches": {
                            "records": [
                                {"uuid": "fc-gone", "name": "gone"},
                                {"uuid": "fc-live", "name": "live"},
                            ]
                        },
                    },
                    raise_on={
                        (
                            "DELETE",
                            "/storage/flexcache/flexcaches/fc-gone",
                        ): make_err()
                    },
                )
                pattern = FlexCacheDelete(client, svm_uuid=SVM)
                pattern.resolve_dependencies()
                results = pattern.delete()
                self._assert_absent_then_continue(
                    pattern,
                    results,
                    "fc-gone",
                    "/storage/flexcache/flexcaches/fc-live",
                    client,
                )

    def test_svm_delete_absent_continues(self):
        # SvmDelete has a single target (the SVM), so "continue" here means the call
        # is recorded as absent rather than raising.
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        "/storage/volumes": {"records": []},
                        f"/svm/svms/{SVM}": {"name": "svm1"},
                    },
                    raise_on={("DELETE", f"/svm/svms/{SVM}"): make_err()},
                )
                pattern = SvmDelete(client, svm_uuid=SVM)
                pattern.resolve_dependencies()
                results = pattern.delete()  # must not raise
                self.assertEqual(results[0]["result"], "absent")
                self.assertIn(f"/svm/svms/{SVM}", client.paths("DELETE"))

    def test_snapmirror_release_absent_continues(self):
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        "/snapmirror/relationships": {
                            "records": [{"uuid": "sm-gone"}, {"uuid": "sm-live"}]
                        }
                    },
                    raise_on={
                        ("DELETE", "/snapmirror/relationships/sm-gone"): make_err()
                    },
                )
                pattern = SnapMirrorRelease(client, svm_uuid=SVM)
                pattern.resolve_dependencies()
                results = pattern.delete()
                self._assert_absent_then_continue(
                    pattern,
                    results,
                    "sm-gone",
                    "/snapmirror/relationships/sm-live",
                    client,
                )

    def test_flexclone_split_delete_absent_continues(self):
        # split=True exercises both calls; the "already absent" surfaces on the volume
        # delete of the first clone, and the second clone is still deleted.
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        "/storage/volumes": {
                            "records": [
                                {"uuid": "clone-gone", "name": "cg"},
                                {"uuid": "clone-live", "name": "cl"},
                            ]
                        }
                    },
                    raise_on={("DELETE", "/storage/volumes/clone-gone"): make_err()},
                )
                pattern = FlexCloneSplitDelete(
                    client, parent_volume_name="parent", split=True
                )
                pattern.resolve_dependencies()
                results = pattern.delete()
                self._assert_absent_then_continue(
                    pattern,
                    results,
                    "clone-gone",
                    "/storage/volumes/clone-live",
                    client,
                )

    def test_flexclone_split_absent_on_split_call_continues(self):
        # When the clone is already gone, the split PATCH itself can report absent.
        # That too must be tolerated (record absent, continue), not raise.
        err = self._absent_message_error()
        client = RecordingClient(
            {
                "/storage/volumes": {
                    "records": [
                        {"uuid": "clone-gone", "name": "cg"},
                        {"uuid": "clone-live", "name": "cl"},
                    ]
                }
            },
            raise_on={("PATCH", "/storage/volumes/clone-gone"): err},
        )
        pattern = FlexCloneSplitDelete(client, parent_volume_name="parent", split=True)
        pattern.resolve_dependencies()
        results = pattern.delete()
        by = {r.get("uuid"): r for r in results}
        self.assertEqual(by["clone-gone"]["result"], "absent")
        self.assertIn("/storage/volumes/clone-live", client.paths("DELETE"))

    def test_fpolicy_teardown_absent_continues(self):
        # The policy delete reports already-absent; the event, engine, and store
        # deletes must still be issued in order.
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        f"/protocols/fpolicy/{SVM}/policies": {
                            "records": [{"name": "pol"}]
                        },
                        f"/protocols/fpolicy/{SVM}/events": {
                            "records": [{"name": "evt"}]
                        },
                        f"/protocols/fpolicy/{SVM}/engines": {
                            "records": [{"name": "eng"}]
                        },
                        f"/protocols/fpolicy/{SVM}/persistent-stores": {
                            "records": [{"name": "ps1"}]
                        },
                    },
                    raise_on={
                        (
                            "DELETE",
                            f"/protocols/fpolicy/{SVM}/policies/pol",
                        ): make_err()
                    },
                )
                pattern = FPolicyTeardown(client, svm_uuid=SVM)
                pattern.resolve_dependencies()
                results = pattern.delete()  # must not raise
                by_name = {r.get("name"): r for r in results}
                self.assertEqual(by_name["pol"]["result"], "absent")
                deletes = client.paths("DELETE")
                # Dependency order preserved for the remaining targets.
                self.assertEqual(
                    deletes,
                    [
                        f"/protocols/fpolicy/{SVM}/policies/pol",
                        f"/protocols/fpolicy/{SVM}/events/evt",
                        f"/protocols/fpolicy/{SVM}/engines/eng",
                        f"/protocols/fpolicy/{SVM}/persistent-stores/ps1",
                    ],
                )

    def test_s3bucket_delete_absent_continues(self):
        # The AD-unreachable 401/403 path is unchanged; a genuine already-absent
        # (404 or phrase) is now also recorded as absent, and the run continues.
        for make_err in (self._absent_message_error, self._absent_404_error):
            with self.subTest(error=make_err.__name__):
                client = RecordingClient(
                    {
                        "/protocols/s3/buckets": {
                            "records": [
                                {
                                    "uuid": "b-gone",
                                    "name": "gone",
                                    "svm": {"uuid": "svm-a", "name": "svmA"},
                                },
                                {
                                    "uuid": "b-live",
                                    "name": "live",
                                    "svm": {"uuid": "svm-b", "name": "svmB"},
                                },
                            ]
                        }
                    },
                    raise_on={
                        (
                            "DELETE",
                            "/protocols/s3/buckets/svm-a/b-gone",
                        ): make_err()
                    },
                )
                pattern = S3BucketDelete(client, cluster_wide=True)
                pattern.resolve_dependencies()
                results = pattern.delete()  # must not raise
                by = {r.get("uuid"): r for r in results}
                self.assertEqual(by["b-gone"]["result"], "absent")
                self.assertIn(
                    "/protocols/s3/buckets/svm-b/b-live", client.paths("DELETE")
                )


class TestGenuineErrorStillRaises(unittest.TestCase):
    """A real error (not already-absent, not s3 access-denied) must still raise.

    Idempotence must not swallow a genuine failure; a 500 with an unrelated message
    stays visible so a real teardown problem surfaces instead of being logged as done.
    """

    @staticmethod
    def _real_error() -> OntapClientError:
        return OntapClientError(
            "boom",
            status_code=500,
            response_body='{"error": {"message": "internal volume busy"}}',
        )

    def test_volume_delete_records_real_error_and_continues(self):
        # volume_delete は 1 本が消せなくても（不可視クローン依存など）残りを進める。
        # 本物のエラーは握りつぶさず result="error" として可視化し、次の対象へ続行する。
        client = RecordingClient(
            {
                "/storage/volumes": {
                    "records": [
                        {"uuid": "v-1", "name": "v1"},
                        {"uuid": "v-2", "name": "v2"},
                    ]
                }
            },
            raise_on={("DELETE", "/storage/volumes/v-1"): self._real_error()},
        )
        pattern = VolumeDelete(client, svm_uuid=SVM)
        pattern.resolve_dependencies()
        results = pattern.delete()
        by_uuid = {r["uuid"]: r for r in results}
        # v-1 はエラーとして記録され、ONTAP のメッセージを保持する。
        self.assertEqual(by_uuid["v-1"]["result"], "error")
        self.assertIn("internal volume busy", by_uuid["v-1"]["error"])
        # v-2 の削除は v-1 の失敗に妨げられず実行される。
        self.assertIn(("DELETE", "/storage/volumes/v-2", None), client.calls)

    def test_s3bucket_delete_reraises_real_error(self):
        client = RecordingClient(
            {
                "/protocols/s3/buckets": {
                    "records": [
                        {
                            "uuid": "b-1",
                            "name": "b1",
                            "svm": {"uuid": "svm-a", "name": "svmA"},
                        }
                    ]
                }
            },
            raise_on={
                ("DELETE", "/protocols/s3/buckets/svm-a/b-1"): self._real_error()
            },
        )
        pattern = S3BucketDelete(client, cluster_wide=True)
        pattern.resolve_dependencies()
        with self.assertRaises(OntapClientError):
            pattern.delete()


if __name__ == "__main__":
    unittest.main()
