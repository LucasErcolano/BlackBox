"""End-to-end smoke: synthetic Tier 3 case -> Claude Opus 4.7 -> PDF report.

One real API call. Logs cost to data/costs.jsonl.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
load_dotenv(ROOT / ".env")

from black_box.analysis import ClaudeClient, synthetic_qa_prompt  # noqa: E402
from black_box.ingestion.render import plot_telemetry  # noqa: E402
from black_box.ingestion.rosbag_reader import TimeSeries  # noqa: E402
from black_box.reporting import build_report, unified_diff_str  # noqa: E402


CASE_KEY = "pid_saturation_01"
CASE_DIR = ROOT / "black-box-bench" / "cases" / CASE_KEY


def load_case_telemetry(npz_path: Path) -> dict[str, TimeSeries]:
    z = np.load(npz_path, allow_pickle=True)
    topics: dict[str, TimeSeries] = {}
    for key in z.files:
        if not key.endswith("__t_ns"):
            continue
        base = key[: -len("__t_ns")]
        topic = "/" + base.replace(".", "/")
        t_ns = z[f"{base}__t_ns"]
        values = z[f"{base}__values"]
        fields_raw = z[f"{base}__fields"]
        fields = [str(f) for f in fields_raw.tolist()]
        topics[topic] = TimeSeries(t_ns=t_ns, values=values, fields=fields)
    return topics


def build_bag_summary(telemetry: dict[str, TimeSeries]) -> str:
    lines = ["Synthetic bag. Topics:"]
    for topic, ts in telemetry.items():
        dur = (ts.t_ns[-1] - ts.t_ns[0]) / 1e9
        lines.append(f"  {topic}: N={len(ts.t_ns)}, duration={dur:.1f}s, fields={ts.fields}")
    return "\n".join(lines)


def main() -> int:
    gt = json.loads((CASE_DIR / "ground_truth.json").read_text())
    telemetry = load_case_telemetry(CASE_DIR / "telemetry.npz")
    summary = build_bag_summary(telemetry)

    marks_ns = [int(gt["window_s"][0] * 1e9), int(gt["window_s"][1] * 1e9)]
    plot_img = plot_telemetry(telemetry, marks_ns=marks_ns, size=(1400, 1000))

    # Keep only key topics in the image to save tokens
    top_topics = ["/pwm", "/odom/pose", "/cmd_vel", "/reference"]
    focused = {k: v for k, v in telemetry.items() if k in top_topics}
    focused_plot = plot_telemetry(focused, marks_ns=marks_ns, size=(1400, 900))

    spec = synthetic_qa_prompt()
    user_fields = {
        "bag_summary": summary,
        "ground_truth_bug": json.dumps(gt, indent=2),
    }

    print(f"[smoke] calling Claude Opus 4.7 on case {CASE_KEY} ...", flush=True)
    t0 = time.time()
    client = ClaudeClient()
    report, cost = client.analyze(
        prompt_spec=spec,
        images=[focused_plot],
        user_fields=user_fields,
        resolution="thumb",
        max_tokens=4000,
    )
    wall = time.time() - t0
    print(f"[smoke] done in {wall:.1f}s", flush=True)
    print(f"[smoke] cost: ${cost.usd_cost:.4f}  tokens in/out: "
          f"{cost.cached_input_tokens}+{cost.uncached_input_tokens} / {cost.output_tokens}")

    # Build PDF
    buggy = (CASE_DIR / "source" / "buggy" / "pid_controller.py").read_text()
    clean = (CASE_DIR / "source" / "clean" / "pid_controller.py").read_text()
    diff = unified_diff_str(buggy, clean, "pid_controller.py (buggy)", "pid_controller.py (patched)")

    # Build pseudo post-mortem dict from synthetic_qa report for the PDF template.
    # (PDF template expects timeline/hypotheses keys; we shape it here.)
    top_h = report.hypotheses[0] if report.hypotheses else None
    pdf_dict = {
        "timeline": [
            {"t_ns": int(gt["window_s"][0] * 1e9), "label": "PWM saturation begins", "cross_view": False},
            {"t_ns": int(gt["window_s"][1] * 1e9), "label": "Pose diverges from reference", "cross_view": False},
        ],
        "hypotheses": [h.model_dump() for h in report.hypotheses],
        "root_cause_idx": 0 if top_h else 0,
        "patch_proposal": diff,
    }

    out_pdf = ROOT / "data" / "reports" / f"{CASE_KEY}.pdf"
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    build_report(
        report_json=pdf_dict,
        artifacts={"frames": [], "plots": [focused_plot, plot_img], "code_diff": diff},
        out_pdf=out_pdf,
        case_meta={
            "case_key": CASE_KEY,
            "bag_path": str(CASE_DIR / "telemetry.npz"),
            "duration_s": float(gt["window_s"][1] - gt["window_s"][0] + 5.0),
            "mode": "synthetic_qa",
        },
    )
    print(f"[smoke] PDF: {out_pdf}  ({out_pdf.stat().st_size} bytes)")

    # Self-eval summary
    print(f"[smoke] predicted={report.self_eval.predicted_bug}  "
          f"truth={report.self_eval.ground_truth_bug}  match={report.self_eval.match}")

    total = client.total_spent_usd() if hasattr(client, "total_spent_usd") else None
    if total is not None:
        print(f"[smoke] total spent across all runs (costs.jsonl): ${total:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
