"""Download one year of ERA5 10 m wind along each route from the Open-Meteo archive.

Run: python scripts/fetch_wind.py [year]
Writes src/gronflad/data/wind/<route>.json (6 hour sampling).
"""

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

from gronflad.route import ROUTES, legs

SPACING_NM = 200.0
URL = "https://archive-api.open-meteo.com/v1/archive"
OUT = Path(__file__).resolve().parents[1] / "src" / "gronflad" / "data" / "wind"


def fetch(lat: float, lon: float, year: int) -> dict:
    query = urllib.parse.urlencode(
        {
            "latitude": f"{lat:.3f}",
            "longitude": f"{lon:.3f}",
            "start_date": f"{year}-01-01",
            "end_date": f"{year}-12-31",
            "hourly": "wind_speed_10m,wind_direction_10m",
            "wind_speed_unit": "ms",
            "models": "era5",
            "timezone": "GMT",
        }
    )
    with urllib.request.urlopen(f"{URL}?{query}", timeout=60) as r:
        return json.load(r)["hourly"]


def main(year: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for route in ROUTES.values():
        points, times = [], None
        for leg in legs(route, SPACING_NM):
            hourly = fetch(leg.lat, leg.lon, year)
            times = hourly["time"][::6]
            points.append(
                {
                    "lat": round(leg.lat, 3),
                    "lon": round(leg.lon, 3),
                    "speed": hourly["wind_speed_10m"][::6],
                    "direction": hourly["wind_direction_10m"][::6],
                }
            )
            time.sleep(0.5)
        data = {
            "route": route.name,
            "year": year,
            "spacing_nm": SPACING_NM,
            "source": "ERA5 (Copernicus Climate Change Service) via Open-Meteo historical weather API",
            "times": times,
            "points": points,
        }
        (OUT / f"{route.slug}.json").write_text(json.dumps(data, separators=(",", ":")))
        print(f"{route.slug}: {len(points)} points, {len(times)} samples")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2024)
