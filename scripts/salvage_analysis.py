"""Recover assistant JSON from stream_events.jsonl when ForensicSession.finalize
raised schema-validation errors.

For each <case>/ that has stream_events.jsonl but no analysis.json, extract
the assistant message text, strip fences, coerce unknown bug_class to "other",
and save analysis.json + build report.pdf.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, "/home/hz/Desktop/BlackBox/src")
from black_box.reporting import build_report  # noqa: E402  (md_report)

ALLOWED = {
    "pid_saturation", "sensor_timeout", "state_machine_deadlock",
    "bad_gain_tuning", "missing_null_check", "calibration_drift",
    "latency_spike", "other",
}


def _strip(text: str) -> str:
    t = text.strip()
    if t.startswith("```json"):
        t = t[7:]
    elif t.startswith("```"):
        t = t[3:]
    if t.endswith("```"):
        t = t[:-3]
    return t.strip()


def _coerce(report: dict) -> dict:
    hyps = report.get("hypotheses") or []
    for h in hyps:
        bc = h.get("bug_class", "other")
        if bc not in ALLOWED:
            h["bug_class"] = "other"
    tl = report.get("timeline") or []
    for ev in tl:
        # t_ns must be int
        try:
            ev["t_ns"] = int(ev.get("t_ns", 0))
        except Exception:
            ev["t_ns"] = 0
        ev["cross_view"] = bool(ev.get("cross_view", False))
        ev["label"] = str(ev.get("label") or ev.get("event") or "event")
    # evidence
    for h in hyps:
        for ev in h.get("evidence", []) or []:
            if "source" not in ev:
                ev["source"] = "telemetry"
            if "topic_or_file" not in ev:
                ev["topic_or_file"] = ev.get("topic") or ev.get("file") or "unknown"
            if "snippet" not in ev:
                ev["snippet"] = str(ev.get("text") or "")
    report.setdefault("root_cause_idx", 0)
    report.setdefault("patch_proposal", "")
    return report


def salvage(case_dir: Path) -> bool:
    events_path = case_dir / "stream_events.jsonl"
    analysis_path = case_dir / "analysis.json"
    if analysis_path.exists():
        return False
    if not events_path.exists():
        return False
    last_text = None
    with open(events_path) as f:
        for line in f:
            try:
                ev = json.loads(line)
            except Exception:
                continue
            if ev.get("type") == "assistant":
                t = ev.get("payload", {}).get("text")
                if t:
                    last_text = t
    if not last_text:
        return False
    raw = _strip(last_text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"  JSON parse failed: {e}")
        return False
    data = _coerce(data)
    analysis_path.write_text(json.dumps(data, indent=2))
    # Build PDF
    case_meta = {
        "case_key": case_dir.name,
        "mode": "post_mortem" if case_dir.name == "sanfer_tunnel" else "scenario_mining",
    }
    try:
        build_report(data, artifacts={}, out_pdf=case_dir / "report.pdf",
                     case_meta=case_meta)
        print(f"  {case_dir.name}: salvaged + PDF built")
    except Exception as e:
        print(f"  {case_dir.name}: salvaged (PDF failed: {e})")
    return True


def main():
    root = Path("/home/hz/Desktop/BlackBox/data/final_runs")
    n = 0
    for case_dir in sorted(root.iterdir()):
        if case_dir.is_dir() and not case_dir.name.startswith("."):
            if salvage(case_dir):
                n += 1
    print(f"Salvaged {n} cases")


if __name__ == "__main__":
    main()
