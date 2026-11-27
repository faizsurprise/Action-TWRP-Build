#!/usr/bin/env python3
"""Exclude only android_robolectric_test declarations from recovery Soong.

Android 12.1 Soong assumes that each Robolectric test has a real
robolectric-android-all-prebuilts runtime. The minimal TWRP manifest omits
Robolectric and, with ALLOW_MISSING_DEPENDENCIES, dereferencing the missing
runtime can panic during graph generation even for tests unrelated to recovery.

Prune the test-only module declarations, NOT production apps and libraries.
Validate every block before writing any file; fail closed on layout changes.
"""

import argparse
from pathlib import Path
import re

HEADER = re.compile(r"(?m)^[ \t]*android_robolectric_test[ \t]*\\{")
MODULE_NAME = re.compile(r'(?m)^[ \t]*name:[ \t]*"([^"]+)"')
SETTINGS_BP = Path("frameworks/base/packages/SettingsLib/tests/robotests/Android.bp")


def module_end(source: str, opening: int) -> int:
    """Find the matching brace, ignoring Blueprint strings and comments."""
    depth = 0
    quoted = False
    escaped = False
    line_comment = False
    block_comment = False
    i = opening
    while i < len(source):
        char = source[i]
        next_char = source[i + 1] if i + 1 < len(source) else ""
        if line_comment:
            if char == "\\n":
                line_comment = False
        elif block_comment:
            if char == "*" and next_char == "/":
                block_comment = False
                i += 1
        elif quoted:
            if escaped:
                escaped = False
            elif char == "\\\\":
                escaped = True
            elif char == '"':
                quoted = False
        elif char == "/" and next_char == "/":
            line_comment = True
            i += 1
        elif char == "/" and next_char == "*":
            block_comment = True
            i += 1
        elif char == '"':
            quoted = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i + 1
            if depth < 0:
                break
        i += 1
    raise ValueError("Malformed android_robolectric_test Blueprint declaration")


def prune(root: Path) -> None:
    planned = []
    removed_names = []
    settings_seen = False

    for path in root.rglob("Android.bp"):
        relative = path.relative_to(root)
        if relative.parts[0] in {"out", ".repo"}:
            continue
        source = path.read_text(encoding="utf-8")
        if "android_robolectric_test" not in source:
            continue
        blocks = []
        for match in HEADER.finditer(source):
            end = module_end(source, match.end() - 1)
            if blocks and match.start() < blocks[-1][1]:
                raise ValueError(f"Overlapping Robolectric test blocks: {relative}")
            block = source[match.start():end]
            names = MODULE_NAME.findall(block)
            if len(names) != 1:
                raise ValueError(
                    f"Unexpected Robolectric module names in {relative}: {names}"
                )
            blocks.append((match.start(), end, names[0]))

        if not blocks:
            continue
        changed = source
        for start, end, name in reversed(blocks):
            changed = changed[:start] + changed[end:]
            removed_names.append(name)

        if relative == SETTINGS_BP:
            expected = {"SettingsLibShell", "SettingsLib-robo-testutils"}
            remaining = set(MODULE_NAME.findall(changed))
            if [name for _, _, name in blocks].count("SettingsLibRoboTests") != 1:
                raise ValueError("Expected SettingsLibRoboTests exactly once")
            if not expected.issubset(remaining):
                raise ValueError("A production or helper SettingsLib module was lost")
            settings_seen = True

        planned.append((path, changed, relative, [name for _, _, name in blocks]))

    # Require evidence of the exact test involved in the previous panic.
    if not settings_seen or not removed_names:
        raise ValueError("SettingsLibRoboTests was not identified; refusing edits")
    if len(removed_names) > 500:
        raise ValueError(f"Unexpected Robolectric test module count: {len(removed_names)}")
    if len(set(removed_names)) != len(removed_names):
        raise ValueError("Duplicate Robolectric module names; inspect the source")

    for path, changed, relative, names in planned:
        path.write_text(changed, encoding="utf-8")
        print(f"Recovery-only Robolectric tests excluded: {relative}: {', '.join(names)}")
    print(
        f"Excluded {len(removed_names)} Robolectric test modules from "
        f"{len(planned)} blueprints; preserved non-test modules."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("source_root", type=Path)
    args = parser.parse_args()
    prune(args.source_root.resolve())
