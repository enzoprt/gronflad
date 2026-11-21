"""Energy, fuel and emissions of a voyage at constant speed.

The calm water shaft power from Holtrop and Mennen is raised by a sea margin
to account for wind, waves and fouling, then converted to fuel energy with a
constant engine efficiency. An efficiency of 0.50 corresponds to a two-stroke
engine with a specific fuel consumption of about 170 g/kWh on MGO.
"""

from dataclasses import dataclass

from .fuels import Fuel, fueleu_limit, fueleu_penalty
from .holtrop_mennen import resistance
from .hull import Hull
from .propulsion import Propeller, Propulsion, propulsion
from .water import KNOT, SEA_WATER_15C, Water

TEU_VOLUME = 6.058 * 2.438 * 2.591  # external volume of a 20 ft container, m3


@dataclass(frozen=True)
class Voyage:
    distance_nm: float
    speed_kn: float
    sea_margin: float = 0.15  # added power over calm water
    auxiliary_power: float = 0.0  # hotel and auxiliary load, W
    engine_efficiency: float = 0.50  # fuel energy to shaft (or electric) energy

    @property
    def duration_h(self) -> float:
        return self.distance_nm / self.speed_kn


@dataclass(frozen=True)
class VoyageEnergy:
    voyage: Voyage
    propulsion: Propulsion
    P_service: float  # shaft power with sea margin, W
    fuel_energy: float  # energy content of the fuel burnt, MJ

    @property
    def shaft_energy(self) -> float:
        """Mechanical energy delivered to the propeller shaft, MJ."""
        return self.P_service * self.voyage.duration_h * 3600 / 1e6


@dataclass(frozen=True)
class FuelUse:
    fuel: Fuel
    energy: float  # MJ
    mass: float  # t
    volume: float  # m3 of fuel
    storage_volume: float  # m3 of storage system, relative to MGO tanks
    intensity: float  # well-to-wake, gCO2eq/MJ, including the wind reward
    ghg: float  # t CO2eq, well-to-wake

    def fueleu_penalty(self, year: int) -> float:
        """FuelEU Maritime penalty in EUR if all this energy is in scope."""
        return fueleu_penalty(self.intensity, self.energy, year)

    def complies(self, year: int) -> bool:
        return self.intensity <= fueleu_limit(year)


def voyage_energy(
    hull: Hull, prop: Propeller, voyage: Voyage, eta_O: float | None = None, water: Water = SEA_WATER_15C
) -> VoyageEnergy:
    """Fuel energy needed to sail `voyage` with `hull` and `prop`."""
    res = resistance(hull, voyage.speed_kn * KNOT, water)
    p = propulsion(hull, prop, res, eta_O=eta_O, water=water)
    P_service = p.P_S * (1 + voyage.sea_margin)
    seconds = voyage.duration_h * 3600
    fuel_energy = (P_service + voyage.auxiliary_power) * seconds / voyage.engine_efficiency / 1e6
    return VoyageEnergy(voyage=voyage, propulsion=p, P_service=P_service, fuel_energy=fuel_energy)


def fuel_use(energy: VoyageEnergy, fuel: Fuel, f_wind: float = 1.0) -> FuelUse:
    """Fuel quantities and emissions to supply `energy` with `fuel`."""
    mass_kg = energy.fuel_energy / fuel.lcv
    volume = mass_kg / fuel.density
    intensity = f_wind * fuel.intensity
    return FuelUse(
        fuel=fuel,
        energy=energy.fuel_energy,
        mass=mass_kg / 1000,
        volume=volume,
        storage_volume=volume * fuel.storage_factor,
        intensity=intensity,
        ghg=intensity * energy.fuel_energy / 1e6,
    )


def compare_fuels(energy: VoyageEnergy, fuels: list[Fuel], f_wind: float = 1.0) -> list[FuelUse]:
    """Fuel use of each candidate fuel for the same voyage energy."""
    return [fuel_use(energy, f, f_wind) for f in fuels]


def teu_slots(volume: float) -> float:
    """Number of 20 ft container slots occupied by a storage volume, m3."""
    return volume / TEU_VOLUME
