#!/usr/bin/env python3
"""Fail-closed audit of the resolved TWRP recovery source manifest.

Run after repo sync and before any Soong build. This validates known real
runtime providers and immutable device pins; it is NOT a replacement for
Soong's full dependency graph or on-device boot/decryption testing.
"""

import argparse
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET

DEVICE_PINS = {
    "device/samsung/exynos2100": (
        "android_device_samsung_exynos2100",
        "0d8b294de8ec86963576ea4710f64207824134c4",
    ),
    "bootable/recovery": (
        "android_bootable_recovery",
        "5c3d206a5eeb3d446bcda8248a405a4b278bab5c",
    ),
    "system/vold": (
        "android_system_vold",
        "a164ba05c5fef288059774a776b2e6e1119957cf",
    ),
}
AOSP_PROVIDER_PROJECTS = {
    "system/media": "platform/system/media",
    "external/speex": "platform/external/speex",
    "packages/modules/NetworkStack": "platform/packages/modules/NetworkStack",
    "packages/modules/NeuralNetworks": "platform/packages/modules/NeuralNetworks",
    "test/vts-testcase/fuzz": "platform/test/vts-testcase/fuzz",
}
EXCLUDED_PROJECTS = {
    "external/grpc-grpc-java",
    "test/vts",
    "test/vts-testcase/hal",
}
PROVIDER_MODULES = {
    "system/media/audio_utils/Android.bp": "libaudioutils",
    "external/speex/Android.bp": "libspeexresampler",
}
MODULE_NAME_RE = re.compile(r'(?m)^[ \t]*name:[ \t]*"([^"]+)"')


def audit(source_root: Path, manifest_file: Path, manifest_sha: str) -> dict:
    root = ET.parse(manifest_file).getroot()
    if root.tag != "manifest":
        raise ValueError("Resolved repo manifest has an unexpected root")

    projects = {}
    for project in root.findall(".//project"):
        name = project.attrib["name"]
        path = project.attrib.get("path", name)
        if path in projects:
            raise ValueError(f"Duplicate checkout path {path}: {name}")
        projects[path] = project

    expected_sha = "6dc117d9cbd08430daa16db2013560e1c4017fa8"
    if manifest_sha != expected_sha:
        raise ValueError(
            f"Unexpected upstream manifest commit {manifest_sha}; "
            f"expected {expected_sha}. Review upstream changes before building."
        )

    revisions = {}
    for path, (expected_name, expected_commit) in DEVICE_PINS.items():
        project = projects.get(path)
        if project is None or project.get("name") != expected_name:
            raise ValueError(f"Missing or mismatched pinned source project: {path}")
        actual = subprocess.check_output(
            ["git", "-C", str(source_root / path), "rev-parse", "HEAD"],
            text=True,
        ).strip()
        if actual != expected_commit:
            raise ValueError(
                f"Wrong pinned commit at {path}: got {actual}, "
                f"expected {expected_commit}"
            )
        revisions[path] = actual

    for path, expected_name in AOSP_PROVIDER_PROJECTS.items():
        project = projects.get(path)
        if project is None or project.get("name") != expected_name:
            raise ValueError(f"Missing required AOSP provider project: {path}")
        if not (source_root / path).is_dir():
            raise ValueError(f"AOSP provider directory was not synced: {path}")

    for path in EXCLUDED_PROJECTS:
        if path in projects or (source_root / path).exists():
            raise ValueError(f"Unwanted test-only project remains: {path}")

    providers = {}
    for relative, required_name in PROVIDER_MODULES.items():
        path = source_root / relative
        source = path.read_text(encoding="utf-8")
        count = MODULE_NAME_RE.findall(source).count(required_name)
        if count != 1:
            raise ValueError(
                f"Expected exactly one genuine Soong definition for "
                f"{required_name} in {relative}; found {count}"
            )
        providers[required_name] = relative

    return {
        "manifest_sha": manifest_sha,
        "checkout_project_count": len(projects),
        "pinned_sources": revisions,
        "required_source_projects": sorted(AOSP_PROVIDER_PROJECTS),
        "excluded_test_projects": sorted(EXCLUDED_PROJECTS),
        "verified_providers": providers,
        "graph_policy": (
            "ALLOW_MISSING_DEPENDENCIES permitted only for recovery-target "
            "graph generation; a missing selected build dependency must fail "
            "the target's Ninja action."
        ),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--source-root", required=True, type=Path)
    p.add_argument("--manifest", required=True, type=Path)
    p.add_argument("--manifest-sha", required=True)
    p.add_argument("--report", required=True, type=Path)
    a = p.parse_args()
    result = audit(a.source_root.resolve(), a.manifest, a.manifest_sha)
    a.report.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        f"Recovery source audit passed: "
        f"{result['checkout_project_count']} resolved projects, "
        f"{len(result['pinned_sources'])} pinned device/build sources, "
        f"{len(result['verified_providers'])} verified runtime providers."
    )


if __name__ == "__main__":
    main()
