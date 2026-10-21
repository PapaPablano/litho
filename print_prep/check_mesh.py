"""Sanity-check an STL before slicing: watertight, size, volume, thin features.

Usage: python check_mesh.py models/stl/pic.stl
"""
import sys

import numpy as np
from stl import mesh


def _edge_stats(faces):
    """Return (open_edges, flipped_edges) for a welded face-index array.

    open_edges: edges not shared by exactly two faces.
    flipped_edges: edges shared by exactly two faces that both run the same way, which means one
    neighbour has reversed winding even though the mesh looks closed.
    """
    n = int(faces.max()) + 1
    a = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]]).astype(np.int64)
    b = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]]).astype(np.int64)
    ukeys, ucounts = np.unique(np.minimum(a, b) * n + np.maximum(a, b), return_counts=True)
    dkeys, dcounts = np.unique(a * n + b, return_counts=True)
    same_way = dkeys[dcounts == 2]
    lo, hi = np.minimum(same_way // n, same_way % n), np.maximum(same_way // n, same_way % n)
    shared_by_two = ucounts[np.searchsorted(ukeys, lo * n + hi)] == 2
    return int((ucounts != 2).sum()), int(shared_by_two.sum())


def _shell_count(faces):
    """Number of connected pieces, or None when SciPy is not installed."""
    try:
        from scipy.sparse import coo_matrix
        from scipy.sparse.csgraph import connected_components
    except ImportError:
        return None
    n = int(faces.max()) + 1
    rows = np.concatenate([faces[:, 0], faces[:, 1]])
    cols = np.concatenate([faces[:, 1], faces[:, 2]])
    return int(connected_components(coo_matrix((np.ones(len(rows)), (rows, cols)), shape=(n, n)), directed=False)[0])


def analyze(path):
    """Measure an STL: triangle count, size in mm, edge problems, volume in mm^3, shell count."""
    m = mesh.Mesh.from_file(path)
    tris = m.vectors
    size = m.max_ - m.min_

    # Weld vertices, then every edge must be shared by exactly two faces.
    pts = np.round(tris.reshape(-1, 3), 4)
    _, inv = np.unique(pts, axis=0, return_inverse=True)
    f = inv.reshape(-1, 3)
    bad, flipped = _edge_stats(f)

    v0, v1, v2 = tris[:, 0], tris[:, 1], tris[:, 2]
    volume = np.einsum("ij,ij->i", v0, np.cross(v1, v2)).sum() / 6.0
    return {"triangles": len(tris), "size": size, "open_edges": bad, "flipped_edges": flipped,
            "shells": _shell_count(f), "volume": volume}


def main(path):
    r = analyze(path)
    size, bad, flipped, volume = r["size"], r["open_edges"], r["flipped_edges"], r["volume"]
    print(f"File:       {path}")
    print(f"Triangles:  {r['triangles']}")
    print(f"Size (mm):  {size[0]:.2f} x {size[1]:.2f} x {size[2]:.2f}")
    print(f"Watertight: {'yes' if bad == 0 else f'NO ({bad} open/non-manifold edges)'}")
    print(f"Winding:    {'consistent' if flipped == 0 else f'NO ({flipped} edges with reversed neighbours)'}")
    if r["shells"] is not None:
        print(f"Shells:     {r['shells']}")
    print(f"Volume:     {volume / 1000:.2f} cm^3" + ("  (NORMALS INVERTED)" if volume < 0 else ""))

    warnings = []
    if size.min() < 0.8:
        warnings.append(f"thinnest dimension {size.min():.2f} mm is under 0.8 mm")
    if bad:
        warnings.append("repair the mesh before slicing")
    if flipped:
        warnings.append("some faces are wound the wrong way; recalculate normals before slicing")
    if r["shells"] and r["shells"] > 1:
        warnings.append(f"{r['shells']} separate pieces; fine for a multi-part print, a stray fragment otherwise")
    for w in warnings:
        print("WARNING:", w)
    return 1 if bad or flipped or volume < 0 else 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    sys.exit(main(sys.argv[1]))
