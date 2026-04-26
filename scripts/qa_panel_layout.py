"""Layout QA for static panels.

Each panel built by build_layout_safe_panels.py emits a sidecar
``<panel>.layout.json`` with the safe area, every card box, and every
text box that was drawn. This script validates:

  * every text box sits inside its parent card,
  * every card sits inside the demo safe area,
  * no two text boxes overlap,
  * no text was drawn outside the safe area.

Exit code is non-zero on any defect, so CI / build_final_video can gate
on it.

Usage:
    python scripts/qa_panel_layout.py [<panel_layout_json> ...]

If no arguments are given, every ``*.layout.json`` under
``demo_assets/final_demo_pack/panels/`` is checked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PANELS = ROOT / "demo_assets/final_demo_pack/panels"

SAFE = {"x_min": 96, "x_max": 1824, "y_min": 72, "y_max": 1008}
FRAME_W, FRAME_H = 1920, 1080


def _rect(b: dict) -> tuple[int, int, int, int]:
    return b["x"], b["y"], b["x"] + b["w"], b["y"] + b["h"]


def _contains(outer: dict, inner: dict, slack: int = 1) -> bool:
    ox0, oy0, ox1, oy1 = _rect(outer)
    ix0, iy0, ix1, iy1 = _rect(inner)
    return (ix0 >= ox0 - slack and iy0 >= oy0 - slack
            and ix1 <= ox1 + slack and iy1 <= oy1 + slack)


def _overlaps(a: dict, b: dict) -> bool:
    ax0, ay0, ax1, ay1 = _rect(a)
    bx0, by0, bx1, by1 = _rect(b)
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _safe_box() -> dict:
    return {
        "x": SAFE["x_min"], "y": SAFE["y_min"],
        "w": SAFE["x_max"] - SAFE["x_min"],
        "h": SAFE["y_max"] - SAFE["y_min"],
    }


def check(layout_path: Path) -> list[str]:
    data = json.loads(layout_path.read_text())
    defects: list[str] = []
    panel = data.get("panel", layout_path.stem)
    cards = data.get("cards", [])
    texts = data.get("texts", [])

    safe = _safe_box()

    # Frame size sanity
    fw, fh = data.get("frame", [FRAME_W, FRAME_H])
    if (fw, fh) != (FRAME_W, FRAME_H):
        defects.append(f"{panel}: frame size {fw}x{fh} != {FRAME_W}x{FRAME_H}")

    # Cards inside safe area
    for c in cards:
        if not _contains(safe, c):
            defects.append(f"{panel}: card {c.get('id','?')} outside safe area: {c}")

    # Each text box inside its card (if it claims one) AND inside safe area
    by_id = {c.get("id"): c for c in cards if c.get("id")}
    for t in texts:
        cid = t.get("card")
        if cid:
            parent = by_id.get(cid)
            if not parent:
                defects.append(f"{panel}: text references unknown card {cid!r}: {t.get('text','?')[:40]!r}")
            elif not _contains(parent, t):
                defects.append(
                    f"{panel}: text overflows card {cid}: {t.get('text','?')[:60]!r} "
                    f"text=({t['x']},{t['y']},{t['w']}x{t['h']}) card=({parent['x']},{parent['y']},{parent['w']}x{parent['h']})"
                )
        if not _contains(safe, t):
            defects.append(
                f"{panel}: text outside safe area: {t.get('text','?')[:60]!r} "
                f"({t['x']},{t['y']},{t['w']}x{t['h']})"
            )

    # No two text boxes overlap (allow same-card siblings to touch but not overlap)
    for i in range(len(texts)):
        for j in range(i + 1, len(texts)):
            a, b = texts[i], texts[j]
            if _overlaps(a, b):
                defects.append(
                    f"{panel}: text overlap: "
                    f"{a.get('text','?')[:30]!r} ⨯ {b.get('text','?')[:30]!r}"
                )

    # Font-size minimums
    for t in texts:
        role = t.get("role", "body")
        size = int(t.get("font_size", 0))
        floor = 22 if role == "label" else 28
        if size < floor:
            defects.append(
                f"{panel}: font {size}px below floor {floor}px (role={role}) "
                f"text={t.get('text','?')[:40]!r}"
            )

    return defects


def main() -> int:
    targets = [Path(p) for p in sys.argv[1:]]
    if not targets:
        targets = sorted(PANELS.glob("*.layout.json"))
    if not targets:
        print("no layout sidecars found; build panels first", file=sys.stderr)
        return 2

    all_defects: dict[str, list[str]] = {}
    for p in targets:
        d = check(p)
        if d:
            all_defects[p.name] = d

    if all_defects:
        print("FAIL: layout defects detected\n")
        for name, defects in all_defects.items():
            print(f"  {name}:")
            for d in defects:
                print(f"    - {d}")
        return 1

    print(f"OK: {len(targets)} panel layouts pass safe-area + bbox + font-size checks")
    return 0


if __name__ == "__main__":
    sys.exit(main())
