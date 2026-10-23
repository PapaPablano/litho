"""Build the printable parts of a car kit from a generated body, check they fit, and write them out.

Pipeline: load the generated body as a clean solid -> build the chassis, wheels and interior from the
subject's real dimensions -> conform the body to them -> check the assembly -> write one STL per part,
laid out as it prints. Writes nothing if the check fails. Run it in the AI environment.

Usage: python make_kit.py models/raw/car.stl --subject mini_countryman --name countryman [--scale 24]
"""
import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import kit_body  # noqa: E402
import kit_check  # noqa: E402
import kit_mesh  # noqa: E402
import kit_parts  # noqa: E402
import subject  # noqa: E402

PRINT_MODES = ("flat", "roof_down", "axle_up")
THIN_FACES = 200000      # the body is thinned to about this many triangles before it is cut


def _rotation(angle, axis):
    import trimesh
    return trimesh.transformations.rotation_matrix(angle, axis)


def print_layout(name, mesh, mode):
    """A copy of `mesh` turned to lie on the bed as `mode` says, centred, with its lowest point at z = 0."""
    out = mesh.copy()
    if mode == "roof_down":
        out.apply_transform(_rotation(np.pi, [1, 0, 0]))
    elif mode == "axle_up":
        # the hub socket is on the inner face: -Y on right-hand wheels, +Y on left-hand wheels
        right = float(mesh.centroid[1]) > 0
        out.apply_transform(_rotation(np.pi / 2 if right else -np.pi / 2, [1, 0, 0]))
    elif mode != "flat":
        raise ValueError(f"{name}: unknown print orientation '{mode}'")
    lo, hi = out.bounds
    out.apply_translation([-(lo[0] + hi[0]) / 2, -(lo[1] + hi[1]) / 2, -lo[2]])
    return out


def _mode(cfg, part):
    return cfg.print_orientation["wheel" if part.startswith("wheel_") else part]


def _check_orientations(cfg):
    for part, mode in cfg.print_orientation.items():
        if mode not in PRINT_MODES:
            raise ValueError(f"config.yaml kit print_orientation for '{part}' is '{mode}'; choose from {', '.join(PRINT_MODES)}")


def _write_kit(folder, layouts):
    """Write every part into a temporary folder, then swap it in, so a failure never leaves a half-written kit."""
    folder = Path(folder)
    folder.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{folder.name}-", dir=folder.parent))
    backup = None
    try:
        for part, mesh in layouts.items():
            mesh.export(str(staging / f"{part}.stl"))
        if folder.exists():
            backup = folder.with_name(f".{folder.name}-old")
            shutil.rmtree(backup, ignore_errors=True)
            folder.rename(backup)
        staging.rename(folder)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        if backup is not None and backup.exists() and not folder.exists():
            backup.rename(folder)
        raise
    if backup is not None:
        shutil.rmtree(backup, ignore_errors=True)


def _build(a):
    """Everything up to and including the check; returns (report, conformed, parts)."""
    print(f"Loading the body: {a.body}")
    body = kit_mesh.thin(kit_mesh.load_solid(a.body, name="body"), a.thin)
    print("Building the chassis, wheels and interior")
    parts = kit_parts.build_parts(a.subject, scale=a.scale, wheel_style=a.wheel_style, clearance_mm=a.clearance)
    print("Fitting the body to them")
    conformed = kit_body.conform_body(body, parts, a.subject, front=a.front)
    return kit_check.check_kit(parts, conformed.shell, a.subject, bed_mm=a.bed_mm), conformed, parts


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("body", help="generated body STL, e.g. models/raw/countryman.stl")
    p.add_argument("--subject", required=True, help="subject name in model_scripts/subjects, or a YAML path")
    p.add_argument("--name", required=True, help="kit name; writes models/kit/<name>/")
    p.add_argument("--out", default=str(ROOT / "models" / "kit"), help="folder that receives <name>/")
    p.add_argument("--scale", type=float, help="print scale denominator (1:N); default from config.yaml")
    p.add_argument("--wheel-style", default="disc", choices=kit_parts.WHEEL_STYLES)
    p.add_argument("--clearance", type=float, help="joint clearance in mm; default from config.yaml")
    p.add_argument("--bed-mm", type=float, help="printer bed edge in mm; default from config.yaml")
    p.add_argument("--front", choices=["+x", "-x"], help="end the generated body's front faces; default is detected")
    p.add_argument("--thin", type=int, default=THIN_FACES, help="triangles to thin the body to before cutting")
    a = p.parse_args(argv)
    folder = Path(a.out) / a.name

    try:
        cfg = subject.kit_config()
        _check_orientations(cfg)                      # before the minute-long build, not after it
        report, conformed, parts = _build(a)
        print(f"{'':8}{'target mm':>9}{'built':>9}{'error':>9}")
        for line in report.lines():
            print(line)
        unverified = subject.kit_spec(a.subject).unverified
        if unverified:
            print("Unverified spec values (confirm or tune): " + ", ".join(unverified))
        if conformed.dropped_pieces:
            print(f"Note: {conformed.dropped_pieces} loose piece(s) were dropped after cutting the glass openings "
                  "(usually the mirrors); check the body in your slicer.")
        if conformed.turned:
            print("Note: the body was turned half a way round so its front faces -X (use --front to override).")
        if not report.ok:
            if folder.exists():
                print(f"NOTE: {folder} is from an earlier run and was NOT updated; do not print it for this body.")
            return report.exit_code
        named = {"body": conformed.shell, "chassis": parts.chassis, "interior": parts.interior,
                 **{f"wheel_{n}": w for n, w in parts.wheels.items()}}
        layouts = {part: print_layout(part, mesh, _mode(cfg, part)) for part, mesh in named.items()}
        _write_kit(folder, layouts)
    except ImportError as e:
        print(e)
        print("Run this in the AI environment: tools/venv-gen/Scripts/python model_scripts/make_kit.py ...")
        return 1
    except Exception as e:          # one handler for every failure, so the user gets a message and not a traceback
        print(f"{type(e).__name__}: {e}" if not isinstance(e, (FileNotFoundError, ValueError)) else e)
        if folder.exists():
            print(f"NOTE: {folder} is from an earlier run and was NOT updated; do not print it for this body.")
        return 1
    print(f"Wrote {len(layouts)} parts to {folder}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
