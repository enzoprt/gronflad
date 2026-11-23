"""Hull drift model, Tillig and Ringsberg (2020), equations (33) and (37)."""

from math import pi, radians

import pytest

from gronflad.drift import c_induced_drag, c_lift, drift_angle, induced_resistance
from gronflad.ships import HM1982_HULL as HULL


def test_lift_equation_33():
    AR, beta = 0.05, radians(5)
    from math import cos, sin
    expected = 0.8 * 0.5 * pi * AR * sin(beta) + 0.6541 * sin(beta) * sin(beta) * cos(beta)
    assert c_lift(beta, AR) == pytest.approx(expected)


def test_lift_is_odd_and_drag_is_even():
    assert c_lift(-0.1, 0.05) == pytest.approx(-c_lift(0.1, 0.05))
    assert c_induced_drag(-0.1, 0.05) == pytest.approx(c_induced_drag(0.1, 0.05))


def test_no_side_force_no_drift():
    assert drift_angle(HULL, 6.0, 0.0) == 0.0
    assert induced_resistance(HULL, 6.0, 0.0) == 0.0


def test_drift_balances_side_force():
    V, side = 6.0, 300e3
    beta = drift_angle(HULL, V, side)
    lift = 0.5 * 1025 * V**2 * HULL.L * HULL.T * c_lift(beta, HULL.T / HULL.L)
    assert lift == pytest.approx(side, rel=1e-6)
    assert 0 < beta < radians(10)


def test_induced_resistance_grows_with_side_force_and_falls_with_speed():
    small, large = induced_resistance(HULL, 6.0, 100e3), induced_resistance(HULL, 6.0, 300e3)
    assert large > small > 0
    assert induced_resistance(HULL, 12.0, 300e3) < large
