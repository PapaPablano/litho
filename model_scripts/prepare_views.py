"""Normalise a folder of views so they pass check_views and feed the shape model consistently.

For each front/back/left/right (and optional top) image: cut out the background, keep the
largest connected piece, crop to the subject, scale every view so the subject is the same
height (the views share the car's height, so this keeps them in proportion), and centre it on
one square transparent canvas with an even margin. Aspect ratios are left alone unless real_mm is given, which balances each view to the real proportions.

Usage: python prepare_views.py "photos/input/<folder>" "photos/output/<folder>_prepared"
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image

CANVAS = 1024
MARGIN = 0.06          # share of the canvas left empty on each side
ALPHA_THRESHOLD = 128  # alpha above this counts as subject
FILL = (127, 127, 127)  # colour under transparent pixels, so no stray colour bleeds in


def cut_out(img, remover=None):
    """RGBA image; removes the background only if the image is fully opaque. Returns (image, remover)."""
    img = img.convert("RGBA")
    if img.getextrema()[3][0] == 255:
        if remover is None:
            try:
                from hy3dgen.rembg import BackgroundRemover
            except ImportError as e:
                raise ImportError(f"background remover not available ({e}); run this in the AI venv") from e
            remover = BackgroundRemover()
        img = remover(img.convert("RGB")).convert("RGBA")
    return img, remover


def largest_piece(img):
    """Drop every opaque blob except the biggest (stray shadows, reflections, speckle)."""
    from scipy import ndimage
    a = np.array(img)
    labels, n = ndimage.label(a[..., 3] > ALPHA_THRESHOLD)
    if n == 0:
        raise ValueError("no subject found after background removal")
    keep = labels == (np.argmax(ndimage.sum(np.ones_like(labels), labels, range(1, n + 1))) + 1)
    a[..., 3] = np.where(keep, a[..., 3], 0)
    return Image.fromarray(a)


def crop_to_subject(img):
    box = Image.fromarray(np.array(img)[..., 3] > ALPHA_THRESHOLD).getbbox()
    return img.crop(box)


def calibrate(crop, name, real_mm):
    """Stretch a cropped view sideways so its width/height matches the real object's proportions.

    Photos taken close up or off-axis distort those proportions; the real size is known, so this
    balances them out before the shape model sees the views. real_mm is (length, width, height).
    """
    length, width, height = real_mm
    target = {"left": length, "right": length, "front": width, "back": width}.get(name)
    if target is None:
        return crop
    k = (target / height) / (crop.width / crop.height)
    return crop.resize((max(1, round(crop.width * k)), crop.height), Image.LANCZOS)


def prepare(views, canvas=CANVAS, margin=MARGIN, real_mm=None):
    """views: {name: RGBA image already cut out}. Returns {name: canvas x canvas RGBA image}.

    With real_mm=(length, width, height) each view is first balanced to the real proportions.
    """
    crops = {}
    for n, v in views.items():
        try:
            crops[n] = crop_to_subject(largest_piece(v))
        except ValueError as e:
            raise ValueError(f"{n}: {e}") from e
        if real_mm:
            crops[n] = calibrate(crops[n], n, real_mm)
    room = canvas * (1 - 2 * margin)
    # one target height for every side view; shrunk for all of them if the widest would not fit.
    # A top view looks down on the car, so it is fitted on its own rather than to that height.
    sides = [c for n, c in crops.items() if n != "top"]
    height = min([room, *(room * c.height / c.width for c in sides)])
    out = {}
    for n, c in crops.items():
        scale = min(room / c.width, room / c.height) if n == "top" else height / c.height
        size = (max(1, round(c.width * scale)), max(1, round(c.height * scale)))
        c = c.resize(size, Image.LANCZOS)
        rgb = Image.new("RGBA", c.size, FILL + (0,))
        rgb.paste(c, (0, 0), c)                       # transparent pixels take FILL, not stray colour
        page = Image.new("RGBA", (canvas, canvas), FILL + (0,))
        page.paste(rgb, ((canvas - size[0]) // 2, (canvas - size[1]) // 2))
        out[n] = page
    return out


def prepare_folder(folder, out_folder, remover=None, real_mm=None):
    """Prepare every view in `folder`, write PNGs to `out_folder`, return that Path."""
    import check_views
    found = check_views.find_views(folder)
    missing = [n for n in check_views.REQUIRED if n not in found]
    if missing:
        raise FileNotFoundError(f"missing views: {', '.join(missing)}")
    views = {}
    for name, path in found.items():
        try:
            with Image.open(path) as im:
                views[name], remover = cut_out(im, remover)
        except OSError as e:
            raise ValueError(f"{name}: cannot read {path} ({e})") from e
    out_folder = Path(out_folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    for stale in check_views.REQUIRED + check_views.OPTIONAL:    # a leftover top.png would be read as a view
        (out_folder / f"{stale}.png").unlink(missing_ok=True)
    for name, img in prepare(views, real_mm=real_mm).items():
        img.save(out_folder / f"{name}.png")
    return out_folder


def main(argv):
    if len(argv) != 3:
        sys.exit(__doc__)
    out = prepare_folder(argv[1], argv[2])
    print(f"Wrote prepared views to {out}")
    return 0


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    sys.exit(main(sys.argv))
