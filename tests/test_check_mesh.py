import subprocess
import sys

import check_mesh
from conftest import ROOT, make_box


def test_closed_cube_is_watertight_with_positive_volume(box_stl):
    r = check_mesh.analyze(str(box_stl("cube.stl", 10, 10, 10)))
    assert r["open_edges"] == 0
    assert r["volume"] > 0
    assert [round(v, 3) for v in r["size"]] == [10.0, 10.0, 10.0]


def test_cube_with_a_missing_face_has_open_edges(box_stl):
    r = check_mesh.analyze(str(box_stl("open.stl", 10, 10, 10, drop_face=True)))
    assert r["open_edges"] > 0


def test_inverted_normals_give_negative_volume(box_stl):
    r = check_mesh.analyze(str(box_stl("flip.stl", 10, 10, 10, inverted=True)))
    assert r["volume"] < 0


def _exit_code(path):
    cmd = [sys.executable, str(ROOT / "print_prep" / "check_mesh.py"), str(path)]
    return subprocess.run(cmd, capture_output=True, text=True).returncode


def test_cli_exit_codes(box_stl):
    assert _exit_code(box_stl("ok.stl", 5, 5, 5)) == 0
    assert _exit_code(box_stl("open.stl", 5, 5, 5, drop_face=True)) == 1
    assert _exit_code(box_stl("flip.stl", 5, 5, 5, inverted=True)) == 1


def test_one_reversed_triangle_is_flagged_even_though_old_checks_pass(box_stl):
    r = check_mesh.analyze(str(box_stl("flip1.stl", 10, 10, 10, flip_one=True)))
    assert r["open_edges"] == 0 and r["volume"] > 0      # what the original check looked at
    assert r["flipped_edges"] > 0


def test_consistent_cube_has_no_flipped_edges_and_one_shell(box_stl):
    r = check_mesh.analyze(str(box_stl("cube.stl", 10, 10, 10)))
    assert r["flipped_edges"] == 0
    assert r["shells"] == 1


def test_two_separate_cubes_report_two_shells(tmp_path):
    from stl import mesh as stl_mesh
    import numpy as np
    a, b = make_box(10, 10, 10), make_box(5, 5, 5, offset=(50, 0, 0))
    both = stl_mesh.Mesh(np.concatenate([a.data, b.data]))
    path = tmp_path / "two.stl"
    both.save(str(path))
    r = check_mesh.analyze(str(path))
    assert r["shells"] == 2 and r["open_edges"] == 0 and r["flipped_edges"] == 0


def test_cli_fails_on_a_reversed_triangle_and_only_warns_on_extra_shells(box_stl, tmp_path):
    assert _exit_code(box_stl("flip1.stl", 5, 5, 5, flip_one=True)) == 1
    from stl import mesh as stl_mesh
    import numpy as np
    both = stl_mesh.Mesh(np.concatenate([make_box(10, 10, 10).data, make_box(5, 5, 5, offset=(50, 0, 0)).data]))
    path = tmp_path / "two.stl"
    both.save(str(path))
    assert _exit_code(path) == 0
