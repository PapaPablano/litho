import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import kit_mesh  # noqa: E402
import make_kit  # noqa: E402
from test_kit_body import _stand_in_body  # noqa: E402

PART_FILES = {"body", "chassis", "interior", "wheel_front_left", "wheel_front_right", "wheel_rear_left", "wheel_rear_right"}


@pytest.fixture(scope="module")
def body_stl(tmp_path_factory):
    path = tmp_path_factory.mktemp("raw") / "body.stl"
    _stand_in_body().export(str(path))
    return path


def _run(body_stl, out, *extra):
    return make_kit.main([str(body_stl), "--subject", "mini_countryman", "--name", "demo", "--out", str(out), *extra])


def test_a_stand_in_body_produces_one_file_per_part_and_exits_zero(body_stl, tmp_path):
    assert _run(body_stl, tmp_path) == 0
    files = {p.stem for p in (tmp_path / "demo").glob("*.stl")}
    assert files == PART_FILES


def test_every_part_is_printed_flat_on_the_bed(body_stl, tmp_path):
    _run(body_stl, tmp_path)
    for path in (tmp_path / "demo").glob("*.stl"):
        mesh = trimesh.load(str(path))
        assert mesh.bounds[0][2] == pytest.approx(0, abs=1e-6), path.name


def test_the_wheels_print_with_the_axle_vertical_and_the_hub_socket_down(body_stl, tmp_path):
    _run(body_stl, tmp_path)
    wheel = trimesh.load(str(tmp_path / "demo" / "wheel_front_right.stl"))
    assert wheel.extents[2] < wheel.extents[0]           # a short cylinder standing on its flat face


def test_scale_32_still_produces_a_kit(body_stl, tmp_path):
    assert _run(body_stl, tmp_path, "--scale", "32") == 0
    assert {p.stem for p in (tmp_path / "demo").glob("*.stl")} == PART_FILES


def test_a_missing_body_file_exits_nonzero_and_names_the_path(tmp_path, capsys):
    code = make_kit.main([str(tmp_path / "nope.stl"), "--subject", "mini_countryman", "--name", "demo", "--out", str(tmp_path)])
    assert code != 0
    assert "nope.stl" in capsys.readouterr().out


def test_a_failed_check_exits_two_and_writes_no_part_files(body_stl, tmp_path):
    assert _run(body_stl, tmp_path, "--bed-mm", "50") == 2
    assert not list((tmp_path / "demo").glob("*.stl")) if (tmp_path / "demo").exists() else True


@pytest.mark.parametrize("wheel", ["wheel_front_right", "wheel_rear_left"])
def test_every_wheel_prints_with_its_hub_socket_on_the_bed_side(body_stl, tmp_path, wheel):
    _run(body_stl, tmp_path)
    mesh = trimesh.load(str(tmp_path / "demo" / f"{wheel}.stl"))
    def slab(z):
        box = trimesh.creation.box(extents=[100, 100, 0.4])
        box.apply_translation([0, 0, z])
        return kit_mesh.overlap_volume(mesh, box)

    near_bed, inside = slab(0.2), slab(4.0)
    assert near_bed < inside                              # the socket hole is visible just above the bed


def test_running_without_the_ai_environment_explains_what_to_do(monkeypatch, tmp_path, capsys):
    def boom(*a, **k):
        raise ImportError("No module named 'trimesh'")
    monkeypatch.setattr(make_kit.kit_mesh, "load_solid", boom)
    code = make_kit.main([str(tmp_path / "x.stl"), "--subject", "mini_countryman", "--name", "demo", "--out", str(tmp_path)])
    assert code == 1
    assert "AI environment" in capsys.readouterr().out
