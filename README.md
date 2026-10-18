# Litho Projects

Photo editing, FreeCAD scripting, and 3D-print prep (lithophanes etc.).

## Layout
- `photos/input/`    original images (never edit in place)
- `photos/output/`   processed images
- `photo_scripts/`   Python scripts for editing/prepping photos
- `freecad_scripts/` FreeCAD macros / headless scripts (run with FreeCADCmd or the Macro editor)
- `models/source/`   .FCStd files
- `models/stl/`      exported meshes
- `print_prep/`      slicer profiles, notes, test prints
- `docs/`            notes

## Setup
    pip install -r requirements.txt

## Quick start
    python photo_scripts/prep_photo.py photos/input/pic.jpg photos/output/pic.png --contrast 1.2
    python photo_scripts/make_lithophane.py photos/output/pic.png models/stl/pic.stl
    python print_prep/check_mesh.py models/stl/pic.stl

Defaults live in `config.yaml`. Print settings: `print_prep/PRINT_SETTINGS.md`.
Frame/stand: edit the values at the top of `freecad_scripts/litho_frame.py`, then run it in FreeCAD.
