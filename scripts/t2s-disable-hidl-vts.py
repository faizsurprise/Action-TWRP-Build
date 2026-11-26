#!/usr/bin/env python3
"""Disable VTS-only HIDL module generation in the recovery build.

The minimal TWRP manifest intentionally excludes the HAL VTS test tree.
Normal HIDL interfaces, adapters, C++ and Java libraries remain generated.
The modification is guarded against upstream source changes.
"""

import argparse
from pathlib import Path

ORIGINAL = (
    "\tshouldGenerateVts := shouldGenerateLibrary && "
    "proptools.BoolDefault(i.properties.Gen_vts, true)"
)
REPLACEMENT = (
    "\tshouldGenerateVts := false "
    "// Recovery-only: don't generate HAL VTS test drivers or profilers"
)


def patch(root: Path) -> None:
    path = root / "system/tools/hidl/build/hidl_interface.go"
    source = path.read_text(encoding="utf-8")
    if source.count(ORIGINAL) != 1:
        raise ValueError(
            f"Refusing to patch unexpected HIDL generator {path}: "
            f"expected exactly one original VTS condition"
        )
    if source.count("if shouldGenerateVts {") != 1:
        raise ValueError(
            f"Refusing to patch unexpected HIDL generator {path}: "
            f"expected exactly one VTS generation block"
        )
    rewritten = source.replace(ORIGINAL, REPLACEMENT, 1)
    if "shouldGenerateLibrary := !isCorePackage(name.string())" not in rewritten:
        raise ValueError("Unexpected library generation logic; refusing patch")
    path.write_text(rewritten, encoding="utf-8")
    print("Disabled only generated HIDL VTS test modules for recovery.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    patch(args.source_root.resolve())
