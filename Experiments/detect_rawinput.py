"""
Raw Input diagnostic for Bluetooth / TWS earbud media keys.

RegisterRawInputDevices with RIDEV_INPUTSINK catches HID consumer-control
packets (the actual Bluetooth payload) before Windows routes them to any app.
This is the level at which earbud play/pause is reliably visible.

Run this, tap your earbuds, and look for WM_INPUT lines.
Ctrl+C to stop.
"""
import ctypes
import ctypes.wintypes
import time

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# ── 64-bit-safe WndProc callback type ─────────────────────────────────────────
WNDPROCTYPE = ctypes.WINFUNCTYPE(
    ctypes.c_ssize_t,
    ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t,
)
user32.DefWindowProcW.restype  = ctypes.c_ssize_t
user32.DefWindowProcW.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_size_t, ctypes.c_ssize_t]

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

# ── Raw Input structures ───────────────────────────────────────────────────────
class RAWINPUTDEVICE(ctypes.Structure):
    _fields_ = [
        ("usUsagePage", ctypes.c_ushort),
        ("usUsage",     ctypes.c_ushort),
        ("dwFlags",     ctypes.c_ulong),
        ("hwndTarget",  ctypes.c_void_p),
    ]

class RAWINPUTHEADER(ctypes.Structure):
    _fields_ = [
        ("dwType",  ctypes.c_ulong),
        ("dwSize",  ctypes.c_ulong),
        ("hDevice", ctypes.c_void_p),
        ("wParam",  ctypes.c_size_t),
    ]

class RAWHID(ctypes.Structure):
    _fields_ = [
        ("dwSizeHid", ctypes.c_ulong),
        ("dwCount",   ctypes.c_ulong),
        ("bRawData",  ctypes.c_ubyte * 1),  # variable length; we read past this
    ]

class RAWINPUT(ctypes.Structure):
    _fields_ = [
        ("header", RAWINPUTHEADER),
        ("data",   RAWHID),
    ]

WM_INPUT       = 0x00FF
RIM_TYPEHID    = 2
RIDEV_INPUTSINK = 0x00000100

# HID Consumer Control usage page and common play/pause usage ID
USAGE_PAGE_CONSUMER = 0x000C
USAGE_PLAY_PAUSE    = 0x00CD   # 205  — what most earbuds send

wnd_proc_ref = None

def wnd_proc(hwnd, msg, wparam, lparam):
    if msg == WM_INPUT:
        ts = time.strftime("%H:%M:%S")

        # First call: ask how big the buffer needs to be
        size = ctypes.c_uint(0)
        user32.GetRawInputData(
            ctypes.c_void_p(lparam),
            0x10000003,          # RID_INPUT
            None,
            ctypes.byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )

        buf = (ctypes.c_ubyte * size.value)()
        user32.GetRawInputData(
            ctypes.c_void_p(lparam),
            0x10000003,
            buf,
            ctypes.byref(size),
            ctypes.sizeof(RAWINPUTHEADER),
        )

        ri = ctypes.cast(buf, ctypes.POINTER(RAWINPUT)).contents
        if ri.header.dwType == RIM_TYPEHID:
            raw_bytes = bytes(buf[ctypes.sizeof(RAWINPUTHEADER):
                                  ctypes.sizeof(RAWINPUTHEADER) + ri.data.dwSizeHid])
            hex_str = " ".join(f"{b:02x}" for b in raw_bytes)

            # Check if bytes match play/pause usage ID (0xCD = 205)
            marker = "  *** PLAY/PAUSE? ***" if 0xcd in raw_bytes else ""
            print(f"[{ts}] WM_INPUT HID  bytes=[ {hex_str} ]{marker}")

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

wnd_proc_ref = WNDPROCTYPE(wnd_proc)

hinstance  = kernel32.GetModuleHandleW(None)
class_name = "VaaniRawInput"

wc               = WNDCLASSEXW()
wc.cbSize        = ctypes.sizeof(WNDCLASSEXW)
wc.lpfnWndProc   = wnd_proc_ref
wc.hInstance     = hinstance
wc.lpszClassName = class_name
user32.RegisterClassExW(ctypes.byref(wc))

hwnd = user32.CreateWindowExW(0, class_name, "VaaniRaw", 0, 0,0,0,0, None, None, hinstance, None)

# Register for Consumer Controls (usage page 0x000C, usage 0x0001 = top-level collection)
# RIDEV_INPUTSINK: receive input even when this window is not in the foreground
rid = RAWINPUTDEVICE()
rid.usUsagePage = USAGE_PAGE_CONSUMER
rid.usUsage     = 0x0001
rid.dwFlags     = RIDEV_INPUTSINK
rid.hwndTarget  = hwnd

result = user32.RegisterRawInputDevices(
    ctypes.byref(rid), 1, ctypes.sizeof(RAWINPUTDEVICE)
)
print(f"RegisterRawInputDevices: {'OK' if result else 'FAILED'}")
print("Tap your earbuds. WM_INPUT lines should appear. Ctrl+C to stop.\n")

msg = ctypes.wintypes.MSG()
try:
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
except KeyboardInterrupt:
    pass
