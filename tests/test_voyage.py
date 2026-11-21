"""Voyage energy and fuel use, checked with hand calculations."""

import pytest

from gronflad.fuels import AMMONIA, HFO, LNG_DIESEL, MGO
from gronflad.ships import HM1982_HULL, HM1982_PROPELLER
from gronflad.voyage import Voyage, compare_fuels, fuel_use, voyage_energy


@pytest.fixture(scope="module")
def energy():
    return voyage_energy(HM1982_HULL, HM1982_PROPELLER, Voyage(distance_nm=5000, speed_kn=25))


def test_energy_balance(energy):
    hours = 200
    expected = energy.propulsion.P_S * 1.15 * hours * 3600 / 0.50 / 1e6
    assert energy.fuel_energy == pytest.approx(expected)
    assert energy.shaft_energy == pytest.approx(expected * 0.5)


def test_fuel_oil_consumption_is_realistic(energy):
    # About 37.5 MW service power for 200 h at 170 g/kWh gives roughly 1300 t of MGO
    use = fuel_use(energy, MGO)
    sfoc = use.mass * 1e6 / (energy.P_service / 1e3 * 200)
    assert sfoc == pytest.approx(3600 / (0.5 * 42.7), rel=1e-6)
    assert 1200 < use.mass < 1400


def test_same_energy_for_every_fuel(energy):
    uses = compare_fuels(energy, [HFO, MGO, LNG_DIESEL, AMMONIA])
    for u in uses:
        assert u.mass * 1000 * u.fuel.lcv == pytest.approx(energy.fuel_energy)


def test_ammonia_needs_about_four_times_the_storage_of_mgo(energy):
    mgo, nh3 = compare_fuels(energy, [MGO, AMMONIA])
    assert nh3.storage_volume / mgo.storage_volume == pytest.approx(4.1, rel=0.02)


def test_wind_reward_scales_emissions(energy):
    base = fuel_use(energy, HFO)
    assisted = fuel_use(energy, HFO, f_wind=0.95)
    assert assisted.ghg == pytest.approx(0.95 * base.ghg)
