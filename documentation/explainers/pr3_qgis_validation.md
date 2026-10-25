# PR #3 local QGIS validation (2026-10-25)

Entry revision: `8e2e2aeb73accf51cd5cf5107658cce4d9e97fc3`.
Baseline: `origin/main` at `fcb4f8d4841b215af7460b8c7e439a905d6fe1ee`.
The final tested revision is recorded in the PR validation comment. Main and PR #2
were not changed. No virtual environment or installed package changes were made.

Runtime: OSGeo4W Python 3.12.15, QGIS 4.2.3, GDAL/OGR 3.13.3,
pytest 9.1.1. Tests use the existing initialized `python-qgis.bat` runtime.
Its environment initialization clears inherited PYTHONPATH, so the test invocation
sets it after initialization and inserts the same source directory into sys.path:

```powershell
& C:\OSGeo4W\bin\python-qgis.bat -c "import sys,os; os.environ['PYTHONPATH']='src'; sys.path.insert(0,'src'); import pytest; raise SystemExit(pytest.main(['-q','--tb=long','-rx']))"
```

## Matrix

| Check | Main baseline | Repaired PR #3 |
| --- | --- | --- |
| Original RORB/URBS suite | 2 passed | 2 passed |
| Containment and validation regressions | 12 failed | 12 passed, none skipped |
| WBNM public fixture generation | Missing `Basin._type` | Same inherited failure, explicitly xfailed |
| Full candidate suite | Not applicable | 14 passed, 1 xfailed |
| Public shapefiles through OGR | Six unique IDs, 0.01 km2 each | Identical |
| Same shapefiles through upstream QVectorLayer/QGIS OGR provider | Same six basins | Identical |
| RORB and URBS output bytes across revisions and adapters | Baseline hashes below | Identical |
| Hole / multipart flattened geometry | No OGR validation helper | Both tested examples rejected as invalid |

The baseline suite used an archive of the exact main revision, with only the OGR
fixture reader overlaid to avoid installing pyshp. The 12 regression tests were
then overlaid in that temporary archive to demonstrate the baseline defects.
The original candidate initially failed collection because pyshp was absent.
The fixture now reads the same tracked shapefiles with OGR instead.

The nearest-centre reproducer assigns main's first centroid an area of 0.0001 km2
instead of 0.01 km2; candidate returns 0.01 and 0.0001 km2 for IDs A and B,
with their original imperviousness values. The repaired candidate also rejects
duplicate catchment IDs, which the entry revision silently accepted.

Invalid-input coverage checks unmatched and boundary centroids, ambiguous
overlap, two centroids in one basin, a basin without a centroid, a self-crossing
polygon, missing centroid/reach attributes, invalid confluence geometry,
zero-length reaches and duplicate IDs. Errors identify the feature, missing
field or association problem. The tests assert the corresponding error messages.

## Reproduce the adapter comparison

Use the unchanged `QVectorLayer` from
[`norman-tom/runoff-model` revision 6d18b7419c4b6b3b28b398ac64840ef14fb9932c](https://github.com/norman-tom/runoff-model/blob/6d18b7419c4b6b3b28b398ac64840ef14fb9932c/runoff_model/custom_types/qvector_layer.py).
Save that file outside the checkout, then run:

```powershell
& C:\OSGeo4W\bin\python-qgis.bat scripts/validate_qgis.py . candidate.json C:\Temp\qvector_layer.py
# Run the same harness against a main archive with the OGR conftest overlay:
& C:\OSGeo4W\bin\python-qgis.bat scripts/validate_qgis.py C:\Temp\baseline baseline.json C:\Temp\qvector_layer.py
```

The harness uses actual QgsVectorLayer sources and QgsFeature records, not a mock
adapter. Public fixture data is used; no private project was inspected. It runs
in a separate headless QGIS application and does not change an open session.
It asserts OGR and QGIS results match. Compare the `ogr` and `qgis` entries in the
two JSON files across revisions; geometry diagnostic entries intentionally differ.

RORB: 2818 characters, SHA-256
`67ae955b515a0594298fa1b0e48005d4d12db520e0a7dc582f37e6e06d6ad815`.
URBS: 619 characters, SHA-256
`f162ca1ee5f1b1cffa3eee30f910e9632d4a3d783fe0411cbf579428db5ad025`.

## Limits and outstanding acceptance

WBNM fails on both revisions at `SubArea.__init__`, which accesses `basin._type`.
This is recorded as a specific expected failure; no valid WBNM output or WBNM
parity is claimed. Repairing that writer is outside this containment change.
RORB/URBS checks establish generation and byte stability, not engine acceptance.

The upstream adapter concatenates every `geometry().vertices()` result. A square
with a square hole (native area 64 m2) and two disjoint squares (200 m2) each
produce ten coordinates and an invalid single OGR ring. Candidate rejects both.
The interface loses ring and part metadata before Builder receives coordinates;
these examples do not prove every unsupported shape will be detected. Holes and
multipart basins remain unsupported. Use valid single exterior rings only.
No geometry-interface expansion or upstream plugin change was made.

Full WBNM validation remains incomplete. No merge, release, or update to upstream
PR #16 is part of this work.
