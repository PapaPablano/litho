# Car kit: print a car as separate parts and assemble it

The kit turns a generated body (see `docs/IMAGE_TO_3D.md`) into a 1:24 model that prints as seven parts: a body shell, a chassis, four wheels and an interior. The chassis, wheels and interior are built from the car's real dimensions, so they fit and are the right size. The body is reshaped to fit over them, with the glass openings cut so the interior shows.

Run these in the AI environment (`tools/venv-gen`), because they need `trimesh`, `pymeshlab` and `manifold3d`.

## Make the kit

1. Generate a body: `tools/venv-gen/Scripts/python model_scripts/generate_shape.py "<photo folder>" --name countryman --low-vram`
2. Build and check the kit:
   `tools/venv-gen/Scripts/python model_scripts/make_kit.py models/raw/countryman.stl --subject mini_countryman --name countryman`
3. Open the parts in `models/kit/countryman/` in your slicer.

The command prints the assembled size against the real car and a list of problems. If any part overlaps another, a joint has no socket, a part is too big for the bed, or a size is more than 2% off, it exits with code 2 and writes nothing. Loading a dense body takes about a minute.

Useful options: `--scale 32` for another scale, `--wheel-style spoke5`, `--clearance 0.2`, `--bed-mm 220` for a smaller printer, and `--front -x` if the body's front is detected the wrong way round.

## The parts

| File | What it is | How it lies on the bed |
|---|---|---|
| `body.stl` | Hollow body shell with open windows, wheel arches and sockets for the chassis pins | Roof down |
| `chassis.stl` | Floor plate with four wheel stubs, four body pins and four interior posts | Flat |
| `interior.stl` | Floor, two front seats, a rear bench and a dashboard | Flat |
| `wheel_*.stl` | Four wheels, each with a hub socket | Standing on the outer face, socket down |

Orientations are set in the `kit:` section of `config.yaml` (`print_orientation`). They are a first guess; change them after your first prints.

## Assemble

1. Press the four wheels onto the chassis stubs and glue them.
2. Seat the interior on the four posts.
3. Lower the body onto the chassis so the four pins enter their sockets. Glue the pins.

## Print settings

Start from `print_prep/PRINT_SETTINGS.md`. For this kit use a 0.4 mm nozzle, 0.12 to 0.16 mm layers on the body, and supports only where the slicer shows overhangs on the body. Print the joint coupon first (see below).

## Prove the joint clearance

The pin-to-socket gap is `joint_clearance_mm` in `config.yaml` (0.15 mm to start). Printers differ, so print the coupon first:

`tools/venv-gen/Scripts/python model_scripts/joint_coupon.py`

It writes `models/kit/joint_coupon.stl`, a small plate with the kit's pin-and-socket joint repeated at stepped clearances. Print it, and find the smallest step where the pin seats without force or sanding. Put that clearance in `config.yaml`, then rebuild the kit.

## Tuning the body

The glass openings, belt line and roof line come from the `kit` block in `model_scripts/subjects/mini_countryman.yaml`. The values marked `unverified` there are estimates. Change them, rebuild, and look at the shell in the slicer or with `python model_scripts/silhouette_compare.py`.

## Known limits

- The windscreen and tailgate glass stay solid; only the side windows are open.
- The glass cuts detach the mirrors, so they are dropped. The command says so.
- The body is reshaped freely to fit the chassis, so wheel arches and curves can look slightly off on a body that started far from the real proportions.
