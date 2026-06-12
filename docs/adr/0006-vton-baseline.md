# ADR 0006: VTON Baseline Strategy

## Status

Accepted.

## Decision

TryOps will use CatVTON or IDM-VTON as the primary modern VTON target, with VITON-HD or HR-VITON as the fallback classical baseline.

## Rationale

CatVTON and IDM-VTON are more compelling for a modern visual demo because they align with diffusion-based VTON. CatVTON is especially attractive because simpler preprocessing improves the MLOps story. VITON-HD or HR-VITON remain useful because they are older, well-known, and easier to discuss as baseline systems.

## Consequences

- The first implementation must avoid training from scratch.
- The benchmark must support cached/degraded-mode outputs.
- Failure labels must include garment texture loss, identity shift, sleeve distortion, pose failure, and background artifacts.

