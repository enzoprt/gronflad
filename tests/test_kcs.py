"""Holtrop-Mennen against the published KCS model test, extrapolated with ITTC 1978.

This is a comparison, not a calibration: the statistical method is expected to
land within about 10 % of a model test for a given hull.
"""

from math import sqrt

import pytest

from gronflad import KNOT, resistance
from gronflad.holtrop_mennen import ittc57
from gronflad.ships import KCS_EFD, KCS_HULL, KCS_LPP
from gronflad.water import G, SEA_WATER_15C, Water

FRESH_WATER_15C = Water(rho=999.1, nu=1.1386e-6)  # assumption, tank temperature not published


def efd_full_scale_ct(form_factor: float) -> float:
    """Model CT extrapolated to full scale with the ITTC 1978 form factor method, without C_A."""
    m = KCS_EFD
    w = FRESH_WATER_15C
    CT_m = m["R_T"] / (0.5 * w.rho * m["V"] ** 2 * m["S"])
    CR = CT_m - form_factor * ittc57(m["V"] * m["L_pp"] / w.nu)
    V_s = m["V"] * sqrt(m["scale"])
    return CR + form_factor * ittc57(V_s * KCS_LPP / SEA_WATER_15C.nu)


def test_published_particulars_are_consistent():
    assert KCS_HULL.volume / (KCS_LPP * KCS_HULL.B * KCS_HULL.T) == pytest.approx(0.651, abs=0.001)
    assert KCS_EFD["V"] * sqrt(KCS_EFD["scale"]) / KNOT == pytest.approx(24.0, abs=0.05)
    assert KCS_EFD["V"] / sqrt(G * KCS_EFD["L_pp"]) == pytest.approx(0.26, abs=0.001)


def test_holtrop_within_ten_percent_of_model_test():
    V = KCS_EFD["V"] * sqrt(KCS_EFD["scale"])
    r = resistance(KCS_HULL, V)
    S = KCS_HULL.wetted_surface + KCS_HULL.S_APP
    ct_holtrop = (r.R_T - r.R_A) / (0.5 * SEA_WATER_15C.rho * V**2 * S)
    ct_efd = efd_full_scale_ct(r.form_factor)
    deviation = ct_holtrop / ct_efd - 1
    assert 0 < deviation < 0.12  # Holtrop overpredicts the KCS, mostly through wave resistance
