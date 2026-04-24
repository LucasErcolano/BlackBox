# SPDX-License-Identifier: MIT
"""Telemetry-drop forensic prompt.

Use case: a sensor subsystem died mid-bag. Some topics keep publishing, some
stop. This prompt takes a per-topic activity timeline (bucketed publish
counts) and asks Claude to identify:

  - which topics dropped, when, and for how long
  - which topics survived (rules out whole-stack crash)
  - the most likely subsystem-level cause within the closed bug taxonomy
  - a scoped patch hint (watchdog, fallback, restart supervisor, ...)

Vision is optional: last-good frame + first-post-drop frame can be passed
when the cameras themselves are the dropped topics. No telemetry needed
from outside the activity matrix — that's the whole point.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# -------- schemas ------------------------------------------------------------


class DroppedSensor(BaseModel):
    topic: str
    last_t_ns_published: int | None = None
    duration_silent_s: float
    msgtype: str | None = None


class SurvivingSensor(BaseModel):
    topic: str
    publishing_through_gap: bool
    approx_hz: float | None = None


class DropEvent(BaseModel):
    t_ns_onset: int
    dropped: list[DroppedSensor]
    surviving: list[SurvivingSensor]
    likely_cause: str
    cause_confidence: float = Field(ge=0.0, le=1.0)
    bug_class: Literal[
        "sensor_timeout",
        "state_machine_deadlock",
        "latency_spike",
        "calibration_drift",
        "pid_saturation",
        "bad_gain_tuning",
        "missing_null_check",
        "unknown",
    ] = "sensor_timeout"
    patch_hint: str = ""


class TelemetryDropReport(BaseModel):
    events: list[DropEvent]
    rationale: str
    overall_severity: Literal["low", "medium", "high", "critical"] = "high"


# -------- prompt -------------------------------------------------------------


SYSTEM_DROP = """You are a forensic analyst reviewing a ROS bag for sensor-subsystem failures. You are given a per-topic activity timeline: for each topic, how many messages it published in each time bucket, plus its msgtype. Optionally, you also receive the last-good frame and the first frame after silence onset when the dropped topic is a camera.

Your job is NOT to explain the whole bag. Your job is narrow:

1. Identify which topics went silent and when.
2. Verify which topics kept publishing through the silence window — this rules out a whole-stack crash and usually points at a single subsystem.
3. Classify the failure mode using the closed taxonomy below.
4. Emit a scoped patch hint if a reasonable one exists. If not, say so.

Be conservative. A brief gap (< 500 ms) in a noisy topic is usually not an event. A topic that goes silent for >2 s while its sibling sensors keep publishing IS an event.

Always respond with JSON only. No preamble, no markdown.
"""


DOMAIN_CONTEXT_DROP = """## Sensor-subsystem taxonomy

Sensor drops usually come from one of the following subsystem-level failures:

1. **Bus or driver fault** — one camera or LIDAR driver crashes; all topics from that driver stop, other sensors continue. Signature: contiguous group of topics on the same driver goes silent simultaneously.
2. **Power rail or hardware-interface fault** — multiple heterogeneous sensors on the same physical rail stop together; topics from independently powered sensors continue. Signature: topics across different driver processes stop at the same t_ns.
3. **ROS node crash** — publishing node died; all its advertised topics stop. Often recoverable via respawn. Signature: topics with the same node prefix all drop.
4. **Timing/buffer overrun** — topics do not die cleanly; publish rate drops gradually over several seconds before going fully silent. Signature: progressive rate decay rather than a cliff.
5. **Upstream dependency** — node is alive but has stopped receiving the input it republishes. Distinguish from (1) by checking whether the upstream input is still arriving from a different publisher.

## What does NOT count as a drop

- Topics that publish on-demand (e.g., /cmd_vel when stationary) naturally have gaps. Do not flag unless the bag context implies the topic should be active.
- Topics with bursty publish patterns (e.g., diagnostic arrays every 10 s) that look silent at sub-second resolution.
- Single missed messages on a high-rate topic — that is jitter, not a drop.

## Patch-hint discipline

Scoped patches only. Examples of valid patch hints:

- "Add watchdog: if /camera_front has no message in WATCHDOG_S, log error and publish /safety/estop."
- "Add fallback: when /lidar/points is silent > 2 s, consumer should treat obstacle map as unknown and reduce speed to CRAWL_V."
- "Add restart supervisor: respawn `camera_driver_node` up to 3 times with exponential backoff on exit."

Never propose architectural rewrites (moving from one stack to another, changing message formats, adding new sensors).

## Evidence strictness

Refer to topics and time buckets exactly as they appear in the activity matrix. Do not invent topic names. If uncertain about an onset t_ns, pick the last bucket where the topic had non-zero count and report it as the onset of silence.

## Worked examples of the reasoning we expect

### Example A — single camera driver crash

Matrix (5 buckets of 1 s):
- /camera_front (sensor_msgs/Image): 10 10 10 0 0
- /camera_left  (sensor_msgs/Image):  0  0  0 0 0
- /camera_right (sensor_msgs/Image): 10 10 10 10 10
- /imu/data     (sensor_msgs/Imu):  100 100 100 100 100

/camera_front stopped at bucket 3. /camera_right continued. /imu alive. /camera_left never published — pre-existing absence, not an event. Verdict: single camera driver fault for the front camera. Patch: watchdog on /camera_front + node respawn.

### Example B — whole-subsystem power drop

Matrix:
- /camera_front: 10 10 0 0 0
- /camera_left:  10 10 0 0 0
- /camera_right: 10 10 0 0 0
- /lidar/points:  5  5 0 0 0
- /imu/data:    100 100 100 100 100

All perception sensors dropped simultaneously at bucket 2. /imu/data on a different rail stayed alive. Verdict: power or bus fault on perception rail. Patch: supervisor that re-initializes the perception rail on multi-sensor silence, and a safety estop triggered by the consumer.

### Example C — gradual degradation, NOT a clean drop

Matrix:
- /lidar/points: 10 10 8 6 3 1 0 0 0

Rate decayed over seconds rather than a cliff. Verdict: timing/buffer overrun or thermal throttling, not a clean driver crash. Confidence ≤ 0.6 because the matrix alone can't tell us which. Patch: instrument driver with rate-health topic and add consumer-side fallback on decay threshold.

### Example D — nothing to report

Matrix:
- /cmd_vel: 0 0 5 20 0 0 10 0 0 0
- /imu/data: 100 100 100 100 100 100 100 100 100 100

/cmd_vel is naturally bursty (only publishes when motion is commanded). /imu/data is steady. No event. Empty events array with rationale explaining why.

## Time-bucket convention

- Bucket indices start at 0 = bag start.
- Onset t_ns for an event = the start of the first all-zero bucket after a publishing run.
- Duration silent = (end of last observed bucket - onset) in seconds; if the topic never recovers within the bag, report duration as the remainder of the bag length.
- If multiple topics drop at the same bucket boundary, report them as a single event with a list of dropped topics, not as separate events.
- If a topic has alternating 0/N patterns with period < 3 buckets, that is jitter, not a drop.
"""


DOMAIN_CONTEXT_DROP_BLOCK = {
    "type": "text",
    "text": DOMAIN_CONTEXT_DROP,
    "cache_control": {"type": "ephemeral"},
}


def telemetry_drop_prompt():
    return {
        "name": "telemetry_drop_v1",
        "system": SYSTEM_DROP,
        "cached_blocks": [DOMAIN_CONTEXT_DROP_BLOCK],
        "user_template": (
            "Analyze the following ROS bag for sensor-subsystem drop events.\n\n"
            "## Bag metadata\n{bag_metadata}\n\n"
            "## Topic activity matrix\n"
            "Rows are topics; columns are {n_buckets} time buckets of {bucket_s}s each, "
            "starting at t=0 (bag start). Each cell is the message count in that bucket. "
            "`msgtype` precedes each row.\n\n"
            "{activity_matrix}\n\n"
            "## Optional visual context\n{visual_context}\n\n"
            "Return JSON with EXACTLY this shape:\n"
            "{{\n"
            '  "events": [\n'
            "    {{\n"
            '      "t_ns_onset": <int>,\n'
            '      "dropped": [{{"topic": "<str>", "last_t_ns_published": <int|null>, "duration_silent_s": <float>, "msgtype": "<str|null>"}}],\n'
            '      "surviving": [{{"topic": "<str>", "publishing_through_gap": <bool>, "approx_hz": <float|null>}}],\n'
            '      "likely_cause": "<one sentence>",\n'
            '      "cause_confidence": <float 0..1>,\n'
            '      "bug_class": "sensor_timeout|state_machine_deadlock|latency_spike|calibration_drift|pid_saturation|bad_gain_tuning|missing_null_check|unknown",\n'
            '      "patch_hint": "<scoped patch, empty string if none>"\n'
            "    }}\n"
            "  ],\n"
            '  "rationale": "<overall reasoning>",\n'
            '  "overall_severity": "low|medium|high|critical"\n'
            "}}\n"
            "No preamble, no markdown fencing."
        ),
        "schema": TelemetryDropReport,
    }


# -------- helpers for caller to build the matrix -----------------------------


def format_activity_matrix(
    topic_msgtypes: dict[str, str],
    bucket_counts: dict[str, list[int]],
    bucket_s: float,
) -> tuple[str, int]:
    """Render an activity matrix table as plain text for the prompt.

    Returns (rendered_text, n_buckets).
    """
    topics = sorted(bucket_counts.keys())
    n_buckets = max((len(bucket_counts[t]) for t in topics), default=0)

    # Header: bucket indices
    lines: list[str] = []
    header_label = "topic (msgtype)".ljust(48)
    bucket_header = " ".join(f"{i:>3d}" for i in range(n_buckets))
    lines.append(f"{header_label} | {bucket_header}")
    lines.append("-" * len(lines[0]))

    for t in topics:
        counts = bucket_counts[t]
        counts = counts + [0] * (n_buckets - len(counts))
        row_counts = " ".join(f"{c:>3d}" for c in counts)
        mt = topic_msgtypes.get(t, "?")
        label = f"{t} ({mt})".ljust(48)
        lines.append(f"{label} | {row_counts}")

    return "\n".join(lines), n_buckets


def bucketize(
    bag_metadata: dict,
    per_topic_timestamps: dict[str, list[int]],
    bucket_s: float = 1.0,
) -> dict[str, list[int]]:
    """Group timestamps into fixed-size buckets from bag start to end.

    per_topic_timestamps: {topic: [t_ns, ...]}
    Returns: {topic: [count_bucket_0, count_bucket_1, ...]}
    """
    start = int(bag_metadata["start_ns"])
    end = int(bag_metadata["end_ns"])
    bucket_ns = int(bucket_s * 1_000_000_000)
    n = max(1, (end - start + bucket_ns - 1) // bucket_ns)

    out: dict[str, list[int]] = {}
    for topic, ts in per_topic_timestamps.items():
        counts = [0] * n
        for t in ts:
            idx = max(0, min(n - 1, (int(t) - start) // bucket_ns))
            counts[idx] += 1
        out[topic] = counts
    return out
