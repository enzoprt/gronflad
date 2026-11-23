"""Shipping routes as great circle legs, with wind statistics along them.

Wind data are ERA5 reanalysis values (Hersbach et al., 2020, Copernicus Climate
Change Service) at 10 m above sea level, retrieved through the Open-Meteo
historical weather API by `scripts/fetch_wind.py` and stored in
`src/gronflad/data/wind`. One full year at 6 hour intervals is kept per route.
"""

import json
from dataclasses import dataclass
from importlib import resources
from math import asin, atan2, cos, degrees, radians, sin, sqrt

EARTH_RADIUS_NM = 3440.065


@dataclass(frozen=True)
class Route:
    name: str
    waypoints: tuple[tuple[float, float], ...]  # (latitude, longitude) in degrees
    slug: str


@dataclass(frozen=True)
class Leg:
    lat: float  # midpoint
    lon: float
    heading: float  # true course, degrees from north
    length_nm: float


def distance_nm(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Great circle distance (haversine)."""
    la1, lo1, la2, lo2 = map(radians, (*a, *b))
    h = sin((la2 - la1) / 2) ** 2 + cos(la1) * cos(la2) * sin((lo2 - lo1) / 2) ** 2
    return 2 * EARTH_RADIUS_NM * asin(sqrt(h))


def initial_course(a: tuple[float, float], b: tuple[float, float]) -> float:
    la1, lo1, la2, lo2 = map(radians, (*a, *b))
    y = sin(lo2 - lo1) * cos(la2)
    x = cos(la1) * sin(la2) - sin(la1) * cos(la2) * cos(lo2 - lo1)
    return degrees(atan2(y, x)) % 360


def intermediate_point(a: tuple[float, float], b: tuple[float, float], f: float) -> tuple[float, float]:
    """Point at fraction f along the great circle from a to b."""
    la1, lo1, la2, lo2 = map(radians, (*a, *b))
    d = distance_nm(a, b) / EARTH_RADIUS_NM
    if d == 0:
        return a
    A, B = sin((1 - f) * d) / sin(d), sin(f * d) / sin(d)
    x = A * cos(la1) * cos(lo1) + B * cos(la2) * cos(lo2)
    y = A * cos(la1) * sin(lo1) + B * cos(la2) * sin(lo2)
    z = A * sin(la1) + B * sin(la2)
    return degrees(atan2(z, sqrt(x * x + y * y))), degrees(atan2(y, x))


def legs(route: Route, spacing_nm: float = 200.0) -> list[Leg]:
    """Split the route into legs of at most `spacing_nm`."""
    out = []
    for a, b in zip(route.waypoints, route.waypoints[1:]):
        n = max(1, round(distance_nm(a, b) / spacing_nm))
        for i in range(n):
            p, q = intermediate_point(a, b, i / n), intermediate_point(a, b, (i + 1) / n)
            mid = intermediate_point(a, b, (i + 0.5) / n)
            out.append(Leg(lat=mid[0], lon=mid[1], heading=initial_course(p, q), length_nm=distance_nm(p, q)))
    return out


def total_distance(route: Route) -> float:
    return sum(distance_nm(a, b) for a, b in zip(route.waypoints, route.waypoints[1:]))


def track(route: Route, spacing_nm: float = 20.0) -> list[tuple[float, float]]:
    """Densified list of points along the route, for maps."""
    pts = []
    for a, b in zip(route.waypoints, route.waypoints[1:]):
        n = max(1, round(distance_nm(a, b) / spacing_nm))
        pts += [intermediate_point(a, b, i / n) for i in range(n)]
    return pts + [route.waypoints[-1]]


ROUTES = {
    r.slug: r
    for r in (
        Route(
            name="Rotterdam to New York (North Atlantic)",
            slug="rotterdam-new-york",
            waypoints=(
                (51.98, 3.90),  # Maas approach
                (51.00, 1.55),  # Dover Strait
                (50.15, -1.60),  # English Channel
                (48.75, -5.60),  # off Ushant
                (40.45, -69.50),  # south of Nantucket
                (40.45, -73.80),  # New York approach
            ),
        ),
        Route(
            name="Fos-sur-Mer to Port Said (Mediterranean)",
            slug="fos-port-said",
            waypoints=(
                (43.25, 4.90),  # Fos approach
                (38.70, 8.60),  # south of Sardinia
                (37.40, 11.40),  # Strait of Sicily
                (34.10, 25.00),  # south of Crete
                (31.45, 32.35),  # Port Said approach
            ),
        ),
    )
}


@dataclass(frozen=True)
class WindSeries:
    """Wind at the midpoint of each leg, aligned in time."""

    legs: list[Leg]
    times: list[str]
    speed: list[list[float]]  # [leg][time], m/s at 10 m
    direction: list[list[float]]  # [leg][time], degrees, direction the wind blows from
    year: int


def load_wind(route: Route) -> WindSeries:
    raw = json.loads(resources.files("gronflad").joinpath(f"data/wind/{route.slug}.json").read_text())
    route_legs = legs(route, raw["spacing_nm"])
    if len(route_legs) != len(raw["points"]):
        raise ValueError(f"Wind file for {route.slug} does not match the route legs, run scripts/fetch_wind.py")
    return WindSeries(
        legs=route_legs,
        times=raw["times"],
        speed=[p["speed"] for p in raw["points"]],
        direction=[p["direction"] for p in raw["points"]],
        year=raw["year"],
    )


def true_wind_angle(wind_from: float, heading: float) -> float:
    """Angle between the bow and the direction the wind comes from, 0 to 180 degrees."""
    a = (wind_from - heading) % 360
    return 360 - a if a > 180 else a
