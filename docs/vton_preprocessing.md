	# VTON Optional Preprocessing

## Purpose

This layer creates optional mask and pose artifacts before the VTON model adapter runs. It does not replace SAM, SCHP, DensePose, or OpenPose. It gives the platform a deterministic, dependency-free compatibility path for models that expect masks, rough person localization, or pose hints.

## Research Basis

- CatVTON is the current preferred open-source target because it is lightweight and reports simplified inference at 1024x768 under roughly 8 GB VRAM. Its dataset layout still includes agnostic mask paths, and the project documents agnostic mask preprocessing for DressCode.
- IDM-VTON remains a higher-quality stretch target. Its public dataset layout includes `image-densepose` and `agnostic-mask`, so the platform needs explicit places to store those signals when a real model adapter is added.
- OpenPose remains the standard open-source reference for whole-body keypoint extraction.
- Segment Anything remains the standard open-source reference for promptable object masks.

Current source references:

- `https://github.com/Zheng-Chong/CatVTON`
- `https://github.com/yisol/IDM-VTON`
- `https://github.com/CMU-Perceptual-Computing-Lab/openpose`
- `https://github.com/facebookresearch/segment-anything`

## Implemented Local Path

The local implementation is split deliberately:

- `src/tryops/pipelines/vton_preprocessing.py` builds mask PNGs, bounding boxes, pose hints, checksums, and a JSON report.
- `src/tryops/native_vton_preprocess.py` serializes RGB images into a stable line-based native wire format.
- `native/cpp/tryops_vton_preprocess/src/tryops_vton_preprocess_cli.cpp` computes coverage, foreground bounding boxes, and rough pose hints in C++.
- `scripts/run_vton_optional_preprocessing.py` runs the full optional preprocessing path.
- `scripts/evaluate_native_vton_preprocess.py` calls only the native C++ CLI for one image.

The output report schema is `tryops.vton_optional_preprocessing.v1`.

## Commands

Build and run the full optional preprocessing sample:

```bash
make vton-preprocess-sample
```

Build and exercise the native CLI directly:

```bash
make native-vton-preprocess-sample
```

Run manually:

```bash
PYTHONPATH=src python scripts/run_vton_optional_preprocessing.py PERSON.png GARMENT.png --cache-dir artifacts/cache/vton_preflight
```

## Output Evidence

The preprocessing report contains:

- Person mask PNG path, checksum, coverage, and bounding box.
- Garment mask PNG path, checksum, coverage, and bounding box.
- Heuristic pose hints for neck, shoulders, torso center, and hips.
- Native C++ evidence for person and garment preprocessing.
- Latency for the preprocessing stage.

The VTON baseline sidecar includes this information under:

- `preprocessing.optional_segmentation`
- `preprocessing.optional_pose`
- `metrics.stage_latency_ms.optional_preprocessing`
- `lineage.person_mask_checksum`
- `lineage.garment_mask_checksum`

## Limitations

This is a smoke-test quality preprocessor. It works on simple backgrounds and gives the MLOps surface real artifacts, but production VTON should replace the heuristic mask with a real human parsing or segmentation adapter and replace the pose hints with DensePose or OpenPose output.
