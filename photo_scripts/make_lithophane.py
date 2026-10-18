"""Convert a (preferably prepped) photo into a lithophane STL.

Dark pixels become thick, bright pixels thin, so light shows the image.

Usage: python make_lithophane.py photos/output/pic.png models/stl/pic.stl [--width 100]
"""
import argparse
from pathlib import Path

import numpy as np
import yaml
from PIL import Image, ImageOps
from stl import mesh

ROOT = Path(__file__).resolve().parent.parent


def load_defaults():
    with open(ROOT / "config.yaml", encoding="utf-8-sig") as f:
        return yaml.safe_load(f)["panel"]


def thickness_map(img, a):
    """Return a 2D array of thickness in mm, with the border padded in."""
    w_px = round(a.width / a.pixel)
    h_px = round(img.height * w_px / img.width)
    img = img.resize((w_px, h_px), Image.LANCZOS)
    b = np.asarray(img, dtype=np.float64) / 255.0
    b = b ** (1.0 / a.gamma)
    t = a.max_thickness - b * (a.max_thickness - a.min_thickness)
    pad = round(a.border / a.pixel)
    if pad:
        t = np.pad(t, pad, mode="constant", constant_values=a.max_thickness)
    return t


def build_mesh(t, pixel):
    """Watertight solid: heightfield top, flat bottom, four side walls."""
    h, w = t.shape
    n = h * w
    ys, xs = np.mgrid[0:h, 0:w]
    x = xs * pixel
    y = (h - 1 - ys) * pixel
    top = np.column_stack([x.ravel(), y.ravel(), t.ravel()])
    bot = np.column_stack([x.ravel(), y.ravel(), np.zeros(n)])
    verts = np.vstack([top, bot])

    idx = np.arange(n).reshape(h, w)
    a, b = idx[:-1, :-1].ravel(), idx[:-1, 1:].ravel()
    d, c = idx[1:, :-1].ravel(), idx[1:, 1:].ravel()
    faces = [
        np.column_stack([a, d, c]), np.column_stack([a, c, b]),              # top (+z)
        np.column_stack([a + n, c + n, d + n]), np.column_stack([a + n, b + n, c + n]),  # bottom (-z)
    ]

    # Perimeter walked counter-clockwise seen from +z.
    ring = np.concatenate([
        idx[0, :0:-1],        # top row, right -> left
        idx[:-1, 0],          # left column, top -> bottom
        idx[-1, :-1],         # bottom row, left -> right
        idx[::-1, -1][:-1],   # right column, bottom -> top
    ])
    p, q = ring, np.roll(ring, -1)
    faces += [np.column_stack([p, p + n, q + n]), np.column_stack([p, q + n, q])]

    f = np.vstack(faces)
    m = mesh.Mesh(np.zeros(len(f), dtype=mesh.Mesh.dtype))
    m.vectors[:] = verts[f]
    return m


def main():
    d = load_defaults()
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--width", type=float, default=d["width_mm"])
    p.add_argument("--min-thickness", type=float, default=d["min_thickness_mm"])
    p.add_argument("--max-thickness", type=float, default=d["max_thickness_mm"])
    p.add_argument("--border", type=float, default=d["border_mm"])
    p.add_argument("--pixel", type=float, default=d["pixel_mm"])
    p.add_argument("--gamma", type=float, default=d["gamma"])
    a = p.parse_args()

    img = ImageOps.exif_transpose(Image.open(a.src)).convert("L")
    t = thickness_map(img, a)
    m = build_mesh(t, a.pixel)
    Path(a.dst).parent.mkdir(parents=True, exist_ok=True)
    m.save(a.dst)
    size = m.max_ - m.min_
    print(f"Saved {a.dst}: {size[0]:.1f} x {size[1]:.1f} x {size[2]:.2f} mm, {len(m.vectors)} triangles")


if __name__ == "__main__":
    main()

