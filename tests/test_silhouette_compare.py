import numpy as np
from PIL import Image

import silhouette_compare as sc
from conftest import make_box


def _box_vectors(*size):
    return make_box(*size).vectors.astype(float)


def _view_png(path, subject_wh, canvas=(640, 360), color=(20, 140, 70)):
    arr = np.full((canvas[1], canvas[0], 3), 30, dtype=np.uint8)
    w, h = subject_wh
    x0, y0 = (canvas[0] - w) // 2, (canvas[1] - h) // 2
    arr[y0:y0 + h, x0:x0 + w] = color
    Image.fromarray(arr).save(path)


def test_side_projection_of_a_box_is_a_rectangle_with_the_right_aspect():
    m = sc.mesh_mask(_box_vectors(125, 50, 37.5), "left", px=400)
    assert m.all()  # cropped to its bounding box, a filled rectangle
    assert abs(m.shape[1] / m.shape[0] - 125 / 37.5) < 0.05


def test_matching_view_overlaps_almost_fully(tmp_path):
    _view_png(tmp_path / "left.png", (500, 150))      # 10:3 like the box
    r = sc.compare(_box_vectors(100, 40, 30), tmp_path, tmp_path / "out", stem="car")
    assert r["left"] > 0.95
    assert (tmp_path / "out" / "car_left_overlay.png").exists()


def test_different_shape_overlaps_less_but_still_writes_overlay(tmp_path):
    _view_png(tmp_path / "left.png", (300, 300))      # square subject vs a long box
    r = sc.compare(_box_vectors(100, 40, 30), tmp_path, tmp_path / "out", stem="car")
    assert r["left"] < 0.7
    assert (tmp_path / "out" / "car_left_overlay.png").exists()


def test_views_that_are_absent_are_skipped(tmp_path):
    _view_png(tmp_path / "left.png", (500, 150))
    r = sc.compare(_box_vectors(100, 40, 30), tmp_path, tmp_path / "out", stem="car")
    assert set(r) == {"left"}
