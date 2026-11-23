"""Drift angle and induced resistance of a hull balancing a side force.

Reference
---------
Tillig, F. and Ringsberg, J.W. (2020). Design, operation and analysis of
    wind-assisted cargo ships. Ocean Engineering, 211, 107603.
    Section 3.6, equations (21), (22), (33), (34) to (37).

The hull is treated as a low aspect ratio wing (AR = T / L) with reference
area L * T. Lift, equation (33):
    c_L = 0.8 * 0.5 * pi * AR * sin(beta) + 0.6541 * sin|beta| * sin(beta) * cos(beta)
Induced drag, equation (37), with the first term built on the potential part
c_L1 of the lift as derived in equations (34) to (36):
    c_Di = 0.66 * c_L1 * |beta|**0.6 + 0.6541 * sin(|beta|)**3

Simplification: the whole side force is taken by the hull. The rudder load and
its resistance, which depend on the yaw moment and so on where the rotors
stand, are not modelled.
"""

from math import pi, radians, sin, cos

from .hull import Hull
from .water import SEA_WATER_15C, Water

K_CROSSFLOW = 0.6541
BETA_MAX = radians(20)  # circulatory lift holds well beyond this, see section 3.6.1


def c_lift_potential(beta: float, AR: float) -> float:
    return 0.8 * 0.5 * pi * AR * sin(beta)


def c_lift(beta: float, AR: float) -> float:
    return c_lift_potential(beta, AR) + K_CROSSFLOW * sin(abs(beta)) * sin(beta) * cos(beta)


def c_induced_drag(beta: float, AR: float) -> float:
    return 0.66 * abs(c_lift_potential(beta, AR)) * abs(beta) ** 0.6 + K_CROSSFLOW * sin(abs(beta)) ** 3


def drift_angle(hull: Hull, V: float, side_force: float, water: Water = SEA_WATER_15C) -> float:
    """Drift angle (rad) at which the hull lift balances `side_force` (N). Capped at BETA_MAX."""
    if V <= 0 or side_force == 0:
        return 0.0
    q_area = 0.5 * water.rho * V**2 * hull.L * hull.T
    target = abs(side_force) / q_area
    AR = hull.T / hull.L
    if c_lift(BETA_MAX, AR) <= target:
        return BETA_MAX
    lo, hi = 0.0, BETA_MAX
    for _ in range(50):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if c_lift(mid, AR) < target else (lo, mid)
    return 0.5 * (lo + hi)


def induced_resistance(hull: Hull, V: float, side_force: float, water: Water = SEA_WATER_15C) -> float:
    """Added resistance (N) from sailing at the drift angle that balances `side_force`."""
    beta = drift_angle(hull, V, side_force, water)
    return 0.5 * water.rho * V**2 * hull.L * hull.T * c_induced_drag(beta, hull.T / hull.L)
