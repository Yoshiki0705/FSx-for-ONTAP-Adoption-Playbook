"""Maintenance / CLI-passthrough operation tests.

Covers the reusable operations discovered against a live cluster, now first-class:
  - recovery-queue purge path (body shape),
  - SnapMirror source-side release/delete body shapes,
  - vserver peer delete query shape,
  - the flexclone has_flexclone -> recovery-queue fallback, and
  - the snapmirror source-side release wired through the pattern.

The CLI passthrough body-vs-query rule is the invariant under test: POST carries its
attributes in the BODY, GET and collection DELETE use the query string. Each test
drives the pattern/dispatch against the RecordingClient and asserts the exact
(method, path, body) assembled, the same way DESIGN.md's path assertions work.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _bootstrap  # noqa: F401  (loads the ontap_ops package by path)
from fake_client import RecordingClient
from ontap_ops.patterns.flexclone_split_delete import FlexCloneSplitDelete
from ontap_ops.patterns.snapmirror_release import SnapMirrorRelease
from ontap_ops.shared.ontap_client import OntapClientError

SVM = "svm-uuid-1"


class TestRecoveryQueueFallback(unittest.TestCase):
    """When a parent reports has_flexclone but the structured REST clone query
    returns nothing, the pattern falls back to `volume clone show` (CLI) and purges
    the named clone from the recovery queue."""

    def test_fallback_purges_cli_visible_clone(self):
        client = RecordingClient(
            {
                # Structured REST sees no clone for the parent.
                "/storage/volumes": {"records": []},
                # But `volume clone show` (CLI) lists a stale clone.
                "/private/cli/volume/clone": {
                    "records": [
                        {"volume": "eda_demo_vol_clone", "vserver": "svmA"},
                    ]
                },
            }
        )
        pattern = FlexCloneSplitDelete(
            client, parent_volume_name="eda_demo_vol", split=False
        )
        targets = pattern.resolve_dependencies()
        # One recovery-queue-clone target discovered via the CLI fallback.
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["kind"], "recovery-queue-clone")
        self.assertEqual(targets[0]["name"], "eda_demo_vol_clone")
        self.assertEqual(targets[0]["vserver"], "svmA")
        # The CLI `volume clone show` GET was issued with parent-volume in the query.
        self.assertIn(
            ("/private/cli/volume/clone", {"parent-volume": "eda_demo_vol"}),
            [(p, b) for (m, p, b) in client.calls if m == "GET"],
        )
        pattern.delete()
        # purge is a POST with vserver+volume in the BODY (not the query).
        self.assertIn(
            (
                "POST",
                "/private/cli/volume/recovery-queue/purge",
                {"vserver": "svmA", "volume": "eda_demo_vol_clone"},
            ),
            client.calls,
        )

    def test_structured_clone_present_skips_fallback(self):
        """A structured clone is handled the normal way; no CLI/recovery-queue call."""
        client = RecordingClient(
            {
                "/storage/volumes": {"records": [{"uuid": "clone-1", "name": "c1"}]},
            }
        )
        pattern = FlexCloneSplitDelete(client, parent_volume_name="parent", split=False)
        targets = pattern.resolve_dependencies()
        self.assertEqual([t["uuid"] for t in targets], ["clone-1"])
        # No CLI clone-show, no recovery-queue purge.
        self.assertNotIn("/private/cli/volume/clone", client.paths("GET"))
        pattern.delete()
        self.assertNotIn(
            "/private/cli/volume/recovery-queue/purge", client.paths("POST")
        )
        self.assertIn("/storage/volumes/clone-1", client.paths("DELETE"))

    def test_fallback_only_when_parent_name_given(self):
        """With no parent name, the pattern never falls back (which parent is
        ambiguous). FS-wide discovery with no clones yields no targets."""
        client = RecordingClient({"/storage/volumes": {"records": []}})
        pattern = FlexCloneSplitDelete(client, parent_volume_name=None, split=False)
        targets = pattern.resolve_dependencies()
        self.assertEqual(targets, [])
        self.assertNotIn("/private/cli/volume/clone", client.paths("GET"))

    def test_recovery_purge_absent_is_idempotent(self):
        """An already-absent recovery-queue clone is recorded absent, not raised."""
        err = OntapClientError(
            "purge failed",
            status_code=400,
            response_body='{"error": {"message": "no entries matching"}}',
        )
        client = RecordingClient(
            {
                "/storage/volumes": {"records": []},
                "/private/cli/volume/clone": {
                    "records": [{"volume": "c_clone", "vserver": "svmA"}]
                },
            },
            raise_on={("POST", "/private/cli/volume/recovery-queue/purge"): err},
        )
        pattern = FlexCloneSplitDelete(client, parent_volume_name="parent", split=False)
        pattern.resolve_dependencies()
        results = pattern.delete()  # must not raise
        self.assertEqual(results[0]["result"], "absent")


class TestSnapMirrorSourceRelease(unittest.TestCase):
    """With an svm_name, the snapmirror_release pattern also releases source-side
    relationships (visible only via the CLI list-destinations by source), so a
    source volume can be deleted."""

    def test_source_side_release_wired_in(self):
        client = RecordingClient(
            {
                # No destination-side structured relationships.
                "/snapmirror/relationships": {"records": []},
                # But the source SVM has a surviving source-side destination.
                "/private/cli/snapmirror/list-destinations": {
                    "records": [
                        {
                            "relationship-id": "rid-1",
                            "source-path": "svmA:src_vol",
                            "destination-path": "svmB:dst_vol",
                        }
                    ]
                },
            }
        )
        pattern = SnapMirrorRelease(client, svm_name="svmA")
        targets = pattern.resolve_dependencies()
        # One source-release target discovered via the CLI by-source query.
        kinds = [t["kind"] for t in targets]
        self.assertIn("snapmirror-source-release", kinds)
        # list-destinations was queried by source-vserver (GET + query).
        self.assertIn(
            (
                "/private/cli/snapmirror/list-destinations",
                {
                    "fields": "relationship-id,source-path,destination-path",
                    "source-vserver": "svmA",
                },
            ),
            [(p, b) for (m, p, b) in client.calls if m == "GET"],
        )
        pattern.delete()
        # release is a POST with source-path + relationship-info-only in the BODY.
        self.assertIn(
            (
                "POST",
                "/private/cli/snapmirror/release",
                {"source-path": "svmA:src_vol", "relationship-info-only": True},
            ),
            client.calls,
        )

    def test_no_svm_name_skips_source_side(self):
        """Without svm_name, only structured destination-side relationships are
        handled; no CLI list-destinations by source is issued."""
        client = RecordingClient(
            {"/snapmirror/relationships": {"records": [{"uuid": "sm-1"}]}}
        )
        pattern = SnapMirrorRelease(client)
        pattern.resolve_dependencies()
        pattern.delete()
        self.assertNotIn(
            "/private/cli/snapmirror/list-destinations", client.paths("GET")
        )
        self.assertIn("/snapmirror/relationships/sm-1", client.paths("DELETE"))

    def test_source_release_absent_is_idempotent(self):
        err = OntapClientError("not found", status_code=404, response_body=None)
        client = RecordingClient(
            {
                "/snapmirror/relationships": {"records": []},
                "/private/cli/snapmirror/list-destinations": {
                    "records": [
                        {
                            "relationship-id": "rid-1",
                            "source-path": "svmA:src_vol",
                            "destination-path": "svmB:dst_vol",
                        }
                    ]
                },
            },
            raise_on={("POST", "/private/cli/snapmirror/release"): err},
        )
        pattern = SnapMirrorRelease(client, svm_name="svmA")
        pattern.resolve_dependencies()
        results = pattern.delete()  # must not raise
        by_kind = {r["kind"]: r for r in results}
        self.assertEqual(by_kind["snapmirror-source-release"]["result"], "absent")


class TestSnapMirrorDeleteByDestination(unittest.TestCase):
    def test_delete_body_shape_destination_only(self):
        client = RecordingClient()
        client.delete_snapmirror_by_destination("svmB:dst_vol")
        self.assertIn(
            (
                "POST",
                "/private/cli/snapmirror/delete",
                {"destination-path": "svmB:dst_vol"},
            ),
            client.calls,
        )


class TestVserverPeerDelete(unittest.TestCase):
    def test_delete_is_query_based(self):
        client = RecordingClient()
        client.delete_vserver_peer("svm1", "peer1")
        self.assertEqual(
            client.paths("DELETE"),
            ["/private/cli/vserver/peer?vserver=svm1&peer-vserver=peer1"],
        )


if __name__ == "__main__":
    unittest.main()
