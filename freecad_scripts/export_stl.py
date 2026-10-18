# Run inside FreeCAD (Macro editor) or: FreeCADCmd export_stl.py
# Exports every visible solid in the active document to models/stl/.
import os
import FreeCAD
import Mesh

doc = FreeCAD.ActiveDocument
out = r"C:\Users\ericm\OneDrive\Desktop\Litho Projects\models\stl"
os.makedirs(out, exist_ok=True)
for obj in doc.Objects:
    if hasattr(obj, "Shape") and obj.Shape.Solids and obj.Visibility:
        path = os.path.join(out, obj.Label + ".stl")
        Mesh.export([obj], path)
        print("Exported", path)
