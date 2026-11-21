"""Propulsion factors and shaft power for single screw ships.

Hull-propeller interaction (w, t, eta_R) and blade area follow Holtrop and
Mennen (1982). The open water efficiency comes from the Wageningen B-series,
or can be given directly.
"""

from dataclasses import dataclass
from math import sqrt

from .holtrop_mennen import Resistance
from .hull import Hull
from .wageningen import BSeries, operating_point, optimum_pitch
from .water import G, SEA_WATER_15C, Water

# p_0 - p_v for sea water at 15 degC, N/m2 (Holtrop and Mennen, 1982)
ATM_MINUS_VAPOUR = 99047.0


@dataclass(frozen=True)
class Propeller:
    D: float  # diameter, m
    Z: int = 4  # number of blades
    clearance: float = 0.2  # blade tip to keel line, m
    AE_A0: float | None = None  # expanded blade area ratio, Keller estimate if None
    P_D: float | None = None  # pitch ratio, optimum for the operating point if None


@dataclass(frozen=True)
class Propulsion:
    """Propulsion factors and powers at one speed. Powers in W."""

    w: float  # effective wake fraction
    t: float  # thrust deduction fraction
    eta_R: float  # relative rotative efficiency
    eta_O: float  # open water efficiency
    eta_S: float  # shafting efficiency
    AE_A0: float
    thrust: float  # N
    P_E: float
    P_S: float
    P_D: float | None = None  # B-series pitch ratio, None when eta_O was given
    J: float | None = None  # advance coefficient
    n: float | None = None  # rate of revolution, 1/s

    @property
    def eta_H(self) -> float:
        """Hull efficiency."""
        return (1 - self.t) / (1 - self.w)

    @property
    def eta_D(self) -> float:
        """Quasi-propulsive efficiency."""
        return self.eta_H * self.eta_O * self.eta_R


def wake_fraction(hull: Hull, prop: Propeller, res: Resistance) -> float:
    """Effective wake fraction for a single screw ship with conventional stern."""
    L, B, T_A, S, D = hull.L, hull.B, hull.T_A, hull.wetted_surface, prop.D
    C_B, C_P = hull.C_B, hull.C_P

    if B / T_A < 5:
        c8 = B * S / (L * D * T_A)
    else:
        c8 = S * (7 * B / T_A - 25) / (L * D * (B / T_A - 3))
    c9 = c8 if c8 < 28 else 32 - 16 / (c8 - 24)
    c11 = T_A / D if T_A / D < 2 else 0.0833333 * (T_A / D) ** 3 + 1.33333

    C_V = res.form_factor * res.C_F + res.C_A
    C_P1 = 1.45 * C_P - 0.315 - 0.0225 * hull.lcb

    return (
        c9 * C_V * L / T_A * (0.0661875 + 1.21756 * c11 * C_V / (1 - C_P1))
        + 0.24558 * sqrt(B / (L * (1 - C_P1)))
        - 0.09726 / (0.95 - C_P)
        + 0.11434 / (0.95 - C_B)
        + 0.75 * hull.C_stern * C_V
        + 0.002 * hull.C_stern
    )


def thrust_deduction(hull: Hull, prop: Propeller) -> float:
    """Thrust deduction fraction for a single screw ship with conventional stern."""
    L, B, T = hull.L, hull.B, hull.T
    if L / B > 5.2:
        c10 = B / L
    else:
        c10 = 0.25 - 0.003328402 / (B / L - 0.134615385)
    C_P1 = 1.45 * hull.C_P - 0.315 - 0.0225 * hull.lcb
    return (
        0.001979 * L / (B - B * C_P1)
        + 1.0585 * c10
        - 0.00524
        - 0.1418 * prop.D**2 / (B * T)
        + 0.0015 * hull.C_stern
    )


def keller_blade_area(hull: Hull, prop: Propeller, thrust: float, water: Water, K: float = 0.2) -> float:
    """Minimum expanded blade area ratio against cavitation (Keller). K = 0.2 for single screw."""
    shaft_immersion = hull.T_A - prop.clearance - prop.D / 2
    p_static = ATM_MINUS_VAPOUR + water.rho * G * shaft_immersion
    return K + (1.3 + 0.3 * prop.Z) * thrust / (prop.D**2 * p_static)


def relative_rotative_efficiency(hull: Hull, AE_A0: float) -> float:
    return 0.9922 - 0.05908 * AE_A0 + 0.07424 * (hull.C_P - 0.0225 * hull.lcb)


def propulsion(
    hull: Hull,
    prop: Propeller,
    res: Resistance,
    eta_O: float | None = None,
    eta_S: float = 0.99,
    water: Water = SEA_WATER_15C,
) -> Propulsion:
    """Shaft power required to overcome resistance `res`.

    If `eta_O` is None, the propeller is modelled as a Wageningen B-series screw.
    """
    w = wake_fraction(hull, prop, res)
    t = thrust_deduction(hull, prop)
    thrust = res.R_T / (1 - t)
    AE_A0 = prop.AE_A0 if prop.AE_A0 is not None else keller_blade_area(hull, prop, thrust, water)
    eta_R = relative_rotative_efficiency(hull, AE_A0)

    op = None
    if eta_O is None:
        V_A = res.V * (1 - w)
        if prop.P_D is None:
            op = optimum_pitch(prop.D, prop.Z, AE_A0, thrust, V_A, water.rho)
        else:
            op = operating_point(BSeries(prop.D, prop.Z, AE_A0, prop.P_D), thrust, V_A, water.rho)
        eta_O = op.eta_O

    P_S = res.P_E / (eta_R * eta_O * eta_S * (1 - t) / (1 - w))
    return Propulsion(
        w=w, t=t, eta_R=eta_R, eta_O=eta_O, eta_S=eta_S, AE_A0=AE_A0, thrust=thrust, P_E=res.P_E, P_S=P_S,
        P_D=op.propeller.P_D if op else None, J=op.J if op else None, n=op.n if op else None,
    )
