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


def test_countryman_kit_block_has_a_source_note_for_every_value():
    k = subject.kit_spec("mini_countryman")
    for field in subject.KIT_FIELDS:
        assert getattr(k, field) > 0
        assert k.sources.get(field), f"no source note for {field}"
    assert k.wheel_diameter_mm == pytest.approx(705, abs=1)


def test_unverified_kit_values_are_reported():
    k = subject.kit_spec("mini_countryman")
    assert "ground_clearance_mm" in k.unverified


def test_a_subject_without_a_kit_block_still_gives_targets_and_names_the_gap(tmp_path):
    f = tmp_path / "plain.yaml"
    f.write_text("length_mm: 4000\nwidth_mm: 1800\nheight_mm: 1500\n", encoding="utf-8")
    assert subject.targets(str(f)).real_mm == (4000.0, 1800.0, 1500.0)
    with pytest.raises(ValueError, match="no kit block"):
        subject.kit_spec(str(f))


def test_kit_block_missing_track_width_names_the_field(tmp_path):
    f = tmp_path / "broken.yaml"
    f.write_text("length_mm: 4000\nwidth_mm: 1800\nheight_mm: 1500\nkit:\n  wheel_diameter_mm: 700\n", encoding="utf-8")
    with pytest.raises(ValueError, match="track_front_mm"):
        subject.kit_spec(str(f))


def test_kit_config_is_1_to_24_while_the_model_section_stays_1_to_32():
    cfg = subject.kit_config()
    assert cfg.scale_denominator == 24
    assert cfg.joint_clearance_mm == pytest.approx(0.15)
    assert cfg.bed_mm == 256
    assert subject.targets("mini_countryman").denominator == 32


def test_a_malformed_window_entry_names_the_problem(tmp_path):
    f = tmp_path / "badwin.yaml"
    base = open(subject.SUBJECTS / "mini_countryman.yaml", encoding="utf-8").read()
    f.write_text(base.replace("{name: front_door, from: 0.34, to: 0.52}", "{name: front_door, from: 0.34}"), encoding="utf-8")
    with pytest.raises(ValueError, match="window"):
        subject.kit_spec(str(f))
