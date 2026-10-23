import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import kit_body  # noqa: E402
import kit_check  # noqa: E402
import kit_parts  # noqa: E402
from test_kit_body import _stand_in_body  # noqa: E402


@pytest.fixture(scope="module")
def kit():
    parts = kit_parts.build_parts("mini_countryman")
    shell = kit_body.conform_body(_stand_in_body(), parts, "mini_countryman").shell
    return parts, shell


def _copy(parts):
    return kit_parts.KitParts(
        chassis=parts.chassis.copy(), interior=parts.interior.copy(),
        wheels={n: w.copy() for n, w in parts.wheels.items()}, joints=parts.joints,
        layout=parts.layout, wheel_style=parts.wheel_style)


def test_a_correctly_built_kit_passes_and_every_gap_equals_the_clearance(kit):
    parts, shell = kit
    report = kit_check.check_kit(parts, shell, "mini_countryman")
    assert report.ok, report.problems
    assert report.exit_code == 0
    for joint in parts.joints:
        assert report.gaps[joint.name] == pytest.approx(joint.clearance, abs=0.02)


def test_the_assembled_size_is_within_two_percent_of_the_real_car(kit):
    parts, shell = kit
    report = kit_check.check_kit(parts, shell, "mini_countryman")
    for name in ("length", "width", "height"):
        target, measured, error = report.size[name]
        assert abs(error) <= 2.0, (name, target, measured)


def test_a_chassis_shifted_into_the_body_reports_an_overlap_and_fails(kit):
    parts, shell = kit
    moved = _copy(parts)
    moved.chassis.apply_translation([0.0, 0.3, 0.0])
    report = kit_check.check_kit(moved, shell, "mini_countryman")
    assert not report.ok
    assert report.exit_code == 2
    assert any("chassis" in p and "overlap" in p for p in report.problems)


def test_a_part_bigger_than_the_bed_fails_naming_the_part(kit):
    parts, shell = kit
    big = _copy(parts)
    big.chassis.apply_scale(3.0)
    report = kit_check.check_kit(big, shell, "mini_countryman", check_overlaps=False)
    assert any("chassis" in p and "bed" in p for p in report.problems)


def test_a_part_that_is_not_a_closed_solid_fails_naming_the_part(kit):
    parts, shell = kit
    broken = _copy(parts)
    broken.interior.update_faces(np.arange(len(broken.interior.faces)) != 0)
    report = kit_check.check_kit(broken, shell, "mini_countryman", check_overlaps=False)
    assert any("interior" in p and "closed" in p for p in report.problems)


def test_a_missing_socket_is_reported(kit):
    parts, shell = kit
    solid_body = _stand_in_body()                      # no sockets cut in it
    report = kit_check.check_kit(parts, solid_body, "mini_countryman", check_overlaps=False)
    assert any("socket" in p for p in report.problems)
