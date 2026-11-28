#!/usr/bin/env python3
"""Mirror verified JHZA6 ramdisk modules into the legacy t2s copy source.

The pinned device tree contains old t2s/recovery/root/lib/modules prebuilts.
Recovery makefiles also copy from this directory, which can take precedence
over the hash-verified JHZA6 module set. Rather than weakening final ramdisk
validation, ensure that *both* source paths contain the exact verified input.
"""

import argparse
from pathlib import Path
import shutil

KNOWN_METADATA = {
    "modules.alias", "modules.dep", "modules.load.recovery", "modules.softdep"
}


def sync(device: Path, min_modules: int = 200) -> dict:
    t2s = device / "t2s"
    staged = t2s / "jhza6-root"
    source_modules = staged / "lib/modules"
    legacy_modules = t2s / "recovery/root/lib/modules"
    source_firmware = staged / "vendor/firmware/y792_t2.bin"
    legacy_firmware = t2s / "recovery/root/vendor/firmware/y792_t2.bin"

    if not legacy_modules.is_dir() or not source_modules.is_dir():
        raise ValueError("Missing legacy t2s or verified JHZA6 module directory")
    if not source_firmware.is_file() or not legacy_firmware.is_file():
        raise ValueError("Missing legacy or verified touchscreen firmware")

    reference = sorted(source_modules.iterdir())
    old = sorted(legacy_modules.iterdir())
    for directory, files in ((source_modules, reference), (legacy_modules, old)):
        for path in files:
            if not path.is_file() or path.is_symlink():
                raise ValueError(f"Unexpected nonregular module source: {path}")
            if path.suffix != ".ko" and path.name not in KNOWN_METADATA:
                raise ValueError(f"Unexpected file in module source directory: {path}")

    modules = [p for p in reference if p.suffix == ".ko"]
    if not min_modules <= len(modules) <= 500:
        raise ValueError(f"Unexpected verified JHZA6 module count: {len(modules)}")
    staged_names = {p.name for p in reference}
    if not KNOWN_METADATA.issubset(staged_names):
        raise ValueError(f"Missing JHZA6 metadata: {sorted(KNOWN_METADATA - staged_names)}")
    load_list = (source_modules / "modules.load.recovery").read_text().split()
    if not load_list or any(name not in staged_names for name in load_list):
        raise ValueError("Verified JHZA6 load list references missing modules")

    mismatched = [
        p.name for p in old
        if p.name in staged_names
        and p.read_bytes() != (source_modules / p.name).read_bytes()
    ]
    stale = sorted(p.name for p in old if p.name not in staged_names)
    # All checks above succeed before any files are replaced.
    shutil.rmtree(legacy_modules)
    shutil.copytree(source_modules, legacy_modules, symlinks=False)
    shutil.copyfile(source_firmware, legacy_firmware)
    for p in reference:
        if p.read_bytes() != (legacy_modules / p.name).read_bytes():
            raise ValueError(f"Mirror verification failed for {p.name}")
    if source_firmware.read_bytes() != legacy_firmware.read_bytes():
        raise ValueError("Touchscreen firmware mirror verification failed")

    result = {
        "staged_modules": len(modules),
        "overwritten_mismatched_legacy_files": len(mismatched),
        "removed_stale_legacy_files": len(stale),
        "cdc_ncm_replaced": "cdc_ncm.ko" in mismatched,
    }
    print(f"JHZA6 ramdisk mirror verified: {result}")
    return result


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("device_path", type=Path)
    args = p.parse_args()
    sync(args.device_path.resolve())


if __name__ == "__main__":
    main()
