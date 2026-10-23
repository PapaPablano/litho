"""Generate the car kit parts that never come from photos: chassis, wheels and interior, with their joints.

Everything is built in the assembled frame: origin on the ground plane under the car's centre, X length
(front toward -X), Y width (left toward -Y), Z up, in print mm at the chosen scale. Joint sizes are in print
mm and do not scale with the car, because a 0.4 mm nozzle sets the smallest sensible pin. Needs the AI
environment (trimesh, manifold3d).
"""
from dataclasses import dataclass

import numpy as np

import kit_mesh
import subject

WHEEL_NAMES = ("front_left", "front_right", "rear_left", "rear_right")
WHEEL_STYLES = ("disc", "spoke5")

# joint and part sizes in print mm
STUB_RADIUS = 2.0
MIN_STUB_LENGTH = 2.5
PAN_THICKNESS = 2.0
BLOCK_DEPTH = 3.0           # how far an axle block reaches in from the chassis edge
BODY_PIN_RADIUS = 1.0
BODY_PIN_HEIGHT = 3.0
POST_PIN_RADIUS = 1.2
POST_PIN_HEIGHT = 1.0       # the part of a post that enters the interior floor
POST_SHOULDER_RADIUS = 2.2
POST_SHOULDER_HEIGHT = 2.0  # the floor rests on this
FLOOR_THICKNESS = 1.2
EPS = 0.1                   # overlap that keeps unioned parts one solid


@dataclass(frozen=True)
class Joint:
    """A pin on one part that seats in a socket on another."""
    name: str
    kind: str                # "stub" (wheel), "pin" (body) or "post" (interior)
    part: str                # the part that carries the socket
    base: np.ndarray         # centre of the pin's base
    axis: np.ndarray         # unit vector along the pin, base to tip
    length: float
    pin_radius: float
    clearance: float

    @property
    def socket_radius(self):
        return self.pin_radius + self.clearance


@dataclass(frozen=True)
class Layout:
    scale: float
    length: float
    width: float
    height: float
    axle_x: tuple            # (front, rear)
    wheel_radius: float
    tyre_width: float
    track: tuple             # (front, rear)
    pan_half_width: float
    pan_x: tuple             # (min, max)
    pan_bottom: float
    pan_top: float
    floor_bottom: float


@dataclass
class KitParts:
    chassis: object
    interior: object
    wheels: dict
    joints: list
    layout: Layout
    wheel_style: str


def _cylinder(radius, length, start, axis, sections=32):
    """A solid cylinder whose base centre is `start` and which runs `length` along `axis`."""
    import trimesh
    axis = np.asarray(axis, dtype=float)
    axis = axis / np.linalg.norm(axis)
    cyl = trimesh.creation.cylinder(radius=radius, height=length, sections=sections)
    cyl.apply_transform(trimesh.geometry.align_vectors([0, 0, 1], axis))
    cyl.apply_translation(np.asarray(start, dtype=float) + axis * length / 2)
    return cyl


def _box(extents, center):
    import trimesh
    b = trimesh.creation.box(extents=extents)
    b.apply_translation(center)
    return b


def joint_pin(joint):
    """The solid pin of a joint."""
    return _cylinder(joint.pin_radius, joint.length, joint.base, joint.axis)


def joint_socket(joint):
    """The hole that receives a joint's pin, cut slightly deeper than the pin is long."""
    return _cylinder(joint.socket_radius, joint.length + joint.clearance, joint.base, joint.axis)


def _layout(name, scale):
    t = subject.targets(name, denominator=scale)
    k = subject.kit_spec(name)
    length, width, height = t.print_mm
    tyre_w = k.tyre_width_mm / scale
    track = (k.track_front_mm / scale, k.track_rear_mm / scale)
    if max(track) + tyre_w > width:
        raise ValueError(
            f"track {max(track):.1f} mm plus tyre {tyre_w:.1f} mm is wider than the body ({width:.1f} mm); "
            "check the track and tyre values in the subject file")
    radius = k.wheel_diameter_mm / 2 / scale
    front_x = -length / 2 + k.front_overhang_mm / scale
    rear_x = length / 2 - k.rear_overhang_mm / scale
    inner = min(track) / 2 - tyre_w / 2
    pan_hw = inner - MIN_STUB_LENGTH
    pan_bottom = k.ground_clearance_mm / scale
    pan_top = pan_bottom + PAN_THICKNESS
    return Layout(
        scale=scale, length=length, width=width, height=height, axle_x=(front_x, rear_x), wheel_radius=radius,
        tyre_width=tyre_w, track=track, pan_half_width=pan_hw, pan_x=(front_x - 6.0, rear_x + 6.0),
        pan_bottom=pan_bottom, pan_top=pan_top, floor_bottom=pan_top + POST_SHOULDER_HEIGHT - 0.0,
    )


def _wheel(style, radius, width, socket_radius, socket_depth):
    """A wheel centred on the origin, axle along +Y, with its hub socket opening on the -Y (inner) face."""
    wheel = _cylinder(radius, width, [0, -width / 2, 0], [0, 1, 0], sections=64)
    rim_radius, rim_depth = radius * 0.62, 0.8
    outer_face = width / 2
    wheel = kit_mesh.subtract(wheel, _cylinder(rim_radius, rim_depth + EPS, [0, outer_face - rim_depth, 0], [0, 1, 0], 64), "wheel")
    if style == "spoke5":
        for i in range(5):
            a = 2 * np.pi * i / 5
            c = [0.40 * radius * np.cos(a), outer_face - rim_depth - 1.0, 0.40 * radius * np.sin(a)]
            wheel = kit_mesh.subtract(wheel, _cylinder(0.17 * radius, 1.0 + EPS, c, [0, 1, 0], 24), "wheel")
    elif style != "disc":
        raise ValueError(f"unknown wheel style '{style}'; choose from {', '.join(WHEEL_STYLES)}")
    return kit_mesh.subtract(wheel, _cylinder(socket_radius, socket_depth + EPS, [0, -width / 2 - EPS, 0], [0, 1, 0], 32), "wheel")


def build_parts(subject_name, scale=None, wheel_style="disc", clearance_mm=None, overrides=None):
    """Build the chassis, four wheels and interior for a subject at `scale`, with joint clearances applied."""
    cfg = subject.kit_config()
    scale = float(scale or cfg.scale_denominator)
    clearance = cfg.joint_clearance_mm if clearance_mm is None else float(clearance_mm)
    overrides = dict(overrides or {})
    lay = _layout(subject_name, scale)

    def gap(name):
        return float(overrides.get(name, clearance))

    joints, pieces = [], []
    hw, zb, zt = lay.pan_half_width, lay.pan_bottom, lay.pan_top
    x0, x1 = lay.pan_x
    pieces.append(_box([x1 - x0, 2 * hw, PAN_THICKNESS], [(x0 + x1) / 2, 0, (zb + zt) / 2]))

    wheel_pos = {}
    for axle, x in zip(("front", "rear"), lay.axle_x):
        for side, sign in (("left", -1), ("right", 1)):
            name = f"{axle}_{side}"
            track = lay.track[0] if axle == "front" else lay.track[1]
            inner = track / 2 - lay.tyre_width / 2
            stub_len = inner - hw
            top = lay.wheel_radius + STUB_RADIUS + 1.0
            pieces.append(_box([2 * (STUB_RADIUS + 1.5), BLOCK_DEPTH, top - zb],
                               [x, sign * (hw - BLOCK_DEPTH / 2 + EPS), (zb + top) / 2]))
            pieces.append(_cylinder(STUB_RADIUS, stub_len + EPS, [x, sign * (hw - EPS), lay.wheel_radius], [0, sign, 0]))
            joints.append(Joint(f"stub_{name}", "stub", name, np.array([x, sign * hw, lay.wheel_radius]),
                                np.array([0.0, sign, 0.0]), stub_len, STUB_RADIUS, gap(f"stub_{name}")))
            wheel_pos[name] = (x, sign * track / 2, sign)

    span = lay.axle_x[1] - lay.axle_x[0]
    pin_x = (lay.axle_x[0] + 0.25 * span, lay.axle_x[1] - 0.25 * span)
    for i, x in enumerate(pin_x):
        for j, sign in enumerate((-1, 1)):
            base = np.array([x, sign * (hw - 1.5), zt])
            pieces.append(_cylinder(BODY_PIN_RADIUS, BODY_PIN_HEIGHT + EPS, base - [0, 0, EPS], [0, 0, 1]))
            joints.append(Joint(f"pin_{i}_{j}", "pin", "body", base, np.array([0.0, 0.0, 1.0]),
                                BODY_PIN_HEIGHT, BODY_PIN_RADIUS, gap(f"pin_{i}_{j}")))

    post_x = (lay.axle_x[0] + 0.12 * span, lay.axle_x[1] - 0.12 * span)
    post_y = 0.45 * hw
    for i, x in enumerate(post_x):
        for j, sign in enumerate((-1, 1)):
            base = np.array([x, sign * post_y, zt + POST_SHOULDER_HEIGHT])
            pieces.append(_cylinder(POST_SHOULDER_RADIUS, POST_SHOULDER_HEIGHT + EPS, [x, sign * post_y, zt - EPS], [0, 0, 1]))
            pieces.append(_cylinder(POST_PIN_RADIUS, POST_PIN_HEIGHT + EPS, base - [0, 0, EPS], [0, 0, 1]))
            joints.append(Joint(f"post_{i}_{j}", "post", "interior", base, np.array([0.0, 0.0, 1.0]),
                                POST_PIN_HEIGHT, POST_PIN_RADIUS, gap(f"post_{i}_{j}")))

    chassis = kit_mesh.union(*pieces, name="chassis")

    wheels = {}
    for name, (x, y, sign) in wheel_pos.items():
        joint = next(j for j in joints if j.name == f"stub_{name}")
        w = _wheel(wheel_style, lay.wheel_radius, lay.tyre_width, joint.socket_radius, joint.length + joint.clearance)
        if sign < 0:
            import trimesh
            w.apply_transform(trimesh.transformations.rotation_matrix(np.pi, [0, 0, 1]))
        w.apply_translation([x, y, lay.wheel_radius])
        wheels[name] = w

    interior = _interior(lay, [j for j in joints if j.kind == "post"])
    return KitParts(chassis=chassis, interior=interior, wheels=wheels, joints=joints, layout=lay, wheel_style=wheel_style)


def _interior(lay, posts):
    """Floor, two front seats, a rear bench and a dashboard, as one solid with sockets for the chassis posts."""
    s = lay.scale
    fx0, fx1 = lay.axle_x[0] + 0.05 * (lay.axle_x[1] - lay.axle_x[0]), lay.axle_x[1] - 0.05 * (lay.axle_x[1] - lay.axle_x[0])
    half = lay.pan_half_width * 0.8
    z0 = lay.floor_bottom
    z1 = z0 + FLOOR_THICKNESS
    parts = [_box([fx1 - fx0, 2 * half, FLOOR_THICKNESS], [(fx0 + fx1) / 2, 0, (z0 + z1) / 2])]
    seat_w, seat_d, seat_h, back_h = 380 / s, 420 / s, 120 / s, 480 / s
    seat_x = fx0 + 0.34 * (fx1 - fx0)
    for sign in (-1, 1):
        parts.append(_box([seat_d, seat_w, seat_h], [seat_x, sign * 0.115 * lay.width, z1 + seat_h / 2 - EPS]))
        parts.append(_box([100 / s, seat_w, back_h], [seat_x + seat_d / 2 + 50 / s - EPS, sign * 0.115 * lay.width, z1 + back_h / 2 - EPS]))
    bench_w = min(2 * half - 2.0, 1000 / s)
    bench_x = fx0 + 0.74 * (fx1 - fx0)
    parts.append(_box([450 / s, bench_w, seat_h], [bench_x, 0, z1 + seat_h / 2 - EPS]))
    parts.append(_box([100 / s, bench_w, back_h], [bench_x + 225 / s + 50 / s - EPS, 0, z1 + back_h / 2 - EPS]))
    parts.append(_box([300 / s, 2 * half - 2.0, 250 / s], [fx0 + 150 / s, 0, z1 + 125 / s - EPS]))
    interior = kit_mesh.union(*parts, name="interior")
    for joint in posts:
        bore = _cylinder(joint.socket_radius, joint.length + joint.clearance + EPS, joint.base - [0, 0, EPS], [0, 0, 1])
        interior = kit_mesh.subtract(interior, bore, "interior")
    return interior


# shared with kit_body, which cuts the body around these parts
cylinder, box = _cylinder, _box
