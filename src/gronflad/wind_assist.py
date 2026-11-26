"""Power saving of Flettner rotors along a route, over a year of real wind.

For each 6 hour ERA5 sample and each leg of the route, the rotors run at the
rotational speed that maximises the net saving. The hull resistance caused by
drifting against the rotor side force is deducted from the thrust. The saving in shaft power is
linearised around the calm water operating point: a rotor thrust T replaces
T * V / (eta_D * eta_S) of shaft power. `exact_saving` checks this against a
full recomputation of the propulsion chain.
"""

from bisect import bisect_right
from dataclasses import dataclass, replace

from .drift import induced_resistance
from .holtrop_mennen import resistance
from .hull import Hull
from .propulsion import Propeller, propulsion
from .rotor import FlettnerRotor, best_rotor_state
from .route import Leg, WindSeries, true_wind_angle
from .voyage import VoyageEnergy
from .water import KNOT

TWS_GRID = [float(v) for v in range(0, 31)]  # m/s
TWA_GRID = [float(a) for a in range(0, 181, 5)]  # degrees


@dataclass(frozen=True)
class RotorTable:
    """Optimal rotor thrust and power on a grid of true wind speed and angle."""

    thrust: list[list[float]]  # [tws][twa], rotor thrust minus drift resistance, N
    power: list[list[float]]  # [tws][twa], W

    def lookup(self, tws: float, twa: float) -> tuple[float, float]:
        tws = min(max(tws, TWS_GRID[0]), TWS_GRID[-1])
        i = min(bisect_right(TWS_GRID, tws) - 1, len(TWS_GRID) - 2)
        j = min(bisect_right(TWA_GRID, twa) - 1, len(TWA_GRID) - 2)
        fx = (tws - TWS_GRID[i]) / (TWS_GRID[i + 1] - TWS_GRID[i])
        fy = (twa - TWA_GRID[j]) / (TWA_GRID[j + 1] - TWA_GRID[j])

        def interp(grid: list[list[float]]) -> float:
            return (
                grid[i][j] * (1 - fx) * (1 - fy)
                + grid[i + 1][j] * fx * (1 - fy)
                + grid[i][j + 1] * (1 - fx) * fy
                + grid[i + 1][j + 1] * fx * fy
            )

        return interp(self.thrust), interp(self.power)


def rotor_table(
    rotor: FlettnerRotor, ship_speed: float, shaft_power_per_newton: float, hull: Hull | None = None
) -> RotorTable:
    """Optimal rotor states on the wind grid. With `hull`, the drift resistance is accounted for."""
    drag = (lambda side: induced_resistance(hull, ship_speed, side)) if hull is not None else None
    states = [
        [best_rotor_state(rotor, tws, twa, ship_speed, shaft_power_per_newton, induced_drag=drag) for twa in TWA_GRID]
        for tws in TWS_GRID
    ]
    return RotorTable(
        thrust=[[s.net_thrust for s in row] for row in states],
        power=[[s.power for s in row] for row in states],
    )


@dataclass(frozen=True)
class WindAssistResult:
    P_S: float  # calm water shaft power without rotors, W
    mean_thrust: float  # N, all rotors, net of drift resistance
    shaft_saving: float  # mean gross shaft power saved, W
    rotor_power: float  # mean electric power to spin the rotors, W
    electric_efficiency: float
    monthly_net_fraction: list[float]  # 12 values
    legs: list[Leg]  # in the direction of travel
    leg_net_fraction: list[float]  # mean net saving on each leg, fraction of P_S
    leg_mean_wind: list[float]  # mean true wind speed at 10 m on each leg, m/s

    @property
    def net_saving(self) -> float:
        """Mean shaft-equivalent power saved after paying for the rotor motors, W."""
        return self.shaft_saving - self.rotor_power / self.electric_efficiency

    @property
    def net_fraction(self) -> float:
        return self.net_saving / self.P_S

    @property
    def wind_power_ratio(self) -> float:
        """P_wind / P_prop used for the FuelEU reward factor (approximation)."""
        return self.shaft_saving / self.P_S


def shaft_power_per_newton(hull: Hull, prop: Propeller, speed_kn: float, eta_O: float | None = None) -> float:
    res = resistance(hull, speed_kn * KNOT)
    p = propulsion(hull, prop, res, eta_O=eta_O)
    return res.V / (p.eta_D * p.eta_S)


def route_saving(
    hull: Hull,
    prop: Propeller,
    rotor: FlettnerRotor,
    wind: WindSeries,
    speed_kn: float,
    reverse: bool = False,
    eta_O: float | None = None,
    electric_efficiency: float = 0.95,
    drift: bool = True,
) -> WindAssistResult:
    """Average rotor saving over every wind sample, weighted by leg length.

    With `drift`, the hull resistance caused by balancing the rotor side force is deducted.
    """
    res = resistance(hull, speed_kn * KNOT)
    p = propulsion(hull, prop, res, eta_O=eta_O)
    k = res.V / (p.eta_D * p.eta_S)
    table = rotor_table(rotor, res.V, k, hull if drift else None)

    legs = list(reversed(wind.legs)) if reverse else wind.legs
    speeds = list(reversed(wind.speed)) if reverse else wind.speed
    directions = list(reversed(wind.direction)) if reverse else wind.direction
    weights = [leg.length_nm for leg in legs]
    total = sum(weights)

    thrust_sum = saving_sum = power_sum = 0.0
    leg_net = [0.0] * len(legs)
    month_net = [0.0] * 12
    month_n = [0] * 12
    for t, stamp in enumerate(wind.times):
        month = int(stamp[5:7]) - 1
        step_net = 0.0
        for i, (leg, w, spd, drn) in enumerate(zip(legs, weights, speeds, directions)):
            heading = (leg.heading + 180) % 360 if reverse else leg.heading
            thrust, power = table.lookup(spd[t], true_wind_angle(drn[t], heading))
            # The rotors cannot save more than the whole shaft power
            saving = min(thrust * k, p.P_S)
            thrust_sum += thrust * w
            saving_sum += saving * w
            power_sum += power * w
            net = saving - power / electric_efficiency
            leg_net[i] += net
            step_net += net * w
        month_net[month] += step_net / total / p.P_S
        month_n[month] += 1

    n = len(wind.times) * total
    return WindAssistResult(
        P_S=p.P_S,
        mean_thrust=thrust_sum / n,
        shaft_saving=saving_sum / n,
        rotor_power=power_sum / n,
        electric_efficiency=electric_efficiency,
        monthly_net_fraction=[month_net[m] / month_n[m] if month_n[m] else 0.0 for m in range(12)],
        legs=legs,
        leg_net_fraction=[v / len(wind.times) / p.P_S for v in leg_net],
        leg_mean_wind=[sum(spd) / len(spd) for spd in speeds],
    )


def exact_saving(hull: Hull, prop: Propeller, speed_kn: float, thrust: float, eta_O: float | None = None) -> float:
    """Shaft power saved by an external thrust, recomputing the propeller operating point."""
    res = resistance(hull, speed_kn * KNOT)
    base = propulsion(hull, prop, res, eta_O=eta_O)
    # Same propeller (fixed pitch), lighter load: scale the resistance components
    scale = (res.R_T - thrust) / res.R_T
    lighter = replace(
        res, R_F=res.R_F * scale, R_APP=res.R_APP * scale, R_W=res.R_W * scale,
        R_B=res.R_B * scale, R_TR=res.R_TR * scale, R_A=res.R_A * scale,
    )
    fixed = replace(prop, P_D=base.P_D) if base.P_D is not None else prop
    return base.P_S - propulsion(hull, fixed, lighter, eta_O=eta_O).P_S


def assisted_energy(energy: VoyageEnergy, result: WindAssistResult) -> VoyageEnergy:
    """Voyage energy with the rotors, applying the mean net saving to the propulsion share."""
    propulsion_share = energy.P_service / (energy.P_service + energy.voyage.auxiliary_power)
    saved = result.net_fraction * propulsion_share * energy.fuel_energy
    return replace(energy, fuel_energy=energy.fuel_energy - saved)
