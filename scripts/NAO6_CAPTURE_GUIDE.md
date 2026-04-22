# NAO6 capture guide (tomorrow's checklist)

Goal: 3-5 short failure recordings, one per `bug_class`, each landing in
`data/bags/nao6/<case_key>/` with the files the NAO6 adapter expects.

## One-time setup (do once before first recording)

1. Get NAO6 on the same LAN as your laptop. Press the chest button; it says its IP aloud. Write that down.
2. On a **Linux or Intel Mac** (Apple Silicon doesn't have a NAOqi SDK wheel), install:

   ```bash
   pip install qi opencv-python numpy
   ```

   If you're on an M-series Mac, run the capture script from **Choregraphe's
   bundled Python** (it ships with a compatible `qi`) or from a Linux VM/box.

3. Test the connection once — from the machine with the SDK:

   ```bash
   python -c "import qi; s = qi.Session(); s.connect('tcp://<IP>:9559'); print('ok')"
   ```

## Per-recording loop (5x)

Pick a `case_key` per scenario. Then for each:

```bash
python scripts/capture_nao6.py --ip <IP> --case <case_key>
```

The script starts recording both cameras + telemetry and prints
"press Ctrl-C to stop".

1. **Before you induce the failure**, let 2-3 seconds of nominal behavior record first. The grounding gate needs a "normal" baseline to compare against.
2. Induce the failure on the robot.
3. Let the failure play out ~2-3 more seconds.
4. Ctrl-C to stop.
5. Open `data/bags/nao6/<case_key>/controller.py` and paste the tiny controller snippet that caused the failure (or a representative one). Just the PID / state-machine / null-check block — not the whole codebase.

## The 5 scenarios

Pick any 3 for the minimum bar; all 5 makes the demo look great.

| case_key            | bug_class              | how to induce it |
|---------------------|------------------------|------------------|
| `c1_faceplant`      | `pid_saturation`       | Nudge the NAO forward at the hips while it's balancing; a wound-up integral won't recover. Or crank `ki` too high and let it diverge. |
| `c2_stale_imu`      | `sensor_timeout`       | Kill the ALMemory subscription to `InertialSensor` mid-walk (or block the wifi so updates stall) — balance controller still reads the last stale value. |
| `c3_deadlock`       | `state_machine_deadlock` | Send a `walk` command immediately after a fall event, before `isFallen` resets. Controller waits forever in a state no one transitions out of. |
| `c4_bad_gain`       | `bad_gain_tuning`      | Set `kp` on the knee to a large value. Knees oscillate visibly — video shows the shake, telemetry shows the oscillation. |
| `c5_cam_drift`      | `calibration_drift`    | Cover half of CameraTop with a hand or post-it during a walk; the top/bottom stereo correspondence breaks and navigation misroutes. |

Keep each clip **short (5-10 seconds)**. Longer clips = more tokens = more API cost.

## What the capture script produces

```
data/bags/nao6/<case_key>/
  top_video.mp4      # CameraTop, 10 fps, 320x240
  bottom_video.mp4   # CameraBottom, 10 fps, 320x240
  telemetry.csv      # ALMemory dump at 100 Hz, columns: t_ns,key,value
  controller.py      # ← paste the failing snippet here
```

This is exactly the shape `NAO6Adapter.ingest(...)` expects — no
conversion step, you just feed the directory into the pipeline.

## If something breaks

- **Cameras record but telemetry is empty** → one of the `ALMEMORY_KEYS` doesn't exist on your robot's firmware. The script skips missing keys silently; check the CSV for which keys you _did_ get and remove the missing ones from `ALMEMORY_KEYS` in the script.
- **MP4 is 0 bytes** → OpenCV's `mp4v` writer failed. Install `ffmpeg` system-wide or switch to `MJPG` + `.avi` in `CameraWriter`.
- **`qi.connect()` hangs** → wrong IP or robot not on the same LAN. Try `ping <IP>` first.
- **Robot voice starts saying weird things** → you accidentally triggered TTS. Ignore, keep recording.
