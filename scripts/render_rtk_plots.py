"""Render the three hero plots for the RTK-heading-break finding.

Outputs:
  docs/assets/rtk_carrier_contrast.png — rover vs moving-base carrier-phase over 1 h
  docs/assets/rel_pos_valid.png         — REL_POS_VALID flag over 1 h (flat zero)
  docs/assets/rtk_numsv.png             — rover numSV over 1 h (no tunnel dropout)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
CASE = REPO / "black-box-bench" / "cases" / "rtk_heading_break_01"
OUT = REPO / "docs" / "assets"
OUT.mkdir(parents=True, exist_ok=True)

npz = np.load(CASE / "telemetry.npz")


def _minutes(t_ns: np.ndarray) -> np.ndarray:
    return (t_ns - t_ns[0]) / 1e9 / 60.0


# ---------- plot 1: rover vs moving-base carrier-phase ---------------------
fig, ax = plt.subplots(figsize=(10, 3.5), dpi=140)
ax.fill_between(
    _minutes(npz["mb_t_ns"]), 0, npz["mb_carr"] + 0.02,
    step="pre", alpha=0.55, label="moving-base (healthy, FLOAT+FIXED 94%)",
)
ax.fill_between(
    _minutes(npz["rover_t_ns"]), 0, npz["rover_carr"] + 0.02,
    step="pre", alpha=0.85, label="rover (CARR_NONE 100% — never locks)",
)
ax.set_yticks([0, 1, 2])
ax.set_yticklabels(["NONE", "FLOAT", "FIXED"])
ax.set_xlabel("bag time (minutes)")
ax.set_ylabel("carrier-phase solution")
ax.set_title("Carrier-phase solution: moving-base is healthy, rover never locks (1 h of driving)")
ax.set_ylim(-0.1, 2.3)
ax.legend(loc="upper right", framealpha=0.9)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "rtk_carrier_contrast.png")
plt.close(fig)
print(f"wrote {OUT / 'rtk_carrier_contrast.png'}")

# ---------- plot 2: REL_POS_VALID flag over time ---------------------------
rel_pos_valid = (npz["relpos_flags"] & 0x04).astype(bool).astype(int)
diff_soln = (npz["relpos_flags"] & 0x02).astype(bool).astype(int)
fig, ax = plt.subplots(figsize=(10, 3.0), dpi=140)
ax.step(_minutes(npz["relpos_t_ns"]), diff_soln + 0.02, where="post",
        label=f"FLAGS_DIFF_SOLN (RTCM received, {diff_soln.mean()*100:.1f}%)", linewidth=1.2)
ax.step(_minutes(npz["relpos_t_ns"]), rel_pos_valid, where="post",
        label=f"FLAGS_REL_POS_VALID (heading usable, {rel_pos_valid.mean()*100:.1f}%)", linewidth=2.5)
ax.set_yticks([0, 1])
ax.set_yticklabels(["0 (off)", "1 (on)"])
ax.set_ylim(-0.2, 1.3)
ax.set_xlabel("bag time (minutes)")
ax.set_title("navrelposned.flags — the rover never emits a valid heading")
ax.legend(loc="center right", framealpha=0.9)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "rel_pos_valid.png")
plt.close(fig)
print(f"wrote {OUT / 'rel_pos_valid.png'}")

# ---------- plot 3: numSV (refutes operator's tunnel theory) --------------
fig, ax = plt.subplots(figsize=(10, 3.0), dpi=140)
ax.plot(_minutes(npz["rover_t_ns"]), npz["rover_numSV"], linewidth=0.6,
        label=f"rover numSV (median {int(np.median(npz['rover_numSV']))}, min {int(npz['rover_numSV'].min())})")
ax.axhline(4, linestyle="--", alpha=0.6,
           label="4 SVs = minimum for 3D fix (tunnel would collapse below this)")
ax.set_xlabel("bag time (minutes)")
ax.set_ylabel("satellites tracked")
ax.set_title("Rover satellite count never collapses — operator's tunnel theory is refuted by the data")
ax.set_ylim(0, npz["rover_numSV"].max() + 3)
ax.legend(loc="lower right", framealpha=0.9)
ax.grid(alpha=0.3)
fig.tight_layout()
fig.savefig(OUT / "rtk_numsv.png")
plt.close(fig)
print(f"wrote {OUT / 'rtk_numsv.png'}")
