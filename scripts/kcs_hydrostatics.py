"""Compute the Holtrop-Mennen inputs of the KCS from its official hull geometry.

Downloads the SIMMAN 2008 IGES file (FORCE Technology) into a temporary folder,
computes the hydrostatics at the design draught and compares them with the
published particulars. The results are stored in gronflad.ships.KCS_HULL.

Run: python scripts/kcs_hydrostatics.py
"""

import io
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from gronflad.hydrostatics import hydrostatics
from gronflad.iges import read_surfaces

URL = "http://www.simman2008.dk/PDF/KCS_hull_SVA.zip"
L_PP, B, T = 230.0, 32.2, 10.8
PUBLISHED = {"volume": 52030.0, "LCB %Lpp": -1.48, "C_M": 0.985, "S w/o rudder": 9530.0, "L_wl": 232.5}


def main() -> None:
    with urllib.request.urlopen(URL, timeout=60) as r:
        archive = zipfile.ZipFile(io.BytesIO(r.read()))
    with tempfile.TemporaryDirectory() as tmp:
        archive.extractall(tmp)
        surfaces = read_surfaces(next(Path(tmp).glob("*.igs")))
    h = hydrostatics(surfaces, T, x_ap=0.0, x_fp=L_PP, n=120)
    computed = {
        "volume": h.volume,
        "LCB %Lpp": (h.lcb_x - L_PP / 2) / L_PP * 100,
        "C_M": h.midship_area / (B * T),
        "S w/o rudder": h.wetted_surface,
        "L_wl": h.L_wl,
    }
    print(f"{'quantity':<14}{'published':>12}{'computed':>12}{'diff %':>9}")
    for key, ref in PUBLISHED.items():
        print(f"{key:<14}{ref:>12.3f}{computed[key]:>12.3f}{(computed[key] / ref - 1) * 100:>9.2f}")
    print()
    print(f"C_WP (on L_wl)   {h.waterplane_area / (h.L_wl * B):.4f}")
    print(f"A_BT             {h.bulb_area:.2f} m2")
    print(f"h_B              {h.bulb_centroid:.2f} m")
    print(f"A_T              {h.transom_area:.2f} m2")
    print(f"i_E              {h.entrance_angle:.2f} deg")
    print(f"LCB % of L_wl    {(h.lcb_x - (L_PP - h.L_wl / 2)) / h.L_wl * 100:.3f}")


if __name__ == "__main__":
    main()
