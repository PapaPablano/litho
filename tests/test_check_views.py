import numpy as np
from PIL import Image

import check_views


def _view(path, size=(640, 360), noisy=False):
    arr = np.full((size[1], size[0], 3), 30, dtype=np.uint8)
    arr[size[1] // 4: 3 * size[1] // 4, size[0] // 5: 4 * size[0] // 5] = (20, 140, 70)
    if noisy:
        rng = np.random.default_rng(1)
        arr = rng.integers(0, 255, arr.shape, dtype=np.uint8)
    Image.fromarray(arr).save(path)


def _set(folder, names=("front", "back", "left", "right"), **kw):
    folder.mkdir(exist_ok=True)
    for n in names:
        _view(folder / f"{n}.png", **kw)
    return folder


def test_arbitrary_screenshots_report_missing_views(tmp_path):
    """Covers AE2."""
    f = tmp_path / "shots"
    f.mkdir()
    for i in range(3):
        _view(f / f"Screenshot_{i}.jpg")
    r = check_views.check(f)
    assert not r.ok
    text = "\n".join(r.problems)
    for name in ("front", "back", "left", "right"):
        assert name in text
    assert "checklist" in text.lower()


def test_complete_clean_set_passes(tmp_path):
    r = check_views.check(_set(tmp_path / "ok"))
    assert r.ok and r.problems == []


def test_mismatched_size_names_the_file(tmp_path):
    f = _set(tmp_path / "mix")
    _view(f / "left.png", size=(800, 450))
    r = check_views.check(f)
    assert not r.ok
    assert any("left" in p and "size" in p.lower() for p in r.problems)


def test_cluttered_background_is_flagged(tmp_path):
    f = _set(tmp_path / "busy")
    _view(f / "back.png", noisy=True)
    r = check_views.check(f)
    assert any("back" in p and "background" in p.lower() for p in r.problems)


def test_low_resolution_is_flagged(tmp_path):
    r = check_views.check(_set(tmp_path / "small", size=(300, 170)))
    assert any("resolution" in p.lower() for p in r.problems)


def test_top_view_is_optional_and_accepted(tmp_path):
    assert check_views.check(_set(tmp_path / "no_top")).ok
    f = _set(tmp_path / "with_top", names=("front", "back", "left", "right", "top"))
    r = check_views.check(f)
    assert r.ok and "top" in r.found
