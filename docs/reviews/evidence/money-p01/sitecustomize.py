"""External launch-only RAM guard; leaves simulator/measuring code unchanged."""
import ctypes
import json
import os
import subprocess
import threading
import time


class _Memory(ctypes.Structure):
    _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong)] + [
        (name, ctypes.c_ulonglong) for name in (
            'total_phys', 'available_phys', 'total_page', 'available_page',
            'total_virtual', 'available_virtual', 'available_extended',
        )
    ]


_lock = threading.Lock()
_init = subprocess.Popen.__init__


def _guarded_init(self, args, *rest, **kwargs):
    if isinstance(args, (list, tuple)) and any('evidence_panel_worker.py' in str(arg) for arg in args):
        with _lock:
            while True:
                state = _Memory()
                state.length = ctypes.sizeof(state)
                if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(state)):
                    raise RuntimeError('Cannot verify free RAM')
                record = {'time': time.time(), 'free_bytes': state.available_phys, 'command': args,
                          'paused': state.available_phys < 3 * 1024**3}
                with open(os.environ['MONEYP01_LAUNCH_LOG'], 'a', encoding='utf-8') as stream:
                    stream.write(json.dumps(record) + '\n')
                if not record['paused']:
                    return _init(self, args, *rest, **kwargs)
                time.sleep(10)
    return _init(self, args, *rest, **kwargs)


subprocess.Popen.__init__ = _guarded_init
