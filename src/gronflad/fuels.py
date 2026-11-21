"""Marine fuels: energy content, storage volume and well-to-wake GHG intensity.

References
----------
Regulation (EU) 2023/1805 (FuelEU Maritime), Annex I (method) and Annex II
    (default emission factors). GWP100 values from Directive (EU) 2018/2001,
    Annex V Part C: CO2 = 1, CH4 = 25, N2O = 298.
DNV GL (2020). Ammonia as a marine fuel, Table 1 (densities of MGO, ammonia
    under pressure and liquid hydrogen).
DNV GL (2020), as quoted by Umweltbundesamt (2022): volume of the fuel
    storage system relative to MGO (LNG 2.3, ammonia 4.1, liquid hydrogen 7.6).
    Storage factors below are derived from these ratios and are indicative.

Where Annex II gives "TBM" (to be measured) for CH4 or N2O in a whole fuel
class, the regulation prescribes the least favourable fossil pathway default,
which is CH4 = 0.00005 and N2O = 0.00018 g/g fuel.

RFNBO (e-fuels) have no default well-to-tank factor. Gronflad sets it so the
well-to-wake intensity equals the 70 % saving threshold of Directive
(EU) 2018/2001 against the 94 gCO2eq/MJ fossil comparator, i.e. the least
favourable e-fuel that still qualifies as RFNBO.
"""

from dataclasses import dataclass, replace

GWP_CH4 = 25
GWP_N2O = 298
FOSSIL_COMPARATOR = 94.0  # gCO2eq/MJ
RFNBO_INTENSITY = FOSSIL_COMPARATOR * (1 - 0.70)  # 28.2 gCO2eq/MJ

# FuelEU limit: reference 91.16 gCO2eq/MJ and reductions per period (Article 4)
FUELEU_REFERENCE = 91.16
FUELEU_REDUCTION = {2025: 0.02, 2030: 0.06, 2035: 0.145, 2040: 0.31, 2045: 0.62, 2050: 0.80}
VLSFO_MJ_PER_T = 41_000
PENALTY_EUR_PER_T_VLSFO = 2_400

TBM_CH4 = 0.00005
TBM_N2O = 0.00018


@dataclass(frozen=True)
class Fuel:
    """A fuel burnt in a given consumer type. Factors follow FuelEU Annex II."""

    name: str
    lcv: float  # lower calorific value, MJ/kg
    wtt: float  # well-to-tank emission factor, gCO2eq/MJ
    cf_co2: float  # g/g fuel
    cf_ch4: float  # g/g fuel
    cf_n2o: float  # g/g fuel
    density: float  # kg/m3, as stored on board
    storage_factor: float = 1.0  # gross storage system volume per m3 of fuel, relative to MGO tanks
    c_slip: float = 0.0  # unburnt fuel (methane slip), % of fuel mass
    consumer: str = "ICE"

    @property
    def ttw_per_g(self) -> float:
        """Tank-to-wake emissions, gCO2eq per g of fuel used, including slip."""
        combusted = self.cf_co2 + self.cf_ch4 * GWP_CH4 + self.cf_n2o * GWP_N2O
        slipped = GWP_CH4  # slipped fuel counts as methane only (Csf_CH4 = 1)
        return (1 - self.c_slip / 100) * combusted + self.c_slip / 100 * slipped

    @property
    def ttw(self) -> float:
        """Tank-to-wake intensity, gCO2eq/MJ."""
        return self.ttw_per_g / (self.lcv / 1000)

    @property
    def intensity(self) -> float:
        """Well-to-wake GHG intensity, gCO2eq/MJ."""
        return self.wtt + self.ttw

    @property
    def volumetric_energy(self) -> float:
        """Energy per m3 of storage system, GJ/m3."""
        return self.lcv * self.density / 1000 / self.storage_factor


def _efuel(fossil: Fuel, name: str) -> Fuel:
    """RFNBO version of a fossil fuel at the minimum qualifying GHG saving."""
    return replace(fossil, name=name, wtt=RFNBO_INTENSITY - fossil.ttw)


HFO = Fuel("HFO", lcv=40.5, wtt=13.5, cf_co2=3.114, cf_ch4=0.00005, cf_n2o=0.00018, density=980)
MGO = Fuel("MGO", lcv=42.7, wtt=14.4, cf_co2=3.206, cf_ch4=0.00005, cf_n2o=0.00018, density=835)
_LNG = dict(lcv=49.1, wtt=18.5, cf_co2=2.750, cf_ch4=0.0, cf_n2o=0.00011, density=450, storage_factor=1.42)
LNG_OTTO_MS = Fuel("LNG, Otto medium speed", c_slip=3.1, **_LNG)
LNG_OTTO_SS = Fuel("LNG, Otto slow speed", c_slip=1.7, **_LNG)
LNG_DIESEL = Fuel("LNG, Diesel slow speed", c_slip=0.2, **_LNG)
METHANOL = Fuel("Methanol (natural gas)", lcv=19.9, wtt=31.3, cf_co2=1.375, cf_ch4=TBM_CH4, cf_n2o=TBM_N2O, density=792)
AMMONIA = Fuel(
    "Ammonia (natural gas)", lcv=18.6, wtt=121, cf_co2=0.0, cf_ch4=TBM_CH4, cf_n2o=TBM_N2O,
    density=610, storage_factor=1.31,
)
HYDROGEN = Fuel(
    "Liquid hydrogen (natural gas)", lcv=120, wtt=132, cf_co2=0.0, cf_ch4=0.0, cf_n2o=0.0,
    density=71, storage_factor=1.82, consumer="Fuel cell",
)
E_METHANOL = _efuel(METHANOL, "e-Methanol")
E_AMMONIA = _efuel(AMMONIA, "e-Ammonia")
E_HYDROGEN = _efuel(HYDROGEN, "e-Hydrogen (liquid)")
E_LNG = _efuel(LNG_DIESEL, "e-LNG, Diesel slow speed")

FUELS = {
    f.name: f
    for f in (
        HFO, MGO, LNG_OTTO_MS, LNG_OTTO_SS, LNG_DIESEL, METHANOL, AMMONIA, HYDROGEN,
        E_METHANOL, E_AMMONIA, E_HYDROGEN, E_LNG,
    )
}


def fueleu_limit(year: int) -> float:
    """FuelEU Maritime GHG intensity limit for a reporting year, gCO2eq/MJ."""
    if year < 2025:
        return FUELEU_REFERENCE
    reduction = max(r for y, r in FUELEU_REDUCTION.items() if y <= year)
    return FUELEU_REFERENCE * (1 - reduction)


def wind_reward(p_wind_over_p_prop: float) -> float:
    """FuelEU reward factor f_wind for wind-assisted propulsion (Annex I)."""
    if p_wind_over_p_prop >= 0.15:
        return 0.95
    if p_wind_over_p_prop >= 0.10:
        return 0.97
    if p_wind_over_p_prop >= 0.05:
        return 0.99
    return 1.0


def fueleu_penalty(intensity: float, energy_MJ: float, year: int) -> float:
    """FuelEU penalty in EUR for a compliance deficit (0 if compliant).

    The compliance balance is (limit - intensity) * energy, in gCO2eq.
    """
    balance = (fueleu_limit(year) - intensity) * energy_MJ
    if balance >= 0:
        return 0.0
    return abs(balance) / (intensity * VLSFO_MJ_PER_T) * PENALTY_EUR_PER_T_VLSFO
