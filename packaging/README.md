# SPARKLE CODER installers

For the managed tester edition, deploy the shared server first using
[PILOT_SETUP.md](../PILOT_SETUP.md). The installer embeds only its public HTTPS
origin. The owner's NVIDIA and admin secrets never enter a desktop build.

## Build on the target OS

```sh
python -m pip install pyinstaller uv
python scripts/configure_pilot.py --url https://YOUR-SERVER.workers.dev
python -m PyInstaller --clean --noconfirm packaging/sparkle-coder.spec
python scripts/bundle_runtime.py
python scripts/smoke_packaged.py dist/SparkleCoder --bundled
```

Use `dist/SparkleCoder.exe` on Windows. Use `--personal` instead of `--url` for
personal development builds. `bundle_runtime.py` copies a relocatable uv-managed
CPython 3.12 distribution, including its license files, beside the app under
`runtime/python`. The app chooses a project's existing virtual environment,
then an explicit interpreter override, then this runtime before searching PATH.
Never use the PyInstaller GUI executable as a project Python interpreter.

On Windows, compile `packaging/windows.iss` with Inno Setup 6. It produces
`out/SPARKLE-CODER-Windows-Setup.exe`, a per-user setup wizard with shortcuts.
It installs under Local AppData and opens the app after installation. Generated
PROJECTS and APP_DATA are excluded from installation and uninstall deletion.

The smoke check copies the app and runtime to a temporary folder, removes
SPARKLE_PYTHON, limits PATH, then verifies the real commands use the bundled
runtime. It covers launch, storage, website pairing, approval, actual scripted
Python repair, history, downloads, revocation and shutdown. It does not invoke
NVIDIA or establish visual quality. Other project tools are not bundled.

## GitHub Actions

The workflow runs Python/gateway/JavaScript tests before building on Windows,
macOS and Linux. Windows additionally installs the EXE silently, verifies the
installed app, reinstalls over sample user data, and checks that uninstall
preserves that data. Linux/macOS produce portable archives with their runtime.

Set repository variable `SPARKLE_PILOT_URL` to the deployed origin. Run
**Build installers** with the tester option enabled. The workflow fails rather
than shipping a tester build with an empty address. Ordinary pushes without
that variable produce personal builds for development checks. `EDITION.txt`
identifies what was built. Tagged builds attach assets to a GitHub Release.
Check the workflow result before sharing the installer.

Builds are unsigned. Code signing and macOS notarization are not configured;
operating-system publisher warnings can appear. Native dialog behavior and
visual checks still need actual target-system verification.
