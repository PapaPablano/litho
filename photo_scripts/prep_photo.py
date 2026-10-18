"""Prepare a photo for lithophane use: grayscale, resize, optional contrast boost.

Usage: python prep_photo.py input.jpg output.png --width 1000 --contrast 1.3
"""
import argparse
from PIL import Image, ImageOps, ImageEnhance


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--width", type=int, default=1000)
    p.add_argument("--contrast", type=float, default=1.0)
    a = p.parse_args()

    img = ImageOps.exif_transpose(Image.open(a.src)).convert("L")
    h = round(img.height * a.width / img.width)
    img = img.resize((a.width, h), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(a.contrast)
    img.save(a.dst)
    print(f"Saved {a.dst} ({a.width}x{h})")


if __name__ == "__main__":
    main()
