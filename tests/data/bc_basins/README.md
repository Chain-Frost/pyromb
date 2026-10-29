# Original PR #16 basin fixtures

Source: [BC_basins.zip](https://github.com/user-attachments/files/17333000/BC_basins.zip)
from [upstream PR #16](https://github.com/norman-tom/pyromb/pull/16).
Archive SHA-256: `eeb2a19cb1a6ba3c2b38660310ebe02ea7a6bf2faab72b7622f2a75692b5b702`.

Each GeoPackage contains only `basins` and `centroids`, the two layers used by
`Builder.basin()`: 15 features each, in the original EPSG:28350 metre-based CRS.
`original.gpkg` preserves source feature IDs, attributes and exact geometry WKB.
`corrected.gpkg` differs only by removing the interior ring of basin feature
index/FID 6 (`id="7"`, associated centroid `Basin_O`). Its exterior is unchanged;
no other coordinates or attributes, including the source `area` field, change.
The source `area` attribute is retained as input data, not used as ground truth.

Conversion used native OGR to copy fields/features without reprojection or
repair. For the corrected feature, a new polygon contains only its original
exterior ring. Native WKB, attributes and feature IDs were compared to the source
shapefiles after conversion. Confluences and reaches are omitted as unnecessary.

`expected_areas.json` records independent native OGR `GetArea()` results and
point-in-polygon associations, not values calculated by Pyromb. Original total:
**1630.4140663031646 km²**; corrected total: **1630.4140715856986 km²**.
The increase is **5.2825339965 m²**, the filled hole's area. Only `Basin_O` changes.
Absolute test tolerances are **0.0001 m² per basin** and **0.001 m² per total**;
relative tolerance is disabled. These allow floating-point summation differences
while remaining well below the hole's area. Geometry comparisons are exact WKB.

Run `tests/test_bc_basin_fixtures.py` in the native GDAL/QGIS environment. Genuine
QGIS cases use the unchanged pinned upstream adapter via `PYROMB_QGIS_ADAPTER`,
as described in the repository README. Original rejection is a passing test;
the corrected version must build without warnings or input mutation.
