"""Mesh helpers for the car kit: turn a generated mesh into a clean solid, thin it, and cut or join solids.

The generator's body is watertight but can carry a few reversed or pinched triangles, which the boolean
engine refuses. make_solid cuts out that small patch and refills it. Needs the AI environment
(trimesh, pymeshlab, manifold3d).
"""
from pathlib import Path

import numpy as np

# patch radius, as a share of the mesh's bounding diagonal, tried in order until the mesh is a solid
PATCH_FRACTIONS = (0.003, 0.006, 0.012, 0.025)
HOLE_FILL_EDGES = 2000


def _defect_faces(mesh):
    """Indices of faces on edges that run the same way twice, or that are not shared by two faces."""
    f = mesh.faces
    n = len(mesh.vertices)
    directed = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    keys = directed[:, 0].astype(np.int64) * n + directed[:, 1]
    unique, counts = np.unique(keys, return_counts=True)
    bad = np.isin(keys, unique[counts > 1])
    edge_keys = np.minimum(directed[:, 0], directed[:, 1]).astype(np.int64) * n + np.maximum(directed[:, 0], directed[:, 1])
    eu, ec = np.unique(edge_keys, return_counts=True)
    bad |= np.isin(edge_keys, eu[ec != 2])
    return np.unique(np.where(bad)[0] % len(f))


def _meshlab_repair(vertices, faces):
    import pymeshlab
    import trimesh
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=np.asarray(vertices, dtype=float), face_matrix=np.asarray(faces, dtype=np.int32)))
    ms.meshing_remove_unreferenced_vertices()
    ms.meshing_repair_non_manifold_edges(method=0)
    ms.meshing_repair_non_manifold_vertices(vertdispratio=0.0)
    ms.meshing_close_holes(maxholesize=HOLE_FILL_EDGES, newfaceselected=False)
    ms.meshing_re_orient_faces_coherently()
    out = ms.current_mesh()
    return trimesh.Trimesh(out.vertex_matrix(), out.face_matrix(), process=True)


def make_solid(mesh, name="mesh"):
    """Return a valid solid made from `mesh`, or raise ValueError naming the part."""
    import trimesh
    m = trimesh.Trimesh(mesh.vertices.copy(), mesh.faces.copy(), process=True)
    if len(m.faces) < 4:
        raise ValueError(f"{name}: too few triangles to be a solid")
    if not m.is_volume:
        trimesh.repair.fix_winding(m)
        trimesh.repair.fix_normals(m)
        trimesh.repair.fill_holes(m)
    if m.is_volume:
        return m
    bad = _defect_faces(m)
    diagonal = float(np.linalg.norm(m.extents))
    if len(bad):
        centers = m.triangles_center
        around = centers[bad].mean(axis=0)
        for fraction in PATCH_FRACTIONS:
            keep = np.linalg.norm(centers - around, axis=1) >= fraction * diagonal
            try:
                fixed = _meshlab_repair(m.vertices, m.faces[keep])
            except Exception:
                continue
            if len(fixed.faces) and fixed.is_volume:
                return fixed
    raise ValueError(f"{name}: could not be repaired into a closed solid; regenerate it or clean it in a mesh editor")


def largest_piece(mesh):
    """The connected piece with the most surface area."""
    parts = mesh.split(only_watertight=False)
    return max(parts, key=lambda p: p.area) if len(parts) > 1 else mesh


def load_solid(path, name="body"):
    """Read an STL, keep its largest piece, and return it as a valid solid."""
    import trimesh
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"{name}: no such file {path}")
    return make_solid(largest_piece(trimesh.load(str(path), force="mesh")), name=name)


def thin(mesh, target_faces):
    """Reduce the triangle count to about `target_faces`, keeping the shape closed."""
    import pymeshlab
    import trimesh
    if len(mesh.faces) <= target_faces:
        return mesh
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    ms.meshing_decimation_quadric_edge_collapse(targetfacenum=int(target_faces), preservetopology=True, qualitythr=0.5)
    out = ms.current_mesh()
    return trimesh.Trimesh(out.vertex_matrix(), out.face_matrix(), process=True)


def _check(meshes, name):
    for m in meshes:
        if not m.is_volume:
            raise ValueError(f"{name}: a mesh is not a closed solid; run make_solid on it first")


def subtract(body, cutter, name="body"):
    """`body` with `cutter` removed."""
    import trimesh
    _check([body, cutter], name)
    return trimesh.boolean.difference([body, cutter], engine="manifold")


def union(*meshes, name="union"):
    import trimesh
    _check(meshes, name)
    return trimesh.boolean.union(list(meshes), engine="manifold")


def intersect(*meshes, name="intersection"):
    import trimesh
    _check(meshes, name)
    return trimesh.boolean.intersection(list(meshes), engine="manifold")


def overlap_volume(a, b):
    """Volume shared by two solids; 0.0 when they do not touch."""
    import trimesh
    out = trimesh.boolean.intersection([a, b], engine="manifold")
    return float(out.volume) if len(out.faces) else 0.0


def weld(mesh, tolerance=0.002):
    """Merge vertices closer than `tolerance` and drop the sliver faces that leaves, so a strict STL check passes."""
    import pymeshlab
    import trimesh
    ms = pymeshlab.MeshSet()
    ms.add_mesh(pymeshlab.Mesh(vertex_matrix=mesh.vertices, face_matrix=mesh.faces))
    ms.meshing_merge_close_vertices(threshold=pymeshlab.PureValue(tolerance))
    ms.meshing_remove_duplicate_faces()
    ms.meshing_remove_null_faces()
    out = ms.current_mesh()
    return trimesh.Trimesh(out.vertex_matrix(), out.face_matrix(), process=True)
