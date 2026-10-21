import pytest

import subject


def test_countryman_targets_at_1_to_32():
    t = subject.targets("mini_countryman")
    assert t.denominator == 32
    assert [round(v, 1) for v in t.print_mm] == [138.8, 57.6, 51.5]


def test_cli_scale_override_changes_targets():
    t = subject.targets("mini_countryman", denominator=24)
    assert round(t.print_mm[0], 1) == 185.0


def test_dimension_overrides_beat_the_subject_file():
    t = subject.targets("mini_countryman", length_mm=4800)
    assert round(t.print_mm[0], 1) == 150.0


def test_missing_height_names_the_field(tmp_path):
    f = tmp_path / "broken.yaml"
    f.write_text("length_mm: 4000\nwidth_mm: 1800\n", encoding="utf-8")
    with pytest.raises(ValueError, match="height_mm"):
        subject.targets(str(f))


def test_unknown_subject_name_is_a_clear_error():
    with pytest.raises(FileNotFoundError, match="no_such_car"):
        subject.targets("no_such_car")


def test_second_subject_needs_only_a_new_file(tmp_path):
    f = tmp_path / "other.yaml"
    f.write_text("length_mm: 3200\nwidth_mm: 1600\nheight_mm: 1400\n", encoding="utf-8")
    t = subject.targets(str(f))
    assert [round(v, 1) for v in t.print_mm] == [100.0, 50.0, 43.8]


def test_defaults_come_from_config():
    t = subject.targets("mini_countryman")
    assert t.tolerance_pct == 2.0
    assert t.max_axis_stretch_pct == 5.0
