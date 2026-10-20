"""Prepare a photo for lithophane use: grayscale, resize, optional contrast boost.

Usage: python prep_photo.py input.jpg output.png --width 1000 --contrast 1.3
       python prep_photo.py input.jpg output.png --fit-mm 195 261   # center-crop to that aspect
       python prep_photo.py input.jpg output.png --fit-mm 205 269 --pad   # pad instead, nothing is cut off
"""
import argparse
from PIL import Image, ImageOps, ImageEnhance


def main():
    p = argparse.ArgumentParser()
    p.add_argument("src")
    p.add_argument("dst")
    p.add_argument("--width", type=int, default=1000)
    p.add_argument("--contrast", type=float, default=1.0)
    p.add_argument("--fit-mm", type=float, nargs=2, metavar=("W", "H"),
                   help="center-crop to the aspect ratio of this image area in mm")
    p.add_argument("--pad", action="store_true",
                   help="with --fit-mm: add white margin to reach the aspect instead of cropping")
    a = p.parse_args()

    Image.MAX_IMAGE_PIXELS = None   # upscaled inputs can be huge
    img = ImageOps.exif_transpose(Image.open(a.src)).convert("L")
    if a.fit_mm:
        want = a.fit_mm[0] / a.fit_mm[1]
        if a.pad:
            w = max(img.width, round(img.height * want))
            h = max(img.height, round(img.width / want))
            canvas = Image.new("L", (w, h), 255)
            canvas.paste(img, ((w - img.width) // 2, (h - img.height) // 2))
            img = canvas
        elif img.width / img.height > want:
            w = round(img.height * want)
            x = (img.width - w) // 2
            img = img.crop((x, 0, x + w, img.height))
        else:
            h = round(img.width / want)
            y = (img.height - h) // 2
            img = img.crop((0, y, img.width, y + h))
    h = round(img.height * a.width / img.width)
    img = img.resize((a.width, h), Image.LANCZOS)
    img = ImageOps.autocontrast(img)
    img = ImageEnhance.Contrast(img).enhance(a.contrast)
    img.save(a.dst)
    print(f"Saved {a.dst} ({a.width}x{h})")


if __name__ == "__main__":
    main()
