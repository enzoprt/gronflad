"""Calm water resistance with the Holtrop and Mennen method.

Reference
---------
Holtrop, J. and Mennen, G.G.J. (1982). An approximate power prediction method.
    International Shipbuilding Progress, 29(335), 166-170.

The implementation follows the 1982 paper formula by formula. Its numerical
example (205 m single screw ship at 25 knots) is reproduced in the test suite.
"""

import warnings
from dataclasses import dataclass
from math import cos, exp, log10, sqrt

from .hull import Hull
from .water import G, SEA_WATER_15C, Water

# Envelope of the regression data reported by Holtrop and Mennen (1982).
VALIDITY = {
    "Fn": (0.0, 0.45),
    "C_P": (0.55, 0.85),
    "L/B": (3.9, 14.9),
    "B/T": (2.1, 4.0),
}


class ValidityWarning(UserWarning):
    """Raised when inputs fall outside the regression envelope of the method."""


@dataclass(frozen=True)
class Resistance:
    """Resistance breakdown at one speed. Forces in N."""

    V: float  # ship speed, m/s
    Fn: float
    Rn: float
    C_F: float
    C_A: float
    form_factor: float  # 1 + k1
    R_F: float
    R_APP: float
    R_W: float
    R_B: float
    R_TR: float
    R_A: float

    @property
    def R_T(self) -> float:
        return self.form_factor * self.R_F + self.R_APP + self.R_W + self.R_B + self.R_TR + self.R_A

    @property
    def P_E(self) -> float:
        """Effective (towing) power in W."""
        return self.R_T * self.V


def ittc57(Rn: float) -> float:
    """ITTC 1957 model-ship correlation line."""
    return 0.075 / (log10(Rn) - 2) ** 2


def run_length(hull: Hull) -> float:
    """Length of the run L_R."""
    C_P = hull.C_P
    return hull.L * (1 - C_P + 0.06 * C_P * hull.lcb / (4 * C_P - 1))


def form_factor(hull: Hull) -> float:
    """Hull form factor 1 + k1."""
    T_L = hull.T / hull.L
    if T_L > 0.05:
        c12 = T_L**0.2228446
    elif T_L > 0.02:
        c12 = 48.20 * (T_L - 0.02) ** 2.078 + 0.479948
    else:
        c12 = 0.479948
    c13 = 1 + 0.003 * hull.C_stern
    C_P = hull.C_P
    return c13 * (
        0.93
        + c12
        * (hull.B / run_length(hull)) ** 0.92497
        * (0.95 - C_P) ** -0.521448
        * (1 - C_P + 0.0225 * hull.lcb) ** 0.6906
    )


def half_entrance_angle(hull: Hull) -> float:
    """Half angle of entrance i_E in degrees, estimated from the main particulars."""
    L, B = hull.L, hull.B
    return 1 + 89 * exp(
        -((L / B) ** 0.80856)
        * (1 - hull.C_WP) ** 0.30484
        * (1 - hull.C_P - 0.0225 * hull.lcb) ** 0.6367
        * (run_length(hull) / B) ** 0.34574
        * (100 * hull.volume / L**3) ** 0.16302
    )


def bulb_factor(hull: Hull) -> float:
    """Reduction of wave resistance due to the bulbous bow, c2."""
    if hull.A_BT == 0:
        return 1.0
    c3 = 0.56 * hull.A_BT**1.5 / (hull.B * hull.T * (0.31 * sqrt(hull.A_BT) + hull.T_F - hull.h_B))
    return exp(-1.89 * sqrt(c3))


def wave_resistance(hull: Hull, V: float, water: Water = SEA_WATER_15C) -> float:
    """Wave making and wave breaking resistance R_W in N."""
    Fn = V / sqrt(G * hull.L)
    if Fn <= 0:
        return 0.0
    L, B, T, vol = hull.L, hull.B, hull.T, hull.volume
    C_P = hull.C_P

    if B / L < 0.11:
        c7 = 0.229577 * (B / L) ** 0.33333
    elif B / L < 0.25:
        c7 = B / L
    else:
        c7 = 0.5 - 0.0625 * L / B
    c1 = 2223105 * c7**3.78613 * (T / B) ** 1.07961 * (90 - half_entrance_angle(hull)) ** -1.37565
    c5 = 1 - 0.8 * hull.A_T / (B * T * hull.C_M)

    if C_P < 0.8:
        c16 = 8.07981 * C_P - 13.8673 * C_P**2 + 6.984388 * C_P**3
    else:
        c16 = 1.73014 - 0.7067 * C_P
    m1 = 0.0140407 * L / T - 1.75254 * vol ** (1 / 3) / L - 4.79323 * B / L - c16

    slenderness = L**3 / vol
    if slenderness < 512:
        c15 = -1.69385
    elif slenderness < 1727:
        c15 = -1.69385 + (L / vol ** (1 / 3) - 8.0) / 2.36
    else:
        c15 = 0.0
    m2 = c15 * C_P**2 * exp(-0.1 * Fn**-2)
    lam = 1.446 * C_P - 0.03 * L / B if L / B < 12 else 1.446 * C_P - 0.36
    d = -0.9

    return c1 * bulb_factor(hull) * c5 * vol * water.rho * G * exp(m1 * Fn**d + m2 * cos(lam * Fn**-2))


def bulb_resistance(hull: Hull, V: float, water: Water = SEA_WATER_15C) -> float:
    """Additional pressure resistance of a bulbous bow near the surface, R_B in N."""
    if hull.A_BT == 0:
        return 0.0
    A_BT, T_F, h_B = hull.A_BT, hull.T_F, hull.h_B
    P_B = 0.56 * sqrt(A_BT) / (T_F - 1.5 * h_B)
    Fn_i = V / sqrt(G * (T_F - h_B - 0.25 * sqrt(A_BT)) + 0.15 * V**2)
    return 0.11 * exp(-3 * P_B**-2) * Fn_i**3 * A_BT**1.5 * water.rho * G / (1 + Fn_i**2)


def transom_resistance(hull: Hull, V: float, water: Water = SEA_WATER_15C) -> float:
    """Additional pressure resistance of an immersed transom, R_TR in N."""
    if hull.A_T == 0:
        return 0.0
    Fn_T = V / sqrt(2 * G * hull.A_T / (hull.B + hull.B * hull.C_WP))
    c6 = 0.2 * (1 - 0.2 * Fn_T) if Fn_T < 5 else 0.0
    return 0.5 * water.rho * V**2 * hull.A_T * c6


def correlation_allowance(hull: Hull) -> float:
    """Model-ship correlation allowance C_A for standard hull roughness (150 um)."""
    c4 = min(hull.T_F / hull.L, 0.04)
    return (
        0.006 * (hull.L + 100) ** -0.16
        - 0.00205
        + 0.003 * sqrt(hull.L / 7.5) * hull.C_B**4 * bulb_factor(hull) * (0.04 - c4)
    )


def check_validity(hull: Hull, Fn: float) -> list[str]:
    """Return the parameters that fall outside the regression envelope."""
    values = {"Fn": Fn, "C_P": hull.C_P, "L/B": hull.L / hull.B, "B/T": hull.B / hull.T}
    return [
        f"{key} = {values[key]:.3f} outside [{lo}, {hi}]"
        for key, (lo, hi) in VALIDITY.items()
        if not lo <= values[key] <= hi
    ]


def resistance(hull: Hull, V: float, water: Water = SEA_WATER_15C) -> Resistance:
    """Calm water resistance of `hull` at speed `V` (m/s)."""
    Fn = V / sqrt(G * hull.L)
    for issue in check_validity(hull, Fn):
        warnings.warn(f"{hull.name}: {issue}", ValidityWarning, stacklevel=2)

    q = 0.5 * water.rho * V**2
    S = hull.wetted_surface
    Rn = V * hull.L / water.nu
    C_F = ittc57(Rn)
    C_A = correlation_allowance(hull)

    return Resistance(
        V=V,
        Fn=Fn,
        Rn=Rn,
        C_F=C_F,
        C_A=C_A,
        form_factor=form_factor(hull),
        R_F=q * S * C_F,
        R_APP=q * hull.S_APP * hull.k2_app * C_F,
        R_W=wave_resistance(hull, V, water),
        R_B=bulb_resistance(hull, V, water),
        R_TR=transom_resistance(hull, V, water),
        R_A=q * S * C_A,
    )
