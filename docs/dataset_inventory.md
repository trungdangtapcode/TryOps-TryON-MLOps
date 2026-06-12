# Dataset Inventory

## Selected Initial Scope

The first reliable demo should use public or synthetic examples and focus on upper-body virtual try-on. Multi-category garments remain stretch scope.

## Candidate Datasets

| Dataset | Use | Strength | Risk / Constraint | Decision |
| --- | --- | --- | --- | --- |
| VITON-HD | VTON baseline and demo subset | Common high-resolution virtual try-on benchmark | License/access must be documented before real use | Candidate fallback |
| Dress Code | Multi-category VTON benchmark | More garment categories | Broader scope increases evaluation complexity | Stretch |
| Public synthetic demo images | Seeded demo and degraded mode | Safe for reproducibility | Lower realism than real benchmark data | Use immediately |
| User uploads | Interactive demo | Realistic professor interaction | Privacy and retention risk | Only store transiently with metadata controls |

Machine-readable license and usage restrictions are stored in `configs/dataset_licenses.json`.

Current constraints:

| Dataset | License / Terms | Current TryOps Use |
| --- | --- | --- |
| Public synthetic demo images | Project Apache-2.0 generator output | Local smoke/demo evidence only |
| VITON-HD | CC-BY-NC-4.0; research/non-commercial only | Candidate fallback, not stored |
| Dress Code | Custom non-commercial academic terms; not released to private companies | Stretch benchmark, not stored |
| User uploads | User-provided content | Transient inference only, no training without consent |

## Excluded for Now

- Private social media images.
- Scraped e-commerce images without license documentation.
- Full multi-category training sets before the single-category demo is stable.
- Large datasets that cannot be reproduced on a fresh machine.

## Bias and Representation Limits

The current local VTON evidence uses synthetic images. It does not prove coverage across body types,
skin tones, poses, garment categories, cultural clothing, age ranges, disability-related fit needs,
or non-upper-body try-on scenarios.

Before using a real dataset subset in a final claim, record:

- license and access terms for the exact subset;
- known demographic, pose, and garment-category coverage;
- excluded or underrepresented groups;
- whether identity, body shape, or garment texture distortions differ across subgroups;
- human-review criteria for sensitive failure cases.

## Data Decision

Use a tiny public/synthetic seeded set for local smoke tests and demo fallback. Add VITON-HD or Dress Code only after license, download steps, checksums, and storage rules are documented for the exact subset.
