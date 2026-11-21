"""Reference ships used for validation and examples."""

from .hull import Hull
from .propulsion import Propeller

# Numerical example of Holtrop and Mennen (1982): hypothetical single screw ship, 25 knots.
HM1982_HULL = Hull(
    name="Holtrop-Mennen 1982 example",
    L=205.0,
    B=32.0,
    T_F=10.0,
    T_A=10.0,
    volume=37500.0,
    lcb=-0.75,
    C_M=0.98,
    C_WP=0.75,
    A_BT=20.0,
    h_B=4.0,
    A_T=16.0,
    S_APP=50.0,
    k2_app=1.5,
    C_stern=10.0,
)
HM1982_PROPELLER = Propeller(D=8.0, Z=4, clearance=0.2)
