"""Turn a generated body into the kit's body shell: sized to the real car, with a cavity for the chassis and
interior, wheel arches, open windows, and sockets for the chassis pins.

The body is scaled sideways to the real width measured below the mirrors, then cut around the parts that
kit_parts built, so the shell seats on the chassis without sanding. Needs the AI environment.
"""
from dataclasses import dataclass

import numpy as np

import kit_mesh
import kit_parts
import subject

WIDTH_BAND = (0.20, 0.42)    # share of body height where the width is measured, below the mirrors
ARCH_GAP = 1.0               # clearance between a tyre and its wheel arch, in print mm
WALL = 2.0                   # side wall thickness around the cabin cavity
ROOF_THICKNESS = 2.0
LIP_HEIGHT = 10.0            # block added above each chassis pin so it has material to seat in, reaching up into the body wall
LIP_HALF_LENGTH = 3.5
FIT_GAP = 0.3                # clearance between the body and the chassis pan or the interior
BIG = 1000.0                 # a cutter dimension large enough to pass through the whole body


@dataclass
class Conformed:
    shell: object
    scale: tuple             # (length, width, height) factors applied to the generated body
    measured_width: float    # width of the generated body below the mirrors, in its own units
    dropped_pieces: int      # small loose pieces the cuts left behind and that were discarded
    turned: bool = False     # True when the body was spun half a turn so its front faces -X


def _check_windows(windows):
    for name, start, end in windows:
        if not (0.0 <= start < end <= 1.0):
            raise ValueError(f"window '{name}' runs from {start} to {end} of the body length; "
                             "it must lie between 0 and 1 and start before it ends")


def _band_width(body, z0, hz):
    """Widest sideways extent of the body in slices through its lower band, and where that band is centred."""
    widths, centres = [], []
    for frac in np.linspace(WIDTH_BAND[0], WIDTH_BAND[1], 7):
        section = body.section(plane_origin=[0, 0, z0 + frac * hz], plane_normal=[0, 0, 1])
        if section is None:
            continue
        y = section.vertices[:, 1]
        widths.append(float(np.ptp(y)))
        centres.append(float(y.min() + y.max()) / 2)
    if not widths:
        raise ValueError("body: nothing found in the lower body band to measure the width from")
    return max(widths), float(np.mean(centres))


def _faces_plus_x(v):
    """True when the +X end looks like the front: an SUV's bonnet end is lower than its tail end."""
    span = np.ptp(v[:, 0])
    lo = v[v[:, 0] < v[:, 0].min() + 0.10 * span, 2].max()
    hi = v[v[:, 0] > v[:, 0].max() - 0.10 * span, 2].max()
    return hi < lo


def _scale_to_real(body, lay, front=None):
    import trimesh
    v = body.vertices.copy()
    turned = bool(_faces_plus_x(v)) if front is None else (front == "+x")
    if turned:                                     # half a turn about Z keeps the winding intact
        v[:, 0], v[:, 1] = -v[:, 0], -v[:, 1]
    z0, z1 = v[:, 2].min(), v[:, 2].max()
    hz = z1 - z0
    measured, cy = _band_width(trimesh.Trimesh(v, body.faces, process=False), z0, hz)
    sx = lay.length / float(np.ptp(v[:, 0]))
    sy = lay.width / measured
    sz = (lay.height - lay.pan_bottom) / hz
    cx = (v[:, 0].min() + v[:, 0].max()) / 2
    v = (v - np.array([cx, cy, z0])) * np.array([sx, sy, sz]) + np.array([0.0, 0.0, lay.pan_bottom])
    return trimesh.Trimesh(v, body.faces.copy(), process=False), (sx, sy, sz), measured, turned


def _greenhouse_cavity(scaled, lay, gx0, gx1):
    """The inside of the cabin: the body shrunk towards its floor, so the walls and roof keep an even thickness."""
    import trimesh
    zt = lay.pan_top
    shrink = trimesh.Trimesh(scaled.vertices.copy(), scaled.faces.copy(), process=False)
    v = shrink.vertices
    v[:, 1] *= (lay.width - 2 * WALL) / lay.width
    v[:, 2] = zt + (v[:, 2] - zt) * (lay.height - ROOF_THICKNESS - zt) / (lay.height - zt)
    shrink = trimesh.Trimesh(v, shrink.faces, process=False)
    window = kit_parts.box([gx1 - gx0, BIG, lay.height], [(gx0 + gx1) / 2, 0, zt + lay.height / 2])
    return kit_mesh.intersect(shrink, window, name="cabin cavity")


def conform_body(body, parts, subject_name, front=None):
    """Return the kit's body shell made from the solid `body`, fitted to `parts`.

    `front` is "+x" or "-x" for the end the generated body's front faces; by default it is detected.
    """
    lay = parts.layout
    kit = subject.kit_spec(subject_name)
    if front not in (None, "+x", "-x"):
        raise ValueError(f"front must be '+x' or '-x', not {front!r}")
    if not kit.windows:
        raise ValueError("the subject's kit block lists no windows; add at least one to cut the glass openings")
    _check_windows(kit.windows)
    scaled, scale, measured, turned = _scale_to_real(body, lay, front)

    hw, zb, zt = lay.pan_half_width, lay.pan_bottom, lay.pan_top
    half_w = lay.width / 2
    x0, x1 = lay.pan_x
    cav = []

    # the chassis pan, with a little room round it
    cav.append(kit_parts.box([x1 - x0 + 2 * FIT_GAP, 2 * (hw + FIT_GAP), zt + 1.0 - (zb - 1.0)],
                             [(x0 + x1) / 2, 0, ((zb - 1.0) + (zt + 1.0)) / 2]))
    # the interior, with room round it
    ib = parts.interior.bounds
    cav.append(kit_parts.box([ib[1][0] - ib[0][0] + 3.0, ib[1][1] - ib[0][1] + 3.0, ib[1][2] + 1.5 - zt],
                             [(ib[0][0] + ib[1][0]) / 2, (ib[0][1] + ib[1][1]) / 2, (zt + ib[1][2] + 1.5) / 2]))
    # the greenhouse, from the first window to the last
    win_lo = min(w[1] for w in kit.windows)
    win_hi = max(w[2] for w in kit.windows)
    gx0, gx1 = -lay.length / 2 + win_lo * lay.length - 1.5, -lay.length / 2 + win_hi * lay.length + 1.5
    cav.append(_greenhouse_cavity(scaled, lay, gx0, gx1))
    cavity = kit_mesh.union(*cav, name="cavity")
    shell = kit_mesh.subtract(scaled, cavity, name="body")

    # a lip above each chassis pin: the generated body's underside can sit well above the chassis edge
    lips = []
    for j in (j for j in parts.joints if j.kind == "pin"):
        sign = 1 if j.base[1] > 0 else -1
        y_in, y_out = hw - 3.5, half_w - WALL + 1.0
        lips.append(kit_parts.box([2 * LIP_HALF_LENGTH, y_out - y_in, LIP_HEIGHT],
                                  [j.base[0], sign * (y_in + y_out) / 2, zt + LIP_HEIGHT / 2]))
    shell = kit_mesh.union(shell, *lips, name="body")

    # open glass, straight through the body
    belt, roof = kit.beltline_height_fraction * lay.height, kit.roof_height_fraction * lay.height
    for name, start, end in kit.windows:
        a, b = -lay.length / 2 + start * lay.length, -lay.length / 2 + end * lay.length
        shell = kit_mesh.subtract(shell, kit_parts.box([b - a, BIG, roof - belt], [(a + b) / 2, 0, (belt + roof) / 2]), name=f"window {name}")

    # wheel arches: a cylinder round each wheel, from just inside the chassis edge outwards
    for name, (axle_x, sign) in _wheel_places(parts).items():
        start = np.array([axle_x, sign * (hw - kit_parts.BLOCK_DEPTH - FIT_GAP), lay.wheel_radius])
        shell = kit_mesh.subtract(shell, kit_parts.cylinder(lay.wheel_radius + ARCH_GAP, BIG, start, [0, sign, 0], 64), name=f"arch {name}")

    # sockets for the chassis pins
    for j in (j for j in parts.joints if j.kind == "pin"):
        shell = kit_mesh.subtract(shell, kit_parts.joint_socket(j), name=j.name)

    shell, dropped = _largest(shell)
    shell = kit_mesh.weld(shell)
    if not shell.is_volume:
        raise ValueError("body: the cut shell is not a closed solid")
    return Conformed(shell=shell, scale=scale, measured_width=measured, dropped_pieces=dropped, turned=turned)


def _wheel_places(parts):
    out = {}
    for j in (j for j in parts.joints if j.kind == "stub"):
        out[j.part] = (float(j.base[0]), 1 if j.base[1] > 0 else -1)
    return out


def _largest(mesh):
    pieces = mesh.split(only_watertight=False)
    if len(pieces) <= 1:
        return mesh, 0
    keep = max(pieces, key=lambda p: p.volume)
    return keep, len(pieces) - 1
