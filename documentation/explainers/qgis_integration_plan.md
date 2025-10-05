# QGIS Integration and Dependency Plan

This note captures the changes required to embed Pyromb as a native QGIS Processing algorithm without introducing non-standard dependencies.

## Dependency expectations inside QGIS

* **Python environment** – Recent QGIS releases ship with Python 3.9+ and include GDAL/OGR, PyQt, NumPy, and QGIS core bindings. Third-party packages such as Shapely are not guaranteed to be present and should be avoided unless bundled manually.
* **Current state** – The repository already limits itself to standard library modules, NumPy, and GDAL/OGR via `osgeo`. A quick audit (`rg "shapely"`) shows no references to Shapely in the current codebase, so future contributions should preserve this dependency footprint.

## Python package installation footprint

Pyromb distributes as a pure Python package with a minimal dependency tree:

* **`gdal`** – Declared in `pyproject.toml` so that the GDAL/OGR Python bindings are available for shapefile access when running outside QGIS. Inside QGIS, the bundled GDAL satisfies this requirement.
* **Standard library / QGIS built-ins** – The remaining imports come from Python's standard library, NumPy, and QGIS' own modules that ship with the application. No additional PyPI packages are installed by default.

When packaging for QGIS Processing, avoid adding new third-party dependencies unless they are guaranteed to be shipped with QGIS or vendored with the plugin.

## Embedding Pyromb as a Processing provider

1. **Processing entry point** – Wrap the logic in `src/app.py` inside a `QgsProcessingAlgorithm` subclass. The `processAlgorithm` method should:
   * Accept parameter definitions for the required vector layers (reaches, basins, centroids, confluences) and optional toggles (plotting, output path).
   * Use `QgsProcessingParameterFeatureSource` to read vector layers directly from the QGIS context, avoiding temporary files.
   * Instantiate `pyromb.Builder`, `Catchment`, and `Traveller` the same way the helper script does.
2. **Vector layer abstraction** – Replace `SFVectorLayer` usage with adapters that can consume `QgsFeatureSource` instances. The goal is to reuse existing validation and geometry code, so consider creating an interface that both the shapefile wrapper and a new QGIS wrapper implement.
3. **Output handling** – The algorithm should write to a processing output (`QgsProcessingOutputFile`) and optionally return the generated vector file path to the model catalog.
4. **Logging and feedback** – Use the `feedback` object provided by QGIS Processing for progress messages instead of the standard `logging` module when running inside QGIS. Retain standard logging for standalone runs by introducing a thin abstraction or conditional helper.

## Geometry logic amendments

The original plugin required adjustments to geometry handling to work reliably inside QGIS. Further work should focus on:

* **Tolerance-aware matching** – `Catchment._find_vertex_by_coordinates` currently uses a numeric tolerance when matching nodes. Confirm that the tolerance is appropriate for the coordinate precision in QGIS projects and expose it as a configurable parameter if needed.
* **Projected vs geographic CRS** – Ensure builders operate on projected coordinates (metres) when computing lengths, slopes, or areas. Incorporate CRS validation in the Processing algorithm to warn users when they run the tool in a geographic CRS.
* **Geometry extraction** – When moving from OGR-based layers to `QgsFeature`, use native geometry accessors (`feature.geometry().asPolyline()` etc.) to avoid relying on Shapely conversion helpers.

## Next steps and open questions

* Define a minimal adapter interface for vector layers so we can plug in both OGR and QGIS data sources without duplicating builder logic.
* Decide whether plotting should remain part of the Processing algorithm or become a standalone diagnostic tool. Plotting libraries may not be available in all QGIS deployments.
* Review existing serialisation helpers (`serialise.py`) to ensure they are optional in production builds; they are mainly for testing and may not suit a Processing context.
* Document user-facing parameter descriptions and default values for the QGIS tool so plugin development can begin immediately after the geometry updates.
