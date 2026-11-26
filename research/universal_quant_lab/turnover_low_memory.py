"""Operational low-memory profile for the frozen provisional turnover campaign."""
import json
from pathlib import Path
import sys
import ctypes
import time
import threading
import duckdb
import numba
from profit_campaign import run
from profit_ledger import Ledger
from eodhd import atomic_json

root=Path(sys.argv[1])
out=root/"results/development-turnover-3m"
config=json.loads((root/"config/development-turnover-3m.json").read_bytes())
connect=duckdb.connect
reserve=Ledger.reserve
set_threads=numba.set_num_threads

def low_memory_connection(*args, **kwargs):
    connection=connect(*args, **kwargs)
    connection.execute("SET threads=1")
    connection.execute("SET memory_limit='192MB'")
    connection.execute("SET preserve_insertion_order=false")
    return connection

duckdb.connect=low_memory_connection
Ledger.reserve=lambda self,job,n: reserve(self,job,min(n,2000))
numba.set_num_threads=lambda n: set_threads(min(2,n))
numba.config.CACHE_DIR=str(root/"feature_cache/numba")
# Windows PROCESS_MEMORY_COUNTERS includes the lifetime peak working set.
class Counters(ctypes.Structure):
    _fields_=[("cb",ctypes.c_uint32),("faults",ctypes.c_uint32)]+[(n,ctypes.c_size_t) for n in
        ("peak","current","pp","p","np","n","pf","ppf")]
start=time.monotonic()
before=json.loads((out/"progress.json").read_bytes())["engineering_completed"]
run(root,config,out)
c=Counters()
if not ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(-1),ctypes.byref(c),ctypes.sizeof(c)):
    raise OSError("Working set sampling failed")
progress=json.loads((out/"progress.json").read_bytes())
elapsed=time.monotonic()-start
atomic_json(out/"memory-benchmark.json",dict(peak_working_set_mib=c.peak/2**20,elapsed_seconds=elapsed,
    new_rows=progress["engineering_completed"]-before,rows_per_second=(progress["engineering_completed"]-before)/elapsed,
    threads=2,duckdb_threads=1,duckdb_limit_mb=192,max_new_lease=2000))
