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

## Setup (AI environment)

The generator runs in its own Python environment so the lithophane scripts stay light. Everything else (`check_views`, `fit_to_scale`, `silhouette_compare`, the tests) runs in the normal environment.

    python -m venv tools/venv-gen
    tools/venv-gen/Scripts/python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128
    tools/venv-gen/Scripts/python -m pip install -r model_scripts/requirements-gen.txt
    git clone --depth 1 https://github.com/Tencent-Hunyuan/Hunyuan3D-2.git tools/Hunyuan3D-2
    tools/venv-gen/Scripts/python -m pip install -e tools/Hunyuan3D-2 --no-deps

`tools/` and `models/raw/` are git-ignored. The first run downloads the model weights from Hugging Face into your user cache.
`pip check` will list the demo-server and texture extras as missing. Shape generation does not use them.

**License.** Hunyuan3D-2 is under the Tencent Hunyuan 3D 2.0 Community License, which does not apply in the European Union, the United Kingdom, or South Korea. Do not use it from those territories.

## Run

    python model_scripts/check_views.py "photos/input/<folder>"
    tools/venv-gen/Scripts/python model_scripts/generate_shape.py "photos/input/<folder>" --name countryman
    python model_scripts/fit_to_scale.py models/raw/countryman.stl --subject mini_countryman
    python model_scripts/silhouette_compare.py models/stl/countryman_1to32.stl "photos/input/<folder>"
    python print_prep/check_mesh.py models/stl/countryman_1to32.stl

`fit_to_scale` exits 0 when every dimension is within the tolerance and the mesh is print-ready, 1 when the mesh is written but has open edges, 2 when a dimension cannot be brought within tolerance (nothing is written; an older file at the output path is left alone and flagged as stale), and 3 for bad input such as a wrong orientation or an unreadable subject file.
For another object, add `model_scripts/subjects/<name>.yaml` with `length_mm`, `width_mm`, `height_mm` and pass `--subject <name>` and `--scale <N>`.

## Feasibility findings (RTX 5060 Laptop, 8 GB, Windows, Python 3.12)

- **GPU support:** PyTorch 2.11.0 with CUDA 12.8 runs real CUDA kernels on the RTX 5060 (compute capability 12.0).
- **Package pins:** `transformers==4.51.3` and `diffusers==0.33.1` are needed. Newer `transformers` (5.x) renames the image-encoder weights and the Hunyuan3D checkpoint fails to load.
- **Memory:** multiview shape generation (fp16, 30 steps, octree 256) loads in about 30 s and peaks at 5.43 GiB allocated (6.09 GiB reserved) with three views and 5.55 GiB (6.30 reserved) with four, so it fits in 8 GB without CPU offload. A generation takes about 3 minutes. `--low-vram` offloads model parts to the CPU if a larger octree is wanted.
- **Views accepted:** `front`, `left`, `back`, and `right`.
- **Output axes:** the generator output is Y-up. `generate_shape.py` rotates it to Z-up and yaws it so the length lies along X, which also fixes the diagonal yaw seen when the input views are 3/4 angles.
- **Not watertight as generated:** the raw mesh comes out as several pieces. `generate_shape.py` keeps the largest, fills small holes, and the result was watertight in the spike.

## Single-image baseline

To compare against a one-view result:

    tools/venv-gen/Scripts/python model_scripts/generate_shape.py "photos/input/<folder>" --name countryman_baseline --baseline left

`--baseline` takes a view name in the folder (or an image path) and needs no complete view set. It runs Hunyuan3D-2mini (0.6B), which is already installed with the multiview model, so it needs no second AI stack. TripoSR was the originally proposed baseline; it needs a compiled extension on Windows and was not installed. The output goes through the same cleanup, `fit_to_scale`, and `silhouette_compare` as the multiview mesh.

On the three stand-in screenshots used for the feasibility run (3/4 views, so not a fair test), proportions came out as length : width : height of 1 : 0.43 : 0.36 for multiview and 1 : 0.46 : 0.38 for the single-image baseline, against the real 1 : 0.42 : 0.37. The multiview mesh fit with a 3.8% width stretch. The baseline missed the width by 10.7% and was refused, which is the accuracy check working as intended.

## Status

Verified on this machine: install, generation (about 3 minutes, 5.6 GiB peak), cleanup to a watertight mesh, fit to the 1:32 Countryman dimensions, and the print-ready check.
Not yet done: a run on clean straight-on views. The seven existing screenshots fail `check_views`, so recapture front, back, left, and right views and run the sequence above to get the printable model.
