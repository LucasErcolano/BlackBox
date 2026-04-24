"""Tier-3 synthetic QA for the no-camera (telemetry-only) branch.

Injects a known failure mode — `/lidar_imu` silent while `/lidar_points`
healthy — and asserts the pipeline classifies it as `sensor_timeout` with
an actionable Ouster/Velodyne patch hint (not a generic "review manually").

No real bag is built here; we exercise the detection + classification
logic directly. The scan step (_scan_lidar_imu) is covered by running it
against an on-disk rosbag2 in the integration path; this test owns the
synthesis -> classification -> report contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import run_session as rs  # type: ignore  # noqa: E402


def test_silent_imu_classifies_as_sensor_timeout():
    evidence = [
        {"source": "telemetry", "channel": "/lidar_imu",
         "snippet": "SILENT (0 messages recorded despite topic being declared)"},
        {"source": "lidar", "channel": "/lidar_points",
         "snippet": "n=4168 span=416.8s avg_rate=10.00Hz (nominal)"},
    ]
    bug_class, patch_hint = rs._classify_moment(
        "/lidar_imu topic silent for entire session", evidence
    )
    assert bug_class == "sensor_timeout"
    # Actionable — driver-specific, NOT "review manually".
    assert "driver" in patch_hint.lower()
    assert "imu" in patch_hint.lower()
    # Must NOT misdiagnose as QoS when metadata shows identical QoS profiles.
    assert "qos" not in patch_hint.lower() or "not a qos mismatch" in patch_hint.lower()


def test_stale_imu_classifies_as_sensor_timeout_with_freshness_hint():
    ev = [{"source": "telemetry", "channel": "/imu/data",
           "snippet": "values frozen for 12.4s"}]
    bug_class, patch_hint = rs._classify_moment("imu stuck / frozen values", ev)
    assert bug_class == "sensor_timeout"
    assert "freshness" in patch_hint.lower() or "reject" in patch_hint.lower()


def test_rate_drop_classifies_as_latency_spike():
    ev = [{"source": "telemetry", "channel": "/odom",
           "snippet": "rate dropped below 50% median for 3.1s"}]
    bug_class, patch_hint = rs._classify_moment(
        "/odom rate drop below threshold", ev
    )
    assert bug_class == "latency_spike"
    assert "cpu" in patch_hint.lower() or "backpressure" in patch_hint.lower()


def test_gap_classifies_with_watchdog_hint():
    ev = [{"source": "telemetry", "channel": "/gnss/fix",
           "snippet": "no messages for 4.2s (gap)"}]
    bug_class, patch_hint = rs._classify_moment("/gnss/fix 4.2s gap", ev)
    assert bug_class == "sensor_timeout"
    assert "watchdog" in patch_hint.lower()


def test_gnss_silent_gets_rtk_specific_hint():
    ev = [{"source": "telemetry", "channel": "/ublox/navpvt",
           "snippet": "SILENT (0 messages)"}]
    _, patch_hint = rs._classify_moment("/ublox/navpvt silent", ev)
    assert "ublox" in patch_hint.lower() or "rtcm" in patch_hint.lower()


def test_stage_report_from_silent_imu_moment(tmp_path):
    """End-to-end contract: a moment describing silent IMU must render a
    report whose top hypothesis is sensor_timeout with the driver-level
    recommendation surfaced verbatim in patch_hint.
    """
    from black_box.ingestion.manifest import Manifest, TopicInfo

    manifest = Manifest(
        root=tmp_path, session_key="synth", bags=[tmp_path / "fake.db3"],
        duration_s=416.8, t_start_ns=0, t_end_ns=416_800_000_000,
    )
    manifest.lidars.append(TopicInfo(
        topic="/lidar_points", msgtype="sensor_msgs/msg/PointCloud2",
        count=4168, kind="lidar",
    ))
    manifest.imus.append(TopicInfo(
        topic="/lidar_imu", msgtype="sensor_msgs/msg/Imu",
        count=0, kind="imu",
    ))

    vision = {
        "mode": "telemetry_only",
        "all_moments": [{
            "t_ns": 0,
            "window": "telemetry_only",
            "label": "/lidar_imu topic silent for entire session",
            "confidence": 0.95,
            "cameras": {"shows": [], "misses": []},
            "evidence": [
                {"source": "telemetry", "channel": "/lidar_imu",
                 "snippet": "SILENT (0 messages recorded)"},
                {"source": "lidar", "channel": "/lidar_points",
                 "snippet": "n=4168 avg_rate=10.00Hz (nominal)"},
            ],
        }],
        "per_window": {},
    }
    report_path = rs.stage_report(
        manifest, vision, {"windows": {}, "cam_topics": []},
        tmp_path, case_key="synth_no_cam_01",
    )
    text = Path(report_path).read_text()
    assert "`sensor_timeout`" in text
    assert "`other`" not in text  # Legacy generic class must be gone.
    assert "driver" in text.lower()
    # No "review manually" dead-end patch hint.
    assert "review flagged moments manually" not in text.lower()


def test_stage_report_no_moments_is_nominal(tmp_path):
    from black_box.ingestion.manifest import Manifest

    manifest = Manifest(
        root=tmp_path, session_key=None, bags=[],
        duration_s=10.0, t_start_ns=0, t_end_ns=10_000_000_000,
    )
    vision = {"all_moments": [], "per_window": {}}
    out = rs.stage_report(manifest, vision, {"windows": {}, "cam_topics": []},
                          tmp_path, case_key="nominal")
    text = Path(out).read_text()
    assert "No anomalies detected" in text
