"""Prompt templates with aggressive caching for Black Box analysis."""

from .schemas import (
    PostMortemReport,
    ScenarioMiningReport,
    SyntheticQAReport,
)


SYSTEM_PROMPT = """You are a forensic analyst for robotic systems. Your role is to analyze logs, telemetry, video frames, and code snippets to diagnose root causes of failures.

Always respond with JSON only. No preamble, no markdown fencing.

Bug taxonomy (closed set of exactly 7 — no other labels are permitted):
- pid_saturation: PID controller integral term grows unbounded
- sensor_timeout: Expected sensor reading never arrives
- state_machine_deadlock: FSM enters unrecoverable state
- bad_gain_tuning: Controller gains cause oscillation or instability
- missing_null_check: Null/invalid sensor value crashes or corrupts state
- calibration_drift: Sensor readings drift over time
- latency_spike: Unexpected delay in loop execution

If nothing in the evidence matches one of the 7 labels, emit an empty
hypothesis list. Never invent a label; never coerce to a catch-all. The
Pydantic validator downstream will reject any label outside this set.

Reasoning rules:
1. Cross-reference evidence across camera, telemetry, code, and timeline sources
2. No speculation; only claim evidence you can point to
3. In scenario mining, if nothing anomalous is detected, return empty moments array—do not fabricate
4. Rank hypotheses by confidence (highest first)
5. Provide natural language patch hints scoped to the root cause
"""


BUG_TAXONOMY_DOC = """
## Bug Class Signatures

### pid_saturation
**What to look for in telemetry**: Integral term of PID controller continuously increases over 10+ seconds without reset. Output command saturates at limits (e.g., motor at 100% PWM). System drifts away from setpoint despite corrections.
**In video**: Robot moves slower than expected, oscillates, or fails to track target.
**Code signature**: Integral accumulator not clamped; no anti-windup logic; error term never reset.

### sensor_timeout
**Telemetry**: Missing packets from sensor topic over 100+ ms window; fallback to stale reading or zero.
**Video**: Erratic motion, freezing, or sudden corrections after gap.
**Code signature**: No heartbeat check; timeout logic not implemented; blocking read without timeout.

### state_machine_deadlock
**Telemetry**: FSM state does not transition for 5+ seconds despite valid trigger conditions.
**Video**: Robot stops responding to input.
**Code signature**: Mutual waits; missing state exit condition; race condition in state variable.

### bad_gain_tuning
**Telemetry**: Control output oscillates with increasing amplitude; error oscillates around setpoint.
**Video**: Jerky, oscillatory movement; overshooting and undershoot.
**Code signature**: Gains (Kp, Ki, Kd) manually set too high; no frequency analysis.

### missing_null_check
**Telemetry**: Sensor output is null/NaN/invalid; calculation produces garbage value.
**Video**: Sudden jump or freeze in robot state.
**Code signature**: No validation before use; math on uninitialized memory or null pointer.

### calibration_drift
**Telemetry**: Sensor baseline drifts 2-5% per minute; error grows linearly.
**Video**: Tracking slowly drifts off target; control becomes ineffective.
**Code signature**: No re-calibration; temperature-dependent sensor not compensated.

### latency_spike
**Telemetry**: Loop cycle time jumps from ~10 ms to 100+ ms for single iteration.
**Video**: Brief stall or delayed response.
**Code signature**: Unprotected I/O, memory allocation, or GC pause in real-time loop.

### Closed-set rule
The taxonomy is frozen at exactly these 7 labels:
`pid_saturation`, `sensor_timeout`, `state_machine_deadlock`, `bad_gain_tuning`,
`missing_null_check`, `calibration_drift`, `latency_spike`.
Any other label is a schema violation — the response will be rejected by
the Pydantic validator downstream. Return an empty hypothesis list rather
than a label outside the set.
"""


FEWSHOT_EXAMPLES = """
## Example 1: Post-Mortem (PID Saturation)

**Input**: Bag contains 60 sec of arm control. Integral term grows from 0 to 500, output clamps at 100%. Arm fails to reach target angle.

**Output**:
{
  "timeline": [
    {"t_ns": 0, "label": "arm_start", "cross_view": false},
    {"t_ns": 10000000000, "label": "integral_begins_growing", "cross_view": true},
    {"t_ns": 40000000000, "label": "output_saturates_at_100", "cross_view": true},
    {"t_ns": 60000000000, "label": "failure_final_angle_wrong", "cross_view": false}
  ],
  "hypotheses": [
    {
      "bug_class": "pid_saturation",
      "confidence": 0.92,
      "summary": "PID integral term unbounded; no anti-windup clamping.",
      "evidence": [
        {"source": "telemetry", "topic_or_file": "arm_controller.log", "t_ns": 10000000000, "snippet": "integral_term: 500, limit: unlimited"},
        {"source": "code", "topic_or_file": "pid.cpp:45", "t_ns": null, "snippet": "integral += error; // no clamp"}
      ],
      "patch_hint": "Clamp integral term: integral = min(max(integral, -limit), +limit). Add anti-windup logic."
    },
    {
      "bug_class": "bad_gain_tuning",
      "confidence": 0.25,
      "summary": "Gains may be too high; hard to rule out without Ziegler-Nichols test.",
      "evidence": [
        {"source": "telemetry", "topic_or_file": "control_output.log", "t_ns": 35000000000, "snippet": "overshoot: 15%"}
      ],
      "patch_hint": "Run system ID; reduce Kp and Ki by 10-15%."
    }
  ],
  "root_cause_idx": 0,
  "patch_proposal": "In pid.cpp, line 45:\n- integral += error;\n+ integral += error;\n+ integral = min(max(integral, -integral_limit), integral_limit);"
}

## Example 2: Scenario Mining (No Anomalies)

**Input**: 30 sec of nominal robot operation.

**Output**:
{
  "moments": [],
  "rationale": "All sensor readings nominal. State machine transitions on schedule. No control saturation. No latency spikes detected."
}
"""


def post_mortem_prompt():
    """
    Post-mortem analysis: given bag, synced frames, and code, rank hypotheses and propose patch.
    Returns: dict with system, cached_blocks, user_template, and schema.
    """
    return {
        "system": SYSTEM_PROMPT,
        "cached_blocks": [
            {
                "type": "text",
                "text": BUG_TAXONOMY_DOC,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": FEWSHOT_EXAMPLES,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "user_template": (
            "Analyze the following failure scenario and produce a ranked list of hypotheses.\n\n"
            "## Bag Summary\n{bag_summary}\n\n"
            "## Synced Frames\n{synced_frames_description}\n\n"
            "## Code Snippets\n{code_snippets}\n\n"
            "Respond with a single JSON object matching the PostMortemReport schema. "
            "No preamble, no markdown fencing."
        ),
        "schema": PostMortemReport,
    }


def scenario_mining_prompt():
    """
    Scenario mining: detect anomalous moments (0..5 per run).
    Returns: dict with system, cached_blocks, user_template, and schema.
    """
    return {
        "system": SYSTEM_PROMPT,
        "cached_blocks": [
            {
                "type": "text",
                "text": BUG_TAXONOMY_DOC,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": FEWSHOT_EXAMPLES,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "user_template": (
            "Scan the following telemetry and frames for anomalous moments. "
            "Return 0–5 moments only. If nothing is anomalous, return an empty moments array. "
            "Do not fabricate anomalies.\n\n"
            "## Bag Summary\n{bag_summary}\n\n"
            "## Synced Frames\n{synced_frames_description}\n\n"
            "Respond with a single JSON object matching the ScenarioMiningReport schema. "
            "No preamble, no markdown fencing."
        ),
        "schema": ScenarioMiningReport,
    }


def synthetic_qa_prompt():
    """
    Synthetic QA: model produces hypotheses, then self-evaluates against ground truth.
    Returns: dict with system, cached_blocks, user_template, and schema.
    """
    return {
        "system": SYSTEM_PROMPT,
        "cached_blocks": [
            {
                "type": "text",
                "text": BUG_TAXONOMY_DOC,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": FEWSHOT_EXAMPLES,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        "user_template": (
            "Analyze the following bag and produce your best hypothesis for the root cause. "
            "Then compare your prediction to the ground truth and provide a self-evaluation.\n\n"
            "## Bag Summary\n{bag_summary}\n\n"
            "## Ground Truth Bug\n{ground_truth_bug}\n\n"
            "Respond with a single JSON object with EXACTLY this shape (no extra keys, no wrapper objects):\n"
            "{{\n"
            '  "hypotheses": [\n'
            "    {{\n"
            '      "bug_class": "<exactly one of: pid_saturation|sensor_timeout|state_machine_deadlock|bad_gain_tuning|missing_null_check|calibration_drift|latency_spike>",\n'
            '      "confidence": <float 0..1>,\n'
            '      "summary": "<short>",\n'
            '      "evidence": [ {{"source": "telemetry|camera|code|timeline", "topic_or_file": "<str>", "t_ns": <int or null>, "snippet": "<str>"}} ],\n'
            '      "patch_hint": "<str>"\n'
            "    }}\n"
            "  ],\n"
            '  "self_eval": {{\n'
            '    "predicted_bug": "<bug_class from your top hypothesis>",\n'
            '    "ground_truth_bug": "<bug_class from the ground truth provided above>",\n'
            '    "match": <true if they match, else false>,\n'
            '    "notes": "<short explanation>"\n'
            "  }}\n"
            "}}\n"
            "No preamble, no markdown fencing, no wrapping the output in any other key."
        ),
        "schema": SyntheticQAReport,
    }
