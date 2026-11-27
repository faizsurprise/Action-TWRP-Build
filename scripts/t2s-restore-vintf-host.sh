#!/usr/bin/env bash
# Restore the real VINTF host assembly library from pinned AOSP 12.1 sources.
# The minimal TWRP manifest removes platform/test/vts-testcase/hal; however
# the retained system/libvintf's assemble_vintf and libassemblevintf require
# libvts_vintf_test_common at build time. Stage only its original 3 files.
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 <android-source-root>" >&2
  exit 2
fi
root="$1"
dest="$root/test/vts-testcase/hal/treble/vintf/libvts_vintf_test_common"
upstream="https://android.googlesource.com/platform/test/vts-testcase/hal/+/refs/tags/android-12.1.0_r4/treble/vintf/libvts_vintf_test_common"

# Git object hashes independently verified against the AOSP 12.1.0_r4
# platform/test/vts-testcase/hal source tree.
declare -A expected_blobs=(
  ["Android.bp"]="ac075929af79c79ae4e93c2af8be8a410469af27"
  ["common.cpp"]="0219996f0a2c2d4b8d26eba9cbd5964c5d07662e"
  ["include/libvts_vintf_test_common/common.h"]="ddfe5a134fc78a5a7fc0616955514e38a3289490"
)

if [[ -d "$root/test/vts-testcase/hal" ]]; then
  echo "Unexpected complete VTS HAL test checkout; refusing overlay" >&2
  exit 1
fi

for file in "Android.bp" "common.cpp" "include/libvts_vintf_test_common/common.h"; do
  path="$dest/$file"
  mkdir -p -- "$(dirname "$path")"
  # Gitiles serves a base64-encoded exact file from the pinned AOSP tag.
  curl --fail --silent --show-error --location --retry 3 \
    --proto '=https' --proto-redir '=https' \
    --connect-timeout 20 --max-time 120 --max-filesize 65536 \
    "$upstream/$file?format=TEXT" | base64 --decode > "$path"
  actual="$(git hash-object "$path")"
  if [[ "$actual" != "${expected_blobs[$file]}" ]]; then
    echo "Pinned source hash mismatch in $file: got $actual" >&2
    exit 1
  fi
  echo "Verified original VINTF host source $file: $actual"
done

if [[ "$(grep -Ec '^[[:space:]]*name:[[:space:]]*"libvts_vintf_test_common"' "$dest/Android.bp")" -ne 1 ]]; then
  echo "Expected exactly one real libvts_vintf_test_common definition" >&2
  exit 1
fi
grep -Fq '"common.cpp"' "$dest/Android.bp"
grep -Fq '"libbase"' "$dest/Android.bp"
grep -Fq '"libvintf"' "$dest/Android.bp"
test -s "$dest/include/libvts_vintf_test_common/common.h"

echo "Restored pinned libvts_vintf_test_common; no VTS test harnesses downloaded."
