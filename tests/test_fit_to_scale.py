import pytest
from stl import mesh

import fit_to_scale
from subject import Targets

# Real car-like box: 4000 x 1600 x 1200 mm at 1:32 -> 125 x 50 x 37.5 mm.
T = Targets(real_mm=(4000, 1600, 1200), denominator=32, tolerance_pct=2.0, max_axis_stretch_pct=5.0)


def _fit(box_stl, tmp_path, size, **kw):
    raw = box_stl("raw.stl", *size, **kw)
    out = tmp_path / "out.stl"
    return fit_to_scale.run(str(raw), T, str(out)), out


def test_four_percent_too_long_is_rescaled_and_passes(box_stl, tmp_path):
    """Covers AE1."""
    r, out = _fit(box_stl, tmp_path, (130, 52, 39))
    assert r.dimensions_ok and r.print_ready and r.exit_code == 0
    assert all(abs(d.error_pct) <= 2.0 for d in r.dims)
    assert out.exists()


def test_small_width_error_is_stretched_within_the_cap(box_stl, tmp_path):
    r, _ = _fit(box_stl, tmp_path, (125, 51.5, 37.5))
    assert r.dimensions_ok
    assert r.stretch["width"] == pytest.approx(50 / 51.5, rel=1e-6)
    assert "length" not in r.stretch


def test_large_width_error_fails_naming_the_width_and_writes_nothing(box_stl, tmp_path):
    r, out = _fit(box_stl, tmp_path, (125, 56, 37.5))
    assert not r.dimensions_ok and r.exit_code == 2
    assert [d.name for d in r.dims if not d.ok] == ["width"]
    assert not out.exists()


@pytest.mark.parametrize("size", [(30, 125, 20), (30, 20, 125)])  # Y longest, Z longest
def test_x_not_longest_is_rejected_as_an_orientation_error(box_stl, tmp_path, size):
    with pytest.raises(ValueError, match="orientation"):
        _fit(box_stl, tmp_path, size)


def test_open_edges_are_written_but_not_print_ready(box_stl, tmp_path):
    """Covers AE3."""
    r, out = _fit(box_stl, tmp_path, (125, 50, 37.5), drop_face=True)
    assert out.exists()
    assert r.dimensions_ok and not r.print_ready and r.exit_code == 1


def test_output_sits_on_z0_centered_and_matches_report(box_stl, tmp_path):
    r, out = _fit(box_stl, tmp_path, (130, 52, 39), offset=(500, -200, 77))
    m = mesh.Mesh.from_file(str(out))
    assert m.min_[2] == pytest.approx(0, abs=1e-6)
    assert (m.min_[0] + m.max_[0]) / 2 == pytest.approx(0, abs=1e-6)
    size = m.max_ - m.min_
    assert [round(float(v), 3) for v in size] == [round(d.measured, 3) for d in r.dims]


def test_height_within_the_cap_is_stretched(box_stl, tmp_path):
    r, _ = _fit(box_stl, tmp_path, (125, 50, 38.8))   # +3.5% high
    assert r.dimensions_ok
    assert r.stretch["height"] == pytest.approx(37.5 / 38.8, rel=1e-6)


def test_height_beyond_the_cap_fails_naming_height_and_writes_nothing(box_stl, tmp_path):
    r, out = _fit(box_stl, tmp_path, (125, 50, 41))   # +9.3% high
    assert [d.name for d in r.dims if not d.ok] == ["height"]
    assert r.exit_code == 2 and not out.exists()


def test_stretch_cap_applies_just_inside_and_just_outside(box_stl, tmp_path):
    inside, _ = _fit(box_stl, tmp_path, (125, 50 / 0.951, 37.5))   # needs -4.9%
    assert inside.dimensions_ok
    outside, _ = _fit(box_stl, tmp_path, (125, 50 / 0.949, 37.5))   # needs -5.1%
    assert not outside.dimensions_ok


def test_inverted_normals_are_written_but_not_print_ready(box_stl, tmp_path):
    r, out = _fit(box_stl, tmp_path, (125, 50, 37.5), inverted=True)
    assert out.exists() and r.dimensions_ok
    assert not r.print_ready and r.exit_code == 1


def _cli(*args):
    import subprocess
    import sys
    from conftest import ROOT
    cmd = [sys.executable, str(ROOT / "model_scripts" / "fit_to_scale.py"), *map(str, args)]
    return subprocess.run(cmd, capture_output=True, text=True)


def test_cli_orientation_error_exits_3_and_flags_a_stale_output(box_stl, tmp_path):
    raw = box_stl("raw.stl", 30, 20, 125)
    out = tmp_path / "earlier.stl"
    out.write_bytes(b"old")
    r = _cli(raw, "--subject", "mini_countryman", "--out", out)
    assert r.returncode == 3
    assert "orientation" in r.stderr and "earlier run" in r.stderr
    assert out.read_bytes() == b"old"      # never overwritten or deleted


def test_cli_unknown_subject_exits_3(box_stl, tmp_path):
    r = _cli(box_stl("raw.stl", 125, 50, 37.5), "--subject", "no_such_car", "--out", tmp_path / "o.stl")
    assert r.returncode == 3 and "no_such_car" in r.stderr


def test_cli_dimension_failure_exits_2_and_flags_a_stale_output(box_stl, tmp_path):
    raw = box_stl("raw.stl", 125, 56, 37.5)
    out = tmp_path / "earlier.stl"
    out.write_bytes(b"old")
    t = tmp_path / "car.yaml"
    t.write_text("length_mm: 4000\nwidth_mm: 1600\nheight_mm: 1200\n", encoding="utf-8")
    r = _cli(raw, "--subject", t, "--out", out)
    assert r.returncode == 2 and "earlier run" in r.stdout
