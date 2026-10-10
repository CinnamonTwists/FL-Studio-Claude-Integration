"""Resolve the user's real FL Studio user-data folder and Documents folder.

FL's "User data folder" (Options > File settings) can live anywhere, and on
Windows Documents is often redirected (e.g. to OneDrive), so ``~/Documents``
is not a safe guess. Resolution order for the FL user-data folder:

  1. $FLSTUDIO_MCP_USER_DATA (full path to the "FL Studio" user-data folder)
  2. HKCU\\Software\\Image-Line\\Shared\\Paths "Shared data" + "FL Studio"
  3. <Documents>/Image-Line/FL Studio
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


def documents_dir() -> Path:
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [("Data1", wintypes.DWORD), ("Data2", wintypes.WORD),
                            ("Data3", wintypes.WORD), ("Data4", ctypes.c_ubyte * 8)]

            # FOLDERID_Documents {FDD39AD0-238F-46AF-ADB4-6C85480369C7}
            fid = GUID(0xFDD39AD0, 0x238F, 0x46AF,
                       (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7))
            buf = ctypes.c_wchar_p()
            if ctypes.windll.shell32.SHGetKnownFolderPath(
                    ctypes.byref(fid), 0, None, ctypes.byref(buf)) == 0:
                try:
                    return Path(buf.value)
                finally:
                    ctypes.windll.ole32.CoTaskMemFree(buf)
        except Exception:
            pass
    return Path.home() / "Documents"


def _registry_path(name: str) -> Path | None:
    if sys.platform != "win32":
        return None
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Image-Line\Shared\Paths") as k:
            value, _ = winreg.QueryValueEx(k, name)
        return Path(os.path.expandvars(value)) if value else None
    except OSError:
        return None


def _registry_shared_data() -> Path | None:
    return _registry_path("Shared data")


def fl_install_dir() -> Path | None:
    return _registry_path("Install path")


def flex_pack_dirs() -> list[Path]:
    """User packs (<shared data>/FLEX/Packs) and factory packs (<install>/Data/Patches/Packs/FLEX/Packs)."""
    dirs = []
    shared, install = _registry_shared_data(), fl_install_dir()
    if shared:
        dirs.append(shared / "FLEX" / "Packs")
    dirs.append(documents_dir() / "Image-Line" / "FLEX" / "Packs")
    if install:
        dirs.append(install / "Data" / "Patches" / "Packs" / "FLEX" / "Packs")
    return [d for d in dirs if d.is_dir()]


def image_line_roots() -> list[Path]:
    """Folders that may contain 'FL Studio*' user-data folders, best first."""
    roots = []
    shared = _registry_shared_data()
    if shared:
        roots.append(shared)
    roots += [documents_dir() / "Image-Line", Path.home() / "Documents" / "Image-Line",
              Path.home() / "Image-Line"]
    return roots


def fl_user_data_dir() -> Path:
    env = os.environ.get("FLSTUDIO_MCP_USER_DATA")
    if env:
        return Path(env)
    for root in image_line_roots():
        if (root / "FL Studio" / "Settings").is_dir():
            return root / "FL Studio"
    return documents_dir() / "Image-Line" / "FL Studio"
