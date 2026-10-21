import subprocess
import sys

import check_mesh
from conftest import ROOT


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
