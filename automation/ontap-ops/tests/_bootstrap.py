"""Test bootstrap for stdlib `unittest discover`.

Two jobs, both done by importing this module at the top of every test module.

1. Load the hyphenated package by path. The package directory is named
   `ontap-ops`, whose hyphen makes it an invalid Python module name, so it cannot
   be imported as `automation.ontap-ops`. This loads the tree once under the
   importable alias `ontap_ops` (its own package registered with
   `submodule_search_locations` so the production `from ..shared` / `from .patterns`
   relative imports resolve), and the tests import from `ontap_ops`.

2. Make the package importable under the Hub's stdlib-only toolchain. The Hub runs
   tests with `python -m unittest discover` on a deliberately stdlib-only
   `requirements-dev.txt`: boto3 and urllib3 are Lambda-runtime-provided, not test
   dependencies, and CI does not install them. The production modules
   `shared/ontap_client.py` and `shared/fsx_helpers.py` do `import boto3` /
   `import urllib3` at module scope, so importing the package would fail with
   `ModuleNotFoundError` on a stdlib-only interpreter. This registers minimal stub
   modules under those names *before* the package is loaded, but only when the real
   packages are absent, so running under a venv that has them is unaffected.

   The stubs carry only the attributes the production code touches when imported or
   when a test exercises it with mocks: the tests never reach the real network or
   AWS paths (every boto3 Session / client and every ONTAP client is a MagicMock or
   a fake), so the stub bodies are never called. This keeps the test suite genuinely
   standard-library-only without adding a test-only seam to the production code.
"""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent.parent  # automation/ontap-ops
ALIAS = "ontap_ops"


def _install_runtime_stubs() -> None:
    """Register stub boto3 / urllib3 only when the real ones are not installed.

    Lets the stdlib-only interpreter import production modules that do a top-level
    `import boto3` / `import urllib3`. A venv that actually has them keeps the real
    packages; the `in sys.modules` / `find_spec` guards make this a no-op there.
    """
    if "boto3" not in sys.modules and importlib.util.find_spec("boto3") is None:
        boto3_stub = types.ModuleType("boto3")

        class _Session:  # stub; real behavior supplied by test mocks
            def __init__(self, *args, **kwargs):
                raise RuntimeError(
                    "boto3 stub Session must be replaced by a test mock; the test "
                    "suite never talks to real AWS."
                )

            def client(self, *args, **kwargs):
                raise RuntimeError("boto3 stub client must be replaced by a test mock")

        boto3_stub.Session = _Session
        sys.modules["boto3"] = boto3_stub

    if "urllib3" not in sys.modules and importlib.util.find_spec("urllib3") is None:
        urllib3_stub = types.ModuleType("urllib3")
        exceptions = types.ModuleType("urllib3.exceptions")

        class _Err(Exception):
            pass

        exceptions.MaxRetryError = _Err
        exceptions.TimeoutError = _Err
        exceptions.InsecureRequestWarning = Warning

        def _unused(*args, **kwargs):  # pragma: no cover - never called by tests
            raise RuntimeError("urllib3 stub called; tests use a fake ONTAP client")

        urllib3_stub.exceptions = exceptions
        urllib3_stub.PoolManager = _unused
        urllib3_stub.Timeout = _unused
        urllib3_stub.Retry = _unused
        urllib3_stub.make_headers = _unused
        urllib3_stub.disable_warnings = _unused
        sys.modules["urllib3"] = urllib3_stub
        sys.modules["urllib3.exceptions"] = exceptions


def load_package() -> None:
    """Load `automation/ontap-ops` once under the alias `ontap_ops`."""
    if ALIAS in sys.modules:
        return
    _install_runtime_stubs()
    init_path = PACKAGE_DIR / "__init__.py"
    spec = importlib.util.spec_from_file_location(
        ALIAS,
        init_path,
        submodule_search_locations=[str(PACKAGE_DIR)],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[ALIAS] = module
    spec.loader.exec_module(module)


load_package()
