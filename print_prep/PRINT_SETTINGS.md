# Lithophane print settings

Starting points; calibrate with a test strip on your own filament.

| Setting | Value | Why |
|---|---|---|
| Filament | White PLA (matte or basic) | Even light diffusion; avoid translucent or silk |
| Layer height | 0.1 mm (0.08 for fine detail) | Thickness steps are the image resolution |
| First layer | 0.2 mm | Good bed adhesion |
| Nozzle | 0.4 mm | 0.25 mm mesh pixels are finer than the nozzle, which is fine |
| Infill | 100% | Any gaps show as bright spots |
| Walls | 2-3 | |
| Orientation | Standing vertical, image face toward the front | Prints the relief with clean layer detail |
| Supports | None | Flat back faces the bed or the build direction |
| Brim | 5-8 mm | A tall thin panel needs the extra bed grip |
| Speed | 40-50 mm/s | Reduces wobble on a tall panel |
| Cooling | Fan 100% after layer 3 | |
| Seam | Aligned or hidden at an edge | |

## Light source
- LED panel or backlight 4000-6000K; the image only shows when lit from behind.
- Keep the panel 1-3 cm from the light for even glow.

## Tuning
- Washed out: raise `max_thickness_mm` (3.0 -> 3.5) or lower `gamma`.
- Too dark: lower `max_thickness_mm` or raise `gamma`.
- Visible banding: use 0.08 mm layers or a larger `min_thickness_mm` gap in whole layers.
- Thickness should be a multiple of layer height (0.6 = 6 layers at 0.1 mm).
