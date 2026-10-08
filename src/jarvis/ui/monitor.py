from __future__ import annotations

import ctypes
import shutil
from dataclasses import dataclass


@dataclass(frozen=True)
class SystemMetrics:
    memory_percent: int
    disk_percent: int
    cpu_percent: int | None


def system_metrics() -> SystemMetrics:
    """Read harmless local system indicators without third-party dependencies."""
    memory = _memory_percent()
    disk = shutil.disk_usage(".")
    disk_percent = round((disk.used / disk.total) * 100) if disk.total else 0
    return SystemMetrics(memory_percent=memory, disk_percent=disk_percent, cpu_percent=None)


def _memory_percent() -> int:
    if hasattr(ctypes, "windll"):
        class MemoryStatus(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(status)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return int(status.dwMemoryLoad)
    return 0
