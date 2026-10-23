import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import kit_body  # noqa: E402
import kit_mesh  # noqa: E402
import kit_parts  # noqa: E402
import subject  # noqa: E402

PINS = None


def _stand_in_body(width_factor=1.25, size=100.0):
    """A boxy stand-in for a generated car (arbitrary units): a long lower box, a cabin, and two mirrors."""
    length, width, height = size, size * 0.45 * width_factor, size * 0.36
    lower = trimesh.creation.box(extents=[length, width, height * 0.5])
    lower.apply_translation([0, 0, height * 0.25])
    cabin = trimesh.creation.box(extents=[length * 0.55, width * 0.9, height * 0.5])
    cabin.apply_translation([length * 0.05, 0, height * 0.75])
    mirrors = []
    for sign in (-1, 1):
        m = trimesh.creation.box(extents=[length * 0.03, width * 0.14, height * 0.04])
        m.apply_translation([-length * 0.15, sign * (width / 2 + width * 0.07), height * 0.58])
        mirrors.append(m)
    return kit_mesh.union(lower, cabin, *mirrors, name="stand-in")


def _conform(body=None, subject_name="mini_countryman"):
    parts = kit_parts.build_parts(subject_name)
    return parts, kit_body.conform_body(body if body is not None else _stand_in_body(), parts, subject_name)


def _has_material(mesh, point, half=0.05):
    """True when the mesh has material at `point` (probed with a tiny box, so no ray-casting library is needed)."""
    probe = trimesh.creation.box(extents=[2 * half] * 3)
    probe.apply_translation(point)
    return kit_mesh.intersect(mesh, probe, name="probe").volume > 0.5 * probe.volume


def _band_width(mesh, lo, hi):
    v = mesh.vertices
    z0 = v[:, 2].min()
    h = v[:, 2].max() - z0
    sel = (v[:, 2] >= z0 + lo * h) & (v[:, 2] <= z0 + hi * h)
    return np.ptp(v[sel, 1])


def test_a_body_25_percent_too_wide_is_conformed_to_the_target_width_below_the_mirror():
    body = _stand_in_body(width_factor=1.25)
    parts, out = _conform(body)
    target = parts.layout.width
    lower = out.shell.vertices
    z = lower[:, 2]
    low_band = (z >= parts.layout.pan_top) & (z <= 0.40 * parts.layout.height)
    assert np.ptp(lower[low_band, 1]) == pytest.approx(target, rel=0.02)
    assert out.shell.extents[0] == pytest.approx(parts.layout.length, rel=0.02)
    assert out.shell.bounds[1][2] == pytest.approx(parts.layout.height, rel=0.02)


def test_the_shell_is_a_closed_solid_that_does_not_touch_any_other_part():
    parts, out = _conform()
    assert out.shell.is_volume
    others = [parts.chassis, parts.interior, *parts.wheels.values()]
    for other in others:
        assert kit_mesh.intersect(out.shell, other, name="fit").volume == pytest.approx(0, abs=1e-3)


def test_the_cabin_is_hollow_and_the_glass_openings_are_open():
    parts, out = _conform()
    lay = parts.layout
    inside_cabin = np.array([[lay.axle_x[1] * 0.3, 0.0, lay.pan_top + 8.0]])
    assert not _has_material(out.shell, inside_cabin[0])
    assert out.shell.volume < 0.6 * _stand_in_solid_volume(lay)


def _stand_in_solid_volume(lay):
    return lay.length * lay.width * lay.height


def test_each_body_pin_has_a_socket_with_the_clearance_around_it():
    parts, out = _conform()
    pins = [j for j in parts.joints if j.kind == "pin"]
    assert pins
    for j in pins:
        mid = j.base + j.axis * (j.length * 0.5)
        lateral = np.array([0.0, 1.0, 0.0])
        assert not _has_material(out.shell, mid + lateral * (j.pin_radius + j.clearance * 0.5))
        assert _has_material(out.shell, mid + lateral * (j.socket_radius + 0.3))


def test_a_body_already_at_the_right_size_is_scaled_by_one():
    lay = kit_parts.build_parts("mini_countryman").layout
    body = trimesh.creation.box(extents=[lay.length, lay.width, lay.height - lay.pan_bottom])
    body.apply_translation([0, 0, lay.pan_bottom + (lay.height - lay.pan_bottom) / 2])
    _, out = _conform(body)
    assert out.scale == pytest.approx((1.0, 1.0, 1.0), abs=0.01)


def test_a_window_outside_the_body_is_refused_and_named(tmp_path):
    f = tmp_path / "badwindow.yaml"
    base = open(subject.SUBJECTS / "mini_countryman.yaml", encoding="utf-8").read()
    f.write_text(base.replace("{name: rear_door, from: 0.55, to: 0.72}", "{name: rear_door, from: 0.55, to: 1.20}"), encoding="utf-8")
    parts = kit_parts.build_parts(str(f))
    with pytest.raises(ValueError, match="rear_door"):
        kit_body.conform_body(_stand_in_body(), parts, str(f))


def _with_tall_tail(tail_at):
    """A stand-in with a tall tail block at one end, the way an SUV's rear is taller than its bonnet."""
    body = _stand_in_body()
    sign = -1 if tail_at == "-x" else 1
    tail = trimesh.creation.box(extents=[10.0, 30.0, 40.0])
    tail.apply_translation([sign * 45.0, 0, 20.0])
    return kit_mesh.union(body, tail, name="tailed")


@pytest.mark.parametrize("tail_at", ["-x", "+x"])
def test_the_body_is_turned_so_its_taller_tail_is_at_plus_x(tail_at):
    parts, out = _conform(_with_tall_tail(tail_at))
    v = out.shell.vertices
    length = parts.layout.length
    rear_top = v[v[:, 0] > 0.40 * length, 2].max()
    front_top = v[v[:, 0] < -0.40 * length, 2].max()
    assert rear_top > front_top
    assert out.turned == (tail_at == "-x")


def test_an_explicit_front_overrides_the_detection():
    parts = kit_parts.build_parts("mini_countryman")
    out = kit_body.conform_body(_with_tall_tail("-x"), parts, "mini_countryman", front="-x")
    assert out.turned is False


def test_the_roof_and_pillars_stay_attached_to_the_shell():
    parts, out = _conform()
    assert out.dropped_pieces <= 2                     # at most the two mirrors, which the glass openings cut loose
    lay = parts.layout
    cabin_x = lay.length * 0.05                       # the stand-in's cabin centre, scaled with the body
    assert _has_material(out.shell, [cabin_x, 0.0, lay.height - 0.6])
