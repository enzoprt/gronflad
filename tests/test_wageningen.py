"""B-series propeller against the numerical example of Holtrop and Mennen (1982), p. 170."""

import pytest

from gronflad import KNOT, propulsion, resistance
from gronflad.ships import HM1982_HULL, HM1982_PROPELLER
from gronflad.wageningen import BSeries, kq_open, kt_open, operating_point

# Published operating point
THRUST = 2172.75e3  # N
N_PUBLISHED = 1.6594  # 1/s
AE_A0 = 0.7393


@pytest.fixture(scope="module")
def V_A():
    res = resistance(HM1982_HULL, 25 * KNOT)
    return res.V * (1 - propulsion(HM1982_HULL, HM1982_PROPELLER, res, eta_O=0.65).w)


def test_scale_correction_geometry():
    prop = BSeries(D=8.0, Z=4, AE_A0=AE_A0, P_D=1.0)
    assert prop.chord_075 == pytest.approx(3.065, abs=1e-3)
    assert prop.thickness_ratio_075 == pytest.approx(0.03524, abs=1e-5)
    assert prop.delta_CD == pytest.approx(0.000956, abs=1e-6)


def test_published_operating_point(V_A):
    # The paper does not print P/D, so find the pitch that gives the published rpm,
    # then compare the independent outputs K_T, K_Q and eta_O.
    lo, hi = 0.9, 1.2
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        op = operating_point(BSeries(8.0, 4, AE_A0, mid), THRUST, V_A, 1025.0)
        lo, hi = (mid, hi) if op.n > N_PUBLISHED else (lo, mid)
    assert op.K_T == pytest.approx(0.18802, rel=1e-3)
    assert op.K_Q == pytest.approx(0.033275, rel=2e-3)
    assert op.eta_O == pytest.approx(0.6461, rel=2e-3)


def test_torque_correction_raises_efficiency(V_A):
    base = operating_point(BSeries(8.0, 4, AE_A0, 1.04), THRUST, V_A, 1025.0)
    corrected = operating_point(BSeries(8.0, 4, AE_A0, 1.04, torque_correction=True), THRUST, V_A, 1025.0)
    assert corrected.eta_O > base.eta_O
    assert corrected.eta_O == pytest.approx(base.eta_O, rel=0.02)


def test_open_water_curve_shape():
    J = [0.0, 0.3, 0.6, 0.9]
    kt = [kt_open(j, 1.0, 0.7, 4) for j in J]
    kq = [kq_open(j, 1.0, 0.7, 4) for j in J]
    assert all(a > b for a, b in zip(kt, kt[1:]))
    assert all(a > b for a, b in zip(kq, kq[1:]))
    assert 0.4 < kt[0] < 0.5  # bollard thrust coefficient of a B4-70 at P/D = 1


def test_full_power_prediction_with_bseries():
    res = resistance(HM1982_HULL, 25 * KNOT)
    p = propulsion(HM1982_HULL, HM1982_PROPELLER, res)
    assert 0.9 < p.P_D < 1.2
    assert p.eta_O == pytest.approx(0.6461, rel=0.01)
    assert p.P_S / 1e3 == pytest.approx(32621, rel=0.01)
