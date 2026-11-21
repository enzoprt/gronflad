"""Resistance breakdown of the Holtrop-Mennen 1982 example ship versus speed.

Run: python examples/resistance_breakdown.py
Writes docs/img/resistance_breakdown.png
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from gronflad import KNOT, resistance
from gronflad.ships import HM1982_HULL as HULL

PUBLISHED_RT_KN = 1793.26  # Holtrop and Mennen (1982), 25 knots

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

speeds_kn = np.linspace(10, 26, 81)
results = [resistance(HULL, v * KNOT) for v in speeds_kn]
layers = {
    "Viscous (friction x form factor)": [r.form_factor * r.R_F / 1e3 for r in results],
    "Wave making": [r.R_W / 1e3 for r in results],
    "Correlation allowance": [r.R_A / 1e3 for r in results],
    "Appendages, bulb, transom": [(r.R_APP + r.R_B + r.R_TR) / 1e3 for r in results],
}

fig, ax = plt.subplots(figsize=(9, 5.2), dpi=200, facecolor=SURFACE)
ax.set_facecolor(SURFACE)
ax.stackplot(speeds_kn, *layers.values(), labels=layers.keys(), colors=SERIES, edgecolor=SURFACE, linewidth=1.5)

top = np.sum(list(layers.values()), axis=0)
ax.plot(speeds_kn, top, color=TEXT_PRIMARY, linewidth=1.2)
ax.scatter([25], [PUBLISHED_RT_KN], s=60, color=SURFACE, edgecolor=TEXT_PRIMARY, linewidth=2, zorder=5)
ax.annotate(
    f"Published total at 25 kn: {PUBLISHED_RT_KN:.0f} kN\nGronflad: {top[speeds_kn == 25][0]:.0f} kN",
    xy=(25, PUBLISHED_RT_KN),
    xytext=(19.3, 1650),
    color=TEXT_PRIMARY,
    fontsize=9,
    arrowprops=dict(arrowstyle="-", color=TEXT_SECONDARY, linewidth=0.8),
)

# Direct labels inside the two main layers
i = np.searchsorted(speeds_kn, 14)
ax.text(14, layers["Viscous (friction x form factor)"][i] / 2, "Viscous", color="white", fontsize=10, weight="bold")
j = np.searchsorted(speeds_kn, 24)
base = layers["Viscous (friction x form factor)"][j]
ax.text(23.4, base + layers["Wave making"][j] / 2, "Wave", color=TEXT_PRIMARY, fontsize=10, weight="bold")

ax.set_xlim(10, 26)
ax.set_ylim(0, None)
ax.set_xlabel("Ship speed (knots)", color=TEXT_SECONDARY)
ax.set_ylabel("Calm water resistance (kN)", color=TEXT_SECONDARY)
ax.set_title(
    "Holtrop-Mennen resistance breakdown, 205 m single screw ship",
    loc="left",
    color=TEXT_PRIMARY,
    fontsize=12,
    weight="bold",
)
ax.grid(axis="y", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(colors=TEXT_SECONDARY, length=0)
ax.legend(loc="upper left", frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY)

out = Path(__file__).resolve().parents[1] / "docs" / "img" / "resistance_breakdown.png"
out.parent.mkdir(parents=True, exist_ok=True)
fig.tight_layout()
fig.savefig(out, facecolor=SURFACE)
print(f"Saved {out}")
