import pytest

trimesh = pytest.importorskip("trimesh")  # these live in the AI environment, not the main one
pytest.importorskip("pymeshlab")
pytest.importorskip("manifold3d")

import kit_mesh  # noqa: E402
import make_kit  # noqa: E402
from kit_helpers import stand_in_body as _stand_in_body  # noqa: E402

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


def test_a_failed_check_leaves_the_earlier_kit_untouched_and_says_so(body_stl, tmp_path, capsys):
    assert _run(body_stl, tmp_path) == 0
    folder = tmp_path / "demo"
    before = {p.name: p.stat().st_mtime_ns for p in folder.glob("*.stl")}
    capsys.readouterr()
    assert _run(body_stl, tmp_path, "--bed-mm", "50") == 2
    assert {p.name: p.stat().st_mtime_ns for p in folder.glob("*.stl")} == before
    assert "NOT updated" in capsys.readouterr().out


def test_an_export_that_fails_part_way_leaves_the_earlier_kit_and_no_temp_folder(body_stl, tmp_path, monkeypatch, capsys):
    assert _run(body_stl, tmp_path) == 0
    folder = tmp_path / "demo"
    before = {p.name: p.stat().st_mtime_ns for p in folder.glob("*.stl")}
    real_export = trimesh.Trimesh.export
    calls = {"n": 0}

    def flaky(self, *a, **k):
        calls["n"] += 1
        if calls["n"] == 3:
            raise OSError("disk full")
        return real_export(self, *a, **k)

    monkeypatch.setattr(trimesh.Trimesh, "export", flaky)
    assert _run(body_stl, tmp_path) == 1
    monkeypatch.undo()
    assert "disk full" in capsys.readouterr().out
    assert {p.name: p.stat().st_mtime_ns for p in folder.glob("*.stl")} == before
    assert [p.name for p in tmp_path.iterdir()] == ["demo"]          # no leftover staging or backup folder


def test_a_new_run_replaces_every_part_of_the_old_kit(body_stl, tmp_path):
    assert _run(body_stl, tmp_path) == 0
    (tmp_path / "demo" / "old_part.stl").write_bytes(b"stale")
    assert _run(body_stl, tmp_path) == 0
    assert {p.stem for p in (tmp_path / "demo").glob("*.stl")} == PART_FILES


def test_an_unknown_print_orientation_is_refused_before_the_long_build(body_stl, tmp_path, monkeypatch, capsys):
    bad = make_kit.subject.kit_config()
    bad = type(bad)(bad.scale_denominator, bad.joint_clearance_mm, bad.bed_mm, {**bad.print_orientation, "body": "sideways"})
    monkeypatch.setattr(make_kit.subject, "kit_config", lambda: bad)
    monkeypatch.setattr(make_kit.kit_mesh, "load_solid", lambda *a, **k: pytest.fail("the body must not be loaded"))
    assert _run(body_stl, tmp_path) == 1
    assert "sideways" in capsys.readouterr().out


def test_an_unexpected_failure_prints_a_message_not_a_traceback(body_stl, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(make_kit.kit_check, "check_kit", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert _run(body_stl, tmp_path) == 1
    assert "RuntimeError: boom" in capsys.readouterr().out
