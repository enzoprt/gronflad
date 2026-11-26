"""Flettner rotor model against Tillig and Ringsberg (2020), Ocean Engineering 211, 107603."""

import pytest

from gronflad.rotor import (
    FlettnerRotor, apparent_wind, best_rotor_state, c_drag, c_lift, c_power, rotor_state, wind_at_height,
)


def test_lift_at_spin_ratio_3():
    # Section 3.4: "the ShipCLEAN simulations ... give a lift coefficient of about 9.5" at SR = 3
    assert c_lift(3) == pytest.approx(9.5, abs=0.05)


def test_minimum_drag_near_spin_ratio_half():
    # Section 4: minimum drag "at a spin ratio of approximately 0.5"
    sr_min = min((c_drag(s / 100), s / 100) for s in range(0, 300))[1]
    assert sr_min == pytest.approx(0.5, abs=0.15)


def test_no_power_when_not_spinning():
    assert c_power(0) == 0.0
    assert c_lift(0) == 0.0


def test_hellmann_profile():
    assert wind_at_height(10, 10) == pytest.approx(10)
    assert wind_at_height(10, 40) == pytest.approx(10 * 4**0.27)


def test_apparent_wind():
    assert apparent_wind(10, 0, 5) == pytest.approx((15, 0))
    assert apparent_wind(10, 180, 5) == pytest.approx((5, 180))
    aws, awa = apparent_wind(5, 90, 5)
    assert aws == pytest.approx(5 * 2**0.5)
    assert awa == pytest.approx(45)


def test_head_wind_gives_no_useful_thrust():
    rotor = FlettnerRotor(D=4, H=24)
    state = best_rotor_state(rotor, tws10=10, twa_deg=0, ship_speed=6, shaft_power_per_newton=8)
    assert state.thrust <= 0
    # The optimiser idles the rotor near minimum drag instead of spinning it hard
    assert state.spin_ratio < 1


def test_beam_wind_gives_thrust():
    rotor = FlettnerRotor(D=4, H=24)
    state = best_rotor_state(rotor, tws10=10, twa_deg=90, ship_speed=6, shaft_power_per_newton=8)
    assert state.thrust > 50e3
    assert state.thrust * 8 > state.power  # net positive


def test_forces_scale_with_rotor_count():
    one = rotor_state(FlettnerRotor(count=1), 10, 90, 6, omega=10)
    three = rotor_state(FlettnerRotor(count=3), 10, 90, 6, omega=10)
    assert three.thrust == pytest.approx(3 * one.thrust)
    assert three.power == pytest.approx(3 * one.power)


def test_operating_limits_are_respected():
    rotor = FlettnerRotor(D=5, H=30, count=2)
    for tws in (5, 10, 20, 30):
        for twa in (30, 60, 90, 120, 150):
            state = best_rotor_state(rotor, tws, twa, ship_speed=12, shaft_power_per_newton=10)
            assert state.omega * 60 / (2 * 3.141592653589793) <= rotor.max_rpm + 1e-9
            assert state.thrust <= rotor.max_thrust * rotor.count + 1e-6


def test_following_wind_at_ship_speed_stays_finite():
    # 5 m/s at 10 m in a following wind matches a 12 knot ship somewhere on the rotor height
    rotor = FlettnerRotor(count=2)
    V = 12 * 1852 / 3600
    thrusts = [best_rotor_state(rotor, 5.0, twa, V, 1.0).thrust for twa in (170, 175, 179.9, 180)]
    assert max(thrusts) < 20e3
    assert abs(thrusts[-1] - thrusts[-2]) < 5e3
