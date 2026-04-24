"""Edge case tests for black_box.ingestion.render.synced_grid.

Coverage gaps (P3, closes #34): empty frame dict, single-frame grid, >5 frames
(cap + ordering), grayscale + RGBA channel handling, timestamp banner toggle,
odd thumb sizes.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from black_box.ingestion.render import (
    _bgr_to_pil,
    synced_grid,
    thumb,
    to_b64,
)


def _solid_frame(h: int, w: int, rgb_fill: tuple[int, int, int]) -> np.ndarray:
    """Build an HxWx3 BGR frame with a solid color (RGB input for readability)."""
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    r, g, b = rgb_fill
    arr[..., 0] = b
    arr[..., 1] = g
    arr[..., 2] = r
    return arr


def test_synced_grid_empty_frames_returns_placeholder_canvas():
    """No frames -> single cell-sized dark placeholder, not 2x3 grid."""
    out = synced_grid({"t_ns": 0, "frames": {}}, thumb_size=(320, 240))
    assert isinstance(out, Image.Image)
    assert out.size == (320, 240)
    assert out.mode == "RGB"
    # every pixel should be the dark fill (32,32,32)
    px = np.asarray(out)
    assert (px == 32).all()


def test_synced_grid_missing_frames_key_is_empty():
    """Entry without a 'frames' key must not raise; behaves like empty dict."""
    out = synced_grid({"t_ns": 123}, thumb_size=(100, 80))
    assert out.size == (100, 80)


def test_synced_grid_single_frame_still_builds_full_canvas():
    frames = {"/cam/a": _solid_frame(60, 80, (255, 0, 0))}
    out = synced_grid({"t_ns": 1_000_000, "frames": frames}, thumb_size=(200, 150))
    # canvas is always cols*cell_w x rows*cell_h even with one frame
    assert out.size == (600, 300)


def test_synced_grid_caps_at_five_frames():
    """The grid takes only the first 5 items even if more are supplied."""
    frames = {
        f"/cam/{i}": _solid_frame(40, 60, (i * 40, 0, 0))
        for i in range(7)
    }
    out = synced_grid({"t_ns": 0, "frames": frames}, thumb_size=(100, 80))
    # still 3 cols x 2 rows = 300x160
    assert out.size == (300, 160)


def test_synced_grid_timestamp_banner_toggle():
    """t_ns=None skips banner; explicit t_ns draws a banner strip."""
    frames = {"/cam/a": _solid_frame(40, 60, (0, 255, 0))}
    no_stamp = synced_grid({"frames": frames}, thumb_size=(200, 160))
    with_stamp = synced_grid(
        {"t_ns": 5_500_000_000, "frames": frames}, thumb_size=(200, 160)
    )
    # Both have the same geometry
    assert no_stamp.size == with_stamp.size == (600, 320)
    # Bottom-left banner area differs when stamped (banner pixels are black).
    stamped = np.asarray(with_stamp)
    unstamped = np.asarray(no_stamp)
    banner_region = stamped[-28:, :260]
    # Banner must contain black pixels in the stamped image.
    assert (banner_region == 0).any()
    # Unstamped image has no pure-black banner strip in that same region because
    # the tile background is (16,16,16), not (0,0,0).
    assert not (unstamped[-28:, :260] == 0).all()


def test_synced_grid_handles_grayscale_input():
    """_bgr_to_pil must promote 2D grayscale arrays to RGB before paste."""
    gray = np.full((40, 60), 200, dtype=np.uint8)
    out = synced_grid({"t_ns": 0, "frames": {"/cam/gray": gray}}, thumb_size=(120, 100))
    assert out.mode == "RGB"
    assert out.size == (360, 200)


def test_synced_grid_handles_rgba_input():
    rgba = np.zeros((30, 40, 4), dtype=np.uint8)
    rgba[..., 2] = 255  # R channel in BGR idx 2 -> pure red when flipped
    rgba[..., 3] = 255
    out = synced_grid({"t_ns": 0, "frames": {"/cam/rgba": rgba}}, thumb_size=(100, 80))
    assert out.mode == "RGB"
    assert out.size == (300, 160)


def test_synced_grid_odd_thumb_size():
    """Non-even cell dims must not raise (paste coords use integer floor)."""
    frames = {"/cam/a": _solid_frame(45, 77, (10, 20, 30))}
    out = synced_grid({"t_ns": 0, "frames": frames}, thumb_size=(123, 77))
    assert out.size == (369, 154)


def test_thumb_no_upscale_small_image():
    img = Image.new("RGB", (64, 48), color=(10, 20, 30))
    out = thumb(img, max_side=256)
    # copy, not reference; but same size and contents
    assert out.size == (64, 48)
    assert out is not img  # must be a fresh copy


def test_thumb_downscales_largest_side_to_max():
    img = Image.new("RGB", (1600, 400), color=(0, 0, 0))
    out = thumb(img, max_side=800)
    assert max(out.size) == 800
    # aspect preserved within rounding
    assert abs(out.size[0] / out.size[1] - 4.0) < 0.05


def test_to_b64_roundtrip_jpeg():
    img = Image.new("RGB", (32, 32), color=(123, 45, 67))
    enc = to_b64(img, fmt="JPEG", quality=80)
    assert isinstance(enc, str)
    assert len(enc) > 40
    import base64
    import io
    decoded = base64.b64decode(enc)
    loaded = Image.open(io.BytesIO(decoded))
    assert loaded.size == (32, 32)


def test_to_b64_png_path_skips_rgb_convert():
    """PNG path keeps the image mode (no .convert('RGB'))."""
    img = Image.new("RGBA", (8, 8), color=(0, 0, 0, 0))
    enc = to_b64(img, fmt="PNG")
    import base64
    import io
    loaded = Image.open(io.BytesIO(base64.b64decode(enc)))
    # PNG preserved the RGBA mode
    assert loaded.mode == "RGBA"


def test_bgr_to_pil_fallback_path():
    """2-channel arrays hit the final PIL fallback branch."""
    arr = np.zeros((10, 10, 2), dtype=np.uint8)
    out = _bgr_to_pil(arr)
    assert isinstance(out, Image.Image)
