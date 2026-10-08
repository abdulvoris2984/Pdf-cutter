# PyInstaller recipe for PDF Cutter. Build with:  pyinstaller pdf-cutter.spec
# Produces dist/PDF-Cutter(.exe) on Windows/Linux and dist/PDF Cutter.app on macOS.
import platform
import sys
from pathlib import Path

import tkinterdnd2
from PyInstaller.utils.hooks import collect_data_files

VERSION = "2.0.0"


def tkdnd_platform() -> str:
    """The tkdnd folder tkinterdnd2 will look for on this machine (see TkinterDnD._require)."""
    machine = platform.machine().lower()
    if sys.platform == "darwin":
        return "osx-arm64" if machine == "arm64" else "osx-x64"
    if sys.platform.startswith("win"):
        return "win-arm64" if "arm" in machine else ("win-x64" if machine.endswith("64") else "win-x86")
    return "linux-arm64" if machine in ("aarch64", "arm64") else "linux-x64"


datas = [("assets", "assets")]
datas += collect_data_files("customtkinter")  # themes and fonts
datas += collect_data_files("pptx")  # PowerPoint templates
binaries = []

# Drag and drop: only bundle the native library for the platform being built.
dnd_folder = Path(tkinterdnd2.__file__).parent / "tkdnd" / tkdnd_platform()
for file in dnd_folder.iterdir():
    target = f"tkinterdnd2/tkdnd/{dnd_folder.name}"
    if file.suffix in (".dll", ".so", ".dylib"):
        binaries.append((str(file), target))
    elif file.suffix == ".tcl":
        datas.append((str(file), target))

a = Analysis(
    ["app.py"],
    datas=datas,
    binaries=binaries,
    hiddenimports=["PIL._tkinter_finder"],  # needed for images in CustomTkinter, PyInstaller misses it
    excludes=["pytest"],
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="PDF Cutter", console=False)
    coll = COLLECT(exe, a.binaries, a.datas, name="PDF Cutter")
    app = BUNDLE(
        coll,
        name="PDF Cutter.app",
        icon="assets/icon.icns",
        bundle_identifier="io.github.abdulvoris2984.pdfcutter",
        info_plist={
            "CFBundleShortVersionString": VERSION,
            "NSHighResolutionCapable": True,
            "NSRequiresAquaSystemAppearance": False,  # allow dark mode
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="PDF-Cutter", console=False, icon="assets/icon.ico",
    )
