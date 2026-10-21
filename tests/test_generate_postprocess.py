import numpy as np
import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")

import generate_shape as gs  # noqa: E402


def _box(extents, center=(0, 0, 0)):
    b = trimesh.creation.box(extents=extents)
    b.apply_translation(center)
    return b


def test_keeps_only_the_larger_of_two_disconnected_boxes():
    big, small = _box((10, 10, 10)), _box((1, 1, 1), center=(50, 0, 0))
    both = trimesh.util.concatenate([big, small])
    out = gs.keep_largest(both)
    assert len(out.vertices) == 8
    assert out.extents == pytest.approx([10, 10, 10])


def test_y_longest_mesh_is_rotated_so_x_is_longest_with_z_up():
    out = gs.orient(_box((30, 125, 20)), up="z")
    assert out.extents == pytest.approx([125, 30, 20])


def test_y_up_convention_is_rotated_to_z_up():
    # a model generated Y-up: length 125 on X, height 20 on Y, width 30 on Z
    out = gs.orient(_box((125, 20, 30)), up="y")
    assert out.extents == pytest.approx([125, 30, 20])


def test_small_hole_is_filled_and_result_is_watertight():
    b = _box((10, 10, 10))
    b.update_faces(np.arange(len(b.faces)) != 0)  # drop one triangle
    assert not b.is_watertight
    assert gs.fill_holes(b).is_watertight


def test_postprocess_pipeline_returns_oriented_watertight_largest_piece():
    both = trimesh.util.concatenate([_box((30, 125, 20)), _box((1, 1, 1), center=(200, 0, 0))])
    out = gs.postprocess(both, up="z")
    assert out.is_watertight
    # normalized to a 100-unit length; the proportions are what must survive
    assert out.extents == pytest.approx([100, 24, 16], abs=0.1)


def test_default_output_path_is_inside_models_raw():
    assert gs.default_out("countryman").parts[-3:] == ("models", "raw", "countryman.stl")


def test_yawed_mesh_is_aligned_so_its_length_lies_along_x():
    """The generator yaws the car when the views are not square-on; orient removes that."""
    b = _box((125, 30, 20))
    b.apply_transform(trimesh.transformations.rotation_matrix(np.radians(40), [0, 0, 1]))
    out = gs.orient(b, up="z")
    assert out.extents == pytest.approx([125, 30, 20], abs=0.5)


def test_repair_closes_a_sliver_gap_that_check_mesh_would_flag(tmp_path):
    """A hairline crack (vertices 0.001 apart) is welded so the exported STL is watertight."""
    import check_mesh
    b = _box((100, 40, 30))
    v = b.vertices.copy()
    v[0] += 0.001                      # nudge one corner so two copies no longer coincide
    cracked = trimesh.Trimesh(np.vstack([v, b.vertices[:1]]), b.faces, process=False)
    out = gs.postprocess(cracked, up="z")
    path = tmp_path / "out.stl"
    out.export(str(path))
    assert check_mesh.analyze(str(path))["open_edges"] == 0
