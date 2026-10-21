# Image to 3D model

Turn a few clean views of an object into a printable, dimensionally accurate STL.

Pipeline: `check_views` -> `generate_shape` -> `fit_to_scale` -> `silhouette_compare`.
Real-world sizes live in `model_scripts/subjects/*.yaml`; the print scale and tolerances live in the `model:` section of `config.yaml`.

## Capture checklist

Put one folder per subject under `photos/input/` (originals are never edited in place).

- One image each named `front`, `back`, `left`, `right`. An optional `top` is used only for the silhouette comparison. png, jpg, or webp.
- Straight-on views: camera level with the subject, not 3/4 angles. A configurator's 3/4 default view does not work; rotate it to true front, back, and side.
- Every image the same pixel size, with the subject centred and a margin on all sides.
- A plain, even background (one flat colour), with no shadows or reflections on it.
- Long edge at least 512 px. Use the longest focal length or least perspective the source offers.

Check a folder before generating:

    python model_scripts/check_views.py "photos/input/<folder>"

The seven MINI Countryman screenshots in `photos/input/3d Model Mini Cooper/` are 3/4 views of mixed sizes, so they fail this check. Recapture them as straight-on views.
