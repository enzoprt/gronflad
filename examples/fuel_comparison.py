"""Well-to-wake GHG intensity and storage volume of marine fuels, for the README.

Run: python examples/fuel_comparison.py
Writes docs/img/fuel_comparison.png
"""

from pathlib import Path

import matplotlib.pyplot as plt

from gronflad.fuels import (
    AMMONIA, E_AMMONIA, E_METHANOL, HFO, LNG_DIESEL, LNG_OTTO_MS, METHANOL, MGO, fueleu_limit,
)

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
BAR = "#2a78d6"

fuels = [HFO, MGO, LNG_OTTO_MS, LNG_DIESEL, METHANOL, AMMONIA, E_METHANOL, E_AMMONIA]
fuels.sort(key=lambda f: f.intensity)
names = [f.name for f in fuels]

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.6), dpi=200, facecolor=SURFACE, sharey=True)
for ax in (ax1, ax2):
    ax.set_facecolor(SURFACE)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=TEXT_SECONDARY, length=0)

ax1.barh(names, [f.intensity for f in fuels], color=BAR, height=0.6)
for year, side in ((2030, "left"), (2040, "right")):
    x = fueleu_limit(year)
    ax1.axvline(x, color=TEXT_SECONDARY, linestyle="--", linewidth=0.9)
    dx = 1 if side == "left" else -1
    ax1.text(x + dx, len(fuels) - 0.45, f"FuelEU {year}", color=TEXT_SECONDARY, fontsize=8, ha=side)
ax1.set_title("Well-to-wake GHG intensity (gCO2eq/MJ)", loc="left", color=TEXT_PRIMARY, fontsize=11, weight="bold")

mgo_volume = 1 / MGO.volumetric_energy
ax2.barh(names, [(1 / f.volumetric_energy) / mgo_volume for f in fuels], color=BAR, height=0.6)
ax2.axvline(1, color=TEXT_SECONDARY, linestyle="--", linewidth=0.9)
ax2.set_title("Storage volume for the same energy (MGO = 1)", loc="left", color=TEXT_PRIMARY, fontsize=11, weight="bold")

fig.text(
    0.01, 0.01,
    "Sources: FuelEU Maritime, Annex II default factors. Storage volumes include tank systems, indicative (DNV GL, 2020).",
    color=TEXT_SECONDARY, fontsize=7.5,
)
out = Path(__file__).resolve().parents[1] / "docs" / "img" / "fuel_comparison.png"
fig.tight_layout(rect=(0, 0.04, 1, 1))
fig.savefig(out, facecolor=SURFACE)
print(f"Saved {out}")
