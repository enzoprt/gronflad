"""Hydrostatics of a half hull given as surfaces, for Holtrop-Mennen inputs.

The hull is tessellated into triangles (x aft to forward, y to port from the
centre plane, z up from the keel). Volumes use the divergence theorem with the
field (0, y, 0), whose flux through the centre plane and the waterplane is
zero, so the open half hull needs no closing faces. Section and waterplane
areas integrate the half-breadth along the segments where the triangles cross the
cutting plane.
"""

from dataclasses import dataclass
from math import atan, degrees

import numpy as np

from .iges import NurbsSurface


def tessellate(surfaces: list[NurbsSurface], n: int = 80) -> np.ndarray:
    """Triangles of all surfaces, shape (m, 3, 3)."""
    tris = []
    for s in surfaces:
        g = s.evaluate(n, n)
        a, b, c, d = g[:-1, :-1], g[1:, :-1], g[1:, 1:], g[:-1, 1:]
        tris.append(np.stack([a, b, c], axis=-2).reshape(-1, 3, 3))
        tris.append(np.stack([a, c, d], axis=-2).reshape(-1, 3, 3))
    return np.concatenate(tris)


def clip_below(tris: np.ndarray, T: float) -> np.ndarray:
    """Parts of the triangles below z = T, as triangles."""
    below = tris[:, :, 2] <= T
    out = [tris[below.all(axis=1)]]
    for tri, mask in zip(tris[below.any(axis=1) & ~below.all(axis=1)], below[below.any(axis=1) & ~below.all(axis=1)]):
        poly = []
        for i in range(3):
            p, q = tri[i], tri[(i + 1) % 3]
            if mask[i]:
                poly.append(p)
            if mask[i] != mask[(i + 1) % 3]:
                f = (T - p[2]) / (q[2] - p[2])
                poly.append(p + f * (q - p))
        for k in range(1, len(poly) - 1):
            out.append(np.array([[poly[0], poly[k], poly[k + 1]]]))
    return np.concatenate(out)


def _segments(tris: np.ndarray, axis: int, value: float) -> np.ndarray:
    """Segments where the triangles cross the plane coordinate[axis] = value, shape (m, 2, 3)."""
    side = tris[:, :, axis] - value
    crossing = (side.min(axis=1) < 0) & (side.max(axis=1) > 0)
    segs = []
    for tri, sd in zip(tris[crossing], side[crossing]):
        pts = []
        for i, j in ((0, 1), (1, 2), (2, 0)):
            if sd[i] * sd[j] < 0:
                pts.append(tri[i] + sd[i] / (sd[i] - sd[j]) * (tri[j] - tri[i]))
        if len(pts) == 2:
            segs.append(pts)
    return np.array(segs).reshape(-1, 2, 3)


def _integral(segs: np.ndarray, along: int) -> tuple[float, float]:
    """Integral of the half-breadth y along a coordinate over a single-valued curve, and its first moment."""
    y = 0.5 * (segs[:, 0, 1] + segs[:, 1, 1])
    d = np.abs(segs[:, 1, along] - segs[:, 0, along])
    m = 0.5 * (segs[:, 0, along] + segs[:, 1, along])
    return float((y * d).sum()), float((y * d * m).sum())


@dataclass(frozen=True)
class Hydrostatics:
    T: float
    volume: float  # m3, both sides
    lcb_x: float  # m, from the origin of the geometry
    wetted_surface: float  # m2, both sides
    waterplane_area: float  # m2
    midship_area: float  # m2
    bulb_area: float  # A_BT, m2, at the forward perpendicular
    bulb_centroid: float  # h_B, m above keel
    transom_area: float  # A_T, m2
    entrance_angle: float  # i_E, degrees
    L_wl: float


def section(tris_wet: np.ndarray, x: float) -> tuple[float, float]:
    """Area (both sides) and centroid height of the immersed section at x."""
    segs = _segments(tris_wet, 0, x)
    if len(segs) == 0:
        return 0.0, 0.0
    half, moment = _integral(segs, 2)
    return 2 * half, moment / half if half > 0 else 0.0


def hydrostatics(surfaces: list[NurbsSurface], T: float, x_ap: float, x_fp: float, n: int = 80) -> Hydrostatics:
    """Hydrostatics at even keel draught T. x_ap and x_fp locate the perpendiculars."""
    tris = clip_below(tessellate(surfaces, n), T)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    normal = 0.5 * np.cross(b - a, c - a)  # area-weighted normals
    area = np.linalg.norm(normal, axis=1)
    centroid = (a + b + c) / 3
    flux = centroid[:, 1] * np.abs(normal[:, 1])  # half-breadth surfaces have outward n_y > 0
    volume_half = flux.sum()
    lcb_x = float((centroid[:, 0] * flux).sum() / volume_half)

    # Waterline just below T, so the cut stays inside the clipped mesh
    wl = _segments(tris, 2, T - 1e-4)
    half_wp, _ = _integral(wl, 0)
    x_min, x_max = wl[:, :, 0].min(), wl[:, :, 0].max()

    # Half angle of entrance from the waterline slope over the forward 10 % of the length, ignoring the stem
    L = x_fp - x_ap
    pts = wl.reshape(-1, 3)
    fwd = (pts[:, 0] > x_fp - 0.10 * L) & (pts[:, 0] < x_fp - 0.01 * L)
    slope = -np.polyfit(pts[fwd, 0], pts[fwd, 1], 1)[0]

    midship, _ = section(tris, 0.5 * (x_ap + x_fp))
    bulb, h_b = section(tris, x_fp)
    transom, _ = section(tris, tris[:, :, 0].min() + 0.05)
    return Hydrostatics(
        T=T,
        volume=float(2 * volume_half),
        lcb_x=lcb_x,
        wetted_surface=float(2 * area.sum()),
        waterplane_area=2 * half_wp,
        midship_area=midship,
        bulb_area=bulb,
        bulb_centroid=h_b,
        transom_area=transom,
        entrance_angle=degrees(atan(slope)),
        L_wl=float(x_max - x_min),
    )
