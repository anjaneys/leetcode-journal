"""Reading text from the Windows clipboard with no extra dependencies.

Solutions are written in LeetCode's browser editor, so the clipboard is how
the code gets back into the repo: Ctrl+A, Ctrl+C in the editor, then save.
"""
from __future__ import annotations

import ctypes
import time
from ctypes import wintypes

CF_UNICODETEXT = 13

_user32 = ctypes.WinDLL("user32", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

_user32.OpenClipboard.argtypes = [wintypes.HWND]
_user32.OpenClipboard.restype = wintypes.BOOL
_user32.GetClipboardData.argtypes = [wintypes.UINT]
_user32.GetClipboardData.restype = wintypes.HANDLE
_user32.CloseClipboard.restype = wintypes.BOOL
_kernel32.GlobalLock.argtypes = [wintypes.HGLOBAL]
_kernel32.GlobalLock.restype = ctypes.c_void_p
_kernel32.GlobalUnlock.argtypes = [wintypes.HGLOBAL]


def read_text() -> str:
    """Current clipboard text, or '' if it holds no text."""
    # Another app can hold the clipboard for a moment (browsers do while
    # copying), so retry briefly instead of failing on the first attempt.
    for _ in range(10):
        if _user32.OpenClipboard(None):
            break
        time.sleep(0.05)
    else:
        return ""
    try:
        handle = _user32.GetClipboardData(CF_UNICODETEXT)
        if not handle:
            return ""
        pointer = _kernel32.GlobalLock(handle)
        if not pointer:
            return ""
        try:
            return ctypes.wstring_at(pointer)
        finally:
            _kernel32.GlobalUnlock(handle)
    finally:
        _user32.CloseClipboard()
