"""
SMTC Win32 interop diagnostic — detect_smtc2.py

get_for_current_view() requires a UWP view and fails in Win32 Python.
The correct Win32 path is ISystemMediaTransportControlsInterop::GetForWindow(hwnd).
This script:
  1. Creates a hidden Win32 HWND.
  2. Calls RoGetActivationFactory to get the interop factory via COM vtable.
  3. Calls GetForWindow(hwnd) to get an SMTC bound to that window.
  4. Tries SystemMediaTransportControls.from_abi(ptr) to wrap it with the
     Python winrt type so we can use Python-style event subscription.
  5. Runs a Win32 message loop so events can fire.

Requires: winrt-Windows.Media (already installed)
Run:      python detect_smtc2.py
Then tap earbuds and look for *** BUTTON PRESSED *** lines.
Ctrl+C to stop.
"""

import ctypes
import ctypes.wintypes

from winrt.windows.media import (
    SystemMediaTransportControls,
    SystemMediaTransportControlsButton,
    MediaPlaybackStatus,
)

combase = ctypes.windll.combase
user32  = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32


# ── GUID helper ────────────────────────────────────────────────────────────────

class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", ctypes.c_ulong),
        ("Data2", ctypes.c_ushort),
        ("Data3", ctypes.c_ushort),
        ("Data4", ctypes.c_ubyte * 8),
    ]

def _guid(s):
    s = s.strip("{}")
    p = s.split("-")
    g = GUID()
    g.Data1 = int(p[0], 16)
    g.Data2 = int(p[1], 16)
    g.Data3 = int(p[2], 16)
    d4 = bytes.fromhex(p[3] + p[4])
    for i, b in enumerate(d4):
        g.Data4[i] = b
    return g

# ISystemMediaTransportControlsInterop — factory for Win32 SMTC binding
IID_INTEROP = _guid("{ddb0472d-c911-4a1f-86d9-dc3d71a95f5a}")
# ISystemMediaTransportControls — the WinRT interface we want back
IID_SMTC    = _guid("{99fa3ff4-1742-42a6-902e-087d41f965ec}")


# ── WinRT apartment init ───────────────────────────────────────────────────────

combase.RoInitialize.restype  = ctypes.HRESULT
combase.RoInitialize.argtypes = [ctypes.c_uint32]

# RO_INIT_SINGLETHREADED = 0; events dispatch on this thread's message pump.
hr = combase.RoInitialize(0)
# 0 = S_OK (first init), 1 = S_FALSE (already init on this thread) — both fine.
if hr not in (0, 1):
    print(f"[WARN] RoInitialize returned {hr:#010x} — continuing anyway.")


# ── WinRT string / factory helpers ────────────────────────────────────────────

combase.WindowsCreateString.restype  = ctypes.HRESULT
combase.WindowsCreateString.argtypes = [
    ctypes.c_wchar_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)
]
combase.WindowsDeleteString.restype  = ctypes.HRESULT
combase.WindowsDeleteString.argtypes = [ctypes.c_void_p]

combase.RoGetActivationFactory.restype  = ctypes.HRESULT
combase.RoGetActivationFactory.argtypes = [
    ctypes.c_void_p,
    ctypes.POINTER(GUID),
    ctypes.POINTER(ctypes.c_void_p),
]

VTABLE_FN = ctypes.WINFUNCTYPE(
    ctypes.HRESULT,
    ctypes.c_void_p,           # this (factory)
    ctypes.c_void_p,           # HWND
    ctypes.POINTER(GUID),      # REFIID
    ctypes.POINTER(ctypes.c_void_p),  # ppv (out)
)


# ── Hidden Win32 window (provides the HWND) ───────────────────────────────────

user32.DefWindowProcW.restype  = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]

WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
)

class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize",        ctypes.c_uint),  ("style",         ctypes.c_uint),
        ("lpfnWndProc",   WNDPROCTYPE),    ("cbClsExtra",    ctypes.c_int),
        ("cbWndExtra",    ctypes.c_int),   ("hInstance",     ctypes.wintypes.HINSTANCE),
        ("hIcon",         ctypes.wintypes.HICON),
        ("hCursor",       ctypes.wintypes.HANDLE),
        ("hbrBackground", ctypes.wintypes.HBRUSH),
        ("lpszMenuName",  ctypes.c_wchar_p), ("lpszClassName", ctypes.c_wchar_p),
        ("hIconSm",       ctypes.wintypes.HICON),
    ]

_wnd_proc_ref = None

def _wnd_proc(hwnd, msg, wp, lp):
    return user32.DefWindowProcW(hwnd, msg, wp, lp)

_wnd_proc_ref = WNDPROCTYPE(_wnd_proc)
hinstance     = kernel32.GetModuleHandleW(None)

wc               = WNDCLASSEXW()
wc.cbSize        = ctypes.sizeof(WNDCLASSEXW)
wc.lpfnWndProc   = _wnd_proc_ref
wc.hInstance     = hinstance
wc.lpszClassName = "VaaniSMTC2"
user32.RegisterClassExW(ctypes.byref(wc))

hwnd = user32.CreateWindowExW(0, "VaaniSMTC2", "VaaniSMTC2", 0,
                               0, 0, 0, 0, None, None, hinstance, None)
print(f"[1] HWND created: {hwnd:#010x}")


# ── Get activation factory (ISystemMediaTransportControlsInterop) ─────────────

class_id = "Windows.Media.SystemMediaTransportControls"
hstr     = ctypes.c_void_p()
combase.WindowsCreateString(class_id, len(class_id), ctypes.byref(hstr))

factory = ctypes.c_void_p()
hr = combase.RoGetActivationFactory(hstr, ctypes.byref(IID_INTEROP), ctypes.byref(factory))
combase.WindowsDeleteString(hstr)
print(f"[2] RoGetActivationFactory: {'OK' if hr == 0 else f'FAIL {hr:#010x}'}")

if hr != 0:
    print("    Cannot get interop factory — stopping.")
    raise SystemExit(1)


# ── Call ISystemMediaTransportControlsInterop::GetForWindow ───────────────────
# vtable layout (IInspectable parent):
#   [0] QueryInterface  [1] AddRef  [2] Release           — IUnknown
#   [3] GetIids  [4] GetRuntimeClassName  [5] GetTrustLevel — IInspectable
#   [6] GetForWindow                                        — this interface

vtable_ptr = ctypes.cast(factory, ctypes.POINTER(ctypes.c_void_p)).contents.value
vtable     = ctypes.cast(vtable_ptr, ctypes.POINTER(ctypes.c_void_p))
get_for_window = VTABLE_FN(vtable[6])

smtc_raw = ctypes.c_void_p()
hr = get_for_window(
    factory,
    ctypes.c_void_p(hwnd),
    ctypes.byref(IID_SMTC),
    ctypes.byref(smtc_raw),
)
addr = smtc_raw.value or 0
print(f"[3] GetForWindow: {'OK' if hr == 0 else f'FAIL {hr:#010x}'}  ptr={addr:#010x}")

if hr != 0:
    print("    GetForWindow failed — stopping.")
    raise SystemExit(1)


# ── Wrap raw pointer with Python winrt type ───────────────────────────────────

has_from_abi = hasattr(SystemMediaTransportControls, 'from_abi')
print(f"[4] SystemMediaTransportControls.from_abi present: {has_from_abi}")

smtc = None
if has_from_abi:
    try:
        smtc = SystemMediaTransportControls.from_abi(addr)
        print(f"    from_abi OK: {smtc}")
    except Exception as e:
        print(f"    from_abi FAILED: {e}")

if smtc is None:
    print("    Cannot wrap pointer — full COM vtable approach needed.")
    raise SystemExit(1)


# ── Configure SMTC and register button handler ───────────────────────────────

try:
    smtc.is_enabled       = True
    smtc.is_play_enabled  = True
    smtc.is_pause_enabled = True
    # PLAYING status makes Windows route media keys to us instead of Spotify/YT Music.
    smtc.playback_status  = MediaPlaybackStatus.PLAYING
    print("[5] SMTC properties set (enabled, play, pause, status=Playing).")
except Exception as e:
    print(f"[5] Failed to set properties: {e}")
    raise SystemExit(1)

_BTN = {
    SystemMediaTransportControlsButton.PLAY_PAUSE: "PLAY_PAUSE",
    SystemMediaTransportControlsButton.PLAY:       "PLAY",
    SystemMediaTransportControlsButton.PAUSE:      "PAUSE",
    SystemMediaTransportControlsButton.STOP:       "STOP",
    SystemMediaTransportControlsButton.NEXT:       "NEXT",
    SystemMediaTransportControlsButton.PREVIOUS:   "PREVIOUS",
}

def _on_button(sender, args):
    name = _BTN.get(args.button, str(args.button))
    print(f"*** BUTTON PRESSED: {name} ***", flush=True)

try:
    smtc.button_pressed += _on_button
    print("[6] ButtonPressed handler registered.")
except Exception as e:
    print(f"[6] Failed to register ButtonPressed: {e}")
    raise SystemExit(1)


# ── Win32 message loop (required for STA event dispatch) ─────────────────────

print("\nAll good. Tap your earbuds now. Ctrl+C to stop.\n")
msg = ctypes.wintypes.MSG()
try:
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
except KeyboardInterrupt:
    print("\nStopped.")
