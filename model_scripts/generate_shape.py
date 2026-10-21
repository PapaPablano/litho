"""Generate a raw, oriented STL from a folder of views, locally (runs in the AI environment).

Pipeline: validate the views -> run the shape model -> clean up the mesh (largest piece, filled
holes) -> rotate so X is length, Y is width, Z is up -> write models/raw/<name>.stl. Scale is
arbitrary here; fit_to_scale.py sets it.

Usage: python generate_shape.py "photos/input/<folder>" --name countryman [--backend hunyuan-mv]
"""
import argparse
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))


def default_out(name):
    return ROOT / "models" / "raw" / f"{name}.stl"


def keep_largest(mesh):
    """Drop floating fragments: keep the connected piece with the most surface area."""
    parts = mesh.split(only_watertight=False)
    if len(parts) <= 1:
        return mesh
    return max(parts, key=lambda p: p.area)


def fill_holes(mesh):
    """Close small gaps left by the generator."""
    import trimesh
    mesh = mesh.copy()
    trimesh.repair.fill_holes(mesh)
    trimesh.repair.fix_normals(mesh)
    return mesh


# rotation that takes each "up" axis of the generator's output to +Z
_UP_TO_Z = {
    "z": np.eye(3),
    "y": np.array([[1, 0, 0], [0, 0, -1], [0, 1, 0]], dtype=float),    # +Y -> +Z
    "-y": np.array([[1, 0, 0], [0, 0, 1], [0, -1, 0]], dtype=float),
    "x": np.array([[0, 0, -1], [0, 1, 0], [1, 0, 0]], dtype=float),    # +X -> +Z
}


def _align_yaw(mesh):
    """Spin about Z so the horizontal bounding box is as small as possible, longest side on X.

    Views that are not square-on make the generator yaw the object; this undoes that.
    """
    import trimesh
    from scipy.spatial import ConvexHull
    xy = mesh.vertices[:, :2]
    hull = xy[ConvexHull(xy).vertices]
    best, best_area = 0.0, None
    for deg in np.arange(0.0, 90.0, 0.25):
        a = np.radians(deg)
        c, s_ = np.cos(a), np.sin(a)
        r = hull @ np.array([[c, -s_], [s_, c]])
        area = np.ptp(r[:, 0]) * np.ptp(r[:, 1])
        if best_area is None or area < best_area:
            best, best_area = a, area
    mesh = mesh.copy()
    mesh.apply_transform(trimesh.transformations.rotation_matrix(-best, [0, 0, 1]))
    if mesh.extents[1] > mesh.extents[0]:
        mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 0, 1]))
    return mesh


def orient(mesh, up="z"):
    """Rotate so `up` points along +Z, then yaw so the longest horizontal extent lies along X."""
    mesh = mesh.copy()
    m = np.eye(4)
    m[:3, :3] = _UP_TO_Z[up]
    mesh.apply_transform(m)
    return _align_yaw(mesh)


WORKING_LENGTH = 100.0   # clean-up runs at a mm-like size so welding tolerances mean the same as in check_mesh
WELD_TOLERANCE = 0.005   # vertices closer than this (in those units) are merged


def normalize_scale(mesh, length=WORKING_LENGTH):
    """Scale so the longest extent is `length`. The true size is set later by fit_to_scale."""
    mesh = mesh.copy()
    mesh.apply_scale(length / mesh.extents.max())
    return mesh


def repair(mesh):
    """Weld sliver vertices and close the gaps marching cubes leaves, so the STL is watertight.

    Plain face deletion opens new holes, so this uses MeshLab's merge-and-repair filters.
    """
    import pymeshlab
    import trimesh
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    ms.meshing_merge_close_vertices(threshold=pymeshlab.PureValue(WELD_TOLERANCE))
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()
    ms.meshing_repair_non_manifold_edges(method=0)
    ms.meshing_close_holes(maxholesize=200)
    out = ms.current_mesh()
    return trimesh.Trimesh(out.vertex_matrix(), out.face_matrix(), process=False)


def postprocess(mesh, up="z"):
    """Largest piece -> mm-sized -> welded and repaired -> small holes filled -> Z-up, length on X."""
    mesh = repair(normalize_scale(keep_largest(mesh)))
    mesh = fill_holes(keep_largest(mesh))
    return orient(mesh, up=up)


# ---- generation backends (need the AI environment: torch + hy3dgen) ----

# Findings from the U1 spike on the RTX 5060 Laptop (8 GB): fp16 multiview at 30 steps,
# octree 256 peaks at ~5.4 GiB allocated; the generator output is Y-up.
HUNYUAN_UP = "y"


def load_views(folder):
    """Read each view as RGBA, removing the background when the image has no transparency."""
    from PIL import Image

    import check_views
    found = check_views._find(folder)
    remover = None
    views = {}
    for name in check_views.REQUIRED:
        img = Image.open(found[name]).convert("RGBA")
        if img.getextrema()[3][0] == 255:        # fully opaque: no cut-out supplied
            if remover is None:
                from hy3dgen.rembg import BackgroundRemover
                remover = BackgroundRemover()
            img = remover(img.convert("RGB"))
        views[name] = img
    return views


def run_hunyuan_mv(views, steps=30, octree=256, seed=12345, low_vram=False):
    """Multiview shape generation with Hunyuan3D-2mv; returns a trimesh."""
    import torch
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        "tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv", variant="fp16",
        **({} if low_vram else {"device": "cuda"}),
    )
    if low_vram:
        pipe.enable_model_cpu_offload()
    return pipe(
        image=views, num_inference_steps=steps, octree_resolution=octree, num_chunks=8000,
        generator=torch.manual_seed(seed), output_type="trimesh",
    )[0]


def load_single_view(folder, view):
    """One view as RGBA (background removed if needed); `view` is a name like 'left' or an image path."""
    from PIL import Image

    import check_views
    path = check_views._find(folder).get(view) if Path(folder).is_dir() else None
    if path is None and Path(view).is_file():
        path = Path(view)
    if path is None:
        raise FileNotFoundError(f"no '{view}' image in {folder}")
    img = Image.open(path).convert("RGBA")
    if img.getextrema()[3][0] == 255:
        from hy3dgen.rembg import BackgroundRemover
        img = BackgroundRemover()(img.convert("RGB"))
    return img


def run_hunyuan_single(image, steps=30, octree=256, seed=12345):
    """Single-image baseline with Hunyuan3D-2mini (0.6B); returns a trimesh."""
    import torch
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        "tencent/Hunyuan3D-2mini", subfolder="hunyuan3d-dit-v2-mini", variant="fp16", device="cuda",
    )
    return pipe(
        image=image, num_inference_steps=steps, octree_resolution=octree, num_chunks=8000,
        generator=torch.manual_seed(seed), output_type="trimesh",
    )[0]


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("views", help="folder with front/back/left/right images")
    p.add_argument("--baseline", metavar="VIEW",
                   help="single-image comparison run on one view (a name like 'left', or an image path); "
                        "needs no complete view set")
    p.add_argument("--name", required=True, help="output name; writes models/raw/<name>.stl")
    p.add_argument("--out", help="output STL path (default models/raw/<name>.stl)")
    p.add_argument("--steps", type=int, default=30)
    p.add_argument("--octree", type=int, default=256, help="mesh resolution; lower uses less VRAM")
    p.add_argument("--seed", type=int, default=12345)
    p.add_argument("--low-vram", action="store_true", help="offload model parts to CPU between stages")
    p.add_argument("--up", default=HUNYUAN_UP, choices=sorted(_UP_TO_Z), help="up axis of the generator output")
    a = p.parse_args(argv)

    if a.baseline:
        try:
            image = load_single_view(a.views, a.baseline)
        except FileNotFoundError as e:
            print(e)
            return 1
        mesh = run_hunyuan_single(image, a.steps, a.octree, a.seed)
    else:
        import check_views
        check = check_views.check(a.views)
        if not check.ok:
            for line in check.problems:
                print(line)
            return 1
        mesh = run_hunyuan_mv(load_views(a.views), a.steps, a.octree, a.seed, a.low_vram)
    mesh = postprocess(mesh, up=a.up)
    out = Path(a.out) if a.out else default_out(a.name)
    out.parent.mkdir(parents=True, exist_ok=True)
    mesh.export(str(out))
    x, y, z = mesh.extents
    print(f"Wrote {out}  extents {x:.3f} x {y:.3f} x {z:.3f} (arbitrary units)  watertight: {mesh.is_watertight}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
