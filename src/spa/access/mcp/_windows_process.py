"""Own one Windows MCP CLI invocation and its inherited children."""

import sys

if sys.platform == "win32":
    import asyncio
    import ctypes
    from ctypes import wintypes
    from typing import Any

    CREATE_SUSPENDED = 0x00000004
    PROCESS_SET_QUOTA_AND_TERMINATE = 0x0101
    TH32CS_SNAPTHREAD = 0x0004
    THREAD_SUSPEND_RESUME = 0x0002

    class _ThreadEntry(ctypes.Structure):
        _fields_ = [
            ("size", wintypes.DWORD),
            ("usage", wintypes.DWORD),
            ("thread_id", wintypes.DWORD),
            ("owner_pid", wintypes.DWORD),
            ("base_priority", wintypes.LONG),
            ("delta_priority", wintypes.LONG),
            ("flags", wintypes.DWORD),
        ]

    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    for _name, _returns, _arguments in (
        ("CreateJobObjectW", wintypes.HANDLE, [ctypes.c_void_p, wintypes.LPCWSTR]),
        (
            "OpenProcess",
            wintypes.HANDLE,
            [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
        ),
        ("AssignProcessToJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.HANDLE]),
        ("TerminateJobObject", wintypes.BOOL, [wintypes.HANDLE, wintypes.UINT]),
        ("CreateToolhelp32Snapshot", wintypes.HANDLE, [wintypes.DWORD, wintypes.DWORD]),
        (
            "Thread32First",
            wintypes.BOOL,
            [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)],
        ),
        (
            "Thread32Next",
            wintypes.BOOL,
            [wintypes.HANDLE, ctypes.POINTER(_ThreadEntry)],
        ),
        (
            "OpenThread",
            wintypes.HANDLE,
            [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD],
        ),
        ("ResumeThread", wintypes.DWORD, [wintypes.HANDLE]),
        ("CloseHandle", wintypes.BOOL, [wintypes.HANDLE]),
    ):
        _function = getattr(_kernel32, _name)
        _function.restype = _returns
        _function.argtypes = _arguments

    def _checked(value):
        if not value:
            raise ctypes.WinError(ctypes.get_last_error())
        return value

    class WindowsJob:
        """Retain ownership even when the selected CLI exits before its child."""

        def __init__(self):
            self.handle = _checked(_kernel32.CreateJobObjectW(None, None))

        def start_options(self) -> dict[str, Any]:
            # Establish ownership before the CLI can create a child or exit.
            return {"creationflags": CREATE_SUSPENDED}

        def acquire(self, process: asyncio.subprocess.Process) -> None:
            pid = process.pid
            process_handle = _checked(
                _kernel32.OpenProcess(PROCESS_SET_QUOTA_AND_TERMINATE, False, pid)
            )
            try:
                _checked(
                    _kernel32.AssignProcessToJobObject(self.handle, process_handle)
                )
            finally:
                _checked(_kernel32.CloseHandle(process_handle))
            snapshot = _kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0)
            if snapshot == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            try:
                entry = _ThreadEntry()
                entry.size = ctypes.sizeof(entry)
                more = _checked(_kernel32.Thread32First(snapshot, ctypes.byref(entry)))
                while more:
                    if entry.owner_pid == pid:
                        thread = _checked(
                            _kernel32.OpenThread(
                                THREAD_SUSPEND_RESUME, False, entry.thread_id
                            )
                        )
                        try:
                            if _kernel32.ResumeThread(thread) == 0xFFFFFFFF:
                                raise ctypes.WinError(ctypes.get_last_error())
                            return
                        finally:
                            _checked(_kernel32.CloseHandle(thread))
                    more = _kernel32.Thread32Next(snapshot, ctypes.byref(entry))
                raise OSError("Suspended SPA CLI thread was not found")
            finally:
                _checked(_kernel32.CloseHandle(snapshot))

        def terminate(self, process: asyncio.subprocess.Process) -> None:
            _checked(_kernel32.TerminateJobObject(self.handle, 1))

        def release(self) -> None:
            # A completed invocation must not acquire kill-on-close semantics.
            _checked(_kernel32.CloseHandle(self.handle))
