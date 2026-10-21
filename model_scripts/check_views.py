"""Check a folder of views before generating a 3D model, and say what to recapture if it falls short.

The folder needs front, back, left and right images (an optional top is used by the
silhouette comparison), in png/jpg/jpeg/webp.

Usage: python check_views.py "photos/input/<folder>"   (exit 1 if the set is not usable)
"""
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from PIL import Image

REQUIRED = ("front", "back", "left", "right")
OPTIONAL = ("top",)
EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
MIN_LONG_EDGE = 512
PLAIN_FRACTION = 0.95   # share of border pixels that must match the border's typical colour
PLAIN_TOLERANCE = 24    # per-channel difference still counted as "the same colour"

CHECKLIST = """Capture checklist (docs/IMAGE_TO_3D.md has the full version):
  - one image each named front, back, left, right (optional: top), any of png/jpg/webp
  - straight-on views: camera level with the subject, not 3/4 angles
  - every image the same pixel size, subject centred with a margin on all sides
  - plain, even background (a flat colour), no shadows or reflections on it
  - long edge at least {min_edge} px; use the longest focal length / least perspective available"""


@dataclass
class Result:
    found: dict = field(default_factory=dict)
    problems: list = field(default_factory=list)

    @property
    def ok(self):
        return not self.problems


def _find(folder):
    found = {}
    for p in sorted(Path(folder).iterdir()):
        if p.suffix.lower() in EXTENSIONS and p.stem.lower() in REQUIRED + OPTIONAL:
            found[p.stem.lower()] = p
    return found


def _border_is_plain(img):
    a = np.asarray(img.convert("RGB"), dtype=np.int16)
    h, w, _ = a.shape
    m = max(2, min(h, w) // 50)
    border = np.concatenate([
        a[:m].reshape(-1, 3), a[-m:].reshape(-1, 3),
        a[:, :m].reshape(-1, 3), a[:, -m:].reshape(-1, 3),
    ])
    typical = np.median(border, axis=0)
    close = (np.abs(border - typical).max(axis=1) <= PLAIN_TOLERANCE).mean()
    return close >= PLAIN_FRACTION


def check(folder):
    r = Result(found=_find(folder))
    missing = [n for n in REQUIRED if n not in r.found]
    if missing:
        r.problems.append(
            f"missing views: {', '.join(missing)}. Name each file front/back/left/right (see the checklist below)."
        )
    sizes = {}
    for name, path in r.found.items():
        with Image.open(path) as img:
            sizes[name] = img.size
            if max(img.size) < MIN_LONG_EDGE:
                r.problems.append(f"{name}: resolution {img.size[0]}x{img.size[1]} is under {MIN_LONG_EDGE} px on the long edge")
            if not _border_is_plain(img):
                r.problems.append(f"{name}: background is not plain (the border is not one even colour)")
    if len(set(sizes.values())) > 1:
        first = next(iter(sizes.values()))
        for name, size in sizes.items():
            if size != first:
                r.problems.append(f"{name}: size {size[0]}x{size[1]} differs from the others ({first[0]}x{first[1]})")
    if r.problems:
        r.problems.append(CHECKLIST.format(min_edge=MIN_LONG_EDGE))
    return r


def main(argv):
    if len(argv) != 2:
        sys.exit(__doc__)
    r = check(argv[1])
    if r.ok:
        print(f"OK: {', '.join(r.found)} look usable.")
        return 0
    for p in r.problems:
        print(p)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
