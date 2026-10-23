"""Scale a generated mesh to a real subject at a print scale, check it, and write the STL.

The raw mesh must already be oriented X = length, Y = width, Z = up (generate_shape.py does that).
The whole mesh is scaled uniformly so its length hits the target, then width and height are
checked. A small per-axis stretch fixes a width or height that misses the tolerance, up to a cap;
beyond the cap the run fails and writes nothing.

Usage: python fit_to_scale.py models/raw/car.stl --subject mini_countryman [--scale 32] [--out models/stl/car.stl]
Exit codes: 0 ok, 1 written but not print-ready, 2 dimensions out of tolerance, 3 bad input (orientation, subject).
"""
import argparse
import sys
import dataclasses
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
from stl import mesh

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "print_prep"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import check_mesh  # noqa: E402
import subject  # noqa: E402

NAMES = ("length", "width", "height")


@dataclass
class Dim:
    name: str
    target: float
    measured: float
    error_pct: float
    ok: bool


@dataclass
class Report:
    dims: list
    stretch: dict = field(default_factory=dict)   # axis name -> factor applied beyond the uniform scale
    wrote: bool = False
    print_ready: bool = False
    analysis: dict = None

    @property
    def dimensions_ok(self):
        return all(d.ok for d in self.dims)

    @property
    def exit_code(self):
        if not self.dimensions_ok:
            return 2
        return 0 if self.print_ready else 1


def _dims(extent, t):
    out = []
    for name, target, measured in zip(NAMES, t.print_mm, extent):
        err = (measured - target) / target * 100
        out.append(Dim(name, target, float(measured), float(err), abs(err) <= t.tolerance_pct))
    return out


def run(src, t, dst):
    """Fit `src` STL to targets `t`; write `dst` unless a dimension cannot meet the tolerance."""
    m = mesh.Mesh.from_file(src)
    verts = m.vectors.astype(np.float64)
    extent = verts.reshape(-1, 3).max(axis=0) - verts.reshape(-1, 3).min(axis=0)
    if not (extent[0] > extent[1] and extent[0] > extent[2]):
        raise ValueError(
            f"orientation: expected X to be the longest axis (X=length, Y=width, Z=up), "
            f"got extents {extent[0]:.1f} x {extent[1]:.1f} x {extent[2]:.1f}"
        )

    scale = t.print_mm[0] / extent[0]
    factors = np.array([scale, scale, scale])
    stretch = {}
    for axis in (1, 2):
        measured = extent[axis] * scale
        target = t.print_mm[axis]
        if abs(measured - target) / target * 100 > t.tolerance_pct:
            k = target / measured
            if abs(k - 1) * 100 <= t.max_axis_stretch_pct:
                factors[axis] = scale * k
                stretch[NAMES[axis]] = k

    dims = _dims(extent * factors, t)
    report = Report(dims=dims, stretch=stretch)
    if not report.dimensions_ok:
        return report

    v = verts * factors
    lo, hi = v.reshape(-1, 3).min(axis=0), v.reshape(-1, 3).max(axis=0)
    v -= np.array([(lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, lo[2]])
    out = mesh.Mesh(np.zeros(len(v), dtype=mesh.Mesh.dtype))
    out.vectors[:] = v
    Path(dst).parent.mkdir(parents=True, exist_ok=True)
    out.save(str(dst))
    report.wrote = True
    report.analysis = check_mesh.analyze(str(dst))
    a = report.analysis
    report.print_ready = a["open_edges"] == 0 and a["flipped_edges"] == 0 and a["volume"] > 0
    return report


def print_report(r, src, dst):
    print(f"Fit {src}")
    print(f"{'':8}{'target mm':>11}{'measured':>10}{'error':>9}  result")
    for d in r.dims:
        print(f"{d.name:<8}{d.target:>11.2f}{d.measured:>10.2f}{d.error_pct:>+8.1f}%  {'PASS' if d.ok else 'FAIL'}")
    for name, k in r.stretch.items():
        print(f"stretched {name} by {(k - 1) * 100:+.1f}% beyond the uniform scale")
    if not r.dimensions_ok:
        bad = ", ".join(d.name for d in r.dims if not d.ok)
        print(f"FAILED: {bad} outside tolerance and not correctable within the stretch cap. Nothing written.")
        if Path(dst).exists():
            print(f"NOTE: {dst} is from an earlier run and was NOT updated; do not print it for this mesh.")
        return
    print(f"Wrote {dst}")
    a = r.analysis
    print(f"Watertight: {'yes' if a['open_edges'] == 0 else 'NO'}   Winding: {'ok' if a['flipped_edges'] == 0 else 'NO'}"
          f"   Volume: {a['volume'] / 1000:.2f} cm^3")
    print("Print-ready." if r.print_ready else "NOT print-ready: repair the mesh before slicing.")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("src")
    p.add_argument("--subject", required=True, help="subject name in model_scripts/subjects or a YAML path")
    p.add_argument("--scale", type=float, help="print scale denominator (1:N); default from config.yaml")
    p.add_argument("--out", help="output STL; default models/stl/<name>_1to<N>.stl")
    p.add_argument("--length-mm", type=float)
    p.add_argument("--width-mm", type=float)
    p.add_argument("--height-mm", type=float)
    p.add_argument("--max-stretch-pct", type=float,
                   help="override the per-axis stretch cap for this run (default from config.yaml)")
    p.add_argument("--force-fit", action="store_true",
                   help="stretch width and height to the targets whatever it takes; distorts wheels and "
                        "round parts, and is reported loudly")
    a = p.parse_args()
    try:
        t = subject.targets(a.subject, denominator=a.scale, max_axis_stretch_pct=a.max_stretch_pct,
                            length_mm=a.length_mm, width_mm=a.width_mm, height_mm=a.height_mm)
        default_cap = t.max_axis_stretch_pct if a.max_stretch_pct is None else subject.targets(a.subject).max_axis_stretch_pct
        if a.force_fit:
            t = dataclasses.replace(t, max_axis_stretch_pct=float("inf"))
    except (ValueError, FileNotFoundError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 3
    dst = a.out or str(ROOT / "models" / "stl" / f"{Path(a.src).stem}_1to{t.denominator:g}.stl")
    try:
        report = run(a.src, t, dst)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if Path(dst).exists():
            print(f"NOTE: {dst} is from an earlier run and was NOT updated.", file=sys.stderr)
        return 3
    print_report(report, a.src, dst)
    over = {n: k for n, k in report.stretch.items() if abs(k - 1) * 100 > default_cap}
    if over and report.wrote:
        print("WARNING: stretch beyond the configured cap (" + ", ".join(f"{n} {(k - 1) * 100:+.1f}%" for n, k in over.items())
              + f" vs {default_cap:g}%). Wheels and other round parts are distorted by this amount; "
              "check the model by eye before printing.")
    return report.exit_code


if __name__ == "__main__":
    sys.exit(main())
