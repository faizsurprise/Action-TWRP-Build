#!/usr/bin/env python3
"""Hide unused AOSP host-only Soong blueprints from a TWRP recovery build.

The minimal TWRP 12.1 manifest intentionally omits host test tooling, but
retains development and GSI tests with references to that tooling. Do not
disable dependency validation or fabricate module definitions; exclude only
confirmed non-recovery Android.bp files after checking their module types.
"""

import argparse
from pathlib import Path
import re

HEADER = re.compile(r"(?m)^([A-Za-z_][A-Za-z0-9_]*)[ \t]*\{")
NAME = re.compile(r'(?m)^[ \t]*name:[ \t]*"([^"]+)"')

# Path -> expected diagnostic module and permitted top-level module kinds.
# Each file is part of host development tools or a device test directory;
# none is used to compile or package the recovery runtime.
SPECS = {
    "development/tools/bugreport/Android.bp": (
        "BugReport",
        {"package", "license", "java_binary_host"},
    ),
    "development/tools/idegen/Android.bp": (
        "idegen",
        {"package", "license", "java_library_host"},
    ),
    "system/gsid/tests/Android.bp": (
        "DSUEndtoEndTest",
        {
            "package", "license", "cc_defaults", "cc_test",
            "java_library_host", "java_test_host",
        },
    ),
    # APEX test fixtures and host tests are not installed in recovery.
    "system/apex/tests/Android.bp": (
        "apex_targetprep_tests",
        {
            "package", "license", "java_defaults", "java_test_host",
            "java_library_host", "apex", "apex_key",
            "android_app_certificate", "prebuilt_etc",
            "android_test_helper_app",
        },
    ),
    # API documentation tooling has been excluded with doclava/jsilver.
    "build/make/tools/apicheck/Android.bp": (
        "apicheck",
        {"package", "license", "java_binary_host"},
    ),
    # The NetworkStack project is needed for its genuine Soong defaults,
    # but its Kotlin/Tradefed host-test helper is not a recovery dependency.
    "packages/modules/NetworkStack/tests/hostlib/Android.bp": (
        "net-host-tests-utils",
        {"package", "license", "java_library_host"},
    ),
}


def prune(root: Path) -> None:
    # Verify every source file before any modifications, so a schema change
    # causes a safe early failure rather than partial cleanup.
    pending = []
    for relative, (expected_name, allowed_kinds) in SPECS.items():
        path = root / relative
        source = path.read_text(encoding="utf-8")
        kinds = HEADER.findall(source)
        names = NAME.findall(source)
        if not kinds or not set(kinds).issubset(allowed_kinds):
            raise ValueError(
                f"Unexpected Soong module kinds in {relative}: {kinds}"
            )
        if names.count(expected_name) != 1:
            raise ValueError(
                f"Expected exactly one {expected_name} in {relative}; "
                f"found module names {names}"
            )
        if not source.rstrip().endswith("}"):
            raise ValueError(f"Unexpected Android.bp ending in {relative}")
        target = path.with_name("Android.bp.twrp-excluded")
        if target.exists():
            raise FileExistsError(f"Target already exists: {target}")
        pending.append((path, target, kinds, expected_name))

    for source, target, kinds, module in pending:
        source.rename(target)
        print(f"Recovery-only: excluded {module} and related host tests: "
              f"{source.relative_to(root)} ({', '.join(kinds)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "source_root", type=Path, help="Root of synced Android source tree"
    )
    args = parser.parse_args()
    prune(args.source_root.resolve())
