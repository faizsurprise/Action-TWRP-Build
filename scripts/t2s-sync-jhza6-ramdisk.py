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
    # AOSP source makes the common recovery files available to every device.
    # This tree additionally supplies t2s-specific overrides; in practice
    # the common PRODUCT_COPY_FILES rules can win at the same destination.
    port_flags = t2s / "recovery/twrp.flags"
    common_flags = device / "recovery/root/system/etc/twrp.flags"
    port_manifest = t2s / "recovery/manifest.xml"
    common_manifest = device / "recovery/root/vendor/etc/vintf/manifest.xml"
    legacy_postboot = device / "recovery/root/system/bin/postrecoveryboot.sh"

    if not legacy_modules.is_dir() or not source_modules.is_dir():
        raise ValueError("Missing legacy t2s or verified JHZA6 module directory")
    if not source_firmware.is_file() or not legacy_firmware.is_file():
        raise ValueError("Missing legacy or verified touchscreen firmware")
    for path in (port_flags, common_flags, port_manifest, common_manifest, legacy_postboot):
        if not path.is_file() or path.is_symlink():
            raise ValueError(f"Missing or invalid t2s recovery overlay source: {path}")
    expected_flags = port_flags.read_bytes()
    expected_manifest = port_manifest.read_bytes()
    if not expected_flags.startswith(b"# mount point") or b"/dev/block/mapper/system" not in expected_flags:
        raise ValueError("Unexpected t2s port twrp.flags contents")
    if b"android.hardware.keymaster" not in expected_manifest or b"android.hardware.gatekeeper" not in expected_manifest:
        raise ValueError("Unexpected t2s port VINTF manifest")
    if b"postrecoveryboot.sh" not in legacy_postboot.name.encode():
        raise ValueError("Unexpected legacy post-boot file")

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
    overridden_common_flags = common_flags.read_bytes() != expected_flags
    overridden_common_manifest = common_manifest.read_bytes() != expected_manifest
    # All checks above succeed before any files are replaced.
    shutil.rmtree(legacy_modules)
    shutil.copytree(source_modules, legacy_modules, symlinks=False)
    shutil.copyfile(source_firmware, legacy_firmware)
    # Mirror the port-defined resources in the common copy source too.
    # This avoids competing PRODUCT_COPY_FILES rules selecting old content.
    shutil.copyfile(port_flags, common_flags)
    shutil.copyfile(port_manifest, common_manifest)
    # The port specifically excludes this legacy auto-execution hook. The
    # current build log confirms it was still copied despite a Make filter.
    # Delete the common source before PRODUCT_COPY_FILES is evaluated.
    legacy_postboot.unlink()
    for p in reference:
        if p.read_bytes() != (legacy_modules / p.name).read_bytes():
            raise ValueError(f"Mirror verification failed for {p.name}")
    if source_firmware.read_bytes() != legacy_firmware.read_bytes():
        raise ValueError("Touchscreen firmware mirror verification failed")
    if common_flags.read_bytes() != expected_flags:
        raise ValueError("S21+ twrp.flags override mirror verification failed")
    if common_manifest.read_bytes() != expected_manifest:
        raise ValueError("S21+ VINTF manifest override mirror verification failed")
    if legacy_postboot.exists():
        raise ValueError("Disallowed legacy postrecoveryboot.sh remains in the source")

    result = {
        "staged_modules": len(modules),
        "overwritten_mismatched_legacy_files": len(mismatched),
        "removed_stale_legacy_files": len(stale),
        "cdc_ncm_replaced": "cdc_ncm.ko" in mismatched,
        "twrp_flags_override": overridden_common_flags,
        "vintf_manifest_override": overridden_common_manifest,
        "removed_legacy_postrecoveryboot": not legacy_postboot.exists(),
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
