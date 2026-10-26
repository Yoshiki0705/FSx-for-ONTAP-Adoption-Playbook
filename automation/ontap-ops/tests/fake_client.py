"""A recording fake of OntapClient for pattern tests.

Records every (method, path, body) the patterns issue and returns canned responses,
so tests can assert a pattern assembles the exact ONTAP REST call DESIGN.md records,
without a live cluster. `wait_ontap_job` is stubbed so 202-job polling is exercised in
assembly order without sleeping.
"""

from __future__ import annotations

from typing import Any


class RecordingClient:
    def __init__(
        self,
        get_responses: dict[str, Any] | None = None,
        raise_on: dict[tuple[str, str], Exception] | None = None,
    ):
        # Map of path -> response dict for GET. Missing paths return {} (treated as 404
        # by callers that check status, but here GET returns empty records).
        self.get_responses = get_responses or {}
        # Map of (verb, path) -> exception. When a recorded verb is issued against a
        # matching path, the call is recorded (so ordering/continuation is observable)
        # and then the exception is raised. Lets a test make a specific delete fail
        # (e.g. an "already absent" OntapClientError) without a bespoke subclass.
        self.raise_on = raise_on or {}
        self.calls: list[tuple[str, str, Any]] = []
        self.jobs_waited: list[str] = []

    def _maybe_raise(self, verb: str, path: str) -> None:
        exc = self.raise_on.get((verb, path))
        if exc is not None:
            raise exc

    # --- recording generic verbs ---
    def get(self, path: str, params: dict | None = None) -> dict:
        self.calls.append(("GET", path, params))
        self._maybe_raise("GET", path)
        return self.get_responses.get(path, {})

    def post(self, path: str, body: dict | None = None) -> dict:
        self.calls.append(("POST", path, body))
        self._maybe_raise("POST", path)
        return {}

    def patch(self, path: str, body: dict | None = None) -> dict:
        self.calls.append(("PATCH", path, body))
        self._maybe_raise("PATCH", path)
        return {}

    def delete(self, path: str) -> dict:
        self.calls.append(("DELETE", path, None))
        self._maybe_raise("DELETE", path)
        return {}

    def wait_ontap_job(self, job_uuid: str, **_: Any) -> dict:
        self.jobs_waited.append(job_uuid)
        return {"state": "success", "uuid": job_uuid}

    # --- shortcuts the patterns call (delegate to recorded verbs) ---
    def list_flexcaches(self, name=None, svm_name=None):
        return self.get(
            "/storage/flexcache/flexcaches",
            {"name": name, "svm.name": svm_name},
        ).get("records", [])

    def get_svm(self, svm_uuid):
        return self.get(f"/svm/svms/{svm_uuid}") or {"name": "svm-under-test"}

    def list_svms(self):
        return self.get("/svm/svms").get("records", [])

    def delete_flexcache(self, uuid):
        return self.delete(f"/storage/flexcache/flexcaches/{uuid}")

    def list_clones_of(self, parent_volume_name):
        return self.get(
            "/storage/volumes",
            {"clone.parent_volume.name": parent_volume_name},
        ).get("records", [])

    def list_clones(self):
        return self.get(
            "/storage/volumes",
            {"fields": "name,uuid,svm,clone"},
        ).get("records", [])

    def split_clone(self, uuid):
        return self.patch(
            f"/storage/volumes/{uuid}",
            {"clone": {"split_initiated": True}},
        )

    def delete_volume(self, uuid):
        return self.delete(f"/storage/volumes/{uuid}")

    def unmount_volume(self, uuid):
        return self.patch(f"/storage/volumes/{uuid}", {"nas": {"path": ""}})

    def list_volumes(self, svm_uuid=None):
        return self.get("/storage/volumes", {"svm.uuid": svm_uuid}).get("records", [])

    def delete_svm(self, uuid):
        return self.delete(f"/svm/svms/{uuid}")

    def list_s3_buckets(self, svm_uuid):
        return self.get(
            "/protocols/s3/buckets",
            {"svm.uuid": svm_uuid},
        ).get("records", [])

    def list_all_s3_buckets(self):
        return self.get(
            "/protocols/s3/buckets",
            {"fields": "name,uuid,svm.uuid,svm.name,volume.name,volume.uuid"},
        ).get("records", [])

    def resolve_s3_bucket_endpoint(self, svm_uuid, bucket_uuid):
        return f"/protocols/s3/buckets/{svm_uuid}/{bucket_uuid}"

    def delete_s3_bucket(self, svm_uuid, bucket_uuid):
        return self.delete(self.resolve_s3_bucket_endpoint(svm_uuid, bucket_uuid))

    def get_audit_config(self, svm_uuid):
        return self.get(f"/protocols/audit/{svm_uuid}")

    def disable_audit(self, svm_uuid):
        return self.patch(f"/protocols/audit/{svm_uuid}", {"enabled": False})

    def delete_audit(self, svm_uuid):
        return self.delete(f"/protocols/audit/{svm_uuid}")

    def delete_object_store_audit(self, svm_uuid):
        return self.delete(f"/protocols/audit/{svm_uuid}/object-store")

    def list_snapmirror_relationships(self, max_records=100):
        return self.get("/snapmirror/relationships").get("records", [])

    def delete_snapmirror(self, uuid):
        return self.delete(f"/snapmirror/relationships/{uuid}")

    def delete_fpolicy_persistent_store(self, svm_uuid, name):
        return self.delete(f"/protocols/fpolicy/{svm_uuid}/persistent-stores/{name}")

    # --- CLI passthrough maintenance shortcuts (delegate to recorded verbs) ---
    def list_recovery_queue(self):
        return self.get("/private/cli/volume/recovery-queue").get("records", [])

    def purge_recovery_queue(self, vserver, volume):
        return self.post(
            "/private/cli/volume/recovery-queue/purge",
            {"vserver": vserver, "volume": volume},
        )

    def list_volume_clones_cli(self, parent_volume_name):
        return self.get(
            "/private/cli/volume/clone",
            {"parent-volume": parent_volume_name},
        ).get("records", [])

    def list_snapmirror_destinations_by_source(
        self, source_path=None, source_vserver=None
    ):
        params = {"fields": "relationship-id,source-path,destination-path"}
        if source_path:
            params["source-path"] = source_path
        if source_vserver:
            params["source-vserver"] = source_vserver
        return self.get("/private/cli/snapmirror/list-destinations", params).get(
            "records", []
        )

    def release_snapmirror_source(
        self, source_path=None, destination_path=None, relationship_id=None
    ):
        body = {}
        if source_path:
            body["source-path"] = source_path
        if relationship_id:
            body["relationship-id"] = relationship_id
        if destination_path:
            body["destination-path"] = destination_path
        else:
            body["relationship-info-only"] = True
        return self.post("/private/cli/snapmirror/release", body)

    def delete_snapmirror_by_destination(self, destination_path):
        return self.post(
            "/private/cli/snapmirror/delete",
            {"destination-path": destination_path},
        )

    def list_vserver_peers(self):
        return self.get("/private/cli/vserver/peer").get("records", [])

    def delete_vserver_peer(self, vserver, peer_vserver):
        from urllib.parse import quote

        return self.delete(
            f"/private/cli/vserver/peer?vserver={quote(vserver)}"
            f"&peer-vserver={quote(peer_vserver)}"
        )

    def paths(self, method: str) -> list[str]:
        """Convenience: the paths issued with a given HTTP method, in order."""
        return [p for (m, p, _b) in self.calls if m == method]
