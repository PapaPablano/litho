# Litho Projects

Photo editing, FreeCAD scripting, and 3D-print prep (lithophanes etc.).

## Layout
- `photos/input/`    original images (never edit in place)
- `photos/output/`   processed images
- `photo_scripts/`   Python scripts for editing/prepping photos
- `model_scripts/`   image-to-3D: view check, shape generation, scale fit, silhouette overlay
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
Frame/stand: run `freecad_scripts/litho_frame.py` in FreeCAD; it sizes itself from the newest panel STL.

## Image to 3D model
Turn clean front/back/left/right views of an object into a printable STL at a real scale:

    python model_scripts/check_views.py "photos/input/<folder>"
    tools/venv-gen/Scripts/python model_scripts/generate_shape.py "photos/input/<folder>" --name car
    python model_scripts/fit_to_scale.py models/raw/car.stl --subject mini_countryman
    python model_scripts/silhouette_compare.py models/stl/car_1to32.stl "photos/input/<folder>"

Needs a separate AI environment and a CUDA 12.8+ PyTorch (RTX 50-series). Setup, the capture checklist, and the Hunyuan3D license note (not valid in the EU, UK, or South Korea) are in `docs/IMAGE_TO_3D.md`. Run the tests with `python -m pytest tests -q`.
