"""Probe raw footage pack inputs via ffprobe -> input_probe.json."""
import json
import subprocess
from pathlib import Path

ROOT = Path("/home/hz/Desktop/BlackBox")
PACK = ROOT / "demo_assets/editor_raw_footage_pack"
OUT = ROOT / "demo_assets/claude_code_final_edit/output/input_probe.json"
OUT.parent.mkdir(parents=True, exist_ok=True)


def probe(p: Path) -> dict:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json",
         "-show_streams", "-show_format", str(p)],
        capture_output=True, text=True, check=True,
    )
    d = json.loads(r.stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    fr = v["r_frame_rate"]
    n, dn = (int(x) for x in fr.split("/"))
    fps = n / dn if dn else 0
    return {
        "path": str(p),
        "filename": p.name,
        "duration_s": float(d["format"]["duration"]),
        "width": v["width"],
        "height": v["height"],
        "fps": fps,
        "codec": v["codec_name"],
        "pix_fmt": v["pix_fmt"],
        "size_bytes": int(d["format"]["size"]),
    }


def main():
    clips = sorted((PACK / "clips").glob("*.mp4"))
    out = {"clips": [probe(c) for c in clips]}
    OUT.write_text(json.dumps(out, indent=2))
    print(f"wrote {OUT} ({len(out['clips'])} clips)")


if __name__ == "__main__":
    main()
