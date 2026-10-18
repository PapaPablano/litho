"""Sanity-check an STL before slicing: watertight, size, volume, thin features.

Usage: python check_mesh.py models/stl/pic.stl
"""
import sys
from collections import Counter

import numpy as np
from stl import mesh


def main(path):
    m = mesh.Mesh.from_file(path)
    tris = m.vectors
    size = m.max_ - m.min_
    print(f"File:       {path}")
    print(f"Triangles:  {len(tris)}")
    print(f"Size (mm):  {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f}")

    # Weld vertices, then every edge must be shared by exactly two faces.
    pts = np.round(tris.reshape(-1, 3), 4)
    _, inv = np.unique(pts, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    edges = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    counts = Counter(map(tuple, edges))
    bad = sum(1 for c in counts.values() if c != 2)
    print(f"Watertight: {'yes' if bad == 0 else f'NO ({bad} open/non-manifold edges)'}")

    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    volume = np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0
    print(f"Volume:     {volume / 1000:.2f} cm^3" + ("  (NORMALS INVERTED)" if volume < 0 else ""))

    warnings = []
    if size.min() < 0.8:
        warnings.append(f"thinnest dimension {size.min():.2f} mm is under 0.8 mm")
    if bad:
        warnings.append("repair the mesh before slicing")
    for w in warnings:
        print("WARNING:", w)
    return 1 if bad or volume < 0 else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
