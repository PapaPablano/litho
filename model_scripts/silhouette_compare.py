"""Overlay a mesh's outline on the supplied views so proportions can be judged by eye.

Writes one PNG per view found (front/back/left/right/top): mesh outline in red, view outline in
green, overlap in yellow. The overlap number is for information only. Views from a configurator
are perspective renders, so expect differences in the wheel arches and roofline even when right.

Usage: python silhouette_compare.py models/stl/car.stl "photos/input/<folder>" [--out photos/output]
"""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from stl import mesh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_views  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# which mesh axes (0=X length, 1=Y width, 2=Z up) become the image's horizontal and vertical
AXES = {"left": (0, 2), "right": (0, 2), "front": (1, 2), "back": (1, 2), "top": (0, 1)}
BG_TOLERANCE = 40


def _crop(mask):
    ys, xs = np.nonzero(mask)
    return mask[ys.min(): ys.max() + 1, xs.min(): xs.max() + 1]


def mesh_mask(vectors, view, px=400):
    """Boolean silhouette of the mesh seen from `view`, cropped to its bounding box."""
    hu, vv = AXES[view]
    pts = vectors.reshape(-1, 3)
    lo, hi = pts.min(axis=0), pts.max(axis=0)
    s = (px - 1) / (hi[hu] - lo[hu])
    w = px
    h = int(np.ceil((hi[vv] - lo[vv]) * s)) + 1
    img = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(img)
    for tri in vectors:
        poly = [((p[hu] - lo[hu]) * s, (hi[vv] - p[vv]) * s) for p in tri]
        draw.polygon(poly, fill=255)
    return _crop(np.asarray(img) > 0)


def view_mask(path):
    """Subject silhouette of a view image on a plain background, cropped to its bounding box."""
    a = np.asarray(Image.open(path).convert("RGB"), dtype=np.int16)
    m = max(2, min(a.shape[:2]) // 50)
    border = np.concatenate([a[:m].reshape(-1, 3), a[-m:].reshape(-1, 3),
                             a[:, :m].reshape(-1, 3), a[:, -m:].reshape(-1, 3)])
    typical = np.median(border, axis=0)
    return _crop(np.abs(a - typical).max(axis=2) > BG_TOLERANCE)


def _place(mask, width, height):
    """Scale mask to `width`, then bottom-centre it on a width x height canvas."""
    h = max(1, round(mask.shape[0] * width / mask.shape[1]))
    img = Image.fromarray((mask * 255).astype(np.uint8)).resize((width, h), Image.NEAREST)
    canvas = np.zeros((height, width), dtype=bool)
    arr = np.asarray(img) > 127
    canvas[height - h:, :] = arr[:height]
    return canvas


def _iou(a, b):
    return float((a & b).sum() / max(1, (a | b).sum()))


def compare(vectors, views_dir, out_dir, stem, px=400):
    """Write overlays for every view present in `views_dir`; return {view: overlap fraction}."""
    found = check_views._find(views_dir)
    out_dir = Path(out_dir)
    results = {}
    for view in AXES:
        if view not in found:
            continue
        mm = mesh_mask(vectors, view, px)
        vm = view_mask(found[view])
        height = max(mm.shape[0], round(vm.shape[0] * px / vm.shape[1]))
        a = _place(mm, px, height)
        b = _place(vm, px, height)
        if view in ("left", "right"):   # which way the car faces is not known, so allow a mirror
            b_flip = b[:, ::-1]
            if _iou(a, b_flip) > _iou(a, b):
                b = b_flip
        results[view] = _iou(a, b)
        rgb = np.zeros((height, px, 3), dtype=np.uint8)
        rgb[a, 0] = 255
        rgb[b, 1] = 255
        out_dir.mkdir(parents=True, exist_ok=True)
        Image.fromarray(rgb).save(out_dir / f"{stem}_{view}_overlay.png")
    return results


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("stl")
    p.add_argument("views")
    p.add_argument("--out", default=str(ROOT / "photos" / "output"))
    a = p.parse_args()
    vectors = mesh.Mesh.from_file(a.stl).vectors.astype(float)
    results = compare(vectors, a.views, a.out, Path(a.stl).stem)
    if not results:
        sys.exit("no front/back/left/right/top views found in " + a.views)
    for view, iou in results.items():
        print(f"{view:<6} overlap {iou:.0%}  -> {Path(a.out) / (Path(a.stl).stem + '_' + view + '_overlay.png')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
