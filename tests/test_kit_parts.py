import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import check_mesh  # noqa: E402
import kit_mesh  # noqa: E402
import kit_parts  # noqa: E402
import subject  # noqa: E402


def _build(**kw):
    return kit_parts.build_parts("mini_countryman", **kw)


def _all_parts(parts):
    return {"chassis": parts.chassis, "interior": parts.interior, **parts.wheels}


def test_every_part_is_a_closed_solid_the_mesh_check_accepts(tmp_path):
    for name, mesh in _all_parts(_build()).items():
        assert mesh.is_volume, name
        path = tmp_path / f"{name}.stl"
        mesh.export(str(path))
        report = check_mesh.analyze(str(path))
        assert report["open_edges"] == 0 and report["flipped_edges"] == 0, name


def test_parts_are_at_1_to_24_in_the_assembled_frame():
    parts = _build()
    t = subject.targets("mini_countryman", denominator=24)
    wheel_z = [w.bounds[0][2] for w in parts.wheels.values()]
    assert all(z == pytest.approx(0, abs=0.05) for z in wheel_z)          # tyres stand on the ground plane
    assert parts.chassis.extents[0] < t.print_mm[0]
    assert set(parts.wheels) == {"front_left", "front_right", "rear_left", "rear_right"}


def test_both_wheel_styles_fit_the_same_chassis_stub_without_changing_the_chassis():
    disc, spoke = _build(wheel_style="disc"), _build(wheel_style="spoke5")
    assert disc.chassis.volume == pytest.approx(spoke.chassis.volume)
    assert np.allclose(disc.chassis.bounds, spoke.chassis.bounds)
    for parts in (disc, spoke):
        for joint in [j for j in parts.joints if j.kind == "stub"]:
            stub = kit_parts.joint_pin(joint)
            wheel = parts.wheels[joint.part]
            assert kit_mesh.intersect(wheel, stub, name="fit").volume == pytest.approx(0, abs=1e-6)
    assert disc.wheels["front_left"].volume != pytest.approx(spoke.wheels["front_left"].volume)


def test_raising_the_clearance_widens_every_socket_and_leaves_every_pin_unchanged():
    small, large = _build(clearance_mm=0.15), _build(clearance_mm=0.30)
    assert small.chassis.volume == pytest.approx(large.chassis.volume)
    for a, b in zip(small.joints, large.joints):
        assert b.socket_radius > a.socket_radius
        assert a.pin_radius == pytest.approx(b.pin_radius)
    assert large.wheels["front_left"].volume < small.wheels["front_left"].volume


def test_a_per_joint_override_changes_only_that_joint():
    base = _build(clearance_mm=0.15)
    over = _build(clearance_mm=0.15, overrides={"stub_front_left": 0.40})
    radii = {j.name: (j.socket_radius, k.socket_radius) for j, k in zip(base.joints, over.joints)}
    changed = [n for n, (a, b) in radii.items() if abs(a - b) > 1e-9]
    assert changed == ["stub_front_left"]
    assert over.wheels["front_left"].volume < base.wheels["front_left"].volume
    assert over.wheels["rear_right"].volume == pytest.approx(base.wheels["rear_right"].volume)


def test_a_track_wider_than_the_body_is_refused_before_any_part_is_built(tmp_path):
    f = tmp_path / "wide.yaml"
    f.write_text(
        "length_mm: 4440\nwidth_mm: 1700\nheight_mm: 1648\nkit:\n  track_front_mm: 1575\n  track_rear_mm: 1575\n"
        "  wheel_diameter_mm: 705\n  tyre_width_mm: 225\n  ground_clearance_mm: 165\n  front_overhang_mm: 868\n"
        "  rear_overhang_mm: 884\n  beltline_height_fraction: 0.58\n  roof_height_fraction: 0.94\n",
        encoding="utf-8")
    with pytest.raises(ValueError, match="track"):
        kit_parts.build_parts(str(f))
