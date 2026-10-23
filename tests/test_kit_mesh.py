import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import kit_mesh  # noqa: E402


def _box(extents, center=(0, 0, 0)):
    b = trimesh.creation.box(extents=extents)
    b.apply_translation(center)
    return b


def test_subtracting_a_small_box_leaves_a_watertight_solid_with_less_volume():
    big, hole = _box((10, 10, 10)), _box((2, 2, 2), center=(5, 0, 0))
    out = kit_mesh.subtract(big, hole, name="body")
    assert out.is_volume
    assert out.volume < big.volume


def test_subtracting_a_box_that_does_not_touch_returns_the_same_volume():
    big, far = _box((10, 10, 10)), _box((1, 1, 1), center=(50, 0, 0))
    out = kit_mesh.subtract(big, far, name="body")
    assert out.volume == pytest.approx(big.volume)


def test_union_and_intersection_of_overlapping_boxes():
    a, b = _box((10, 10, 10)), _box((10, 10, 10), center=(5, 0, 0))
    assert kit_mesh.union(a, b, name="x").volume == pytest.approx(1500)
    assert kit_mesh.intersect(a, b, name="x").volume == pytest.approx(500)


def test_thinning_a_dense_sphere_keeps_its_volume_within_two_percent():
    s = trimesh.creation.icosphere(subdivisions=6, radius=10)
    out = kit_mesh.thin(s, target_faces=5000)
    assert len(out.faces) <= 5500
    assert out.volume == pytest.approx(s.volume, rel=0.02)


def test_a_flipped_face_is_repaired_into_a_usable_solid():
    s = trimesh.creation.icosphere(subdivisions=3, radius=10)
    s.faces[0] = s.faces[0][::-1]                  # one reversed triangle: closed but inconsistent winding
    assert not s.is_volume
    assert kit_mesh.make_solid(s, name="body").is_volume


def test_a_missing_face_is_repaired():
    b = _box((10, 10, 10))
    b.update_faces(np.arange(len(b.faces)) != 0)
    assert not b.is_watertight
    assert kit_mesh.make_solid(b, name="body").is_volume


def test_an_unrepairable_mesh_raises_an_error_naming_the_part():
    junk = trimesh.Trimesh(vertices=np.random.default_rng(0).random((30, 3)), faces=[[0, 1, 2]], process=False)
    with pytest.raises(ValueError, match="chassis"):
        kit_mesh.make_solid(junk, name="chassis")


def test_loading_an_stl_keeps_only_real_parts_and_returns_a_solid(tmp_path):
    body = _box((100, 40, 30))
    speck = _box((1, 1, 1), center=(200, 0, 0))
    path = tmp_path / "body.stl"
    trimesh.util.concatenate([body, speck]).export(str(path))
    out = kit_mesh.load_solid(path, name="body")
    assert out.is_volume
    assert out.extents == pytest.approx([100, 40, 30])
