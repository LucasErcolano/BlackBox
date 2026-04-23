"""Tests for the black_box.reporting module."""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from black_box.reporting import (
    build_report,
    demo_side_by_side_html,
    parse_patch_proposal,
    scoped_check,
    side_by_side_html,
    unified_diff_str,
)


def _make_image(w: int = 200, h: int = 200, color=(200, 220, 255)) -> Image.Image:
    img = Image.new("RGB", (w, h), color)
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, w - 10, h - 10], outline=(0, 0, 0), width=2)
    d.text((20, 20), "test", fill=(0, 0, 0))
    return img


def test_build_report_smoke(tmp_path: Path) -> None:
    report_json = {
        "hypotheses": [
            {
                "bug_class": "perception_dropout",
                "summary": "Camera topic silent for 1.2s before collision.",
                "confidence": 0.82,
                "is_root_cause": True,
                "evidence": [
                    {
                        "source": "rosbag",
                        "topic_or_file": "/camera/image_raw",
                        "t_ns": 1_700_000_000_000,
                        "snippet": "no messages 1.7e12..1.701e12",
                    }
                ],
                "patch_hint": "Add watchdog on /camera/image_raw.",
            },
            {
                "bug_class": "controller_gain",
                "summary": "Lateral gain too aggressive after dropout recovery.",
                "confidence": 0.41,
                "evidence": [],
                "patch_hint": "Reduce Kp by 30%.",
            },
        ],
        "timeline": [
            {"t_ns": 1_700_000_000_000, "label": "start", "source": "bag"},
            {"t_ns": 1_700_500_000_000, "label": "camera silent", "source": "bag"},
            {"t_ns": 1_701_000_000_000, "label": "collision", "source": "bag"},
        ],
    }

    frame = _make_image()
    plot = _make_image(400, 200, color=(255, 255, 255))

    old = "a\nb\nc\nd\ne\n"
    new = "a\nb\nC\nd\ne\n"
    diff = unified_diff_str(old, new, "before.py", "after.py")
    assert diff.count("\n") >= 5

    artifacts = {"frames": [frame], "plots": [plot], "code_diff": diff}
    case_meta = {
        "case_key": "case_demo_001",
        "bag_path": "/tmp/example.bag",
        "duration_s": 12.5,
        "mode": "post_mortem",
    }

    # build_report now emits Markdown; suffix is normalized to .md.
    out_path = tmp_path / "out.pdf"
    result = build_report(report_json, artifacts, out_path, case_meta)

    expected = out_path.with_suffix(".md")
    assert result == expected
    assert expected.exists()
    size = expected.stat().st_size
    assert size > 1024, f"report too small: {size} bytes"


def test_unified_diff_and_scoped_check() -> None:
    old = "line1\nline2\nline3\n"
    new = "line1\nLINE2\nline3\n"
    diff = unified_diff_str(old, new)
    assert "-line2" in diff
    assert "+LINE2" in diff
    scoped, reason = scoped_check(diff)
    assert scoped is True, reason

    # 100-line rewrite
    big_old = "\n".join(f"old_{i}" for i in range(100)) + "\n"
    big_new = "\n".join(f"new_{i}" for i in range(100)) + "\n"
    big_diff = unified_diff_str(big_old, big_new)
    scoped2, reason2 = scoped_check(big_diff, max_hunks=3, max_lines=40)
    assert scoped2 is False
    assert reason2  # non-empty reason
    assert ("hunks" in reason2) or ("lines" in reason2)


def test_side_by_side_html() -> None:
    old = "alpha\nbeta\ngamma\n"
    new = "alpha\nBETA\ngamma\ndelta\n"
    html_out = side_by_side_html(old, new, title="example-patch")
    assert "alpha" in html_out
    assert "BETA" in html_out
    assert "delta" in html_out
    assert "#e6ffed" in html_out  # added bg color
    assert "<html" in html_out.lower()


def test_demo_side_by_side_html_has_ntsb_chrome() -> None:
    old = "x = 1\ny = 2\n"
    new = "x = 1\ny = clamp(2, 0, 5)\n"
    out = demo_side_by_side_html(
        old, new,
        file_path="src/controller.cpp",
        case_key="c1_faceplant",
        title="Proposed Fix",
    )
    # Banner + case key visible
    assert "BLACK BOX — FORENSIC DIFF" in out
    assert "c1_faceplant" in out
    assert "src/controller.cpp" in out
    # Legend keys
    assert "− removed" in out
    assert "+ added" in out
    # Demo-size font: 14px, not 12px
    assert "font-size:14px" in out
    # Both columns still rendered
    assert "clamp(2, 0, 5)" in out


def test_parse_patch_proposal_extracts_file_and_sides() -> None:
    text = (
        "In pid_controller.cpp, line 45:\n"
        "- integral += error;\n"
        "+ integral += error;\n"
        "+ integral = clamp(integral, -1.0, 1.0);\n"
    )
    path, old, new = parse_patch_proposal(text)
    assert path == "pid_controller.cpp"
    assert "integral += error;" in old
    assert "clamp(integral" in new
    assert "clamp(integral" not in old


def test_parse_patch_proposal_empty_text() -> None:
    path, old, new = parse_patch_proposal("")
    assert path == "patch"
    assert old == ""
    assert new == ""


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
