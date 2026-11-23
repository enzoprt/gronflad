"""Hydrostatics from NURBS surfaces, checked on shapes with exact answers."""

from math import pi, sqrt

import numpy as np
import pytest

from gronflad.hydrostatics import hydrostatics
from gronflad.iges import NurbsSurface

L, B, H = 100.0, 20.0, 12.0


def plane(p00, p10, p01, p11) -> NurbsSurface:
    return NurbsSurface(
        degree_u=1, degree_v=1, knots_u=np.array([0, 0, 1, 1.0]), knots_v=np.array([0, 0, 1, 1.0]),
        weights=np.ones((2, 2)), points=np.array([[p00, p01], [p10, p11]], dtype=float),
        u_range=(0.0, 1.0), v_range=(0.0, 1.0),
    )


def box() -> list[NurbsSurface]:
    """Half of a rectangular barge: side and bottom only, the ends carry no y flux."""
    side = plane((0, B / 2, 0), (L, B / 2, 0), (0, B / 2, H), (L, B / 2, H))
    bottom = plane((0, 0, 0), (L, 0, 0), (0, B / 2, 0), (L, B / 2, 0))
    return [side, bottom]


def half_cylinder(R: float) -> list[NurbsSurface]:
    """Quarter circle section (exact rational quadratic) swept along x, axis at z = R."""
    w = sqrt(2) / 2
    arc = [(0, 0, 0), (0, R, 0), (0, R, R)]  # bottom centre to side, control points in (x, y, z)
    pts = np.array([[[0, y, z], [L, y, z]] for _, y, z in arc], dtype=float)
    return [
        NurbsSurface(
            degree_u=2, degree_v=1, knots_u=np.array([0, 0, 0, 1, 1, 1.0]), knots_v=np.array([0, 0, 1, 1.0]),
            weights=np.array([[1, 1], [w, w], [1, 1]]), points=pts, u_range=(0.0, 1.0), v_range=(0.0, 1.0),
        )
    ]


def test_box_barge():
    T = 8.0
    h = hydrostatics(box(), T, x_ap=0, x_fp=L, n=20)
    assert h.volume == pytest.approx(L * B * T, rel=1e-9)
    assert h.lcb_x == pytest.approx(L / 2, rel=1e-9)
    assert h.waterplane_area == pytest.approx(L * B, rel=1e-6)
    assert h.midship_area == pytest.approx(B * T, rel=1e-6)
    assert h.wetted_surface == pytest.approx(L * B + 2 * L * T, rel=1e-6)


def test_rational_circle_section():
    R = 10.0
    h = hydrostatics(half_cylinder(R), T=R, x_ap=0, x_fp=L, n=200)
    assert h.volume == pytest.approx(pi * R**2 / 2 * L, rel=1e-3)
    assert h.midship_area == pytest.approx(pi * R**2 / 2, rel=1e-3)
    assert h.wetted_surface == pytest.approx(pi * R * L, rel=1e-3)
