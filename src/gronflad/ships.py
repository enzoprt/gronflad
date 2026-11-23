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

# KRISO Container Ship (KCS) at design draught. Published particulars from SIMMAN 2008
# (FORCE Technology). C_WP, A_BT, h_B, A_T, i_E and the LCB on L_wl are not published:
# they were computed from the official IGES hull by scripts/kcs_hydrostatics.py, which
# also reproduces the published volume, LCB, C_M and wetted surface within 0.2 %.
KCS_HULL = Hull(
    name="KCS",
    L=232.5,
    B=32.2,
    T_F=10.8,
    T_A=10.8,
    volume=52030.0,
    lcb=-0.938,  # % of L_wl from the middle of the waterline (-1.48 % of L_pp from midship)
    C_M=0.985,
    C_WP=0.822,
    A_BT=29.3,
    h_B=5.23,
    A_T=0.0,
    S_APP=115.0,  # rudder
    k2_app=1.5,
    C_stern=0.0,  # assumption: normal afterbody sections
    S=9530.0,
    i_E=12.6,
)
KCS_LPP = 230.0
KCS_PROPELLER = Propeller(D=7.9, Z=5, AE_A0=0.8, P_D=0.997)

# Calm water model test at FORCE Technology, scale 1/37.89, sinkage and trim free
# (Lee et al., 2019, Brodogradnja 70(2), doi:10.21278/brod70204, Table 2 and Table 6).
KCS_EFD = {
    "scale": 37.89,
    "L_pp": 6.0702,
    "S": 6.6177 + 0.0801,  # hull and rudder, m2
    "V": 2.006,  # m/s, design speed, Fn = 0.26
    "R_T": 51.591,  # N
}
