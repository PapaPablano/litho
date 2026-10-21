"""Shared helpers: put the script folders on sys.path and build small test meshes."""
import sys
from pathlib import Path

import numpy as np
import pytest
from stl import mesh

ROOT = Path(__file__).resolve().parent.parent
for sub in ("print_prep", "model_scripts"):
    sys.path.insert(0, str(ROOT / sub))

# Corners of a box and its 12 outward-facing triangles (counter-clockwise from outside).
_CORNERS = np.array([[x, y, z] for z in (0, 1) for y in (0, 1) for x in (0, 1)], dtype=float)
_FACES = [
    (0, 2, 1), (1, 2, 3),  # bottom (-z)
    (4, 5, 6), (5, 7, 6),  # top (+z)
    (0, 1, 4), (1, 5, 4),  # front (-y)
    (2, 6, 3), (3, 6, 7),  # back (+y)
    (0, 4, 2), (2, 4, 6),  # left (-x)
    (1, 3, 5), (3, 7, 5),  # right (+x)
]


def make_box(sx, sy, sz, *, drop_face=False, inverted=False, flip_one=False, offset=(0.0, 0.0, 0.0)):
    """Return a numpy-stl Mesh of a box with the given size in mm."""
    faces = list(_FACES)
    if drop_face:
        faces = faces[2:]
    if inverted:
        faces = [(a, c, b) for a, b, c in faces]
    if flip_one:                                  # reverse a single triangle: edges stay shared, winding breaks
        a, b, c = faces[-1]
        faces[-1] = (a, c, b)
    verts = _CORNERS * np.array([sx, sy, sz]) + np.array(offset)
    m = mesh.Mesh(np.zeros(len(faces), dtype=mesh.Mesh.dtype))
    for i, f in enumerate(faces):
        m.vectors[i] = verts[list(f)]
    return m


@pytest.fixture
def box_stl(tmp_path):
    """Factory: write a box STL to tmp_path and return its path."""
    def build(name="box.stl", *args, **kwargs):
        path = tmp_path / name
        make_box(*args, **kwargs).save(str(path))
        return path
    return build
