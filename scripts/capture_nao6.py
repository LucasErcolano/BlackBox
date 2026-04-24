# SPDX-License-Identifier: MIT
"""NAO6 capture helper — records CameraTop + CameraBottom + ALMemory to disk.

Usage::

    python scripts/capture_nao6.py --ip 192.168.1.42 --case c1_faceplant

Produces, under ``data/bags/nao6/<case_key>/``:

    top_video.mp4      — CameraTop at 10 fps 320x240 (QVGA)
    bottom_video.mp4   — CameraBottom at 10 fps 320x240 (QVGA)
    telemetry.csv      — ALMemory dump at 100 Hz, columns: t_ns,key,value
    controller.py      — (you paste the controller snippet that caused the failure)

Controls:
    Ctrl-C     stops cleanly and writes all artifacts.

Requirements on the capture host:
    pip install qi  # NAOqi Python SDK — https://doc.aldebaran.com/2-5/dev/python/install_guide.html
    pip install opencv-python numpy

The NAO6 robot itself does not need anything installed; we talk to NAOqi
over the network. Default NAOqi port is 9559.

If the ``qi`` SDK is not available (e.g. Apple Silicon — Aldebaran hasn't
published an ARM wheel) run this on a Linux/Intel box that is on the same
network as the robot, OR run it inside the Choregraphe-bundled Python.
"""

from __future__ import annotations

import argparse
import csv
import signal
import sys
import threading
import time
from pathlib import Path

# NAOqi SDK — imported lazily so the script can be unit-tested / help-printed
# on a host where the SDK isn't installed.
try:
    import qi  # type: ignore[import-not-found]
except ImportError:
    qi = None  # Sentinel — checked in main().

try:
    import cv2  # type: ignore[import-not-found]
    import numpy as np  # type: ignore[import-not-found]
except ImportError:
    cv2 = None
    np = None


# ----- what we log from ALMemory --------------------------------------------
# Keep this list small: fewer keys = smaller CSV = faster parse. These are the
# ones that actually discriminate between the 7 bug classes.
ALMEMORY_KEYS: tuple[str, ...] = (
    "InertialSensor/AngleX/Sensor/Value",
    "InertialSensor/AngleY/Sensor/Value",
    "InertialSensor/GyrX/Sensor/Value",
    "InertialSensor/GyrY/Sensor/Value",
    "InertialSensor/AccX/Sensor/Value",
    "InertialSensor/AccY/Sensor/Value",
    "InertialSensor/AccZ/Sensor/Value",
    "Motion/Walking",
    "Motion/MoveMode",
    "HeadYaw/Position/Sensor/Value",
    "HeadPitch/Position/Sensor/Value",
    "LHipPitch/Position/Sensor/Value",
    "RHipPitch/Position/Sensor/Value",
    "LKneePitch/Position/Sensor/Value",
    "RKneePitch/Position/Sensor/Value",
    "LAnklePitch/Position/Sensor/Value",
    "RAnklePitch/Position/Sensor/Value",
)

# Camera constants — ALVideoDevice resolution / colorspace enums
_RES_QVGA = 1           # 320x240
_COLORSPACE_BGR = 13    # OpenCV-friendly
_FPS = 10
_W, _H = 320, 240


# ----- writers --------------------------------------------------------------

class CameraWriter:
    """Owns one ALVideoDevice subscription + MP4 writer."""

    def __init__(self, session, camera_idx: int, out_path: Path, client_name: str) -> None:
        self._video = session.service("ALVideoDevice")
        self._client = self._video.subscribeCamera(
            client_name, camera_idx, _RES_QVGA, _COLORSPACE_BGR, _FPS
        )
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        self._writer = cv2.VideoWriter(str(out_path), fourcc, _FPS, (_W, _H))

    def tick(self) -> None:
        img = self._video.getImageRemote(self._client)
        if img is None:
            return
        w, h, data = img[0], img[1], img[6]
        arr = np.frombuffer(data, dtype=np.uint8).reshape(h, w, 3)
        self._writer.write(arr)

    def close(self) -> None:
        try:
            self._video.unsubscribe(self._client)
        finally:
            self._writer.release()


class TelemetryWriter:
    """Polls ALMemory at a fixed rate and streams rows to a CSV."""

    def __init__(self, session, out_path: Path, hz: int = 100) -> None:
        self._memory = session.service("ALMemory")
        self._f = out_path.open("w", newline="")
        self._csv = csv.writer(self._f)
        self._csv.writerow(["t_ns", "key", "value"])
        self._period_s = 1.0 / hz
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            t_ns = time.time_ns()
            for key in ALMEMORY_KEYS:
                try:
                    val = self._memory.getData(key)
                except Exception:
                    continue  # key missing — skip this tick
                self._csv.writerow([t_ns, key, val])
            time.sleep(self._period_s)

    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=2.0)
        self._f.close()


# ----- orchestration --------------------------------------------------------

def capture(ip: str, port: int, case_key: str, out_root: Path) -> Path:
    case_dir = out_root / case_key
    case_dir.mkdir(parents=True, exist_ok=True)

    assert qi is not None, "NAOqi SDK (qi) not installed"
    assert cv2 is not None and np is not None, "opencv-python / numpy not installed"

    session = qi.Session()
    session.connect(f"tcp://{ip}:{port}")

    top = CameraWriter(session, camera_idx=0, out_path=case_dir / "top_video.mp4",
                       client_name=f"blackbox_top_{case_key}")
    bottom = CameraWriter(session, camera_idx=1, out_path=case_dir / "bottom_video.mp4",
                          client_name=f"blackbox_bottom_{case_key}")
    tele = TelemetryWriter(session, out_path=case_dir / "telemetry.csv", hz=100)

    stop = threading.Event()

    def _sigint(_sig, _frm):
        stop.set()
    signal.signal(signal.SIGINT, _sigint)

    print(f"[capture] recording -> {case_dir}")
    print("[capture] press Ctrl-C to stop")

    tele.start()
    frame_period_s = 1.0 / _FPS
    try:
        while not stop.is_set():
            tick_start = time.monotonic()
            top.tick()
            bottom.tick()
            elapsed = time.monotonic() - tick_start
            if elapsed < frame_period_s:
                time.sleep(frame_period_s - elapsed)
    finally:
        print("[capture] stopping...")
        tele.close()
        top.close()
        bottom.close()

    controller_path = case_dir / "controller.py"
    if not controller_path.exists():
        controller_path.write_text(
            '"""Paste the controller snippet responsible for this failure."""\n',
            encoding="utf-8",
        )

    print(f"[capture] done: {case_dir}")
    return case_dir


def main() -> int:
    ap = argparse.ArgumentParser(description="Capture a NAO6 failure for Black Box analysis.")
    ap.add_argument("--ip", required=True, help="NAO6 IP address on your LAN")
    ap.add_argument("--port", type=int, default=9559)
    ap.add_argument("--case", required=True,
                    help="short case key, e.g. c1_faceplant, c2_stale_imu")
    ap.add_argument("--out", type=Path, default=Path("data/bags/nao6"))
    args = ap.parse_args()

    if qi is None:
        sys.stderr.write(
            "ERROR: NAOqi Python SDK (qi) not found.\n"
            "Install per https://doc.aldebaran.com/2-5/dev/python/install_guide.html\n"
            "Note: no ARM wheel — run on a Linux/Intel host on the same LAN as the NAO.\n"
        )
        return 2
    if cv2 is None or np is None:
        sys.stderr.write("ERROR: opencv-python + numpy required (pip install opencv-python numpy)\n")
        return 2

    capture(args.ip, args.port, args.case, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
