# SPDX-License-Identifier: MIT
"""Quick bag duration probe via connection index (no message scan)."""
import sys
from pathlib import Path
from rosbags.rosbag1 import Reader

for p in sys.argv[1:]:
    with Reader(Path(p)) as r:
        dur = (r.end_time - r.start_time) / 1e9
        print(f"{p}: duration={dur:.1f}s  start_ns={r.start_time}  end_ns={r.end_time}")
