"""Safety-gate tests: allowlist, keep-list, dry-run default.

A file_system_id outside the allowlist or inside the keep-list must be refused before
any mutating call. dry_run defaults true; only confirm:true acts.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import _bootstrap  # noqa: F401  (loads the ontap_ops package by path)
from ontap_ops.shared.safety import (
    SafetyViolation,
    assert_in_scope,
    assert_maintenance_allowed,
    get_maintenance_list,
    is_dry_run,
)

FS = "fs-0123456789abcdef0"
OTHER_FS = "fs-aaaaaaaaaaaaaaaaa"


class TestAllowlist(unittest.TestCase):
    def test_in_allowlist_passes(self):
        # No exception == accepted.
        assert_in_scope(FS, env={"ONTAP_OPS_ALLOWLIST": FS})

    def test_not_in_allowlist_refused(self):
        with self.assertRaises(SafetyViolation):
            assert_in_scope(FS, env={"ONTAP_OPS_ALLOWLIST": OTHER_FS})

    def test_empty_allowlist_refuses_everything(self):
        with self.assertRaises(SafetyViolation):
            assert_in_scope(FS, env={"ONTAP_OPS_ALLOWLIST": ""})

    def test_keep_list_refused_even_if_allowlisted(self):
        # Defense in depth: being in the allowlist does not override the keep-list.
        with self.assertRaises(SafetyViolation):
            assert_in_scope(
                FS,
                env={"ONTAP_OPS_ALLOWLIST": FS, "ONTAP_OPS_KEEP_LIST": FS},
            )

    def test_missing_file_system_id_refused(self):
        with self.assertRaises(SafetyViolation):
            assert_in_scope("", env={"ONTAP_OPS_ALLOWLIST": FS})

    def test_comma_and_space_separated_allowlist(self):
        env = {"ONTAP_OPS_ALLOWLIST": "fs-aaaaaaaaaaaaaaaaa, fs-0123456789abcdef0"}
        assert_in_scope(FS, env=env)


class TestAllowlistTable(unittest.TestCase):
    """A representative table of allow/deny cases, replacing the hypothesis property.

    A target is accepted iff it is in the allowlist and not in the keep-list. The
    table covers: listed id accepted, unlisted id refused, keep-list refusal even
    when allowlisted, empty allowlist refusing everything, and multi-entry lists.
    """

    FS_A = "fs-0123456789abcdef0"
    FS_B = "fs-abcdef0123456789a"
    FS_C = "fs-aaaaaaaaaaaaaaaaa"

    def test_allowlist_accepts_only_listed_ids(self):
        allow = f"{self.FS_A} {self.FS_B}"
        cases = [
            # (file_system_id, allowlist, keep_list, should_pass)
            (self.FS_A, allow, "", True),
            (self.FS_B, allow, "", True),
            (self.FS_C, allow, "", False),  # not listed
            (self.FS_A, "", "", False),  # empty allowlist refuses everything
            (self.FS_A, self.FS_A, self.FS_A, False),  # keep-list wins over allowlist
            (self.FS_B, allow, self.FS_B, False),  # keep-list refuses a listed id
            ("", allow, "", False),  # missing id
        ]
        for fsid, allowlist, keep_list, should_pass in cases:
            with self.subTest(fsid=fsid, allowlist=allowlist, keep_list=keep_list):
                env = {
                    "ONTAP_OPS_ALLOWLIST": allowlist,
                    "ONTAP_OPS_KEEP_LIST": keep_list,
                }
                if should_pass:
                    assert_in_scope(fsid, env=env)  # must not raise
                else:
                    with self.assertRaises(SafetyViolation):
                        assert_in_scope(fsid, env=env)

    def test_keep_list_refuses_even_if_passed_in_allowlist(self):
        # Explicit statement of the defense-in-depth rule, across several ids.
        for fsid in (self.FS_A, self.FS_B, self.FS_C):
            with self.subTest(fsid=fsid):
                env = {"ONTAP_OPS_ALLOWLIST": fsid, "ONTAP_OPS_KEEP_LIST": fsid}
                with self.assertRaises(SafetyViolation):
                    assert_in_scope(fsid, env=env)


class TestMaintenanceGate(unittest.TestCase):
    """Maintenance (surgical, non-teardown) ops are allowed when the FS is in the
    allowlist OR the maintenance list, and refused otherwise. The maintenance list
    never opens a teardown path (that stays on assert_in_scope)."""

    def test_allowed_via_maintenance_list(self):
        assert_maintenance_allowed(FS, env={"ONTAP_OPS_MAINTENANCE_FSIDS": FS})

    def test_allowed_via_allowlist(self):
        assert_maintenance_allowed(FS, env={"ONTAP_OPS_ALLOWLIST": FS})

    def test_refused_when_in_neither(self):
        with self.assertRaises(SafetyViolation):
            assert_maintenance_allowed(FS, env={"ONTAP_OPS_ALLOWLIST": OTHER_FS})

    def test_refused_when_both_empty(self):
        with self.assertRaises(SafetyViolation):
            assert_maintenance_allowed(FS, env={})

    def test_missing_file_system_id_refused(self):
        with self.assertRaises(SafetyViolation):
            assert_maintenance_allowed("", env={"ONTAP_OPS_MAINTENANCE_FSIDS": FS})

    def test_maintenance_list_parse_comma_and_space(self):
        env = {"ONTAP_OPS_MAINTENANCE_FSIDS": f"{OTHER_FS}, {FS}"}
        self.assertEqual(get_maintenance_list(env), [OTHER_FS, FS])

    def test_maintenance_list_does_not_grant_teardown(self):
        # A FS only in the maintenance list is still refused by assert_in_scope.
        with self.assertRaises(SafetyViolation):
            assert_in_scope(FS, env={"ONTAP_OPS_MAINTENANCE_FSIDS": FS})


class TestDryRunDefault(unittest.TestCase):
    def test_dry_run_default_true(self):
        self.assertIs(is_dry_run({}), True)
        self.assertIs(is_dry_run(None), True)

    def test_dry_run_requires_confirm_true(self):
        self.assertIs(is_dry_run({"confirm": True}), False)
        # dry_run flag alone cannot turn off the guard; only confirm:true acts.
        self.assertIs(is_dry_run({"dry_run": False}), True)
        self.assertIs(is_dry_run({"confirm": False}), True)


if __name__ == "__main__":
    unittest.main()
