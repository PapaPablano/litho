# Parametric lithophane frame + stand for FreeCAD, sized from a panel STL.
# Run in the Macro editor, or: FreeCADCmd litho_frame.py
# Set PANEL_STL below, or leave it None to use the newest STL in models/stl.
# Frame settings come from the `frame:` section of config.yaml.
# The panel slides in from the top; a window lets light through and a foot keeps it upright.
import os
import FreeCAD as App
import Part
import Mesh

PANEL_STL = os.environ.get("LITHO_PANEL")   # e.g. r"...\models\stl\pic.stl"
ROOT = r"C:\Users\ericm\OneDrive\Desktop\Litho Projects"
FOOT_DEPTH = 40.0    # foot front-to-back, for stability
FOOT_EXTRA = 10.0    # foot is this much wider than the frame


def load_frame_config(path):
    """Read the flat `frame:` section of config.yaml (FreeCAD's Python may lack yaml)."""
    cfg, in_frame = {}, False
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.split("#")[0].rstrip()
            if not line.strip():
                continue
            if not line.startswith(" "):
                in_frame = line.strip() == "frame:"
            elif in_frame:
                key, val = line.split(":", 1)
                cfg[key.strip()] = float(val)
    return cfg


def newest_panel(stl_dir):
    files = [os.path.join(stl_dir, n) for n in os.listdir(stl_dir)
             if n.lower().endswith(".stl") and not n.lower().startswith(("litho_frame", "test_strip"))]
    if not files:
        raise SystemExit("No panel STL found in " + stl_dir)
    return max(files, key=os.path.getmtime)


cfg = load_frame_config(os.path.join(ROOT, "config.yaml"))
WALL, LIP, CLEAR = cfg["wall_mm"], cfg["lip_mm"], cfg["clearance_mm"]
DEPTH, BASE = cfg["depth_mm"], cfg["base_mm"]

stl_dir = os.path.join(ROOT, "models", "stl")
panel_path = PANEL_STL or newest_panel(stl_dir)
bb = Mesh.Mesh(panel_path).BoundBox
PANEL_W, PANEL_H, PANEL_T = bb.XLength, bb.YLength, bb.ZLength   # make_lithophane.py layout
print("Panel: %s  %.1f x %.1f x %.2f mm" % (os.path.basename(panel_path), PANEL_W, PANEL_H, PANEL_T))

V = App.Vector
outer_w = PANEL_W + 2 * WALL
outer_h = PANEL_H + WALL        # no wall on top: panel slides in there
slot_w, slot_t = PANEL_W + CLEAR, PANEL_T + CLEAR
if slot_t > DEPTH - 2:
    raise SystemExit("Frame depth_mm is too small for this panel's thickness")

doc = App.newDocument("LithoFrame")

# Frame block, centered in X, standing on the foot.
frame = Part.makeBox(outer_w, DEPTH, outer_h, V(-outer_w / 2, -DEPTH / 2, BASE))
# Slot: open at the top, centered in depth.
slot = Part.makeBox(slot_w, slot_t, PANEL_H + 1, V(-slot_w / 2, -slot_t / 2, BASE + WALL))
# Window: through front and back so light passes.
win_w, win_h = PANEL_W - 2 * LIP, PANEL_H - 2 * LIP
win = Part.makeBox(win_w, DEPTH + 2, win_h, V(-win_w / 2, -DEPTH / 2 - 1, BASE + WALL + LIP))
frame = frame.cut(slot).cut(win)

# Foot: wider and deeper than the frame.
foot = Part.makeBox(outer_w + FOOT_EXTRA, FOOT_DEPTH, BASE, V(-(outer_w + FOOT_EXTRA) / 2, -FOOT_DEPTH / 2, 0))
body = frame.fuse(foot).removeSplitter()

obj = doc.addObject("Part::Feature", "LithoFrame")
obj.Shape = body
doc.recompute()

out = os.path.join(stl_dir, "litho_frame.stl")
Mesh.export([obj], out)
doc.saveAs(os.path.join(ROOT, "models", "source", "litho_frame.FCStd"))
print("Exported", out)
