"""Open water characteristics of Wageningen B-series propellers.

References
----------
Oosterveld, M.W.C. and van Oossanen, P. (1975). Further computer-analyzed data
    of the Wageningen B-screw series. International Shipbuilding Progress,
    22(251), 251-262.
Holtrop, J. and Mennen, G.G.J. (1982). An approximate power prediction method.
    International Shipbuilding Progress, 29(335), p. 169 (scale correction).

The polynomials give K_T and K_Q at a Reynolds number of 2e6. Full scale values
use the drag correction of Holtrop and Mennen (1982), which is consistent with
their propulsion factors. Their numerical example (p. 170) corrects K_T but
reports the uncorrected K_Q, so the torque correction is off by default. This
reproduces the published efficiency and is about 1 % conservative on power. The coefficient table was cross-checked term by term
against two independent open source implementations (MSS, NTNU and xdyn, Sirehna).
"""

import warnings
from dataclasses import dataclass
from math import log10, pi

from .holtrop_mennen import ValidityWarning

VALIDITY = {
    "P/D": (0.5, 1.4),
    "AE/A0": (0.30, 1.05),
    "Z": (2, 7),
}
K_P = 0.00003  # standard blade surface roughness, m

# (C, s, t, u, v): K = sum C * J**s * (P/D)**t * (AE/A0)**u * Z**v
KT_TERMS = (
    (0.00880496, 0, 0, 0, 0),
    (-0.204554, 1, 0, 0, 0),
    (0.166351, 0, 1, 0, 0),
    (0.158114, 0, 2, 0, 0),
    (-0.147581, 2, 0, 1, 0),
    (-0.481497, 1, 1, 1, 0),
    (0.415437, 0, 2, 1, 0),
    (0.0144043, 0, 0, 0, 1),
    (-0.0530054, 2, 0, 0, 1),
    (0.0143481, 0, 1, 0, 1),
    (0.0606826, 1, 1, 0, 1),
    (-0.0125894, 0, 0, 1, 1),
    (0.0109689, 1, 0, 1, 1),
    (-0.133698, 0, 3, 0, 0),
    (0.00638407, 0, 6, 0, 0),
    (-0.00132718, 2, 6, 0, 0),
    (0.168496, 3, 0, 1, 0),
    (-0.0507214, 0, 0, 2, 0),
    (0.0854559, 2, 0, 2, 0),
    (-0.0504475, 3, 0, 2, 0),
    (0.010465, 1, 6, 2, 0),
    (-0.00648272, 2, 6, 2, 0),
    (-0.00841728, 0, 3, 0, 1),
    (0.0168424, 1, 3, 0, 1),
    (-0.00102296, 3, 3, 0, 1),
    (-0.0317791, 0, 3, 1, 1),
    (0.018604, 1, 0, 2, 1),
    (-0.00410798, 0, 2, 2, 1),
    (-0.000606848, 0, 0, 0, 2),
    (-0.0049819, 1, 0, 0, 2),
    (0.0025983, 2, 0, 0, 2),
    (-0.000560528, 3, 0, 0, 2),
    (-0.00163652, 1, 2, 0, 2),
    (-0.000328787, 1, 6, 0, 2),
    (0.000116502, 2, 6, 0, 2),
    (0.000690904, 0, 0, 1, 2),
    (0.00421749, 0, 3, 1, 2),
    (5.65229e-05, 3, 6, 1, 2),
    (-0.00146564, 0, 3, 2, 2),
)

KQ_TERMS = (
    (0.00379368, 0, 0, 0, 0),
    (0.00886523, 2, 0, 0, 0),
    (-0.032241, 1, 1, 0, 0),
    (0.00344778, 0, 2, 0, 0),
    (-0.0408811, 0, 1, 1, 0),
    (-0.108009, 1, 1, 1, 0),
    (-0.0885381, 2, 1, 1, 0),
    (0.188561, 0, 2, 1, 0),
    (-0.00370871, 1, 0, 0, 1),
    (0.00513696, 0, 1, 0, 1),
    (0.0209449, 1, 1, 0, 1),
    (0.00474319, 2, 1, 0, 1),
    (-0.00723408, 2, 0, 1, 1),
    (0.00438388, 1, 1, 1, 1),
    (-0.0269403, 0, 2, 1, 1),
    (0.0558082, 3, 0, 1, 0),
    (0.0161886, 0, 3, 1, 0),
    (0.00318086, 1, 3, 1, 0),
    (0.015896, 0, 0, 2, 0),
    (0.0471729, 1, 0, 2, 0),
    (0.0196283, 3, 0, 2, 0),
    (-0.0502782, 0, 1, 2, 0),
    (-0.030055, 3, 1, 2, 0),
    (0.0417122, 2, 2, 2, 0),
    (-0.0397722, 0, 3, 2, 0),
    (-0.00350024, 0, 6, 2, 0),
    (-0.0106854, 3, 0, 0, 1),
    (0.00110903, 3, 3, 0, 1),
    (-0.000313912, 0, 6, 0, 1),
    (0.0035985, 3, 0, 1, 1),
    (-0.00142121, 0, 6, 1, 1),
    (-0.00383637, 1, 0, 2, 1),
    (0.0126803, 0, 2, 2, 1),
    (-0.00318278, 2, 3, 2, 1),
    (0.00334268, 0, 6, 2, 1),
    (-0.00183491, 1, 1, 0, 2),
    (0.000112451, 3, 2, 0, 2),
    (-2.97228e-05, 3, 6, 0, 2),
    (0.000269551, 1, 0, 1, 2),
    (0.00083265, 2, 0, 1, 2),
    (0.00155334, 0, 2, 1, 2),
    (0.000302683, 0, 6, 1, 2),
    (-0.0001843, 0, 0, 2, 2),
    (-0.000425399, 0, 3, 2, 2),
    (8.69243e-05, 3, 3, 2, 2),
    (-0.0004659, 0, 6, 2, 2),
    (5.54194e-05, 1, 6, 2, 2),
)


def _poly(terms, J: float, P_D: float, AE_A0: float, Z: int) -> float:
    return sum(c * J**s * P_D**t * AE_A0**u * Z**v for c, s, t, u, v in terms)


def kt_open(J: float, P_D: float, AE_A0: float, Z: int) -> float:
    """Thrust coefficient of the B-series at Rn = 2e6."""
    return _poly(KT_TERMS, J, P_D, AE_A0, Z)


def kq_open(J: float, P_D: float, AE_A0: float, Z: int) -> float:
    """Torque coefficient of the B-series at Rn = 2e6."""
    return _poly(KQ_TERMS, J, P_D, AE_A0, Z)


def check_validity(P_D: float, AE_A0: float, Z: int) -> list[str]:
    values = {"P/D": P_D, "AE/A0": AE_A0, "Z": Z}
    return [
        f"{key} = {values[key]:.3f} outside [{lo}, {hi}]"
        for key, (lo, hi) in VALIDITY.items()
        if not lo <= values[key] <= hi
    ]


@dataclass(frozen=True)
class BSeries:
    """A Wageningen B-series propeller at full scale."""

    D: float  # diameter, m
    Z: int  # number of blades
    AE_A0: float  # expanded blade area ratio
    P_D: float  # pitch ratio
    torque_correction: bool = False  # apply the full scale K_Q correction

    @property
    def chord_075(self) -> float:
        """Chord length at 0.75 R, m."""
        return 2.073 * self.AE_A0 * self.D / self.Z

    @property
    def thickness_ratio_075(self) -> float:
        """Thickness to chord ratio at 0.75 R."""
        return (0.0185 - 0.00125 * self.Z) * self.D / self.chord_075

    @property
    def delta_CD(self) -> float:
        """Profile drag difference between model (Rn = 2e6) and full scale."""
        c = self.chord_075
        return (2 + 4 * self.thickness_ratio_075) * (0.003605 - (1.89 + 1.62 * log10(c / K_P)) ** -2.5)

    def kt(self, J: float) -> float:
        """Full scale thrust coefficient."""
        correction = self.delta_CD * 0.3 * self.P_D * self.D * self.chord_075 * self.Z / self.D**2
        return kt_open(J, self.P_D, self.AE_A0, self.Z) + correction

    def kq(self, J: float) -> float:
        """Full scale torque coefficient."""
        if not self.torque_correction:
            return kq_open(J, self.P_D, self.AE_A0, self.Z)
        correction = self.delta_CD * 0.25 * self.chord_075 * self.Z / self.D
        return kq_open(J, self.P_D, self.AE_A0, self.Z) - correction

    def eta_o(self, J: float) -> float:
        """Open water efficiency."""
        return J * self.kt(J) / (2 * pi * self.kq(J))


@dataclass(frozen=True)
class OperatingPoint:
    propeller: BSeries
    J: float  # advance coefficient
    n: float  # rate of revolution, 1/s
    K_T: float
    K_Q: float
    eta_O: float

    @property
    def rpm(self) -> float:
        return self.n * 60


def operating_point(prop: BSeries, thrust: float, V_A: float, rho: float) -> OperatingPoint:
    """Advance coefficient at which `prop` delivers `thrust` (N) at advance speed `V_A` (m/s).

    Solves K_T(J) / J**2 = T / (rho D**2 V_A**2) by bisection.
    """
    for issue in check_validity(prop.P_D, prop.AE_A0, prop.Z):
        warnings.warn(f"B-series propeller: {issue}", ValidityWarning, stacklevel=2)

    load = thrust / (rho * prop.D**2 * V_A**2)
    lo, hi = 1e-3, 2.0
    # Upper bound: the J where K_T vanishes, so the residual changes sign in [lo, hi]
    while prop.kt(hi) > 0 and hi < 5:
        hi += 0.5
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if prop.kt(mid) / mid**2 > load:
            lo = mid
        else:
            hi = mid
    J = 0.5 * (lo + hi)
    return OperatingPoint(
        propeller=prop, J=J, n=V_A / (J * prop.D), K_T=prop.kt(J), K_Q=prop.kq(J), eta_O=prop.eta_o(J)
    )


def optimum_pitch(
    D: float, Z: int, AE_A0: float, thrust: float, V_A: float, rho: float
) -> OperatingPoint:
    """Pitch ratio giving the highest open water efficiency for a fixed diameter and thrust."""

    def efficiency(P_D: float) -> float:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", ValidityWarning)
            return operating_point(BSeries(D, Z, AE_A0, P_D), thrust, V_A, rho).eta_O

    # Golden section search over the valid pitch range
    lo, hi = VALIDITY["P/D"]
    g = (5**0.5 - 1) / 2
    a, b = hi - g * (hi - lo), lo + g * (hi - lo)
    fa, fb = efficiency(a), efficiency(b)
    for _ in range(60):
        if fa > fb:
            hi, b, fb = b, a, fa
            a = hi - g * (hi - lo)
            fa = efficiency(a)
        else:
            lo, a, fa = a, b, fb
            b = lo + g * (hi - lo)
            fb = efficiency(b)
    return operating_point(BSeries(D, Z, AE_A0, 0.5 * (lo + hi)), thrust, V_A, rho)
