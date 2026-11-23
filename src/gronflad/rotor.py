"""Flettner rotor sails: forces, power consumption and propulsion power saving.

Reference
---------
Tillig, F. and Ringsberg, J.W. (2020). Design, operation and analysis of
    wind-assisted cargo ships. Ocean Engineering, 211, 107603.
    Equations (2) to (9) and (14). Open access (CC BY).

The lift, drag and power coefficients are the ShipCLEAN fits, based on the CFD
of Li et al. (2012) and corrected against full-scale measurements on a 4 x 24 m
rotor. They hold for rotors with an aspect ratio of about 6 and an end disc of
twice the rotor diameter. Agreement with measurements is best for spin ratios
of 1.5 to 2.5 and degrades above 4, so Gronflad caps the spin ratio at 4.

Operating limits default to the manufacturer data of a 30 x 5 m Norsepower
Rotor Sail (brochure, 2025): 0 to 225 rpm and 270 kN maximum continuous thrust.

Simplifications, stated so they can be checked:
- The wind profile over the sea follows the Hellmann law with alpha = 0.27.
- Interaction between rotors, and between rotors and superstructure, is ignored.
- Drift resistance from the side force is handled in `drift.py`, rudder resistance is ignored.
"""

from collections.abc import Callable
from dataclasses import dataclass, replace
from math import atan2, cos, degrees, hypot, pi, radians, sin

RHO_AIR = 1.225  # kg/m3
HELLMANN = 0.27
SPIN_RATIO_MAX = 4.0
N_STRIPS = 10


def c_lift(sr: float) -> float:
    return -0.0046 * sr**5 + 0.1145 * sr**4 - 0.9817 * sr**3 + 3.1309 * sr**2 - 0.1039 * sr


def c_drag(sr: float) -> float:
    return -0.0017 * sr**5 + 0.0464 * sr**4 - 0.4424 * sr**3 + 1.7243 * sr**2 - 1.641 * sr + 0.6375


def c_power(sr: float) -> float:
    return 0.0001 * sr**5 - 0.0004 * sr**4 + 0.0143 * sr**3 - 0.0168 * sr**2 + 0.0234 * sr


def wind_at_height(tws10: float, h: float) -> float:
    """True wind speed at height h (m) from the 10 m value, Hellmann law."""
    return tws10 * (h / 10) ** HELLMANN


def apparent_wind(tws: float, twa_deg: float, ship_speed: float) -> tuple[float, float]:
    """Apparent wind speed (m/s) and angle (deg, 0 = from ahead, 0 to 180).

    `twa_deg` is the true wind angle from the bow, 0 = head wind, 180 = following wind.
    """
    twa = radians(twa_deg)
    ahead = tws * cos(twa) + ship_speed
    abeam = tws * sin(twa)
    return hypot(ahead, abeam), abs(degrees(atan2(abeam, ahead)))


@dataclass(frozen=True)
class FlettnerRotor:
    D: float = 5.0  # rotor diameter, m
    H: float = 30.0  # rotor height, m
    base_height: float = 20.0  # rotor foot above the waterline, m
    count: int = 1
    max_rpm: float = 225.0
    max_thrust: float = 270e3  # maximum continuous thrust per rotor, N

    @property
    def area(self) -> float:
        """Projected area of one rotor, m2."""
        return self.D * self.H


@dataclass(frozen=True)
class RotorState:
    """Rotor set operating at one wind condition."""

    omega: float  # rotational speed, rad/s
    spin_ratio: float  # at mid height
    thrust: float  # N, all rotors, positive forward
    side_force: float  # N, all rotors
    power: float  # electric power to spin all rotors, W
    induced_drag: float = 0.0  # hull resistance added by drifting against the side force, N

    @property
    def net_thrust(self) -> float:
        return self.thrust - self.induced_drag


def rotor_state(rotor: FlettnerRotor, tws10: float, twa_deg: float, ship_speed: float, omega: float) -> RotorState:
    """Forces and power of `rotor` at rotational speed `omega`, integrated over its height."""
    thrust = side = power = 0.0
    strip_area = rotor.area / N_STRIPS
    for i in range(N_STRIPS):
        h = rotor.base_height + (i + 0.5) * rotor.H / N_STRIPS
        aws, awa = apparent_wind(wind_at_height(tws10, h), twa_deg, ship_speed)
        if aws == 0:
            continue
        sr = omega * rotor.D / 2 / aws
        q = 0.5 * RHO_AIR * aws**2 * strip_area
        lift, drag = q * c_lift(sr), q * c_drag(sr)
        a = radians(awa)
        # Lift acts perpendicular to the apparent wind, the spin direction is chosen to push forward
        thrust += lift * sin(a) - drag * cos(a)
        side += lift * cos(a) + drag * sin(a)
        power += q * aws * c_power(sr)
    mid = rotor.base_height + rotor.H / 2
    aws_mid, _ = apparent_wind(wind_at_height(tws10, mid), twa_deg, ship_speed)
    return RotorState(
        omega=omega,
        spin_ratio=omega * rotor.D / 2 / aws_mid if aws_mid else 0.0,
        thrust=thrust * rotor.count,
        side_force=side * rotor.count,
        power=power * rotor.count,
    )


def best_rotor_state(
    rotor: FlettnerRotor,
    tws10: float,
    twa_deg: float,
    ship_speed: float,
    shaft_power_per_newton: float,
    electric_efficiency: float = 0.95,
    steps: int = 41,
    induced_drag: Callable[[float], float] | None = None,
) -> RotorState:
    """Rotational speed that maximises the net saving in fuel power.

    `shaft_power_per_newton` converts rotor thrust into saved shaft power (V / eta_D).
    The rotor motor power comes from the same engines through a generator and drive
    of efficiency `electric_efficiency`. `induced_drag` maps the side force (N) to the
    hull resistance it causes, see `drift.induced_resistance`.
    """
    mid = rotor.base_height + rotor.H / 2
    aws_mid, _ = apparent_wind(wind_at_height(tws10, mid), twa_deg, ship_speed)
    if aws_mid == 0:
        return RotorState(0.0, 0.0, 0.0, 0.0, 0.0)
    omega_max = rotor.max_rpm * 2 * pi / 60
    best, best_gain = None, -float("inf")
    for k in range(steps):
        sr = SPIN_RATIO_MAX * k / (steps - 1)
        omega = sr * aws_mid / (rotor.D / 2)
        if omega > omega_max:
            break
        state = rotor_state(rotor, tws10, twa_deg, ship_speed, omega=omega)
        if state.thrust > rotor.max_thrust * rotor.count:
            break
        if induced_drag is not None:
            state = replace(state, induced_drag=induced_drag(state.side_force))
        gain = state.net_thrust * shaft_power_per_newton - state.power / electric_efficiency
        if gain > best_gain:
            best, best_gain = state, gain
    if best is None:  # even the slowest spin breaks a limit, so the rotor stays idle
        best = rotor_state(rotor, tws10, twa_deg, ship_speed, omega=0.0)
        if induced_drag is not None:
            best = replace(best, induced_drag=induced_drag(best.side_force))
    return best


def rpm(state: RotorState) -> float:
    return state.omega * 60 / (2 * pi)
