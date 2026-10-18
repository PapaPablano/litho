# Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| Image looks washed out, low contrast | Thickness range too narrow, or photo is flat | Raise `max_thickness_mm` (3.0 to 3.5), use `--contrast 1.3` in prep |
| Image too dark, details lost in shadows | Thick areas block too much light | Lower `max_thickness_mm`, or raise `gamma` (1.2-1.6) |
| Highlights blown out | Thin areas pass too much light | Raise `min_thickness_mm` (0.6 to 0.8) |
| Visible horizontal bands | Layer height too coarse for smooth gradients | Use 0.08 mm layers; keep thicknesses multiples of layer height |
| Bright pinholes | Gaps in infill or under-extrusion | 100% infill, check flow rate, dry filament |
| Panel wobbles or ribs on the print | Tall thin part moving while printing | Add a brim, slow to 40 mm/s, avoid drafts |
| Uneven glow, hot spots | Light too close or point-like | Move the light back or use a diffuser sheet behind the panel |
| Slicer says non-manifold / open edges | Corrupt mesh | Run `check_mesh.py`, regenerate the STL, or repair in the slicer |
| Panel won't fit the frame | Slot is smaller than the real panel | Re-run `litho_frame.py` so it re-reads the panel STL; raise `clearance_mm` in `config.yaml` |
| STL is huge or slicer is slow | Resolution finer than needed | Raise `pixel_mm` (0.25 to 0.4) |
| `ModuleNotFoundError` | Dependencies missing | `pip install -r requirements.txt` |
