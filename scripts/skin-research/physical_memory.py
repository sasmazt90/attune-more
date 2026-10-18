"""Live physical RAM, with a GIL-releasing Windows API binding.

Cache only the System32 function binding, never a memory observation.  The
PERFORMANCE_INFORMATION contract is the same one used by psutil on Windows.
"""
import ctypes
import os
from functools import lru_cache

import psutil


class PhysicalMemoryUnavailable(RuntimeError):
    pass


class _PerformanceInformation(ctypes.Structure):
    _fields_ = [
        ('cb', ctypes.c_uint32),
        *[(name, ctypes.c_size_t) for name in (
            'CommitTotal', 'CommitLimit', 'CommitPeak', 'PhysicalTotal',
            'PhysicalAvailable', 'SystemCache', 'KernelTotal', 'KernelPaged',
            'KernelNonpaged', 'PageSize')],
        ('HandleCount', ctypes.c_uint32),
        ('ProcessCount', ctypes.c_uint32),
        ('ThreadCount', ctypes.c_uint32),
    ]


@lru_cache(maxsize=1)
def _windows_binding():
    # LOAD_LIBRARY_SEARCH_SYSTEM32: neither CWD nor PATH supplies this DLL.
    # WinDLL releases the GIL during the native call; PyDLL must not be used.
    dll = ctypes.WinDLL('psapi.dll', use_last_error=True, winmode=0x800)
    query = dll.GetPerformanceInfo
    query.argtypes = [ctypes.POINTER(_PerformanceInformation), ctypes.c_uint32]
    query.restype = ctypes.c_int32  # BOOL, including on 64-bit Windows.
    return dll, query


def available_physical_bytes():
    """Read current available physical bytes or fail closed; no RAM cache."""
    if os.name != 'nt':
        return psutil.virtual_memory().available
    try:
        pointer_size = ctypes.sizeof(ctypes.c_size_t)
        expected_size = {4: 56, 8: 104}.get(pointer_size)
        if expected_size is None or ctypes.sizeof(_PerformanceInformation) != expected_size:
            raise ValueError('Unsupported PERFORMANCE_INFORMATION ABI')
        info = _PerformanceInformation()
        info.cb = ctypes.sizeof(info)
        _dll, query = _windows_binding()
        ctypes.set_last_error(0)
        if not query(ctypes.byref(info), info.cb):
            error = ctypes.get_last_error()
            raise OSError(error, 'GetPerformanceInfo failed')
        page = int(info.PageSize)
        total = int(info.PhysicalTotal)
        available = int(info.PhysicalAvailable)
        if (info.cb != expected_size or page == 0 or page & (page - 1)
                or total == 0 or available > total
                or total * page > (1 << 64) - 1):
            raise ValueError('Invalid physical RAM observation')
        return available * page
    except (OSError, ValueError, AttributeError) as error:
        raise PhysicalMemoryUnavailable('Live physical RAM query failed') from error
