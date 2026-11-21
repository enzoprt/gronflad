"""Hull description shared by the resistance and propulsion models."""

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class Hull:
    """Main particulars of a displacement hull.

    Units are SI (m, m2, m3). LCB follows the Holtrop convention: percent of
    L, measured from 0.5 L, positive forward.
    """

    L: float  # length on waterline
    B: float  # moulded breadth
    T_F: float  # draught at forward perpendicular
    T_A: float  # draught at aft perpendicular
    volume: float  # displacement volume
    lcb: float  # longitudinal centre of buoyancy, % of L fwd of 0.5 L
    C_M: float  # midship section coefficient
    C_WP: float  # waterplane area coefficient
    A_BT: float = 0.0  # transverse bulb area at forward perpendicular
    h_B: float = 0.0  # height of bulb centroid above keel
    A_T: float = 0.0  # immersed transom area at rest
    S_APP: float = 0.0  # wetted area of appendages
    k2_app: float = 1.5  # equivalent appendage form factor (1 + k2)
    C_stern: float = 0.0  # afterbody: -10 V sections, 0 normal, +10 U with Hogner stern
    S: float | None = None  # bare hull wetted surface, estimated if None
    name: str = "hull"

    @property
    def T(self) -> float:
        return 0.5 * (self.T_F + self.T_A)

    @property
    def C_B(self) -> float:
        return self.volume / (self.L * self.B * self.T)

    @property
    def C_P(self) -> float:
        return self.C_B / self.C_M

    @property
    def wetted_surface(self) -> float:
        """Wetted surface of the bare hull, estimated with Holtrop (1984) if not given."""
        if self.S is not None:
            return self.S
        L, B, T = self.L, self.B, self.T
        C_B, C_M, C_WP = self.C_B, self.C_M, self.C_WP
        return L * (2 * T + B) * sqrt(C_M) * (
            0.4530 + 0.4425 * C_B - 0.2862 * C_M - 0.003467 * B / T + 0.3696 * C_WP
        ) + 2.38 * self.A_BT / C_B
