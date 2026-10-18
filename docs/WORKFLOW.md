# Lithophane workflow

1. **Choose a photo.** High contrast, a clear subject, and a simple background work best. Put the original in `photos/input/` and never edit it in place.
2. **Calibrate once per filament.** Run `print_prep/test_strip.py`, print the strip, hold it to your light, and note the thinnest and thickest steps that look right. Set them in `config.yaml`.
3. **Prep the photo.**
   `python photo_scripts/prep_photo.py photos/input/pic.jpg photos/output/pic.png --contrast 1.2`
   For a whole folder: `python photo_scripts/batch_prep.py --contrast 1.2`
4. **Make the STL.**
   `python photo_scripts/make_lithophane.py photos/output/pic.png models/stl/pic.stl`
5. **Check it.**
   `python print_prep/check_mesh.py models/stl/pic.stl` should say watertight and show the size you expect.
6. **Make the frame (optional).** Set the panel size in `freecad_scripts/litho_frame.py` to the size `check_mesh.py` reported, then run it in FreeCAD.
7. **Slice and print.** Use `print_prep/PRINT_SETTINGS.md`. Print the panel standing vertical, with a brim.
8. **Light it.** Use a white LED backlight 1-3 cm behind the panel.

## Iterating
Change one thing at a time (contrast, gamma, thickness range) and keep notes next to the print in `print_prep/`. Small test prints of a cropped face or detail area save filament.
