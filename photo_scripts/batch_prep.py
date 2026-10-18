"""Prep every image in a folder (grayscale, resize, contrast), optionally making STLs too.

Usage: python batch_prep.py [--src photos/input] [--dst photos/output] [--width 1000]
                            [--contrast 1.2] [--stl models/stl]
"""
import argparse
from pathlib import Path

from PIL import Image, ImageEnhance, ImageOps

ROOT = Path(__file__).resolve().parent.parent
EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}


def prep(src, width, contrast):
    img = ImageOps.exif_transpose(Image.open(src)).convert("L")
    h = round(img.height * width / img.width)
    img = img.resize((width, h), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    return ImageEnhance.Contrast(img).enhance(contrast)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default=str(ROOT / "photos" / "input"))
    p.add_argument("--dst", default=str(ROOT / "photos" / "output"))
    p.add_argument("--width", type=int, default=1000)
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--stl", help="also write a lithophane STL per image into this folder")
    a = p.parse_args()

    src, dst = Path(a.src), Path(a.dst)
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(f for f in src.iterdir() if f.suffix.lower() in EXTS)
    if not files:
        raise SystemExit(f"No images found in {src}")

    if a.stl:
        import make_lithophane as ml
        d = ml.load_defaults()
        stl_dir = Path(a.stl)
        stl_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        img = prep(f, a.width, a.contrast)
        out = dst / (f.stem + ".png")
        img.save(out)
        print(f"{f.name} -> {out.name}")
        if a.stl:
            args = argparse.Namespace(
                width=d["width_mm"], min_thickness=d["min_thickness_mm"],
                max_thickness=d["max_thickness_mm"], border=d["border_mm"],
                pixel=d["pixel_mm"], gamma=d["gamma"],
            )
            m = ml.build_mesh(ml.thickness_map(img, args), args.pixel)
            m.save(stl_dir / (f.stem + ".stl"))
            print(f"  STL: {f.stem}.stl")


if __name__ == "__main__":
    main()
