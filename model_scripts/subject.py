"""Load a subject's real-world size and turn it into print-size targets.

A subject is a small YAML file (see subjects/) giving length_mm, width_mm and height_mm.
Scale and tolerances come from the `model:` section of config.yaml; keyword overrides win.
"""
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SUBJECTS = Path(__file__).resolve().parent / "subjects"
FIELDS = ("length_mm", "width_mm", "height_mm")


@dataclass(frozen=True)
class Targets:
    real_mm: tuple          # (length, width, height) of the real object
    denominator: float      # print scale 1:N
    tolerance_pct: float
    max_axis_stretch_pct: float

    @property
    def print_mm(self):
        return tuple(v / self.denominator for v in self.real_mm)


def _read_yaml(path):
    with open(path, encoding="utf-8-sig") as f:
        return yaml.safe_load(f) or {}


def _subject_path(name):
    p = Path(name)
    if p.suffix in (".yaml", ".yml") or p.parent != Path("."):
        return p
    return SUBJECTS / f"{name}.yaml"


def targets(name, denominator=None, tolerance_pct=None, max_axis_stretch_pct=None, **dims):
    """Resolve print-size targets for a subject name or YAML path.

    `dims` may override length_mm / width_mm / height_mm.
    """
    path = _subject_path(name)
    if not path.exists():
        raise FileNotFoundError(f"subject '{name}' not found (looked for {path})")
    data = {**_read_yaml(path), **{k: v for k, v in dims.items() if v is not None}}
    for field in FIELDS:
        if data.get(field) is None:
            raise ValueError(f"{path.name}: missing {field}")
    cfg = _read_yaml(ROOT / "config.yaml").get("model", {})
    return Targets(
        real_mm=tuple(float(data[f]) for f in FIELDS),
        denominator=float(denominator or cfg.get("scale_denominator", 32)),
        tolerance_pct=float(tolerance_pct if tolerance_pct is not None else cfg.get("tolerance_pct", 2.0)),
        max_axis_stretch_pct=float(
            max_axis_stretch_pct if max_axis_stretch_pct is not None else cfg.get("max_axis_stretch_pct", 5.0)
        ),
    )


KIT_FIELDS = (
    "track_front_mm", "track_rear_mm", "wheel_diameter_mm", "tyre_width_mm",
    "ground_clearance_mm", "front_overhang_mm", "rear_overhang_mm",
    "beltline_height_fraction", "roof_height_fraction",
)


@dataclass(frozen=True)
class KitSpec:
    """Extra real-world numbers the car kit needs, each with a source note."""
    track_front_mm: float
    track_rear_mm: float
    wheel_diameter_mm: float
    tyre_width_mm: float
    ground_clearance_mm: float
    front_overhang_mm: float
    rear_overhang_mm: float
    beltline_height_fraction: float
    roof_height_fraction: float
    windows: tuple           # of (name, from_fraction, to_fraction) along the length
    sources: dict
    unverified: tuple        # names of values to confirm or tune by eye


@dataclass(frozen=True)
class KitConfig:
    scale_denominator: float
    joint_clearance_mm: float
    bed_mm: float


def kit_spec(name):
    """The kit block of a subject, or ValueError naming what is missing."""
    path = _subject_path(name)
    if not path.exists():
        raise FileNotFoundError(f"subject '{name}' not found (looked for {path})")
    kit = _read_yaml(path).get("kit")
    if not kit:
        raise ValueError(f"{path.name}: no kit block")
    for field in KIT_FIELDS:
        if kit.get(field) is None:
            raise ValueError(f"{path.name}: kit block is missing {field}")
    windows = tuple((w["name"], float(w["from"]), float(w["to"])) for w in kit.get("windows", []))
    return KitSpec(
        **{field: float(kit[field]) for field in KIT_FIELDS},
        windows=windows,
        sources=dict(kit.get("sources", {})),
        unverified=tuple(kit.get("unverified", [])),
    )


def kit_config():
    """Kit scale, joint clearance and bed size from the `kit:` section of config.yaml."""
    cfg = _read_yaml(ROOT / "config.yaml").get("kit", {})
    return KitConfig(
        scale_denominator=float(cfg.get("scale_denominator", 24)),
        joint_clearance_mm=float(cfg.get("joint_clearance_mm", 0.15)),
        bed_mm=float(cfg.get("bed_mm", 256)),
    )
