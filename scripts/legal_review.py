"""Legal pre-upload review (OPTIONAL).

Status: bag owners have cleared frames and short clips from the
sanfer_sanisidro and related sessions for public demo / thread / PDF use
with faces and plates UNBLURRED. Running this script is no longer a
pre-publication requirement for those bags. Keep it around for (a) bags
from other sources whose consent is unclear, or (b) optional redaction
when a particular frame contains a third party you'd rather not show.

Reads images from data/uploads_raw/, runs Haar cascades for faces + plates,
writes annotated previews to data/uploads_review/ with numbered bboxes so
the user can approve/reject each detection before blurring.

Detections are saved as <stem>.detections.json; apply_redaction.py consumes
that JSON + an inclusion list to produce the final redacted image.

Usage:
    python scripts/legal_review.py                  # all files in uploads_raw
    python scripts/legal_review.py bag1_recovered   # one stem
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "uploads_raw"
REVIEW = ROOT / "data" / "uploads_review"
REVIEW.mkdir(parents=True, exist_ok=True)

CASCADE_DIR = Path(cv2.data.haarcascades)
FACE_FRONTAL = cv2.CascadeClassifier(str(CASCADE_DIR / "haarcascade_frontalface_default.xml"))
FACE_PROFILE = cv2.CascadeClassifier(str(CASCADE_DIR / "haarcascade_profileface.xml"))
PLATE_RUS = cv2.CascadeClassifier(str(CASCADE_DIR / "haarcascade_russian_plate_number.xml"))
PLATE_GEN = cv2.CascadeClassifier(str(CASCADE_DIR / "haarcascade_license_plate_rus_16stages.xml"))
BODY_UPPER = cv2.CascadeClassifier(str(CASCADE_DIR / "haarcascade_upperbody.xml"))


def _detect(img_gray, cascade, scale=1.1, min_neighbors=4, min_size=(20, 20)):
    rects = cascade.detectMultiScale(img_gray, scaleFactor=scale,
                                     minNeighbors=min_neighbors, minSize=min_size)
    return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in rects]


def _iou(a, b):
    ax1, ay1, aw, ah = a; ax2, ay2 = ax1 + aw, ay1 + ah
    bx1, by1, bw, bh = b; bx2, by2 = bx1 + bw, by1 + bh
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0, ix2 - ix1) * max(0, iy2 - iy1)
    union = aw * ah + bw * bh - inter
    return inter / union if union else 0.0


def _dedup(rects, thr=0.3):
    out = []
    for r in rects:
        if all(_iou(r, o) < thr for o in out):
            out.append(r)
    return out


def review(path: Path) -> dict:
    img = cv2.imread(str(path))
    if img is None:
        raise RuntimeError(f"cannot read {path}")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    faces = _detect(gray, FACE_FRONTAL, min_size=(24, 24)) + \
            _detect(gray, FACE_PROFILE, min_size=(24, 24))
    faces = _dedup(faces)

    plates = _detect(gray, PLATE_RUS, min_size=(30, 10)) + \
             _detect(gray, PLATE_GEN, min_size=(30, 10))
    plates = _dedup(plates)

    bodies = _detect(gray, BODY_UPPER, min_size=(40, 40))
    bodies = _dedup(bodies)

    detections = []
    for i, r in enumerate(faces):
        detections.append({"id": f"F{i}", "kind": "face", "bbox": r})
    for i, r in enumerate(plates):
        detections.append({"id": f"P{i}", "kind": "plate", "bbox": r})
    for i, r in enumerate(bodies):
        detections.append({"id": f"B{i}", "kind": "body_upper", "bbox": r})

    preview = img.copy()
    colors = {"face": (0, 0, 255), "plate": (0, 255, 255), "body_upper": (255, 200, 0)}
    for d in detections:
        x, y, w, h = d["bbox"]
        c = colors[d["kind"]]
        cv2.rectangle(preview, (x, y), (x + w, y + h), c, 2)
        label = f"{d['id']}"
        cv2.putText(preview, label, (x, max(0, y - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, c, 2)

    out_preview = REVIEW / f"{path.stem}.review.png"
    out_json = REVIEW / f"{path.stem}.detections.json"
    cv2.imwrite(str(out_preview), preview)
    out_json.write_text(json.dumps({
        "source": str(path.relative_to(ROOT)),
        "image_size": [int(img.shape[1]), int(img.shape[0])],
        "detections": detections,
    }, indent=2))

    return {
        "source": path.name,
        "preview": str(out_preview.relative_to(ROOT)),
        "counts": {
            "faces": len(faces), "plates": len(plates), "bodies": len(bodies),
        },
    }


def main() -> None:
    stems = sys.argv[1:]
    if stems:
        paths = [RAW / f"{s}.png" for s in stems]
    else:
        paths = sorted(RAW.glob("*.png")) + sorted(RAW.glob("*.jpg"))
    results = [review(p) for p in paths if p.exists()]
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
