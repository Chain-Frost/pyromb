# AI Contributor Playbook

Use this playbook when applying AI-assisted development to Pyromb. It distils the key conventions, guardrails, and exploratory steps that have helped previous iterations succeed.

## Before writing code

1. **Understand the target module** – Read the relevant files under `src/pyromb` (especially the `core` package) before proposing changes. The architecture overview in this folder explains the data flow and should be revisited when planning large updates.
2. **Confirm geometry expectations** – All geometry work happens through the abstractions in `core/geometry`. Avoid introducing new geometry libraries; reuse the existing point/line/polygon classes or extend them cautiously.
3. **Check dependency rules** – QGIS deployments expect only standard library, NumPy, and GDAL/OGR dependencies. If a feature appears to require Shapely or other heavy GIS libraries, reconsider the approach or design a fallback that uses native QGIS geometry APIs.
4. **Plan for serialisation** – Any new attributes that affect the output vector files must propagate through `Builder`, `Catchment`, and the relevant `model` writer. Sketch the end-to-end data path before coding to avoid partial integrations.

## During implementation

* **Reuse builders and validators** – Keep shapefile parsing inside the builder. If you need additional validation rules, add them to `core/geometry/shapefile_validation.py` so they apply consistently across entry points.
* **Maintain tolerance handling** – When matching coordinates, continue to use tolerance-based comparisons. If more precision is necessary, introduce configurable parameters rather than hard-coded thresholds.
* **Instrument with logging** – Use the `logging` module for standalone scripts and prepare to swap in QGIS `feedback` hooks when integrating into Processing. Avoid print statements.

## Testing strategy

1. **Unit coverage** – Prioritise pure Python units (geometry, maths, model writers) because they run reliably in CI and do not require QGIS.
2. **Integration checks** – For geometry or builder changes, run the helper script (`python -m src.app`) against the sample data in the `data` directory to confirm end-to-end output remains valid.
3. **Regression artefacts** – Use the serialisation helpers in `serialise.py` to capture JSON or CSV snapshots of intermediate structures when diagnosing behaviour differences between QGIS and standalone runs.

## Follow-up questions to resolve

* Do we need a dedicated fixture generation script to refresh sample shapefiles for new test cases?
* Should tolerance thresholds become part of a configuration file so they can be tuned per project?
* Would a lightweight CLI wrapper around the builder be useful for non-QGIS environments once the Processing integration is complete?
