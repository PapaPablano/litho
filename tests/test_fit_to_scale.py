import numpy as np
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


def test_z_longer_than_x_is_rejected_as_an_orientation_error(box_stl, tmp_path):
    with pytest.raises(ValueError, match="orientation"):
        _fit(box_stl, tmp_path, (30, 125, 20))


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
