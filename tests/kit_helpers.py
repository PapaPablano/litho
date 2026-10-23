"""Shared builders for the kit tests (they need the AI environment, so everything imports lazily)."""


def stand_in_body(width_factor=1.25, size=100.0):
    """A boxy stand-in for a generated car (arbitrary units): a long lower box, a cabin, and two mirrors."""
    import kit_mesh
    import trimesh
    length, width, height = size, size * 0.45 * width_factor, size * 0.36
    lower = trimesh.creation.box(extents=[length, width, height * 0.5])
    lower.apply_translation([0, 0, height * 0.25])
    cabin = trimesh.creation.box(extents=[length * 0.55, width * 0.9, height * 0.5])
    cabin.apply_translation([length * 0.05, 0, height * 0.75])
    mirrors = []
    for sign in (-1, 1):
        m = trimesh.creation.box(extents=[length * 0.03, width * 0.14, height * 0.04])
        m.apply_translation([-length * 0.15, sign * (width / 2 + width * 0.07), height * 0.58])
        mirrors.append(m)
    return kit_mesh.union(lower, cabin, *mirrors, name="stand-in")
