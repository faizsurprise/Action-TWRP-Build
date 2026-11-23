"""Validate a built t2s recovery before generating release assets."""

import argparse
from pathlib import Path
import re
import stat
import struct
import subprocess
import sys
import zlib


MAX_IMAGE_SIZE = 67_108_864
MAX_RAMDISK_SIZE = 256 * 1024 * 1024
PAGE_SIZE = 4096
SAMSUNG_MARKER = b"SEANDROIDENFORCE"


def require(condition, message):
    if not condition:
        raise ValueError(message)


def align(size, boundary):
    return (size + boundary - 1) // boundary * boundary


def boot_sections(data, prebuilts):
    require(data[:8] == b"ANDROID!" and len(data) >= PAGE_SIZE, "Invalid boot magic or header")
    kernel_size, ramdisk_size = struct.unpack_from("<I4xI", data, 8)
    second_size = struct.unpack_from("<I", data, 24)[0]
    page_size, version = struct.unpack_from("<II", data, 36)
    require((page_size, version, second_size) == (PAGE_SIZE, 2, 0),
            "Expected a v2 boot image with 4096-byte pages and no second-stage loader")
    dtbo_size, dtbo_offset, header_size, dtb_size = struct.unpack_from("<IQII", data, 1632)
    require(header_size == 1660, "Invalid v2 header size")
    kernel_addr, ramdisk_addr, tags_addr = struct.unpack_from("<I4xI8xI", data, 12)
    dtb_addr = struct.unpack_from("<Q", data, 1652)[0]
    require((kernel_addr, ramdisk_addr, tags_addr, dtb_addr)
            == (0x80008000, 0x84000000, 0x80000000, 0x80000000),
            "Boot image load addresses differ from JHZA6")

    ramdisk_offset = align(PAGE_SIZE + kernel_size, PAGE_SIZE)
    require(dtbo_offset == align(ramdisk_offset + ramdisk_size, PAGE_SIZE),
            "Invalid recovery DTBO offset")
    dtb_offset = align(dtbo_offset + dtbo_size, PAGE_SIZE)
    payload_end = align(dtb_offset + dtb_size, PAGE_SIZE)
    require(payload_end <= len(data), "Truncated boot image sections")

    for offset, size, name in (
        (PAGE_SIZE, kernel_size, "Image"),
        (dtbo_offset, dtbo_size, "dtbo.img"),
        (dtb_offset, dtb_size, "dtb"),
    ):
        require(size > 0 and data[offset:offset + size] == (prebuilts / name).read_bytes(),
                f"Boot image section {name} differs from the staged JHZA6 input")

    require(ramdisk_size > 0, "Empty recovery ramdisk")
    return data[ramdisk_offset:ramdisk_offset + ramdisk_size], payload_end


def ramdisk_entries(compressed):
    inflater = zlib.decompressobj(zlib.MAX_WBITS + 16)
    archive = inflater.decompress(compressed, MAX_RAMDISK_SIZE + 1)
    require(len(archive) <= MAX_RAMDISK_SIZE, "Uncompressed ramdisk exceeds 256 MiB")
    require(inflater.eof and not inflater.unused_data, "Expected one complete gzip member")

    archive = memoryview(archive)
    entries = {}
    offset = 0
    while offset + 110 <= len(archive):
        require(archive[offset:offset + 6] == b"070701", "Invalid newc CPIO header")
        fields = [int(archive[i:i + 8].tobytes(), 16) for i in range(offset + 6, offset + 110, 8)]
        mode, size, name_size = fields[1], fields[6], fields[11]
        name_end = offset + 110 + name_size
        file_offset = align(name_end, 4)
        file_end = file_offset + size
        offset = align(file_end, 4)
        require(name_size > 1 and offset <= len(archive), "Truncated CPIO entry")
        name = archive[name_end - name_size:name_end].tobytes()
        require(name.endswith(b"\0") and b"\0" not in name[:-1], "Invalid CPIO entry name")
        name = name[:-1].decode("utf-8").removeprefix("./")
        if name == "TRAILER!!!":
            require(size == 0 and not any(archive[offset:]), "Unexpected data after the CPIO trailer")
            return entries
        require(name not in entries, f"Duplicate CPIO entry {name!r}")
        entries[name] = (mode, archive[file_offset:file_end])
    raise ValueError("Missing CPIO trailer")


def validate_ramdisk(compressed, device):
    entries = ramdisk_entries(compressed)
    for name in ("system/bin/recovery", "system/bin/twrp"):
        mode, contents = entries.get(name, (0, b""))
        require(stat.S_ISREG(mode) and mode & 0o111 and len(contents) >= 64
                and contents[:6] == b"\x7fELF\x02\x01"
                and struct.unpack_from("<H", contents, 18)[0] == 183,
                f"Missing executable AArch64 ELF ramdisk entry {name}")

    staged_root = device / "jhza6-root"
    modules = staged_root / "lib/modules"
    module_names = (modules / "modules.load.recovery").read_text().split()
    require(module_names and all((modules / name).is_file() for name in module_names),
            "The staged JHZA6 module load list is empty or incomplete")
    firmware = staged_root / "vendor/firmware/y792_t2.bin"
    sources = {
        path.relative_to(staged_root).as_posix(): path
        for path in (*modules.iterdir(), firmware)
    }
    sources.update({
        "system/etc/init/init.exynos2100.crypto.rc": device / "recovery/init.exynos2100.crypto.rc",
        "system/etc/recovery.fstab": device / "recovery.fstab",
        "system/etc/twrp.flags": device / "recovery/twrp.flags",
        "vendor/etc/vintf/manifest.xml": device / "recovery/manifest.xml",
    })
    for name, source in sources.items():
        mode, contents = entries.get(name, (0, b""))
        require(stat.S_ISREG(mode) and contents == source.read_bytes(),
                f"Ramdisk entry {name} differs from the source input")
    require("system/bin/postrecoveryboot.sh" not in entries,
            "Unexpected postrecoveryboot.sh in the t2s ramdisk")
    print(f"- Ramdisk: valid gzip/newc, two AArch64 recovery executables, "
          f"{len(module_names)} module load entries, matching touchscreen firmware and port files")


def validate_avb(data, payload_end, image, avbtool):
    if data[-64:-60] != b"AVBf":
        require(data[payload_end:] == SAMSUNG_MARKER, "Unexpected data after boot image payload")
        print("- AVB: no footer. Samsung SEANDROIDENFORCE marker present. Image is unsigned.")
        return

    original_size, vbmeta_offset, vbmeta_size = struct.unpack_from(">QQQ", data, len(data) - 52)
    require(payload_end <= original_size <= vbmeta_offset
            and vbmeta_size >= 256 and vbmeta_offset + vbmeta_size <= len(data) - 64,
            "Invalid AVB footer bounds")
    command = [sys.executable, str(avbtool)]
    info = subprocess.check_output(command + ["info_image", "--image", str(image)], text=True)
    algorithm = re.search(r"^Algorithm:\s+(SHA(?:256|512)_RSA\d+)$", info, re.MULTILINE)
    recovery_hash = re.search(
        rf"^    Hash descriptor:\n      Image Size:\s+{original_size} bytes\n"
        r"      Hash Algorithm:\s+sha(?:256|512)\n      Partition Name:\s+recovery\n"
        r"      Salt:[^\n]*\n      Digest:\s+[0-9a-f]+$", info, re.MULTILINE,
    )
    require(algorithm and recovery_hash, "AVB requires a signature and full recovery hash descriptor")
    require(image.name == "recovery.img", "AVB must verify the recovery.img asset itself")
    subprocess.check_output(command + ["verify_image", "--image", str(image)], text=True)
    print(f"- AVB: {algorithm[1]} signature and recovery digest verified using the embedded key.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image", type=Path)
    parser.add_argument("device", type=Path, help="Path to the patched and staged t2s directory")
    parser.add_argument("avbtool", type=Path)
    args = parser.parse_args()

    try:
        size = args.image.stat().st_size
        require(0 < size <= MAX_IMAGE_SIZE, f"Image size {size} exceeds the limit or is empty")
        data = args.image.read_bytes()
        ramdisk, payload_end = boot_sections(data, args.device / "prebuilt")
        print(f"- Image size: {size:,} of {MAX_IMAGE_SIZE:,} bytes")
        print("- Boot header: v2, 4096-byte pages, matching JHZA6 load addresses, kernel, DTB and recovery DTBO")
        validate_ramdisk(ramdisk, args.device)
        validate_avb(data, payload_end, args.image, args.avbtool)
    except (OSError, ValueError, struct.error, subprocess.CalledProcessError, zlib.error) as error:
        parser.exit(1, f"Recovery validation failed: {error}\n")


if __name__ == "__main__":
    main()
