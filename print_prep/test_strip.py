"""Make a stepped-thickness test strip to calibrate light transmission on your filament.

Each step is a whole number of layers thick. Print it, hold it to your light, and pick the
min/max thickness that looks right, then put those in config.yaml.

Usage: python test_strip.py models/stl/test_strip.stl [--min 0.4] [--max 3.2] [--layer 0.1] [--steps 8]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "photo_scripts"))
import make_lithophane as ml  # noqa: E402


def main():
    p = argparse.ArgumentParser()
    p.add_argument("dst")
    p.add_argument("--min", type=float, default=0.4)
    p.add_argument("--max", type=float, default=3.2)
    p.add_argument("--layer", type=float, default=0.1)
    p.add_argument("--steps", type=int, default=8)
    p.add_argument("--step-width", type=float, default=10.0)
    p.add_argument("--height", type=float, default=30.0)
    p.add_argument("--pixel", type=float, default=0.5)
    a = p.parse_args()

    layers = np.unique(np.round(np.linspace(a.min, a.max, a.steps) / a.layer).astype(int))
    cols = round(a.step_width / a.pixel)
    rows = round(a.height / a.pixel)
    t = np.hstack([np.full((rows, cols), n * a.layer) for n in layers])

    m = ml.build_mesh(t, a.pixel)
    Path(a.dst).parent.mkdir(parents=True, exist_ok=True)
    m.save(a.dst)
    print("Steps (mm):", ", ".join(f"{n * a.layer:.1f}" for n in layers))
    print(f"Saved {a.dst}")


if __name__ == "__main__":
    main()
