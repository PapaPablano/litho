"""Check, before anything is printed, that the kit's parts fit together.

Reports: every part is a closed solid that passes the existing mesh check, no two parts overlap, every
joint has a socket with the intended gap, the assembled size is within tolerance of the real car, and every
part fits the printer bed. check_kit returns a KitReport; exit_code is 0 when everything passes and 2 when not.
Needs the AI environment.
"""
import itertools
import os
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "print_prep"))

import check_mesh  # noqa: E402
import kit_mesh  # noqa: E402
import subject  # noqa: E402

OVERLAP_TOLERANCE = 0.05     # mm^3 shared between two parts before they count as overlapping
SOCKET_SEARCH = 2.0          # how far beyond the pin a socket wall may sit and still be found, in mm
WIDTH_BAND_TOP = 0.40        # share of overall height below which the width is measured (clear of the mirrors)


@dataclass
class KitReport:
    problems: list = field(default_factory=list)
    overlaps: dict = field(default_factory=dict)      # "a/b" -> shared volume in mm^3
    gaps: dict = field(default_factory=dict)          # joint name -> measured gap in mm
    size: dict = field(default_factory=dict)          # length/width/height -> (target, measured, error %)

    @property
    def ok(self):
        return not self.problems

    @property
    def exit_code(self):
        return 0 if self.ok else 2

    def lines(self):
        out = []
        for name, (target, measured, error) in self.size.items():
            out.append(f"{name:<8}{target:>9.2f}{measured:>9.2f}{error:>+8.1f}%")
        out.extend(f"PROBLEM: {p}" for p in self.problems)
        out.append("Kit fits." if self.ok else "Kit does NOT fit; fix the problems above before printing.")
        return out


def _named_parts(parts, shell):
    return {"body": shell, "chassis": parts.chassis, "interior": parts.interior, **parts.wheels}


def _mesh_check(name, mesh, problems):
    if not mesh.is_volume:
        problems.append(f"{name}: not a closed solid")
        return
    fd, path = tempfile.mkstemp(suffix=".stl")
    os.close(fd)
    try:
        mesh.export(path)
        report = check_mesh.analyze(path)
    finally:
        os.unlink(path)
    if report["open_edges"] or report["flipped_edges"]:
        problems.append(f"{name}: fails the mesh check ({report['open_edges']} open edges, {report['flipped_edges']} reversed)")


def _gap(joint, mating):
    """Measured gap between a joint's pin and the nearest socket wall, or None when there is no socket."""
    v = mating.vertices - joint.base
    along = v @ joint.axis
    radial = np.linalg.norm(v - np.outer(along, joint.axis), axis=1)
    near = (along >= -0.2) & (along <= joint.length + 0.01) & (radial < joint.pin_radius + SOCKET_SEARCH)
    if not near.any():
        return None
    return float(radial[near].min() - joint.pin_radius)


def _size(parts, shell, name, report, tolerance):
    lay = parts.layout
    t = subject.targets(name, denominator=lay.scale)
    meshes = [shell, parts.chassis, parts.interior, *parts.wheels.values()]
    lo = np.min([m.bounds[0] for m in meshes], axis=0)
    hi = np.max([m.bounds[1] for m in meshes], axis=0)
    v = shell.vertices
    low = (v[:, 2] >= lay.pan_top) & (v[:, 2] <= WIDTH_BAND_TOP * hi[2])
    width = float(np.ptp(v[low, 1])) if low.any() else float(hi[1] - lo[1])
    measured = {"length": float(hi[0] - lo[0]), "width": width, "height": float(hi[2] - max(lo[2], 0.0))}
    for axis, target in zip(("length", "width", "height"), t.print_mm):
        error = (measured[axis] - target) / target * 100
        report.size[axis] = (target, measured[axis], error)
        if abs(error) > tolerance:
            report.problems.append(f"{axis}: {measured[axis]:.2f} mm against {target:.2f} mm ({error:+.1f}%)")


def check_kit(parts, shell, subject_name, bed_mm=None, check_overlaps=True):
    """Check that `parts` and the body `shell` fit together and fit the printer."""
    report = KitReport()
    cfg = subject.kit_config()
    bed = cfg.bed_mm if bed_mm is None else bed_mm
    tolerance = subject.targets(subject_name, denominator=parts.layout.scale).tolerance_pct
    named = _named_parts(parts, shell)

    for name, mesh in named.items():
        _mesh_check(name, mesh, report.problems)
        if float(np.max(mesh.extents)) > bed:
            report.problems.append(f"{name}: {float(np.max(mesh.extents)):.0f} mm does not fit the {bed:.0f} mm bed in any orientation")

    if check_overlaps:
        for (a, ma), (b, mb) in itertools.combinations(named.items(), 2):
            if not (ma.is_volume and mb.is_volume):
                continue
            if np.any(ma.bounds[1] < mb.bounds[0]) or np.any(mb.bounds[1] < ma.bounds[0]):
                continue
            try:
                shared = kit_mesh.overlap_volume(ma, mb)
            except Exception as e:                      # keep the report the single failure channel
                report.problems.append(f"{a} and {b}: could not measure the overlap ({e})")
                continue
            if shared > OVERLAP_TOLERANCE:
                report.overlaps[f"{a}/{b}"] = shared
                report.problems.append(f"{a} and {b} overlap by {shared:.2f} mm^3")

    for joint in parts.joints:
        gap = _gap(joint, named[joint.part])
        if gap is None:
            report.problems.append(f"{joint.name}: no socket found in {joint.part}")
            continue
        report.gaps[joint.name] = gap
        if gap < min(0.05, joint.clearance / 2):
            report.problems.append(f"{joint.name}: gap {gap:.2f} mm is tighter than the {joint.clearance:.2f} mm clearance")

    _size(parts, shell, subject_name, report, tolerance)
    return report
