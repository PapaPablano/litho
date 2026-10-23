import sys

import numpy as np
import pytest
from PIL import Image

import check_views
import generate_shape as gs
import prepare_views


def _shot(path, size, box):
    """Opaque screenshot: grey wall with a green subject at box=(x0, y0, x1, y1)."""
    a = np.full((size[1], size[0], 3), 90, dtype=np.uint8)
    x0, y0, x1, y1 = box
    a[y0:y1, x0:x1] = (20, 140, 70)
    Image.fromarray(a).save(path)


class _Remover:
    """Stand-in for the background remover: keeps the green pixels."""
    def __call__(self, img):
        a = np.array(img.convert("RGB"))
        rgba = np.dstack([a, np.where(a[..., 1] > 120, 255, 0).astype(np.uint8)])
        return Image.fromarray(rgba)


def _folder(tmp_path):
    f = tmp_path / "in"
    f.mkdir()
    _shot(f / "left.png", (1080, 419), (100, 60, 1000, 360))    # long, 300 tall
    _shot(f / "right.png", (1080, 524), (50, 100, 1050, 400))   # long, 300 tall
    _shot(f / "back.png", (1080, 903), (300, 200, 800, 500))    # narrow, 300 tall
    _shot(f / "front.png", (650, 689), (100, 200, 500, 500))
    return f


def test_prepared_views_share_size_and_subject_height(tmp_path):
    out = prepare_views.prepare_folder(_folder(tmp_path), tmp_path / "out", remover=_Remover())
    heights = set()
    for name in check_views.REQUIRED:
        img = Image.open(out / f"{name}.png")
        assert img.size == (prepare_views.CANVAS, prepare_views.CANVAS)
        heights.add(img.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()[3]
                    - img.getchannel("A").point(lambda v: 255 if v > 128 else 0).getbbox()[1])
    assert max(heights) - min(heights) <= 1


def test_prepared_folder_passes_check_views(tmp_path):
    out = prepare_views.prepare_folder(_folder(tmp_path), tmp_path / "out", remover=_Remover())
    assert check_views.check(out).ok


def test_widest_view_fits_inside_margin(tmp_path):
    out = prepare_views.prepare_folder(_folder(tmp_path), tmp_path / "out", remover=_Remover())
    x0, _, x1, _ = Image.open(out / "left.png").getchannel("A").getbbox()
    assert x0 >= prepare_views.CANVAS * prepare_views.MARGIN - 1
    assert prepare_views.CANVAS - x1 >= prepare_views.CANVAS * prepare_views.MARGIN - 1


def test_stray_speck_is_dropped():
    a = np.zeros((200, 200, 4), dtype=np.uint8)
    a[50:150, 50:150] = (0, 200, 0, 255)
    a[5:8, 5:8] = (0, 200, 0, 255)
    box = prepare_views.crop_to_subject(prepare_views.largest_piece(Image.fromarray(a)))
    assert box.size == (100, 100)


def test_missing_view_is_reported(tmp_path):
    f = _folder(tmp_path)
    (f / "back.png").unlink()
    with pytest.raises(FileNotFoundError, match="back"):
        prepare_views.prepare_folder(f, tmp_path / "out", remover=_Remover())


def test_empty_cutout_names_the_view(tmp_path):
    f = _folder(tmp_path)
    _shot(f / "back.png", (650, 689), (0, 0, 0, 0))      # no green: nothing survives the cut-out
    with pytest.raises(ValueError, match="back: no subject"):
        prepare_views.prepare_folder(f, tmp_path / "out", remover=_Remover())


def test_unreadable_image_names_the_view(tmp_path):
    f = _folder(tmp_path)
    (f / "left.png").write_bytes(b"not an image")
    with pytest.raises(ValueError, match="left"):
        prepare_views.prepare_folder(f, tmp_path / "out", remover=_Remover())


def test_missing_remover_is_an_import_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "hy3dgen", None)
    monkeypatch.setitem(sys.modules, "hy3dgen.rembg", None)
    with pytest.raises(ImportError, match="AI venv"):
        prepare_views.cut_out(Image.new("RGB", (8, 8)))


def test_top_view_does_not_shrink_the_side_views(tmp_path):
    f = _folder(tmp_path)
    _shot(f / "top.png", (1080, 1080), (100, 400, 980, 700))   # wide and short
    out = prepare_views.prepare_folder(f, tmp_path / "out", remover=_Remover())
    heights = {n: (lambda b: b[3] - b[1])(Image.open(out / f"{n}.png").getchannel("A").getbbox())
               for n in ("front", "back", "left", "right")}
    (tmp_path / "again").mkdir()
    base = prepare_views.prepare_folder(_folder(tmp_path / "again"), tmp_path / "out2", remover=_Remover())
    ref = (lambda b: b[3] - b[1])(Image.open(base / "left.png").getchannel("A").getbbox())
    assert all(abs(h - ref) <= 1 for h in heights.values())


def test_stale_view_in_output_folder_is_removed(tmp_path):
    out = tmp_path / "out"
    out.mkdir()
    Image.new("RGBA", (4, 4)).save(out / "top.png")
    prepare_views.prepare_folder(_folder(tmp_path), out, remover=_Remover())
    assert not (out / "top.png").exists()


def test_main_reports_a_prepare_error_and_exits_1(monkeypatch, capsys, tmp_path):
    def boom(*a, **k):
        raise ValueError("back: no subject found after background removal")
    monkeypatch.setattr(prepare_views, "prepare_folder", boom)
    assert gs.main([str(tmp_path), "--name", "x"]) == 1
    assert "back: no subject" in capsys.readouterr().out


def test_no_prepare_skips_preparation(monkeypatch, capsys, tmp_path):
    def boom(*a, **k):
        raise AssertionError("prepare_folder must not run")
    monkeypatch.setattr(prepare_views, "prepare_folder", boom)
    assert gs.main([str(tmp_path), "--name", "x", "--no-prepare"]) == 1    # check_views then refuses the empty folder
    assert capsys.readouterr().out.strip()
