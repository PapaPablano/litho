"""A small test print that shows which joint clearance seats cleanly on your printer.

Makes two plates in one STL: one carries pins, the other carries matching sockets, repeated at stepped
clearances around the configured value. Print it, press the plates together, and note the smallest step that
seats without force or sanding. Needs the AI environment.

Usage: python joint_coupon.py [--steps 5] [--step-mm 0.05] [--clearance 0.15] [--out models/kit/joint_coupon.stl]
"""
import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

import kit_mesh  # noqa: E402
import kit_parts  # noqa: E402
import subject  # noqa: E402

PITCH = 10.0              # spacing between steps along the plate
ROW_GAP = 8.0             # spacing between the pin row and the stub row
PLATE_PAD = 4.0           # plate margin round the joints
PIN_PLATE_THICKNESS = 2.0
SOCKET_PLATE_THICKNESS = 6.0
EPS = kit_parts.EPS


@dataclass
class Coupon:
    pins: object
    sockets: object
    clearances: list
    joints: list             # (kind, step index, pin radius, clearance)
    plate_offset_y: float    # how far the socket plate sits from the pin plate as laid out for printing

    @property
    def mesh(self):
        """Both plates as one printable mesh, side by side."""
        import trimesh
        return trimesh.util.concatenate([self.pins, self.sockets])

    def pins_mated(self):
        """The pin plate turned over and pressed onto the socket plate, to check the fit."""
        import trimesh
        out = self.pins.copy()
        length = float(out.bounds[1][0])
        out.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 1, 0]))     # flip, keeping the rows' sides
        # after the flip the plate face the pins grew from is at z = -thickness; seat that face on the socket plate's top
        out.apply_translation([length, self.plate_offset_y, SOCKET_PLATE_THICKNESS + PIN_PLATE_THICKNESS])
        return out


def build_coupon(clearance_mm=None, steps=5, step_mm=0.05):
    """Two plates with pins and sockets at `steps` clearances centred on `clearance_mm`."""
    import trimesh
    if steps < 2:
        raise ValueError("steps must be at least 2 to compare clearances")
    centre = subject.kit_config().joint_clearance_mm if clearance_mm is None else float(clearance_mm)
    clearances = [centre + (i - (steps - 1) / 2) * step_mm for i in range(steps)]
    if min(clearances) <= 0:
        raise ValueError(f"clearance range {min(clearances):.2f} to {max(clearances):.2f} mm reaches zero; "
                         "raise the centre value or lower the step")
    width = 2 * ROW_GAP + 2 * PLATE_PAD
    length = (steps - 1) * PITCH + 2 * PLATE_PAD + 4.0
    rows = {"pin": (-ROW_GAP / 2, kit_parts.BODY_PIN_RADIUS, kit_parts.BODY_PIN_HEIGHT),
            "stub": (ROW_GAP / 2, kit_parts.STUB_RADIUS, kit_parts.MIN_STUB_LENGTH)}

    pins = [kit_parts.box([length, width, PIN_PLATE_THICKNESS], [length / 2, 0, PIN_PLATE_THICKNESS / 2])]
    sockets = kit_parts.box([length, width, SOCKET_PLATE_THICKNESS], [length / 2, 0, SOCKET_PLATE_THICKNESS / 2])
    joints = []
    for i, c in enumerate(clearances):
        x = PLATE_PAD + 2.0 + i * PITCH
        for kind, (y, r, h) in rows.items():
            pins.append(kit_parts.cylinder(r, h + EPS, [x, y, PIN_PLATE_THICKNESS - EPS], [0, 0, 1]))
            hole = kit_parts.cylinder(r + c, h + c + EPS, [x, y, SOCKET_PLATE_THICKNESS - h - c], [0, 0, 1])
            sockets = kit_mesh.subtract(sockets, hole, name="coupon")
            joints.append((kind, i, r, c))
        # one more notch on the front edge for every step, so the steps can be told apart after printing
        for n in range(i + 1):
            notch = kit_parts.box([1.0, 1.6, 1.0], [x - 2.0 + n * 1.6, -width / 2 + 0.4, SOCKET_PLATE_THICKNESS - 0.4])
            sockets = kit_mesh.subtract(sockets, notch, name="coupon")
    pin_plate = kit_mesh.union(*pins, name="coupon")
    offset = width + 6.0
    sockets.apply_translation([0, offset, 0])
    return Coupon(pins=pin_plate, sockets=sockets, clearances=clearances, joints=joints, plate_offset_y=offset)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--steps", type=int, default=5)
    p.add_argument("--step-mm", type=float, default=0.05)
    p.add_argument("--clearance", type=float, help="centre clearance in mm; default from config.yaml")
    p.add_argument("--out", default=str(ROOT / "models" / "kit" / "joint_coupon.stl"))
    a = p.parse_args(argv)
    try:
        coupon = build_coupon(a.clearance, a.steps, a.step_mm)
    except ValueError as e:
        print(e)
        return 1
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    coupon.mesh.export(str(out))
    print(f"Wrote {out}")
    print("Steps, from the one-notch end: " + ", ".join(f"{i + 1} notch{'es' if i else ''} = {c:.2f} mm" for i, c in enumerate(coupon.clearances)))
    print("Print it, press the pin plate onto the socket plate, and set the smallest clearance that seats without force "
          "as joint_clearance_mm in config.yaml.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
