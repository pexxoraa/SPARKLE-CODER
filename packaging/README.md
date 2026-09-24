# Building SPARKLE CODER executables

The executable includes Python for the interface. Python projects and the offline
demo still need an installed Python 3.11+ interpreter. Install other tools such as
Node.js when required by your projects. **Check setup** helps identify missing tools.

## Build locally

Run from a clean checkout, separately on each target operating system:

```sh
python -m pip install pyinstaller
python -m PyInstaller packaging/sparkle-coder.spec
python scripts/smoke_packaged.py dist/SparkleCoder
```

On Windows, use `dist/SparkleCoder.exe` in the last command. The smoke check
starts a disposable copy and exercises website pairing, command approval, real
Python repair, saved history, downloads, revocation and shutdown. It uses a
scripted model and does not contact NVIDIA or test native GUI dialogs.

Only the application and explicit UI/guide files are bundled. Distribute the
executable without APP_DATA, PROJECTS, credentials or personal configuration.
Users should keep the executable in a writable folder with their data folders.

## GitHub builds

Run **Build installers** from the repository's Actions tab, or push a version
tag matching `v*`. The workflow builds on Windows, macOS and Linux and runs the
packaged smoke check on each. Successful tagged builds attach three files to a
release: SparkleCoder-Windows.exe, SparkleCoder-macOS and SparkleCoder-Linux.

The release job has `contents: write` permission. A private repository's releases
still require repository access; a release link does not grant public access.

## Validation limits

The Linux artifact can be validated in this workspace. Windows/macOS executable
runs and native folder selection require their own platform checks; mocked
windowless-picker tests do not establish native behavior. GitHub runner success
must be checked before claiming all three artifacts work.

The artifacts are unsigned. Verify the source and build origin before accepting
an operating-system warning. Signing and notarization are not configured.
