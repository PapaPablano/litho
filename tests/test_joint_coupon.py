import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import joint_coupon  # noqa: E402
import kit_mesh  # noqa: E402
import subject  # noqa: E402


def test_the_coupon_has_one_pin_and_socket_joint_per_clearance_step_and_is_two_solids():
    c = joint_coupon.build_coupon(steps=5)
    assert len(c.clearances) == 5
    assert len(c.joints) == 10                       # a body-pin joint and a wheel-stub joint at every step
    assert c.pins.is_volume and c.sockets.is_volume
    assert len(c.mesh.split(only_watertight=False)) == 2


def test_the_clearance_range_is_centred_on_the_configured_value_and_stays_positive():
    c = joint_coupon.build_coupon(steps=5, step_mm=0.05)
    centre = subject.kit_config().joint_clearance_mm
    assert c.clearances[2] == pytest.approx(centre)
    assert min(c.clearances) > 0
    assert c.clearances == sorted(c.clearances)


def test_pressed_together_the_two_plates_do_not_overlap_at_any_step():
    c = joint_coupon.build_coupon(steps=5)
    mated = c.pins_mated()
    assert mated.bounds[0][2] < joint_coupon.SOCKET_PLATE_THICKNESS - 2.0        # the pins really go into the sockets
    assert kit_mesh.overlap_volume(mated, c.sockets) == pytest.approx(0, abs=1e-6)


def test_a_pin_pressed_in_with_too_little_clearance_would_collide():
    c = joint_coupon.build_coupon(steps=5)
    squeezed = c.pins_mated()
    squeezed.apply_translation([0.0, 0.4, 0.0])                                    # 0.4 mm sideways exceeds every step
    assert kit_mesh.overlap_volume(squeezed, c.sockets) > 0


def test_fewer_than_two_steps_is_refused():
    with pytest.raises(ValueError, match="steps"):
        joint_coupon.build_coupon(steps=1)


def test_a_range_that_would_reach_zero_clearance_is_refused():
    with pytest.raises(ValueError, match="clearance"):
        joint_coupon.build_coupon(clearance_mm=0.05, steps=5, step_mm=0.05)
