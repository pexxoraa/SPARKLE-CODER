# PyInstaller spec for a single-file SPARKLE CODER executable.
#
# Build locally (must run on the OS you're building FOR — PyInstaller does
# not cross-compile):
#   pip install pyinstaller
#   pyinstaller packaging/sparkle-coder.spec
#   -> output lands in dist/SparkleCoder(.exe)
#
# In practice, use the GitHub Actions workflow instead
# (.github/workflows/build-installers.yml), which runs this exact command on
# real Windows, macOS, and Linux runners and publishes all three as a
# Release automatically — see packaging/README.md.
from pathlib import Path

project_root = Path(SPECPATH).resolve().parent

a = Analysis(
    [str(Path(SPECPATH) / "bootstrap.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[
        (str(project_root / 'sparkle_coder' / 'distribution.json'), 'sparkle_coder'),
        (str(project_root / "sparkle_coder" / "ui"), "sparkle_coder/ui"),
        (str(project_root / "OPEN_FIRST.html"), "."),
    ],
    hiddenimports=["tkinter", "tkinter.filedialog", "tkinter.messagebox"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SparkleCoder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,       # no terminal window; errors show as a message box (see launcher.py)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,   # unsigned — see packaging/README.md for what that means for testers
    entitlements_file=None,
    icon=None,            # add an .ico/.icns here later if you want a custom icon
)
