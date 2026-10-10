"""Screen capture, template matching and focus-verified input (Windows).

Safety rule: input is only ever sent while a window belonging to FL Studio's
process is in the foreground. If focus can't be confirmed we raise instead of
typing blind into whatever app the user is in.
"""

from __future__ import annotations

import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path

import numpy as np

TEMPLATES = Path(__file__).parent / "templates"


class DesktopError(RuntimeError):
    pass


def _require_windows():
    if sys.platform != "win32":
        raise DesktopError("desktop automation is currently Windows-only")


_dpi_set = False


def _dpi_aware():
    global _dpi_set
    if not _dpi_set:
        ctypes.windll.user32.SetProcessDPIAware()
        _dpi_set = True


# -- focus ---------------------------------------------------------------------

def _pid_of(hwnd) -> int:
    pid = wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(wintypes.HWND(hwnd), ctypes.byref(pid))
    return pid.value


def fl_hwnd():
    from ..pyscript_trigger import find_fl_hwnd
    return find_fl_hwnd()


def fl_is_foreground() -> bool:
    """True when the foreground window belongs to FL's process (main window,
    plugin window or one of FL's own dialogs)."""
    h = fl_hwnd()
    fg = ctypes.windll.user32.GetForegroundWindow()
    return bool(h and fg and _pid_of(fg) == _pid_of(h))


def _class_name(hwnd) -> str:
    buf = ctypes.create_unicode_buffer(64)
    ctypes.windll.user32.GetClassNameW(wintypes.HWND(hwnd), buf, 64)
    return buf.value


_FL_CORE_CLASSES = {"TFruityLoopsMainForm", "TApplication"}


def fl_dialogs(standard_only: bool = False) -> list:
    """Visible top-level windows owned by FL's process other than its main window:
    Windows common dialogs (#32770, e.g. Save As) and FL's own popups (e.g.
    'Project size warning', confirmations). [(hwnd, title, class)]."""
    h = fl_hwnd()
    if not h:
        return []
    pid, out = _pid_of(h), []
    u = ctypes.windll.user32
    proto = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def cb(hwnd, _):
        if u.IsWindowVisible(hwnd) and _pid_of(hwnd) == pid:
            cls = _class_name(hwnd)
            if cls not in _FL_CORE_CLASSES and (not standard_only or cls == "#32770"):
                t = ctypes.create_unicode_buffer(128)
                u.GetWindowTextW(hwnd, t, 128)
                out.append((hwnd, t.value, cls))
        return True
    u.EnumWindows(proto(cb), 0)
    return out


def wait_for_fl_dialog(title: str | None = None, timeout: float = 10.0):
    """Wait until an FL-owned standard dialog is in the FOREGROUND; return its hwnd.
    Nothing gets typed until this succeeds, so keys can't land in the wrong window."""
    t0 = time.time()
    while time.time() - t0 < timeout:
        fg = ctypes.windll.user32.GetForegroundWindow()
        for hwnd, t, _cls in fl_dialogs(standard_only=True):
            if hwnd == fg and (title is None or title.lower() in t.lower()):
                return hwnd
        time.sleep(0.2)
    return None


def close_window(hwnd):
    ctypes.windll.user32.PostMessageW(wintypes.HWND(hwnd), 0x0010, 0, 0)   # WM_CLOSE (= Cancel)


def fl_monitor_rect():
    """(left, top, right, bottom) of the monitor FL's main window is on."""
    _dpi_aware()
    h = fl_hwnd()
    if not h:
        raise DesktopError("FL Studio window not found")
    u = ctypes.windll.user32
    mon = u.MonitorFromWindow(wintypes.HWND(h), 2)

    class MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT),
                    ("rcWork", wintypes.RECT), ("dwFlags", wintypes.DWORD)]
    mi = MONITORINFO()
    mi.cbSize = ctypes.sizeof(MONITORINFO)
    u.GetMonitorInfoW(mon, ctypes.byref(mi))
    r = mi.rcMonitor
    return r.left, r.top, r.right, r.bottom


def ensure_fl_foreground(retries: int = 3):
    _require_windows()
    from ..pyscript_trigger import force_focus
    h = fl_hwnd()
    if not h:
        raise DesktopError("FL Studio main window not found -- is FL running?")
    for _ in range(retries):
        if fl_is_foreground():
            return
        force_focus(h)
        time.sleep(0.35)
    if not fl_is_foreground():
        raise DesktopError("could not bring FL Studio to the foreground; refusing to send input")


# -- capture + matching --------------------------------------------------------

_grab_origin = (0, 0)


def grab(region=None) -> np.ndarray:
    """Greyscale float32 screenshot of FL's monitor (physical pixels)."""
    global _grab_origin
    _require_windows()
    _dpi_aware()
    from PIL import ImageGrab
    region = region or fl_monitor_rect()
    _grab_origin = region[:2]
    img = ImageGrab.grab(bbox=region, all_screens=True)
    return np.asarray(img.convert("L"), dtype=np.float32)


def save_screenshot(path: str, region=None) -> str:
    """Save a screenshot; defaults to FL's monitor only (never other monitors)."""
    _dpi_aware()
    from PIL import ImageGrab
    ImageGrab.grab(bbox=region or fl_monitor_rect(), all_screens=True).save(path)
    return path


def locate(template: str, img: np.ndarray | None = None, min_score: float = 0.8):
    """Find a template PNG on screen by normalised cross-correlation.

    Returns (x, y, score) of the template's top-left in screen coordinates,
    or None when the best match is below ``min_score``.
    """
    from PIL import Image
    from scipy.signal import fftconvolve
    if img is None:
        img = grab()
    t = np.asarray(Image.open(TEMPLATES / template).convert("L"), dtype=np.float32)
    t = t - t.mean()
    tn = np.sqrt((t ** 2).sum())
    corr = fftconvolve(img, t[::-1, ::-1], mode="valid")
    ones = np.ones_like(t)
    s1 = fftconvolve(img, ones, mode="valid")
    s2 = fftconvolve(img ** 2, ones, mode="valid")
    var = s2 - s1 ** 2 / t.size
    ncc = corr / (np.sqrt(np.maximum(var, 1.0)) * tn)
    ncc[var < t.size * 25.0] = 0          # flat regions carry no signal
    y, x = np.unravel_index(int(np.argmax(ncc)), ncc.shape)
    score = float(ncc[y, x])
    if score < min_score:
        return None
    ox, oy = _grab_origin                 # grab() captures FL's monitor; map back to screen coords
    return int(x) + ox, int(y) + oy, round(score, 3)


# -- input (only after ensure_fl_foreground) ----------------------------------

def move(x, y, settle=0.12):
    _dpi_aware()
    ctypes.windll.user32.SetCursorPos(int(x), int(y))
    time.sleep(settle)


def click(x, y, settle=0.3):
    ensure_fl_foreground()
    move(x, y)
    u = ctypes.windll.user32
    u.mouse_event(0x2, 0, 0, 0, 0)
    u.mouse_event(0x4, 0, 0, 0, 0)
    time.sleep(settle)


def wheel(x, y, notches: int):
    ensure_fl_foreground()
    move(x, y)
    for _ in range(abs(notches)):
        ctypes.windll.user32.mouse_event(0x800, 0, 0, 120 if notches > 0 else -120, 0)
        time.sleep(0.06)


def hotkey(*keys, settle=0.3):
    ensure_fl_foreground()
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.hotkey(*keys)
    time.sleep(settle)


def type_text(text: str, settle=0.3):
    ensure_fl_foreground()
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.write(text, interval=0.01)
    time.sleep(settle)
