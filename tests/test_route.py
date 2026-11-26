"""Route geometry, wind data and route-averaged rotor saving."""

import pytest

from gronflad.rotor import FlettnerRotor
from gronflad.route import ROUTES, distance_nm, initial_course, legs, load_wind, total_distance, true_wind_angle
from gronflad.ships import HM1982_HULL, HM1982_PROPELLER
from gronflad.wind_assist import exact_saving, route_saving, shaft_power_per_newton


def test_one_degree_of_latitude_is_sixty_miles():
    assert distance_nm((0, 0), (1, 0)) == pytest.approx(60.04, abs=0.01)


def test_courses():
    assert initial_course((0, 0), (1, 0)) == pytest.approx(0)
    assert initial_course((0, 0), (0, 1)) == pytest.approx(90)
    assert initial_course((0, 0), (-1, 0)) == pytest.approx(180)


def test_true_wind_angle():
    assert true_wind_angle(0, 0) == 0  # northerly wind, heading north
    assert true_wind_angle(0, 180) == 180
    assert true_wind_angle(270, 0) == 90
    assert true_wind_angle(90, 0) == 90


def test_legs_cover_the_route():
    for route in ROUTES.values():
        assert sum(leg.length_nm for leg in legs(route)) == pytest.approx(total_distance(route), rel=1e-6)


def test_wind_files_are_complete():
    for route in ROUTES.values():
        wind = load_wind(route)
        assert len(wind.times) >= 1460
        assert all(len(s) == len(wind.times) for s in wind.speed)
        assert all(v is not None and 0 <= v < 60 for s in wind.speed for v in s)


def test_linearised_saving_is_conservative():
    k = shaft_power_per_newton(HM1982_HULL, HM1982_PROPELLER, 14)
    for thrust in (100e3, 300e3):
        exact = exact_saving(HM1982_HULL, HM1982_PROPELLER, 14, thrust)
        assert thrust * k <= exact
        assert thrust * k == pytest.approx(exact, rel=0.15)


@pytest.mark.filterwarnings("ignore")
def test_route_saving_is_bounded():
    wind = load_wind(ROUTES["fos-port-said"])
    none = route_saving(HM1982_HULL, HM1982_PROPELLER, FlettnerRotor(count=0), wind, 16)
    assert none.net_fraction == 0
    two = route_saving(HM1982_HULL, HM1982_PROPELLER, FlettnerRotor(count=2), wind, 16)
    assert 0 < two.net_fraction < 0.5
    assert len(two.monthly_net_fraction) == 12


@pytest.mark.filterwarnings("ignore")
def test_drift_reduces_the_saving():
    wind = load_wind(ROUTES["fos-port-said"])
    rotor = FlettnerRotor(count=2)
    without = route_saving(HM1982_HULL, HM1982_PROPELLER, rotor, wind, 14, drift=False)
    with_drift = route_saving(HM1982_HULL, HM1982_PROPELLER, rotor, wind, 14)
    assert 0 < with_drift.net_fraction < without.net_fraction


@pytest.mark.filterwarnings("ignore")
def test_leg_savings_add_up_to_the_route_saving():
    wind = load_wind(ROUTES["rotterdam-new-york"])
    for reverse in (False, True):
        r = route_saving(HM1982_HULL, HM1982_PROPELLER, FlettnerRotor(count=2), wind, 14, reverse=reverse)
        assert len(r.leg_net_fraction) == len(r.legs) == len(wind.legs)
        weighted = sum(f * leg.length_nm for f, leg in zip(r.leg_net_fraction, r.legs))
        assert weighted / sum(leg.length_nm for leg in r.legs) == pytest.approx(r.net_fraction, rel=1e-9)
        assert all(0 < v < 30 for v in r.leg_mean_wind)
    # Legs run in the direction of travel
    assert r.legs[0].lon < -30
