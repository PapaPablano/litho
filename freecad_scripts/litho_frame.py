# Parametric lithophane frame + stand for FreeCAD.
# Run in the Macro editor, or: FreeCADCmd litho_frame.py
# Edit the values below to match the panel from make_lithophane.py / config.yaml.
# The panel slides in from the top; a window lets light through and a foot keeps it upright.
import os
import FreeCAD as App
import Part
import Mesh

PANEL_W = 100.0      # panel width incl. border (mm); check_mesh.py reports the real size
PANEL_H = 150.0      # panel height incl. border (mm)
PANEL_T = 3.0        # max panel thickness (mm)
WALL = 8.0           # frame border around the panel
LIP = 3.0            # overlap holding the panel in
CLEAR = 0.4          # slot clearance
DEPTH = 12.0         # front-to-back depth of the frame
BASE = 6.0           # foot height
FOOT_DEPTH = 40.0    # foot front-to-back, for stability
OUT = r"C:\Users\ericm\OneDrive\Desktop\Litho Projects\models\stl\litho_frame.stl"

V = App.Vector
outer_w = PANEL_W + 2 * WALL
outer_h = PANEL_H + WALL        # no wall on top: panel slides in there

doc = App.newDocument("LithoFrame")

# Frame block, centered in X, standing on the foot.
frame = Part.makeBox(outer_w, DEPTH, outer_h, V(-outer_w / 2, -DEPTH / 2, BASE))

# Slot: open at the top, centered in depth.
slot_t = PANEL_T + CLEAR
slot = Part.makeBox(PANEL_W + CLEAR, slot_t, PANEL_H + 1, V(-(PANEL_W + CLEAR) / 2, -slot_t / 2, BASE + WALL))
# Window: through the front/back so light passes.
win = Part.makeBox(PANEL_W - 2 * LIP, DEPTH + 2, PANEL_H - 2 * LIP,
                   V(-(PANEL_W - 2 * LIP) / 2, -DEPTH / 2 - 1, BASE + WALL + LIP))
frame = frame.cut(slot).cut(win)

# Foot: wider and deeper than the frame.
foot = Part.makeBox(outer_w + 10, FOOT_DEPTH, BASE, V(-(outer_w + 10) / 2, -FOOT_DEPTH / 2, 0))
body = frame.fuse(foot).removeSplitter()

obj = doc.addObject("Part::Feature", "LithoFrame")
obj.Shape = body
doc.recompute()

os.makedirs(os.path.dirname(OUT), exist_ok=True)
Mesh.export([obj], OUT)
print("Exported", OUT)
