"""Unit tests for fail-closed recovery-only Robolectric Blueprint pruning."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "t2s-prune-robolectric.py"
SETTINGS = Path("frameworks/base/packages/SettingsLib/tests/robotests/Android.bp")


def put(root: Path, relative: Path, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


SETTINGS_SOURCE = """
package {
    default_applicable_licenses: ["frameworks_base_license"],
}
android_app {
    name: "SettingsLibShell",
}
android_robolectric_test {
    name: "SettingsLibRoboTests",
    // braces inside comments should not end a module: } {
    srcs: ["src/{example}/**/*.java"],
    test_options: {
        timeout: 36000,
    },
}
java_library {
    name: "SettingsLib-robo-testutils",
}
"""

OTHER_SOURCE = """
android_robolectric_test {
    name: "AuxiliaryRoboTests",
    static_libs: ["robolectric-host-android_all"],
}
cc_library {
    name: "real-recovery-helper",
}
"""


class RobolectricPruningTests(unittest.TestCase):
    def run_pruner(self, root: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(root)],
            text=True, capture_output=True, check=False,
        )

    def test_removes_only_robolectric_tests(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = put(root, SETTINGS, SETTINGS_SOURCE)
            other = put(root, Path("frameworks/base/other/Android.bp"), OTHER_SOURCE)
            result = self.run_pruner(root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn('name: "SettingsLibRoboTests"', settings.read_text())
            self.assertNotIn('name: "AuxiliaryRoboTests"', other.read_text())
            self.assertIn('name: "SettingsLibShell"', settings.read_text())
            self.assertIn('name: "SettingsLib-robo-testutils"', settings.read_text())
            self.assertIn('name: "real-recovery-helper"', other.read_text())
            self.assertIn("Excluded 2 Robolectric test modules", result.stdout)

    def test_malformed_blueprint_fails_without_partial_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = put(root, SETTINGS, SETTINGS_SOURCE)
            malformed = put(
                root, Path("frameworks/base/other/Android.bp"),
                'android_robolectric_test {\n    name: "BrokenTest",\n',
            )
            result = self.run_pruner(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(settings.read_text(), SETTINGS_SOURCE)
            self.assertIn("BrokenTest", malformed.read_text())

    def test_missing_required_settings_test_fails_without_edit(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            other = put(root, Path("somewhere/Android.bp"), OTHER_SOURCE)
            result = self.run_pruner(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(other.read_text(), OTHER_SOURCE)


if __name__ == "__main__":
    unittest.main()
