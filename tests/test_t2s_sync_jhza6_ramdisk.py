"""Regression tests for replacing conflicting t2s legacy kernel prebuilts."""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/t2s-sync-jhza6-ramdisk.py"
SPEC = spec_from_file_location("t2s_jhza6_mirror", SCRIPT)
MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def create(root: Path, relative: str, data: bytes) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def fixture(device: Path) -> tuple[Path, Path]:
    old = device / "t2s/recovery/root/lib/modules"
    new = device / "t2s/jhza6-root/lib/modules"
    for root, prefix in ((old, b"old"), (new, b"new")):
        for filename in ("cdc_ncm.ko", "abc.ko"):
            create(root, filename, b"\\x7fELF" + prefix + filename.encode())
        for filename, content in (
            ("modules.alias", b"alias\n"),
            ("modules.dep", b"dep\n"),
            ("modules.load.recovery", b"abc.ko cdc_ncm.ko\n"),
            ("modules.softdep", b"softdep\n"),
        ):
            create(root, filename, content)
    create(device, "t2s/recovery/root/vendor/firmware/y792_t2.bin", b"old-fw")
    create(device, "t2s/jhza6-root/vendor/firmware/y792_t2.bin", b"new-fw")
    return old, new


class T2sRamdiskMirrorTests(unittest.TestCase):
    def test_mirrors_exact_staged_modules_firmware_and_removes_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "device/samsung/exynos2100"
            old, new = fixture(device)
            create(old, "deprecated.ko", b"stale")
            result = MODULE.sync(device, min_modules=2)
            self.assertEqual(result["staged_modules"], 2)
            self.assertTrue(result["cdc_ncm_replaced"])
            self.assertEqual(result["removed_stale_legacy_files"], 1)
            self.assertEqual(
                {p.name: p.read_bytes() for p in old.iterdir()},
                {p.name: p.read_bytes() for p in new.iterdir()},
            )
            self.assertEqual(
                (device / "t2s/recovery/root/vendor/firmware/y792_t2.bin").read_bytes(),
                b"new-fw",
            )

    def test_unknown_legacy_file_fails_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "device/samsung/exynos2100"
            old, _ = fixture(device)
            unusual = create(old, "unexpected.conf", b"preserve")
            original = (old / "cdc_ncm.ko").read_bytes()
            with self.assertRaisesRegex(ValueError, "Unexpected file"):
                MODULE.sync(device, min_modules=2)
            self.assertEqual((old / "cdc_ncm.ko").read_bytes(), original)
            self.assertEqual(unusual.read_bytes(), b"preserve")

    def test_missing_staged_load_module_fails_without_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            device = Path(tmp) / "device/samsung/exynos2100"
            old, new = fixture(device)
            create(new, "modules.load.recovery", b"missing.ko\n")
            original = (old / "cdc_ncm.ko").read_bytes()
            with self.assertRaisesRegex(ValueError, "references missing modules"):
                MODULE.sync(device, min_modules=2)
            self.assertEqual((old / "cdc_ncm.ko").read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
