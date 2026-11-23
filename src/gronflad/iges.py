"""Minimal reader for rational B-spline surfaces (IGES entity 128).

Enough to tessellate hull surfaces published as IGES files, such as the KCS
hull of the SIMMAN 2008 workshop. Other entity types are ignored.
"""

from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class NurbsSurface:
    degree_u: int
    degree_v: int
    knots_u: np.ndarray
    knots_v: np.ndarray
    weights: np.ndarray  # (n_u, n_v)
    points: np.ndarray  # (n_u, n_v, 3)
    u_range: tuple[float, float]
    v_range: tuple[float, float]

    def evaluate(self, n_u: int, n_v: int) -> np.ndarray:
        """Points on a regular (n_u, n_v) parameter grid, shape (n_u, n_v, 3)."""
        u = np.linspace(*self.u_range, n_u)
        v = np.linspace(*self.v_range, n_v)
        Bu = _basis(self.knots_u, self.degree_u, self.points.shape[0], u)  # (n_u, ncu)
        Bv = _basis(self.knots_v, self.degree_v, self.points.shape[1], v)  # (n_v, ncv)
        w = self.weights
        num = np.einsum("ai,bj,ij,ijk->abk", Bu, Bv, w, self.points)
        den = np.einsum("ai,bj,ij->ab", Bu, Bv, w)
        return num / den[..., None]


def _basis(knots: np.ndarray, p: int, n: int, t: np.ndarray) -> np.ndarray:
    """B-spline basis functions N_{i,p}(t) for all i, Cox-de Boor recursion."""
    t = np.clip(t, knots[p], knots[n])
    N = np.zeros((t.size, len(knots) - 1))
    for i in range(len(knots) - 1):
        N[:, i] = (knots[i] <= t) & (t < knots[i + 1])
    # The end of the range belongs to the last non-empty span
    last = max(i for i in range(len(knots) - 1) if knots[i] < knots[i + 1])
    N[t >= knots[n], :] = 0.0
    N[t >= knots[n], last] = 1.0
    for k in range(1, p + 1):
        nxt = np.zeros((t.size, len(knots) - 1 - k))
        for i in range(len(knots) - 1 - k):
            d1, d2 = knots[i + k] - knots[i], knots[i + k + 1] - knots[i + 1]
            a = (t - knots[i]) / d1 * N[:, i] if d1 > 0 else 0.0
            b = (knots[i + k + 1] - t) / d2 * N[:, i + 1] if d2 > 0 else 0.0
            nxt[:, i] = a + b
        N = nxt
    return N[:, :n]


def read_surfaces(path: str | Path) -> list[NurbsSurface]:
    lines = Path(path).read_text(errors="ignore").splitlines()
    section = {s: [ln[:72] for ln in lines if len(ln) > 72 and ln[72] == s] for s in "GDP"}
    params = "".join(section["G"])
    delimiter = params[2] if params.startswith("1H") else ","
    record_end = params[params.index(delimiter, 3) + 3] if params[3:5] == "1H" else ";"

    # Parameter data, keyed by the pointer of its directory entry
    data: dict[int, list[float]] = {}
    current, buf = None, ""
    for ln in [ln for ln in lines if len(ln) > 72 and ln[72] == "P"]:
        pointer = int(ln[64:72])
        if pointer != current:
            current, buf = pointer, ""
        buf += ln[:64]
        if record_end in buf:
            fields = buf.split(record_end)[0].replace("D", "E").split(delimiter)
            data[current] = [float(f) for f in fields if f.strip()]

    surfaces = []
    d = section["D"]
    for i in range(0, len(d), 2):
        if int(d[i][:8]) != 128:
            continue
        p = data[i + 1]
        k1, k2, m1, m2 = (int(x) for x in p[1:5])
        n1, n2 = k1 + 1, k2 + 1
        a = 10
        knots_u = np.array(p[a : a + n1 + m1 + 1])
        a += n1 + m1 + 1
        knots_v = np.array(p[a : a + n2 + m2 + 1])
        a += n2 + m2 + 1
        weights = np.array(p[a : a + n1 * n2]).reshape(n2, n1).T
        a += n1 * n2
        points = np.array(p[a : a + 3 * n1 * n2]).reshape(n2, n1, 3).transpose(1, 0, 2)
        a += 3 * n1 * n2
        surfaces.append(
            NurbsSurface(
                degree_u=m1, degree_v=m2, knots_u=knots_u, knots_v=knots_v, weights=weights, points=points,
                u_range=(p[a], p[a + 1]), v_range=(p[a + 2], p[a + 3]),
            )
        )
    return surfaces
