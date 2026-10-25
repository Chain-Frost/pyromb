# PR #4 attribute validation evidence (2026-10-25)

Branch: `validation/attribute-outlet-identifiers`.
Entry head: `3fe4362aac5b49b99ac951da4625229418b00f7c`, verified against GitHub
and fetched origin before editing. Parent: PR #3 at
`11ad683b78705f82a24c5416525b273d3368c110`.
The exact final tested commit is recorded in the PR validation comment.

## Implementation and review

Builder validates finite numeric slopes and impervious fractions, integral reach
types 1–4, and numeric/bool binary outlet flags. Exactly one outlet is required.
Catchment rejects empty and globally duplicate identifiers before traversal.
Review found that non-finite NumPy float32 and Decimal identifiers escaped the
original float-only check; the fix checks numeric identifier types, with
regressions. No traversal, writer, dependency, installed package, or other PR was
changed. README's stale nearest-centre and first-outlet descriptions were corrected.

## Runtime and results

Existing OSGeo4W Python 3.12.15, QGIS 4.2.3, GDAL 3.13.3, pytest 9.1.1.
No virtual environment or package installations.

| Check | Result |
| --- | --- |
| Full pytest suite | 121 passed, 1 xfailed; zero skipped |
| Model validation module | 55 passed |
| New OGR/QGIS adapter module | 52 passed |
| Public fixture | Six basins, each 0.01 km2; original impervious fractions retained |
| Parent/candidate comparison | All four RORB/URBS × OGR/QGIS output files byte-identical; JSON results equal |
| WBNM on parent and candidate | Same missing `Basin._type` error; no WBNM acceptance claimed |
| Ruff: Builder and both attribute test modules | Passed (0.16.6) |
| Whitespace | `git diff --check` passed |

Ruff on Catchment reports five inherited diagnostics: module/constructor
docstrings, summary formatting, trailing whitespace and the existing traversal's
`l` variable. They are outside the numeric identifier fix; no repository-wide
lint-clean claim is made. Pytest emits one existing OGR future warning about
the GDAL 4 exception default.

Both real adapters read generated public/synthetic shapefiles to exercise field
coercion, null/blank/missing values, fractional/unsupported types, negative and
non-finite slopes, impervious bounds and non-finite values, zero/multiple outlets,
invalid binary flags and cross-layer identifier collisions. Memory-layer tests
also cover booleans, numeric strings, and duplicate IDs within every category.
QGIS runs in a separate headless application; teardown occurs at session end
because exiting QGIS also tears down OGR drivers used by later tests.

## Reproduction

Use the unchanged upstream
[QVectorLayer at 6d18b7419c4b6b3b28b398ac64840ef14fb9932c](https://github.com/norman-tom/runoff-model/blob/6d18b7419c4b6b3b28b398ac64840ef14fb9932c/runoff_model/custom_types/qvector_layer.py),
Git blob `cf6d99adc58569684eab6dc459322324ccc1045b`.
The tested local file SHA-256 is
`de524015fa66963a458a3d747e251f2a6b3fbaadc58048423aeedba2fd1de5ce`.
Save it outside the checkout and set the adapter path:

```powershell
$env:PYROMB_QGIS_ADAPTER = 'C:\Temp\qvector_layer.py'
& C:\OSGeo4W\bin\python-qgis.bat -c "import sys,os; os.environ['PYTHONPATH']='src'; sys.path.insert(0,'src'); import pytest; raise SystemExit(pytest.main(['-q','--tb=long','-rx']))"
# The focused run uses the same launcher/environment:
# pytest.main(['-q','tests/test_model_validation.py','tests/test_qgis_attributes.py'])
& C:\OSGeo4W\bin\python-qgis.bat scripts/validate_qgis.py . C:\Temp\candidate.json $env:PYROMB_QGIS_ADAPTER C:\Temp\candidate-outputs
```

Without the adapter variable, QGIS-specific tests explicitly skip; such a run
does not satisfy this PR's acceptance. The reported run supplied it and had no
skips. The OGR half remains independent of QGIS imports.

Archive the exact parent with `git archive` into a temporary directory and run
the current `scripts/validate_qgis.py` against that root, retaining output files
in a separate directory. This leaves PR #3 and its branch untouched. Compare
JSON results and all four `.txt` files as bytes.

| Model | UTF-8 bytes | SHA-256 (both revisions, both adapters) |
| --- | --- | --- |
| RORB | 2818 | `67ae955b515a0594298fa1b0e48005d4d12db520e0a7dc582f37e6e06d6ad815` |
| URBS | 619 | `f162ca1ee5f1b1cffa3eee30f910e9632d4a3d783fe0411cbf579428db5ad025` |

## Slope semantics and limits

Retain rejection of negative reach slopes. HARC's primary support discussion
[Fatal error – slope < 0.00](https://harc.com.au/forums/topic/fatal-error-slope-0-00/)
describes RORB's handling of very flat type 2/3 reaches, including a 0.05% floor;
its [catchment-slope guidance](https://harc.com.au/forums/reply/2560/) distinguishes
the reach types using slope. This supports treating slope as a routing magnitude,
not the signed gradient of digitised line coordinates. Zero remains accepted;
this PR does not clamp slopes or introduce new model-specific minimums.

D. G. Carroll's [URBS v4.40 manual](https://www.scribd.com/document/93746264/URBSManualV440),
sections 2.1 and 5.1, defines channel slope Sc in m/m and uses it in the routing
storage relationship. No documented negative reach-slope convention or sentinel
was found there or in the public fixture. Inferring a non-negative magnitude is
consistent with that relationship; this is not proof of every newer URBS engine's
parser behaviour. Negative values used for unrelated URBS dam/flow commands are
not reach slopes. No proprietary model was inspected to seek exceptions.

Output checks establish generation and parity on the representative public
fixture, not hydraulic engine execution or universal writer support for all
reach types. WBNM remains an inherited, separately recorded defect. PR #4 remains
stacked on PR #3; no rebase, retarget, merge or release is part of this validation.
