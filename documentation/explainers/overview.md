# Pyromb Architecture Overview

This explainer summarises how the Pyromb library organises its logic so that AI-assisted contributors can quickly locate the right components.

## High-level package structure

Pyromb exposes a builder-style API for turning GIS vector layers into hydrologic model control files. The key entry point used by the command-line helper script is `src/app.py`, which orchestrates shapefile ingestion, catchment assembly, and file serialisation. It instantiates vector layer wrappers, builds model components with `pyromb.Builder`, connects them into a `Catchment`, then produces the RORB or WBNM text output via a `Traveller`. The helper also supports optional plotting and serialisation for regression testing. `src/app_testing.py` mirrors this workflow with different defaults for test automation, while `serialise.py` and `plot_catchment.py` contain supporting utilities for debugging and visualisation.

Inside the Python package (`src/pyromb`), functionality is grouped into four domains:

* `core`: domain models and algorithms for catchment construction, traversal, and validation. This includes attribute classes (basins, reaches, confluences), geometry abstractions that wrap raw coordinates, and the `Catchment` and `Traveller` classes that connect everything into incidence matrices and model-specific exports.
* `math`: hydrologic calculations (e.g. loss models) that are used during serialisation of the output control files.
* `model`: format-specific builders for RORB and WBNM control vectors, and serialisation helpers that convert the in-memory catchment into strings written by the traveller.
* `resources`: default templates and static assets used by the model writers.

Supporting modules such as `sf_vector_layer.py` expose a minimal wrapper around OGR vector layers so the builder can consume shapefile geometry consistently.

## Data flow from GIS layers to control files

1. **Load vector data** – Shapefiles for reaches, basins, centroids, and confluences are opened via `SFVectorLayer`, which exposes iterable records with geometry and attributes.
2. **Build domain objects** – `pyromb.Builder` reads the vector layers, instantiates geometry primitives (`core.geometry`) and attribute classes, and returns lists of reaches, basins, and confluences.
3. **Assemble the catchment** – A `Catchment` is created from those components. It deduplicates vertices, computes distance-based incidence matrices, and determines upstream/downstream relationships used later by the traveller.
4. **Generate model output** – A `Traveller` walks the connected catchment to populate model-specific writers (`model` package). For RORB this produces a `vector.catg`; for WBNM a `runfile.wbnm`. Optional plotting uses the connected structure to render diagnostic figures.

Understanding this flow helps target AI-driven changes: geometry or validation fixes generally belong in `core.geometry` or the builder; file-format changes live in `model`; and QGIS integration work happens in the app wrapper and layer adapters.
