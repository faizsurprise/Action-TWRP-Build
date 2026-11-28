# TWRP build for Samsung Galaxy S21+ Exynos

**Recovery Build** targets SM-G996B (`t2s`) on firmware G996BXXSJHZA6. It builds the patched TWRP 3.7.1 source using the minimal TWRP 12.1 manifest on a GitHub-hosted Ubuntu 22.04 x64 runner.

1. Set the repository Actions secret `JHZA6_RECOVERY_URL` to a private HTTPS download of the verified raw JHZA6 recovery image. Use a URL that the runner can fetch directly. The required SHA-256 is `31d3fd5882b57a3fb772991e56ce24c9df51fceb25240237844616b194d1faa7`.
2. As the repository owner, manually run **Recovery Build** on the default branch. Select **Publish the validated image as an experimental prerelease** if you have permission to redistribute the firmware components included in the output.
3. Check the run log for disk measurements and validation results. The workflow checks for at least 8 GiB free before sync and again before compilation. Peak disk usage during a complete build still needs measurement on this runner.

Successful publication adds `recovery.img` and `recovery.img.sha256` to GitHub Releases. The workflow checks the partition size, v2 boot layout, staged JHZA6 sections, recovery ramdisk, and any embedded AVB footer. The current device build disables AVB and appends the Samsung `SEANDROIDENFORCE` marker. Device boot, verified-boot acceptance, and decryption are untested.


## Recovery-only source graph policy

The TWRP 12.1 upstream default manifest lists approximately 1,061 projects
and its minimal removal manifest excludes approximately 828. The resulting
checkout is intentionally **not a complete Android platform tree**. Soong
therefore encounters dependencies belonging to tools, tests and platform
components unrelated to the requested recovery image.

The **Recovery Build** workflow now uses this explicit two-stage policy:

1. **Fail-closed source audit.** The upstream `twrp-12.1` manifest revision
   is pinned to `6dc117d9cbd08430daa16db2013560e1c4017fa8`. After sync,
   `scripts/t2s-source-audit.py` checks the merged `repo manifest`, the
   three exact Samsung/TWRP/vold Git revisions, required original source
   projects, and the actual `libaudioutils` and `libspeexresampler`
   Soong declarations. Unexpected project changes stop the build.
2. **Recovery-target dependency validation.** The workflow sets
   `ALLOW_MISSING_DEPENDENCIES=true` **only inside the build step** to let
   Soong generate a graph despite undefined modules in unrelated Android
   projects. It then invokes `mka recoveryimage -j2`, **not** an all-platform
   build. Android 12.1 Soong emits failing Ninja actions for missing
   dependencies required by compiled modules; a missing dependency actually
   needed by recovery therefore fails the selected build and blocks output
   publication. Failures include an excerpt in the Actions job summary.

The t2s device patch explicitly sets
`BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES := true` in its
`t2s/BoardConfig.mk`, because the hash-verified JHZA6 recovery image supplies
ARM64 kernel `.ko` ELF modules that are copied into
`recovery/root/lib/modules`. Android 12.1 normally prohibits ELF inputs
under `PRODUCT_COPY_FILES`; this supported BoardConfig exception bypasses
that general ELF-copy rule for this device build. It does **not** skip the
existing reference-image SHA-256 or final image/ramdisk content validation.
The workflow also preflights the flag and the staged ELF kernel-module magic.

### 64 MiB S21+ recovery image budget

Build 20 successfully compiled and assembled `recovery.img`, but the
`68,288,528`-byte image exceeded the device's fixed `67,108,864`-byte
recovery partition by `1,179,664` bytes. The partition limit must **not**
be increased to make an oversized image appear valid.

The t2s-specific `BoardConfig.mk` patch now omits nonessential utilities:
Bash, Nano, NTFS-3G userspace tools, Magiskboot repack tooling, and additional
UI languages. It retains encryption/FBE components, Exynos crypto support,
recovery logging, ADB, and dynamic partition support. These optional features
will therefore be unavailable in this size-constrained build.

The workflow also switches TeamWin's existing gzip-based ramdisk compression
to `minigzip -9` for stronger **lossless** compression. It does not change
the ramdisk format or any staged JHZA6 kernel modules. If the image remains
oversized, the Actions summary reports the sizes of the image, compressed
ramdisk, kernel, DTB, and recovery DTBO for further evidence-led reduction.

### Verified JHZA6 kernel-module provenance

Build 21 completed the entire `recoveryimage` target and produced a
`62,844,944`-byte image, within the `67,108,864`-byte partition limit.
Its independent ramdisk validator correctly rejected a byte mismatch in
`lib/modules/cdc_ncm.ko`. The pinned device tree contains an older
`t2s/recovery/root/lib/modules` collection (261 kernel modules and
metadata), while the verified JHZA6 image stages 270 modules under
`t2s/jhza6-root/lib/modules`. Both paths can feed ramdisk copy rules.

After verifying the private reference image SHA-256, the build runs
`scripts/t2s-sync-jhza6-ramdisk.py` to replace the legacy t2s module
directory with the original JHZA6 files and overwrite the matching
`vendor/firmware/y792_t2.bin`. Other recovery resources are untouched.
The script fails closed if it encounters unexpected module-source files,
missing module load entries, or an implausible module count. Regression tests
run during Actions preflight. Build 22 compiled the entire `recoveryimage` target again, producing
`63,148,048` bytes within the 64 MiB recovery partition. Validation then
detected that `system/etc/twrp.flags` came from the common legacy
`recovery/root/system/etc/twrp.flags`, not from the S21+ port's patched
`t2s/recovery/twrp.flags`. The build log also showed the legacy
`system/bin/postrecoveryboot.sh` being included despite the t2s-specific
copy filter. To fix these confirmed conflicts, the source mirroring step
now places the port's exact `twrp.flags` and `manifest.xml` bytes in
the common copy locations and removes only the legacy post-boot hook
from the temporary source checkout. These changes do **not** modify the
upstream pinned repository or bypass final ramdisk validation.

The final validator still compares every
kernel module and port file in the generated ramdisk byte-for-byte against
the SHA-256-verified reference inputs. No validation check is bypassed.

The final 64 MiB check and independent image-content validation remain
mandatory. A successful static build does not prove One UI 7 bootability or
FBEv2 decryption.

This is not a license to stub missing recovery libraries, disable image checks,
or assume the resulting image boots. Once produced, the recovery image must
still pass static partition/header checks and must be tested for boot,
decryption and One UI 7 / Android 15 compatibility **before flashing**.
Publishing is disabled by default (`publish=false`).

The VINTF host assembler is a special exception to the otherwise excluded
VTS project: Android 12.1's `system/libvintf` directly links
`libvts_vintf_test_common` when building `assemble_vintf`. After the
source audit and test cleanup, `scripts/t2s-restore-vintf-host.sh`
restores only the library's original `Android.bp`, `common.cpp`, and
`include/libvts_vintf_test_common/common.h` from
`platform/test/vts-testcase/hal` at `android-12.1.0_r4`. All three
are checked against their known Git blob hashes. This preserves the real
host-tool dependency without syncing the VTS test tree.

The recovery source preparation also removes only `android_robolectric_test`
module declarations using `scripts/t2s-prune-robolectric.py`. This is needed
because the Android 12.1 Robolectric test builder can panic when
`ALLOW_MISSING_DEPENDENCIES` permits its missing host runtime:
`robolectric-android-all-prebuilts`. It preserves other modules in the
same `Android.bp` files, verifies the previously failing
`SettingsLibRoboTests` was removed, and runs synthetic regression tests
before source checkout.

The legacy explicit exclusions for known host documentation/tests remain to
reduce unnecessary graph work. They are intentionally guarded against upstream
source changes; they should not need to expand every time a new unrelated
platform test dependency is discovered.

### Validated recovery artifacts

Build 23 (run `46097526475`) **successfully compiled and passed every
static validation check** at 63,148,048 bytes, including exact JHZA6
kernel/DTB/DTBO and ramdisk component comparisons. However, that run had
`publish=false` and no `upload-artifact` step; its temporary IMG was
not retained as a downloadable Actions artifact.

The workflow now supports an explicit `save_artifact=true` dispatch input
(default: `false`). When enabled, a successful build archives
`recovery.img` and `recovery.img.sha256` together in the Actions run for
14 days, without creating a GitHub release. The user can download the ZIP
under **Actions → selected run → Artifacts**. As this repository is public
and the IMG incorporates proprietary JHZA6 components, **assume that
enabling the artifact may make the IMG accessible to others**. The user
should choose whether to enable it.

```sh
gh workflow run "Recovery Build.yml" \
  -R faizsurprise/Action-TWRP-Build --ref main \
  -f publish=false -f save_artifact=true
```

A successful build and byte-for-byte static validation do **not** prove the
IMG can boot, pass the device's verified-boot chain, or decrypt One UI 7
FBEv2 data. Do not flash without a device-specific test/restore plan.

### Commands from Termux

```sh
gh workflow run "Recovery Build.yml" \
  -R faizsurprise/Action-TWRP-Build --ref main -f publish=false
gh run watch -R faizsurprise/Action-TWRP-Build
```

---

## Upstream builder documentation

The generic parameters and SSH instructions below apply to the legacy builder workflows.

## OrangeFox is [here](https://github.com/ZH-XiJun/Action-OFRP-Builder)

---

## Changes ahead of [azwhikaru/Action-TWRP-Builder](https://github.com/azwhikaru/Action-TWRP-Builder)

- Added `Recovery Build (Ubuntu 18.04)` in order to make recovery for old version of Android (Kitkat, Lollipop etc.)
- Optimized the body of releases.
- ...

## Thanks to
- All contributors

---

## Release Notes
```
= 2024
- Added `Recovery Build (Ubuntu 18.04)` and keep maintaining the workflow.
- Trying to build CWM Recovery, but it seems that my device tree is broken and none of my try was successful. (If u can solve this, pls submit a PR!)

= 2022/10/28
- OFRP manifest is changed, so not fully support OFRP now (if you can slove this, please submit a pull request!)

= 2022/07/08
- TWRP and TWRP-based 5.X ~ 12.X are ***ALL COMPILED SUCCESSFULLY***

= 2022/07/06
- Add support for 5.1 branch

= 2022/07/05
- Updated to work with trees back to 6.0
- Add conditionals to include common trees for syncing
- Update README for SSH keys

= 2022/07/04
- Updated to work with Android 12.1 AOSP minimal TWRP manifest

= 2022/05/29
- Should work correctly with Android 11 based source code

= 2022/02/03
- Due to the hardware resource limitation of GitHub action, this version cannot be compiled based on AOSP and other source codes of Android 11 and above. If necessary, please use local compilation

= 2021/10/29: 
- Refactored version 2.0
- Completely reconstruct the use logic to reduce the difficulty of use
- Optimize the parameter transfer part, now you can run multiple Workers at the same time
```

-----

## Parameter Description

| Name | Description | Example |
| ------------ | -------------------- | ------------ |
| `MANIFEST_URL` | Source address | https://github.com/minimal-manifest-twrp/platform_manifest_twrp_aosp.git |
| `MANIFEST_BRANCH` | Source branch | twrp-12.1 |
| `DEVICE_TREE_URL` | Device address | https://github.com/TeamWin/android_device_asus_I003D |
| `DEVICE_TREE_BRANCH` | Device branch | android-12.1 |
| `DEVICE_PATH` | Device location | device/asus/I003D |
| `COMMON_TREE_URL` | Common tree address | https://github.com/TeamWin/android_device_asus_sm8250-common |
| `COMMON_PATH` | Common tree location | device/asus/sm8250-common |
| `DEVICE_NAME` | Model name | I003D |
| `MAKEFILE_NAME` | Makefile name | twrp_I003D |
| `BUILD_TARGET` | Build Target Partition (boot/recovery/vendorboot) | recovery |

-----

## How to use
```
For example, your username is: JohnSmith
```
#### 1. Click 'Fork' in the upper right corner of this repository
![image](https://user-images.githubusercontent.com/37921907/177914706-c92476c5-7e14-4fb3-be94-0c8a11dae874.png)
#### 2. After waiting for the automatic redirection, you will see your own username
![image](https://user-images.githubusercontent.com/37921907/177915106-5bde6fc9-303c-479e-b290-22b48efd1e4e.png)
#### 3. Change the [username and email](https://github.com/CaptainThrowback/Action-Recovery-Builder/blob/main/.github/workflows/Recovery%20Build.yml#L100-L101) in the workflow to reflect your Github credentials (optional)
## Setting up SSH Keys (optional)
#### 4. Go to Settings, then select Deploy keys and select "Add deploy key" button.

#### 5. On your Android device, install [Termux](https://github.com/termux/termux-app/releases)

#### 6. Install openssh in Termux and generate ssh keys. (Do not use passphrase for keys)
NOTE: When creating the deploy key for a repository like git@github.com:owner/repo.git or https://github.com/owner/repo, put that URL into the key comment. (Hint: Try ssh-keygen ... -C "git@github.com:owner/repo.git".)
owner = your Github username
```
pkg install openssh
ssh-keygen -t ed25519 -C "git@github.com:owner/Action-Recovery-Builder.git"
```
#### 7. Add the keys to your repo. In Termux, use the following commands:
```
cd /data/data/com.termux/files/usr/etc/ssh
cat ssh_host_ed25519_key.pub
```
  Select and copy the key then paste in the box for Key.
  You can name it whatever you choose for the title.

#### 8. Now to add your private ssh key. Back in Termux:
```
cat ssh_host_ed25519_key
```
   Copy the output from Termux.

   In your browser, select *Secrets* under the Security tab.
   Select Actions
   Select New repository secret
   For the New secret name, it should be SSH_PRIVATE_KEY
   Paste the output from ssh_host_ed25519_key into the Value box.
   Then select Add secret.

## Building the Recovery
#### 9. Select the legacy workflow for your Android build tree
![image](https://user-images.githubusercontent.com/37921907/177915304-8731ed80-1d49-48c9-9848-70d0ac8f2720.png)
#### 10. Click 'Run workflow' and fill in according to the above 'parameter description'
![image](https://user-images.githubusercontent.com/37921907/177915346-71c29149-78fb-4a00-996f-5d84ffc9eb8c.png)
#### 11. After filling in, click 'Run workflow' to start running

-----

## Compilation results
Can be downloaded at [Release](../../releases)

-----
## Remark

#### TeamWin Recovery Project: https://github.com/minimal-manifest-twrp
#### OrangeFox Recovery Project: https://gitlab.com/OrangeFox/Manifest
#### SKYHAWK Recovery Project: https://github.com/SHRP/platform_manifest_twrp_omni
