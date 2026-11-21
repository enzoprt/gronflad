"""Physical properties of water and standard constants."""

from dataclasses import dataclass

G = 9.80665  # m/s2
KNOT = 1852 / 3600  # m/s


@dataclass(frozen=True)
class Water:
    """Water properties used by resistance calculations."""

    rho: float  # kg/m3
    nu: float  # kinematic viscosity, m2/s


# Sea water at 15 degC: density used by Holtrop and Mennen (1982), viscosity from ITTC 2011.
SEA_WATER_15C = Water(rho=1025.0, nu=1.18831e-6)
