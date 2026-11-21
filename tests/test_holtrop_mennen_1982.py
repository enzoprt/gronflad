"""Reproduce the numerical example of Holtrop and Mennen (1982), p. 170."""

import warnings

import pytest

from gronflad import KNOT, Hull, ValidityWarning, propulsion, resistance
from gronflad.holtrop_mennen import bulb_factor, half_entrance_angle, run_length
from gronflad.ships import HM1982_HULL as HULL
from gronflad.ships import HM1982_PROPELLER as PROP

V = 25 * KNOT


@pytest.fixture(scope="module")
def res():
    return resistance(HULL, V)


def test_hull_geometry():
    assert HULL.C_P == pytest.approx(0.5833, abs=1e-4)
    assert HULL.wetted_surface == pytest.approx(7381.45, abs=0.01)
    assert run_length(HULL) == pytest.approx(81.385, abs=1e-3)
    assert half_entrance_angle(HULL) == pytest.approx(12.08, abs=0.01)
    assert bulb_factor(HULL) == pytest.approx(0.7595, abs=1e-4)


def test_coefficients(res):
    assert res.Fn == pytest.approx(0.2868, abs=1e-4)
    assert res.C_F == pytest.approx(0.001390, abs=1e-6)
    assert res.C_A == pytest.approx(0.000352, abs=1e-6)
    assert res.form_factor == pytest.approx(1.156, abs=1e-3)


@pytest.mark.parametrize(
    "component, published_kN, rel",
    [
        ("R_F", 869.63, 1e-3),
        ("R_APP", 8.83, 1e-3),
        ("R_W", 557.11, 1e-3),
        ("R_B", 0.049, 1e-2),
        # The paper rounds C_A before computing R_A, hence a looser tolerance.
        ("R_A", 221.98, 1e-2),
        ("R_T", 1793.26, 1e-3),
    ],
)
def test_resistance_components(res, component, published_kN, rel):
    assert getattr(res, component) / 1e3 == pytest.approx(published_kN, rel=rel)


def test_transom_is_dry(res):
    assert res.R_TR == 0.0


def test_propulsion(res):
    p = propulsion(HULL, PROP, res, eta_O=0.6461)
    assert p.w == pytest.approx(0.2584, abs=1e-3)
    assert p.t == pytest.approx(0.1747, abs=1e-3)
    assert p.thrust / 1e3 == pytest.approx(2172.75, rel=2e-3)
    assert p.AE_A0 == pytest.approx(0.7393, abs=1e-3)
    assert p.eta_R == pytest.approx(0.9931, abs=1e-3)
    assert p.P_E / 1e3 == pytest.approx(23063, rel=2e-3)
    assert p.P_S / 1e3 == pytest.approx(32621, rel=3e-3)


def test_validity_warning_outside_envelope():
    barge = Hull(L=100, B=40, T_F=5, T_A=5, volume=17000, lcb=0, C_M=0.99, C_WP=0.9)
    with pytest.warns(ValidityWarning):
        resistance(barge, 5 * KNOT)


def test_no_warning_inside_envelope():
    with warnings.catch_warnings():
        warnings.simplefilter("error", ValidityWarning)
        resistance(HULL, V)
