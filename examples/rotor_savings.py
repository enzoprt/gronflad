"""Net propulsion power saving of two Flettner rotors versus ship speed, on three routes.

Run: python examples/rotor_savings.py
Writes docs/img/rotor_savings.png
"""

import warnings
from pathlib import Path

import matplotlib.pyplot as plt

from gronflad import ValidityWarning
from gronflad.rotor import FlettnerRotor
from gronflad.route import ROUTES, load_wind
from gronflad.ships import HM1982_HULL, HM1982_PROPELLER
from gronflad.wind_assist import route_saving

SURFACE = "#fcfcfb"
TEXT_PRIMARY = "#0b0b0b"
TEXT_SECONDARY = "#52514e"
GRID = "#e4e3df"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]

ROTOR = FlettnerRotor(D=5, H=30, count=2)
SPEEDS = [10, 12, 14, 16, 18, 20, 22, 25]
CASES = [
    ("rotterdam-new-york", True, "New York to Rotterdam"),
    ("rotterdam-new-york", False, "Rotterdam to New York"),
    ("shanghai-rotterdam", False, "Shanghai to Rotterdam via Suez"),
    ("fos-port-said", False, "Fos-sur-Mer to Port Said"),
]

fig, ax = plt.subplots(figsize=(9, 5), dpi=200, facecolor=SURFACE)
ax.set_facecolor(SURFACE)
with warnings.catch_warnings():
    warnings.simplefilter("ignore", ValidityWarning)
    for (slug, reverse, label), color in zip(CASES, SERIES):
        wind = load_wind(ROUTES[slug])
        saving = [
            100 * route_saving(HM1982_HULL, HM1982_PROPELLER, ROTOR, wind, v, reverse=reverse).net_fraction
            for v in SPEEDS
        ]
        ax.plot(SPEEDS, saving, color=color, linewidth=2, marker="o", markersize=5, label=label)
        print(label, [round(s, 1) for s in saving])

ax.set_xlabel("Ship speed (knots)", color=TEXT_SECONDARY)
ax.set_ylabel("Net saving in propulsion power (%)", color=TEXT_SECONDARY)
ax.set_title(
    "Two 30 x 5 m Flettner rotors, 205 m ship, ERA5 wind of 2024",
    loc="left", color=TEXT_PRIMARY, fontsize=12, weight="bold",
)
ax.set_ylim(0, None)
ax.grid(axis="y", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
for side in ("top", "right", "left"):
    ax.spines[side].set_visible(False)
ax.spines["bottom"].set_color(GRID)
ax.tick_params(colors=TEXT_SECONDARY, length=0)
ax.legend(frameon=False, fontsize=9, labelcolor=TEXT_SECONDARY)
fig.text(
    0.01, 0.01,
    "Hull drift resistance included. Upper bound: rotor interaction and rudder resistance not modelled. Model: Tillig and Ringsberg (2020).",
    color=TEXT_SECONDARY, fontsize=7.5,
)
out = Path(__file__).resolve().parents[1] / "docs" / "img" / "rotor_savings.png"
fig.tight_layout(rect=(0, 0.03, 1, 1))
fig.savefig(out, facecolor=SURFACE)
print(f"Saved {out}")
