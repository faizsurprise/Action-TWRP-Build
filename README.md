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

This is not a license to stub missing recovery libraries, disable image checks,
or assume the resulting image boots. Once produced, the recovery image must
still pass static partition/header checks and must be tested for boot,
decryption and One UI 7 / Android 15 compatibility **before flashing**.
Publishing is disabled by default (`publish=false`).

The legacy explicit exclusions for known host documentation/tests remain to
reduce unnecessary graph work. They are intentionally guarded against upstream
source changes; they should not need to expand every time a new unrelated
platform test dependency is discovered.

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
