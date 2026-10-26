"""A recording fake of OntapClient for pattern tests.

Records every (method, path, body) the patterns issue and returns canned responses,
so tests can assert a pattern assembles the exact ONTAP REST call DESIGN.md records,
without a live cluster. `wait_ontap_job` is stubbed so 202-job polling is exercised in
assembly order without sleeping.
"""

from __future__ import annotations

from typing import Any


class RecordingClient:
    def __init__(self, get_responses: dict[str, Any] | None = None):
        # Map of path -> response dict for GET. Missing paths return {} (treated as 404
        # by callers that check status, but here GET returns empty records).
        self.get_responses = get_responses or {}
        self.calls: list[tuple[str, str, Any]] = []
        self.jobs_waited: list[str] = []

    # --- recording generic verbs ---
    def get(self, path: str, params: dict | None = None) -> dict:
        self.calls.append(("GET", path, params))
        return self.get_responses.get(path, {})

    def post(self, path: str, body: dict | None = None) -> dict:
        self.calls.append(("POST", path, body))
        return {}

    def patch(self, path: str, body: dict | None = None) -> dict:
        self.calls.append(("PATCH", path, body))
        return {}

    def delete(self, path: str) -> dict:
        self.calls.append(("DELETE", path, None))
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

    def delete_flexcache(self, uuid):
        return self.delete(f"/storage/flexcache/flexcaches/{uuid}")

    def list_clones_of(self, parent_volume_name):
        return self.get(
            "/storage/volumes",
            {"clone.parent_volume.name": parent_volume_name},
        ).get("records", [])

    def split_clone(self, uuid):
        return self.patch(
            f"/storage/volumes/{uuid}",
            {"clone": {"split_initiated": True}},
        )

    def delete_volume(self, uuid):
        return self.delete(f"/storage/volumes/{uuid}")

    def list_volumes(self, svm_uuid=None):
        return self.get("/storage/volumes", {"svm.uuid": svm_uuid}).get("records", [])

    def delete_svm(self, uuid):
        return self.delete(f"/svm/svms/{uuid}")

    def list_s3_buckets(self, svm_uuid):
        return self.get(
            "/protocols/s3/buckets",
            {"svm.uuid": svm_uuid},
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

    def paths(self, method: str) -> list[str]:
        """Convenience: the paths issued with a given HTTP method, in order."""
        return [p for (m, p, _b) in self.calls if m == method]
