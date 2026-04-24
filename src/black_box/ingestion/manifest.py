# SPDX-License-Identifier: MIT
"""Platform-agnostic session manifest.

Input: path (file or folder) + optional operator prompt.
Output: Manifest describing which sensors are actually present in the bag
set, without assuming any particular robot class (car/boat/drone/arm/...).

The manifest is the single source of truth for prompt construction: the
generic prompt builder reads it instead of hardcoding "5 cameras, AV rig".

Design rules:
- Do NOT assume autonomy. A session may be human-driven with external
  robotics payload. Autonomy is only asserted if the user prompt says so
  or if controller/cmd topics are present AND populated.
- Do NOT blacklist environmental hypotheses (tunnel, shadow, rain).
  Those are candidates to confirm, not findings to reject.
- Do NOT invent sensors. If no IMU topic exists, the manifest says so.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from rosbags.highlevel import AnyReader

from .session import SessionAssets, discover_session_assets


# Message-type buckets. Kept explicit — no regex-on-topic-name guesswork.
_CAM_MSGTYPES = {
    "sensor_msgs/msg/Image", "sensor_msgs/Image",
    "sensor_msgs/msg/CompressedImage", "sensor_msgs/CompressedImage",
}
_LIDAR_MSGTYPES = {
    "sensor_msgs/msg/PointCloud2", "sensor_msgs/PointCloud2",
    "sensor_msgs/msg/LaserScan", "sensor_msgs/LaserScan",
}
_IMU_MSGTYPES = {"sensor_msgs/msg/Imu", "sensor_msgs/Imu"}
_GNSS_MSGTYPES = {
    "sensor_msgs/msg/NavSatFix", "sensor_msgs/NavSatFix",
    # ublox / RTK variants observed in the wild
    "ublox_msgs/msg/NavPVT", "ublox_msgs/NavPVT",
    "ublox_msgs/msg/NavRELPOSNED", "ublox_msgs/NavRELPOSNED",
    "ublox_msgs/msg/NavRELPOSNED9", "ublox_msgs/NavRELPOSNED9",
    "ublox_msgs/msg/RxmRTCM", "ublox_msgs/RxmRTCM",
    "gps_msgs/msg/GPSFix", "gps_msgs/GPSFix",
}
_ODOM_MSGTYPES = {
    "nav_msgs/msg/Odometry", "nav_msgs/Odometry",
    "geometry_msgs/msg/PoseWithCovarianceStamped",
    "geometry_msgs/PoseWithCovarianceStamped",
}
_CMD_MSGTYPES = {
    "geometry_msgs/msg/Twist", "geometry_msgs/Twist",
    "geometry_msgs/msg/TwistStamped", "geometry_msgs/TwistStamped",
    "ackermann_msgs/msg/AckermannDriveStamped",
    "ackermann_msgs/AckermannDriveStamped",
    "dataspeed_ulc_msgs/msg/UlcCmd", "dataspeed_ulc_msgs/UlcCmd",
}
_AUDIO_MSGTYPES = {"audio_common_msgs/msg/AudioData", "audio_common_msgs/AudioData"}


@dataclass
class TopicInfo:
    topic: str
    msgtype: str
    count: int = 0
    kind: str = ""  # camera|lidar|imu|gnss|odom|cmd|audio|other


@dataclass
class Manifest:
    root: Path
    session_key: str | None
    bags: list[Path]
    duration_s: float | None
    t_start_ns: int | None
    t_end_ns: int | None
    cameras: list[TopicInfo] = field(default_factory=list)
    lidars: list[TopicInfo] = field(default_factory=list)
    imus: list[TopicInfo] = field(default_factory=list)
    gnss: list[TopicInfo] = field(default_factory=list)
    odom: list[TopicInfo] = field(default_factory=list)
    cmd: list[TopicInfo] = field(default_factory=list)
    audio: list[TopicInfo] = field(default_factory=list)
    other: list[TopicInfo] = field(default_factory=list)
    peripheral_audio: list[Path] = field(default_factory=list)
    peripheral_video: list[Path] = field(default_factory=list)
    peripheral_logs: list[Path] = field(default_factory=list)
    user_prompt: str | None = None

    def has_cameras(self) -> bool:
        return bool(self.cameras)

    def has_telemetry(self) -> bool:
        return bool(self.imus or self.gnss or self.odom or self.cmd)

    def has_cmd(self) -> bool:
        return any(t.count > 0 for t in self.cmd)

    def autonomy_signal(self) -> str:
        """Conservative autonomy read. Does NOT assume."""
        if self.user_prompt:
            lp = self.user_prompt.lower()
            if "manual" in lp or "human-driven" in lp or "operator driving" in lp:
                return "manual (stated by operator)"
            if "autonomous" in lp or "self-driv" in lp or "auto mode" in lp:
                return "autonomous (stated by operator)"
        if self.has_cmd():
            return "unknown (control topics present but could be teleop)"
        return "unknown (no control topics recorded)"

    def summary_lines(self) -> list[str]:
        def _fmt(items: list[TopicInfo]) -> str:
            if not items:
                return "(none)"
            return ", ".join(f"{t.topic} [{t.msgtype}, n={t.count}]" for t in items)
        lines = [
            f"session_key={self.session_key!r} bags={len(self.bags)}",
            f"duration_s={self.duration_s}",
            f"autonomy={self.autonomy_signal()}",
            f"cameras: {_fmt(self.cameras)}",
            f"lidars:  {_fmt(self.lidars)}",
            f"imus:    {_fmt(self.imus)}",
            f"gnss:    {_fmt(self.gnss)}",
            f"odom:    {_fmt(self.odom)}",
            f"cmd:     {_fmt(self.cmd)}",
            f"audio:   {_fmt(self.audio)}",
        ]
        if self.user_prompt:
            lines.append(f"user_prompt={self.user_prompt!r}")
        return lines


def _classify(msgtype: str) -> str:
    if msgtype in _CAM_MSGTYPES: return "camera"
    if msgtype in _LIDAR_MSGTYPES: return "lidar"
    if msgtype in _IMU_MSGTYPES: return "imu"
    if msgtype in _GNSS_MSGTYPES: return "gnss"
    if msgtype in _ODOM_MSGTYPES: return "odom"
    if msgtype in _CMD_MSGTYPES: return "cmd"
    if msgtype in _AUDIO_MSGTYPES: return "audio"
    return "other"


def build_manifest(
    path: str | Path | SessionAssets,
    user_prompt: str | None = None,
    count_messages: bool = True,
) -> Manifest:
    """Scan a session path and return a typed Manifest.

    `path` can be a file, folder, or a prebuilt SessionAssets.
    `user_prompt` is the operator's optional free-text hint — preserved
    verbatim so the prompt builder can pass it to the model unchanged.
    `count_messages=False` skips per-topic message counts for speed on
    very large (100GB+) bag sets where only topic presence is needed.
    """
    if isinstance(path, SessionAssets):
        assets = path
    else:
        assets = discover_session_assets(path)

    bags = [Path(b) for b in assets.bags]
    m = Manifest(
        root=assets.root,
        session_key=assets.session_key,
        bags=bags,
        duration_s=None,
        t_start_ns=None,
        t_end_ns=None,
        peripheral_audio=list(assets.audio),
        peripheral_video=list(assets.video),
        peripheral_logs=list(assets.logs),
        user_prompt=user_prompt,
    )
    if not bags:
        return m

    with AnyReader(bags) as reader:
        m.t_start_ns = int(reader.start_time) if reader.start_time else None
        m.t_end_ns = int(reader.end_time) if reader.end_time else None
        if m.t_start_ns is not None and m.t_end_ns is not None:
            m.duration_s = (m.t_end_ns - m.t_start_ns) / 1e9

        # Aggregate counts across connections that share a topic.
        by_topic: dict[str, TopicInfo] = {}
        for conn in reader.connections:
            ti = by_topic.get(conn.topic)
            if ti is None:
                ti = TopicInfo(
                    topic=conn.topic, msgtype=conn.msgtype, count=0,
                    kind=_classify(conn.msgtype),
                )
                by_topic[conn.topic] = ti
            if count_messages:
                ti.count += int(getattr(conn, "msgcount", 0) or 0)

        for ti in by_topic.values():
            bucket = {
                "camera": m.cameras, "lidar": m.lidars, "imu": m.imus,
                "gnss": m.gnss, "odom": m.odom, "cmd": m.cmd,
                "audio": m.audio, "other": m.other,
            }[ti.kind]
            bucket.append(ti)

        for bucket in (m.cameras, m.lidars, m.imus, m.gnss, m.odom,
                       m.cmd, m.audio, m.other):
            bucket.sort(key=lambda t: t.topic)

    return m


def manifest_to_prompt_block(m: Manifest) -> str:
    """Render the manifest as plain text for inclusion in a system/context block."""
    def _sensor(label: str, items: list[TopicInfo]) -> str:
        if not items:
            return f"- {label}: none recorded"
        rows = [f"  - {t.topic}  ({t.msgtype}, n={t.count})" for t in items]
        return f"- {label}:\n" + "\n".join(rows)

    dur = f"{m.duration_s:.1f}s" if m.duration_s else "unknown"
    parts = [
        "## Session capability manifest",
        f"- root: {m.root}",
        f"- bags: {len(m.bags)} file(s), duration {dur}",
        f"- autonomy: {m.autonomy_signal()}",
        _sensor("cameras", m.cameras),
        _sensor("lidars", m.lidars),
        _sensor("imus", m.imus),
        _sensor("gnss / rtk", m.gnss),
        _sensor("odometry / pose", m.odom),
        _sensor("control commands", m.cmd),
        _sensor("audio streams", m.audio),
    ]
    if m.peripheral_audio or m.peripheral_video or m.peripheral_logs:
        parts.append(
            f"- peripheral files: audio={len(m.peripheral_audio)} "
            f"video={len(m.peripheral_video)} logs={len(m.peripheral_logs)}"
        )
    return "\n".join(parts)
