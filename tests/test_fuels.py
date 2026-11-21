"""Fuel factors and GHG intensities from FuelEU Maritime, Regulation (EU) 2023/1805."""

import pytest

from gronflad import fuels
from gronflad.fuels import (
    AMMONIA, E_AMMONIA, E_METHANOL, HFO, HYDROGEN, LNG_DIESEL, LNG_OTTO_MS, MGO, METHANOL,
    fueleu_limit, fueleu_penalty, wind_reward,
)


def ttw(cf_co2, cf_ch4, cf_n2o, lcv_MJ_per_g, slip=0.0):
    """Annex I, Equation (1) tank-to-wake term written out by hand."""
    combusted = cf_co2 + 25 * cf_ch4 + 298 * cf_n2o
    return ((1 - slip / 100) * combusted + slip / 100 * 25) / lcv_MJ_per_g


@pytest.mark.parametrize(
    "fuel, expected",
    [
        (HFO, 13.5 + ttw(3.114, 0.00005, 0.00018, 0.0405)),
        (MGO, 14.4 + ttw(3.206, 0.00005, 0.00018, 0.0427)),
        (LNG_OTTO_MS, 18.5 + ttw(2.750, 0, 0.00011, 0.0491, slip=3.1)),
        (LNG_DIESEL, 18.5 + ttw(2.750, 0, 0.00011, 0.0491, slip=0.2)),
        (METHANOL, 31.3 + ttw(1.375, 0.00005, 0.00018, 0.0199)),
        (AMMONIA, 121 + ttw(0, 0.00005, 0.00018, 0.0186)),
        (HYDROGEN, 132.0),
    ],
)
def test_intensity_matches_annex_factors(fuel, expected):
    assert fuel.intensity == pytest.approx(expected, rel=1e-9)


def test_intensity_values():
    assert HFO.intensity == pytest.approx(91.74, abs=0.01)
    assert MGO.intensity == pytest.approx(90.77, abs=0.01)
    assert LNG_OTTO_MS.intensity == pytest.approx(89.2, abs=0.1)
    assert LNG_DIESEL.intensity == pytest.approx(76.1, abs=0.1)


def test_methane_slip_penalises_otto_engines():
    assert LNG_OTTO_MS.intensity > LNG_DIESEL.intensity + 10


def test_grey_ammonia_and_hydrogen_are_worse_than_hfo():
    assert AMMONIA.intensity > HFO.intensity
    assert HYDROGEN.intensity > HFO.intensity


def test_efuels_meet_rfnbo_threshold():
    for f in (E_METHANOL, E_AMMONIA):
        assert f.intensity == pytest.approx(28.2)


def test_volumetric_energy_fuel_only():
    # DNV GL (2020), Ammonia as a marine fuel, Table 1
    assert MGO.lcv * MGO.density / 1000 == pytest.approx(35.7, abs=0.05)
    assert AMMONIA.lcv * AMMONIA.density / 1000 == pytest.approx(11.4, abs=0.06)  # printed rounded
    assert HYDROGEN.lcv * HYDROGEN.density / 1000 == pytest.approx(8.52, abs=0.01)


def test_fueleu_limits():
    assert fueleu_limit(2024) == pytest.approx(91.16)
    assert fueleu_limit(2025) == pytest.approx(89.3368)
    assert fueleu_limit(2030) == pytest.approx(85.6904)
    assert fueleu_limit(2050) == pytest.approx(18.232)


def test_fueleu_penalty():
    # A deficit of exactly 1 t VLSFO equivalent (intensity x 41 000 MJ) costs 2400 EUR
    intensity = 100.0
    energy = 41_000 * intensity / (intensity - fueleu_limit(2025))
    assert fueleu_penalty(intensity, energy, 2025) == pytest.approx(2400)
    assert fueleu_penalty(LNG_DIESEL.intensity, 1e6, 2025) == 0.0


def test_wind_reward():
    assert wind_reward(0.02) == 1.0
    assert wind_reward(0.05) == 0.99
    assert wind_reward(0.12) == 0.97
    assert wind_reward(0.30) == 0.95


def test_catalogue_names_unique():
    assert len(fuels.FUELS) == 12
