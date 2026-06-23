import ctypes
import ctypes.wintypes
import time

user32   = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

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

WM_APPCOMMAND = 0x0319
WM_SHELLHOOK  = user32.RegisterWindowMessageW("SHELLHOOK")

SHELL_HOOK_NAMES = {
    1: "WINDOWCREATED", 2: "WINDOWDESTROYED", 3: "ACTIVATESHELLWINDOW",
    4: "WINDOWACTIVATED", 5: "GETMINRECT", 6: "REDRAW", 7: "TASKMAN",
    8: "LANGUAGE", 9: "SYSMENU", 10: "ENDTASK", 11: "ACCESSIBILITYSTATE",
    12: "APPCOMMAND", 13: "WINDOWREPLACED", 14: "WINDOWACTIVATING",
    16: "FLASH", 20: "RUDEAPPACTIVATED", 32: "WINDOWACTIVATED_HIGH",
    33: "RUDEAPPACTIVATED_HIGH",
}
APPCOMMAND_NAMES = {
    11: "NEXTTRACK", 12: "PREVTRACK", 13: "STOP",
    14: "PLAY_PAUSE", 46: "PLAY", 47: "PAUSE",
}

wnd_proc_ref = None

def wnd_proc(hwnd, msg, wparam, lparam):
    ts = time.strftime("%H:%M:%S")

    if msg == WM_APPCOMMAND:
        cmd  = (lparam >> 16) & 0xFFF
        name = APPCOMMAND_NAMES.get(cmd, f"code {cmd}")
        print(f"[{ts}] *** WM_APPCOMMAND  cmd={cmd} ({name})")

    elif msg == WM_SHELLHOOK:
        hook_code  = wparam & 0xFFFF
        hook_name  = SHELL_HOOK_NAMES.get(hook_code, f"code {hook_code}")
        cmd        = (lparam >> 16) & 0xFFF
        cmd_name   = APPCOMMAND_NAMES.get(cmd, f"cmd {cmd}")
        print(f"[{ts}]  SHELLHOOK  {hook_name:<22}  lparam={lparam:#018x}  app_cmd={cmd_name}")

    return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

wnd_proc_ref = WNDPROCTYPE(wnd_proc)

hinstance  = kernel32.GetModuleHandleW(None)
class_name = "VaaniDiag4"

wc               = WNDCLASSEXW()
wc.cbSize        = ctypes.sizeof(WNDCLASSEXW)
wc.lpfnWndProc   = wnd_proc_ref
wc.hInstance     = hinstance
wc.lpszClassName = class_name
user32.RegisterClassExW(ctypes.byref(wc))

hwnd = user32.CreateWindowExW(0, class_name, "VaaniDiag", 0, 0,0,0,0, None, None, hinstance, None)
user32.RegisterShellHookWindow(hwnd)

print("All messages shown with timestamps. Tap earbuds and look for new lines.")
print("Ctrl+C to stop.\n")

msg = ctypes.wintypes.MSG()
try:
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        user32.TranslateMessage(ctypes.byref(msg))
        user32.DispatchMessageW(ctypes.byref(msg))
except KeyboardInterrupt:
    pass
