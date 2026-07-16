from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
STARTUP_LIMIT_MB = 400
OPERATION_LIMIT_MB = 450


PROFILE_CODE = r"""
import ctypes
import importlib
import json
import os
import sys

sys.path.insert(0, r'__BASE_DIR__')
os.environ.setdefault('MAPBOX_ACCESS_TOKEN', 'memory-profile-token')

def rss_mb():
    if sys.platform == 'win32':
        from ctypes import wintypes
        class PMCEX(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t), ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t), ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t), ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t), ('PeakPagefileUsage', ctypes.c_size_t),
                ('PrivateUsage', ctypes.c_size_t),
            ]
        psapi = ctypes.WinDLL('Psapi.dll')
        kernel = ctypes.WinDLL('Kernel32.dll')
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(PMCEX), wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        counters = PMCEX()
        counters.cb = ctypes.sizeof(PMCEX)
        if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise ctypes.WinError()
        return counters.WorkingSetSize / 1024 / 1024, counters.PeakWorkingSetSize / 1024 / 1024
    import resource
    current = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    return current, current

results = []
def record(stage):
    rss, peak = rss_mb()
    results.append({'stage': stage, 'rss_mb': round(rss, 1), 'peak_mb': round(peak, 1)})

record('process_start')
app_module = importlib.import_module('app')
record('app_import')

client = app_module.server.test_client()
response = client.get('/')
if response.status_code != 200:
    raise SystemExit(f'Root page returned HTTP {response.status_code}')
record('root_request')

import data_store
metadata = data_store.get_metadata()
record('metadata_query')

characteristics = data_store.get_all_characteristics()
characteristic = 'pH' if 'pH' in characteristics else characteristics[0]
min_year, max_year = data_store.get_date_bounds()
map_df = data_store.get_map_aggregates(characteristic=characteristic, start_year=min_year, end_year=max_year)
record('map_query')
ts_df = data_store.get_timeseries(characteristic=characteristic, start_year=min_year, end_year=max_year)
record('timeseries_query')
export_df = data_store.get_export_data(characteristic=characteristic, start_year=min_year, end_year=max_year)
record('export_query')

print(json.dumps({'results': results, 'rows': {
    'metadata': len(metadata), 'map': len(map_df), 'timeseries': len(ts_df), 'export': len(export_df)
}}, indent=2))
"""


def main() -> int:
    env = os.environ.copy()
    env.setdefault("MAPBOX_ACCESS_TOKEN", "memory-profile-token")
    env.setdefault("PYTHONIOENCODING", "utf-8")
    code = PROFILE_CODE.replace("__BASE_DIR__", str(BASE_DIR))
    proc = subprocess.run([sys.executable, "-c", code], cwd=BASE_DIR, env=env, text=True, capture_output=True)
    if proc.stdout:
        print(proc.stdout)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr)
    if proc.returncode != 0:
        return proc.returncode
    payload = json.loads(proc.stdout[proc.stdout.index("{"):])
    import_peak = max(item["peak_mb"] for item in payload["results"] if item["stage"] in {"process_start", "app_import"})
    operation_peak = max(item["peak_mb"] for item in payload["results"])
    if import_peak > STARTUP_LIMIT_MB:
        print(f"FAIL: startup peak {import_peak:.1f} MB exceeds {STARTUP_LIMIT_MB} MB", file=sys.stderr)
        return 2
    if operation_peak > OPERATION_LIMIT_MB:
        print(f"FAIL: operation peak {operation_peak:.1f} MB exceeds {OPERATION_LIMIT_MB} MB", file=sys.stderr)
        return 3
    print(f"PASS: startup peak {import_peak:.1f} MB; operation peak {operation_peak:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
